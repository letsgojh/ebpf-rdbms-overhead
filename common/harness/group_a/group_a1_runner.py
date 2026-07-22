#!/usr/bin/env python3
"""common/harness/group_a/group_a1_runner.py

Group A-1 오케스트레이션: probe 하나(또는 baseline=none)를 attach하고
`harness_floor`를 --reps회 반복 실행해 raw delta 파일들과
results/group_a/<system>_<probe_type>_na_na.csv를 만든다.

이 스크립트 자체는 일반 사용자 권한으로 실행한다. `/sys/fs/bpf`가 root:root 700이라 pin
생성/삭제·조회(attach_probe/detach_probe/bpf_stats 안의 bpftool·rm 호출)만 내부적으로 `sudo`를
붙여 실행한다 — 그래서 harness 실행, CSV/raw 파일 쓰기는 전부 이 스크립트를 부른 사용자 소유로
남는다(예전처럼 스크립트 전체를 sudo로 감쌀 필요 없음). 최초 sudo 호출 시 터미널에서 비밀번호
프롬프트가 뜬다(그 뒤로는 sudo 자격 캐시 유지 시간 동안 재입력 불필요).

01_experiment_design.md A-1 "측정 절차"(118~124행)와 대응:
  1. probe 미부착(baseline) 또는 2. probe family 하나 부착
  3. harness_floor 반복 실행
  4. bpftool prog show로 run_time_ns/run_cnt 기록
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # bootstrap_ci.py는 common/harness/ (한 단계 위)에 있음
from bootstrap_ci import per_run_metrics  # noqa: E402  (mean/p50/p99/p999 재사용)

PROBES_DIR = HERE.parent.parent / "probes"  # common/harness/group_a -> common/probes
PIN_DIR = Path("/sys/fs/bpf")

PROBE_OBJ = {
    "kprobe": "kprobe_empty.bpf.o",
    "fentry": "fentry_empty.bpf.o",
    "tracepoint": "tracepoint_empty.bpf.o",
    "raw_tracepoint": "raw_tracepoint_empty.bpf.o",
}

CSV_FIELDS = [
    "system", "group", "sub_experiment", "probe_type", "probe_location", "sf", "run_id",
    "throughput_qps", "throughput_degradation_pct",
    "latency_p50_ms", "latency_p95_ms", "latency_p99_ms", "latency_p999_ms",
    "latency_overhead_p50_pct", "latency_overhead_p95_pct", "latency_overhead_p99_pct", "latency_overhead_p999_pct",
    "cpu_overhead_pct", "run_time_ns", "run_cnt",
    "cycles", "instructions", "ipc", "cache_miss", "dtlb_miss", "ctx_switch",
    "kernel_version", "system_version_hash", "timestamp",
]


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as e:
        # bpftool -j는 에러도 JSON으로 stdout에 찍는 경우가 있어(예: {"error":"..."}),
        # stderr만 보면 놓친다 — 둘 다 보여준다.
        print(f"[CMD FAILED] {' '.join(cmd)}\nstdout: {e.stdout!r}\nstderr: {e.stderr!r}", file=sys.stderr)
        raise


def attach_probe(probe_type: str) -> Path:
    """`/sys/fs/bpf`는 root:root 700(sticky)이라 이 디렉토리 안 파일은 존재 확인조차 root만
    가능하다 — 그래서 존재 여부를 미리 체크하지 않고 `rm -f`(없어도 에러 안 남)로 무조건 지운 뒤
    다시 만든다. 이 두 명령만 root가 필요하고, 나머지(harness 실행/CSV 쓰기)는 일반 사용자로 돈다."""
    obj = PROBES_DIR / PROBE_OBJ[probe_type]
    if not obj.exists():
        raise FileNotFoundError(f"{obj} 없음 — common/probes에서 `make` 먼저 실행할 것")
    pin_path = PIN_DIR / f"floor_{probe_type}"
    _run(["sudo", "rm", "-f", str(pin_path)])
    _run(["sudo", "bpftool", "prog", "load", str(obj), str(pin_path), "autoattach"])
    return pin_path


def detach_probe(pin_path: Path | None) -> None:
    if pin_path is not None:
        _run(["sudo", "rm", "-f", str(pin_path)])


def _first(data):
    """bpftool -j 출력은 selector가 있어도 리스트로 감싸 나올 때가 있다 — 둘 다 받아준다."""
    return data[0] if isinstance(data, list) else data


def _bpftool_json(cmd: list[str]) -> dict:
    """bpftool -j show 계열 전용 실행기.

    실측 결과: `bpftool -j link show pinned <path>`는 exit code 255를 내면서도 stdout에
    완전히 유효한 JSON(예: {"id":1553,...,"prog_id":50884,...})을 이미 다 찍어놓는 경우가 있었다
    (아마 pid 보유자 목록 등 부가 정보를 추가로 조회하다 실패해도 주 결과는 이미 flush된 뒤라서로
    추정 — 정확한 원인은 bpftool 소스 확인 전까지 불명). 그래서 exit code가 아니라 "stdout이
    유효한 JSON이고 필요한 키가 있는가"를 성공 기준으로 삼는다.
    """
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[WARN] {' '.join(cmd)} exit={proc.returncode} (stdout이 유효하면 계속 진행)\n"
              f"  stderr: {proc.stderr!r}", file=sys.stderr)
    try:
        return _first(json.loads(proc.stdout))
    except json.JSONDecodeError as e:
        print(f"[CMD FAILED] {' '.join(cmd)}\nstdout: {proc.stdout!r}\nstderr: {proc.stderr!r}", file=sys.stderr)
        raise RuntimeError(f"bpftool 출력 파싱 실패: {' '.join(cmd)}") from e


def bpf_stats(pin_path: Path) -> tuple[int, int]:
    """bpftool prog show의 run_time_ns/run_cnt (bpf_stats_enabled=1 필요).

    attach_probe()가 `autoattach`로 로드하면 pin_path에는 prog가 아니라 **link**가 pin된다
    (bpftool-prog(8) 문서: "only the link ... is pinned, not the program as such"). 그래서
    link에서 prog_id를 얻은 뒤 그 id로 prog show를 다시 조회해야 한다.
    """
    link_data = _bpftool_json(["sudo", "bpftool", "-j", "link", "show", "pinned", str(pin_path)])
    prog_id = link_data["prog_id"]
    prog_data = _bpftool_json(["sudo", "bpftool", "-j", "prog", "show", "id", str(prog_id)])
    return int(prog_data.get("run_time_ns", 0)), int(prog_data.get("run_cnt", 0))


def kernel_version() -> str:
    return _run(["uname", "-r"]).strip()


def run_one_rep(harness: Path, n: int, raw_path: Path, pin_path: Path | None) -> dict:
    before = bpf_stats(pin_path) if pin_path else (None, None)
    _run([str(harness), str(n), str(raw_path)])
    after = bpf_stats(pin_path) if pin_path else (None, None)

    metrics = per_run_metrics([raw_path])  # ns 단위, harness_floor가 TSC->ns 환산해서 덤프
    return {
        "run_time_ns": (after[0] - before[0]) if pin_path else None,
        "run_cnt": (after[1] - before[1]) if pin_path else None,
        "latency_p50_ms": float(metrics["p50"][0]) / 1e6,
        "latency_p99_ms": float(metrics["p99"][0]) / 1e6,
        "latency_p999_ms": float(metrics["p999"][0]) / 1e6,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--system", required=True, choices=["duckdb", "postgresql", "mysql", "clickhouse", "umbra"])
    parser.add_argument("--probe-type", required=True,
                         choices=["none", "kprobe", "fentry", "tracepoint", "raw_tracepoint"])
    parser.add_argument("--reps", type=int, default=100, help="반복 횟수 (A-1 기본 100)")
    parser.add_argument("--n", type=int, default=10_000_000, help="반복 1회당 syscall 호출 횟수 (A-1 기본 N=10^7)")
    parser.add_argument("--outdir", type=Path, required=True, help="raw delta 파일 및 CSV를 쓸 디렉토리")
    parser.add_argument("--harness", type=Path, default=HERE / "harness_floor")
    args = parser.parse_args()

    # Path()가 "./harness_floor" 같은 상대경로의 선행 "./"를 정규화로 지워버려 슬래시 없는
    # 맨 파일명("harness_floor")이 되는 경우가 있다 — subprocess가 이를 $PATH에서만 찾다가
    # 못 찾는다(run_group_a1.sh의 sudo "$0" 버그와 동일 계열). 항상 절대경로로 고정한다.
    args.harness = args.harness.resolve()

    if not args.harness.exists():
        print(f"[ERROR] harness 실행파일 없음: {args.harness} (common/harness/group_a에서 `make build`로 먼저 빌드)", file=sys.stderr)
        return 1

    raw_dir = args.outdir / "raw" / args.probe_type
    raw_dir.mkdir(parents=True, exist_ok=True)

    pin_path = attach_probe(args.probe_type) if args.probe_type != "none" else None

    try:
        k_version = kernel_version()
        for run_id in range(args.reps):
            raw_path = raw_dir / f"run{run_id:03d}.txt"
            result = run_one_rep(args.harness, args.n, raw_path, pin_path)

            row = {name: None for name in CSV_FIELDS}
            row.update({
                "system": args.system,
                "group": "A",
                "sub_experiment": "A-1",
                "probe_type": args.probe_type,
                "run_id": run_id,
                "latency_p50_ms": result["latency_p50_ms"],
                "latency_p99_ms": result["latency_p99_ms"],
                "latency_p999_ms": result["latency_p999_ms"],
                "run_time_ns": result["run_time_ns"],
                "run_cnt": result["run_cnt"],
                "kernel_version": k_version,
                "system_version_hash": "na",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })

            # 0.2 파일명 규칙: <system>_<probe_type>_<sf|na>_<probe_location|na>_run<NN>.csv
            # run 1개 = 행 1개 = 파일 1개. (harness_floor 크래시로 일부 run만 유실돼도
            # 나머지 run 파일은 안전하게 남는다.)
            csv_path = args.outdir / f"{args.system}_{args.probe_type}_na_na_run{run_id:03d}.csv"
            with csv_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerow(row)

            print(f"[{args.probe_type}] run {run_id + 1}/{args.reps} 완료 → {csv_path.name}", file=sys.stderr)
    finally:
        detach_probe(pin_path)

    print(f"CSV: {args.outdir}/{args.system}_{args.probe_type}_na_na_run*.csv")
    print(f"raw dumps: {raw_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
