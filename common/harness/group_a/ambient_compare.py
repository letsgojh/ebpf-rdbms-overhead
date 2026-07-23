#!/usr/bin/env python3
"""common/harness/group_a/ambient_compare.py

A-2(앰비언트 부하 민감도) 비교 도구(`docs/01_experiment_design.md` A-2절).

A-1 floor(배경 DB 없음, --floor-outdir)와, 배경 DB를 idle로 띄운 채 같은 하네스를 다시 돌린
결과(배경 상태별로 별도 --outdir, --ambient로 지정)를 probe_type별로 비교한다.
`report_xlsx.py`의 vs_none 시트는 "같은 outdir 안에서 probe_type vs none"을 비교하는 용도라
이 축(outdir이 다른 두 조건 비교)에는 못 쓴다.

raw 파일(반복당 최대 10^7줄)을 조건(floor 1개 + ambient N개)당 한 번만 읽어서 metric 4종
(mean/p50/p99/p999) 비교에 재사용한다. CLI로 metric마다 `bootstrap_ci.py compare`를 따로
부르면 같은 조건의 raw를 metric 개수만큼 다시 읽게 된다.

해석 기준(A-2): 한 행의 ci_overlap=True면 그 probe_type·배경 조합은 "메커니즘 비용이 DB
존재와 무관"을 지지. False면 어떤 배경이 얼마나 영향을 주는지 diff_ns/diff_pct로 정량화.
"""
from __future__ import annotations

import argparse
import csv
import socket
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bootstrap_ci import METRICS, compare_metrics, per_run_metrics  # noqa: E402

FIELDNAMES = [
    "probe_type", "ambient", "metric",
    "floor_ns", "floor_ci_low_ns", "floor_ci_high_ns",
    "ambient_ns", "ambient_ci_low_ns", "ambient_ci_high_ns",
    "diff_ns", "diff_pct", "mannwhitney_u", "p_value", "significant", "ci_overlap",
    "note",
]

NON_BASELINE_PROBES = ["kprobe", "fentry", "tracepoint", "raw_tracepoint"]
RANK_METRIC = "p99"  # "family 간 차이" 순위는 tail latency(p99)로 판단 — mean은 tail 차이를 덮어버림


def _raw_paths(outdir: Path, probe_type: str) -> list[Path]:
    d = outdir / "raw" / probe_type
    return sorted(d.glob("*.txt")) if d.is_dir() else []


def _parse_ambient(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--ambient는 이름=결과디렉토리 형식이어야 함: {spec!r}")
    name, path = spec.split("=", 1)
    return name, Path(path)


def select_top_probes(floor_outdir: Path, top_n: int, n_resamples: int, seed) -> list[dict]:
    """A-1 floor에서 none 대비 RANK_METRIC(p99) overhead_pct가 큰 순으로 정렬한 목록.

    01_experiment_design.md A-2: "probe family는 A-1에서 family 간 차이가 가장 컸던 1~2종으로
    축소" — 이 선택을 사람이 report.xlsx를 보고 눈으로 고르는 대신 floor 데이터에서 직접 계산한다.

    percent만으로는 실제 절대 수치(ns)를 알 수 없어 보고용으로 부족하므로, 각 probe_type의
    none/probe 절대값(ns, CI)과 Mann-Whitney U/유의성까지 함께 반환한다.
    """
    baseline_paths = _raw_paths(floor_outdir, "none")
    if not baseline_paths:
        raise ValueError(f"floor outdir에 none(baseline) raw 없음: {floor_outdir}")
    baseline_metrics = per_run_metrics(baseline_paths)

    ranked = []
    for probe_type in NON_BASELINE_PROBES:
        paths = _raw_paths(floor_outdir, probe_type)
        if not paths:
            continue
        probe_metrics = per_run_metrics(paths)
        result = compare_metrics(
            baseline_metrics[RANK_METRIC], probe_metrics[RANK_METRIC], metric=RANK_METRIC,
            random_state=seed, n_resamples=n_resamples,
        )
        none_point = result["ci_a"]["point"]
        probe_point = result["ci_b"]["point"]
        overhead_pct = (probe_point - none_point) / none_point * 100 if none_point else 0.0
        ranked.append({
            "probe_type": probe_type,
            "metric": RANK_METRIC,
            "none_ns": round(none_point, 3),
            "none_ci_low_ns": round(result["ci_a"]["ci_low"], 3),
            "none_ci_high_ns": round(result["ci_a"]["ci_high"], 3),
            "probe_ns": round(probe_point, 3),
            "probe_ci_low_ns": round(result["ci_b"]["ci_low"], 3),
            "probe_ci_high_ns": round(result["ci_b"]["ci_high"], 3),
            "overhead_ns": round(probe_point - none_point, 3),
            "overhead_pct": round(overhead_pct, 3),
            "mannwhitney_u": round(result["mannwhitney_u"], 2),
            "p_value": round(result["p_value"], 6),
            "significant": result["significant"],
            "ci_overlap": result["ci_overlap"],
        })
    if not ranked:
        raise ValueError(f"floor outdir에 비교할 probe_type(kprobe 등) raw가 하나도 없음: {floor_outdir}")

    ranked.sort(key=lambda item: item["overhead_pct"], reverse=True)
    return ranked


def build_rows(
    floor_outdir: Path,
    probes: list[str],
    ambients: list[tuple[str, Path]],
    n_resamples: int,
    seed,
) -> list[dict]:
    rows = []
    for probe_type in probes:
        floor_paths = _raw_paths(floor_outdir, probe_type)
        if not floor_paths:
            rows.append({"probe_type": probe_type, "ambient": "-", "note": f"floor outdir에 raw 없음: {floor_outdir}"})
            continue
        floor_metrics = per_run_metrics(floor_paths)  # probe_type당 한 번만 로드 — ambient N개와 비교하며 재사용
        for ambient_name, ambient_outdir in ambients:
            ambient_paths = _raw_paths(ambient_outdir, probe_type)
            if not ambient_paths:
                rows.append({"probe_type": probe_type, "ambient": ambient_name, "note": f"raw 없음: {ambient_outdir}"})
                continue
            ambient_metrics = per_run_metrics(ambient_paths)  # 이 조건당 한 번만 로드 — metric 4개와 비교하며 재사용
            for metric in METRICS:
                result = compare_metrics(
                    floor_metrics[metric], ambient_metrics[metric], metric=metric,
                    random_state=seed, n_resamples=n_resamples,
                )
                floor_point = result["ci_a"]["point"]
                ambient_point = result["ci_b"]["point"]
                rows.append({
                    "probe_type": probe_type,
                    "ambient": ambient_name,
                    "metric": metric,
                    "floor_ns": round(floor_point, 3),
                    "floor_ci_low_ns": round(result["ci_a"]["ci_low"], 3),
                    "floor_ci_high_ns": round(result["ci_a"]["ci_high"], 3),
                    "ambient_ns": round(ambient_point, 3),
                    "ambient_ci_low_ns": round(result["ci_b"]["ci_low"], 3),
                    "ambient_ci_high_ns": round(result["ci_b"]["ci_high"], 3),
                    "diff_ns": round(ambient_point - floor_point, 3),
                    "diff_pct": round((ambient_point - floor_point) / floor_point * 100, 2) if floor_point else None,
                    "mannwhitney_u": round(result["mannwhitney_u"], 2),
                    "p_value": round(result["p_value"], 6),
                    "significant": result["significant"],
                    "ci_overlap": result["ci_overlap"],
                })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--floor-outdir", type=Path, required=True, help="A-1 결과 디렉토리 (배경 없음 baseline)")
    parser.add_argument(
        "--system", choices=["duckdb", "postgresql", "mysql", "clickhouse", "umbra"],
        help="--rank-only 결과를 .xlsx로 낼 때 systems/README.md 압축 파일명 규칙과 맞추기 위한 시스템 이름 (--rank-only 시 필수)",
    )
    parser.add_argument(
        "--rank-only", action="store_true",
        help="배경 데이터 없이, floor만으로 probe_type별 none 대비 p99 overhead_pct 순위를 .xlsx로 내고 종료 "
             "(A-2에서 배경상태별로 실제 재실행할 probe_type을 정하기 전에 먼저 확인하는 용도)",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--probe", dest="probes", action="append",
        choices=["none", "kprobe", "fentry", "tracepoint", "raw_tracepoint"],
        help="비교할 probe_type 직접 지정. 여러 번 지정 가능 (--top-n과 동시 사용 불가)",
    )
    selector.add_argument(
        "--top-n", type=int,
        help=f"A-1 floor에서 none 대비 {RANK_METRIC} overhead_pct가 큰 상위 N개 probe_type을 자동 선택 "
             "(01_experiment_design.md A-2: family 간 차이가 가장 컸던 1~2종)",
    )
    parser.add_argument(
        "--ambient", dest="ambients", action="append", type=_parse_ambient,
        help="배경상태이름=결과디렉토리 (예: duckdb=../../../systems/duckdb/results/group_a_ambient_duckdb). 여러 번 지정 가능",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="출력 경로 (--rank-only: 기본 <floor-outdir>/ebpf-rdbms-overhead_<system>_groupA_ambientrank_<날짜>_<host>.xlsx / "
             "그 외: 기본 ambient_compare.csv)",
    )
    parser.add_argument("--n-resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0, help="재현 가능한 비교를 위한 기본 seed(0)")
    args = parser.parse_args()

    if args.rank_only:
        if not args.system:
            parser.error("--rank-only에는 --system이 필요합니다 (출력 .xlsx 파일명에 씀)")
        ranked = select_top_probes(args.floor_outdir, len(NON_BASELINE_PROBES), args.n_resamples, args.seed)
        print(f"A-1 floor 기준 none 대비 {RANK_METRIC} overhead_pct 순위:")
        for item in ranked:
            print(
                f"  {item['probe_type']}: {item['overhead_pct']:.2f}%  "
                f"(none={item['none_ns']}ns, {item['probe_type']}={item['probe_ns']}ns, "
                f"overhead={item['overhead_ns']}ns, p={item['p_value']:.4g})"
            )

        if args.output:
            output = args.output
        else:
            stamp = date.today().strftime("%Y%m%d")
            host = socket.gethostname()
            output = args.floor_outdir / f"ebpf-rdbms-overhead_{args.system}_groupA_ambientrank_{stamp}_{host}.xlsx"
        rank_df = pd.DataFrame([{"rank": i + 1, **item} for i, item in enumerate(ranked)])
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            rank_df.to_excel(writer, sheet_name="rank", index=False)
        print(f"순위 리포트 생성: {output}")
        return 0

    if args.probes is None and args.top_n is None:
        parser.error("--probe 또는 --top-n 중 하나를 지정하세요 (또는 순위만 보려면 --rank-only)")
    if not args.ambients:
        parser.error("--ambient를 하나 이상 지정하세요")

    if args.top_n is not None:
        ranked = select_top_probes(args.floor_outdir, args.top_n, args.n_resamples, args.seed)
        print(f"A-1 floor 기준 none 대비 {RANK_METRIC} overhead_pct 순위: " + ", ".join(f"{item['probe_type']}={item['overhead_pct']:.2f}%" for item in ranked))
        if args.top_n > len(ranked):
            print(f"[경고] top-n={args.top_n}이 floor에 있는 probe_type 수({len(ranked)})보다 큼 — {len(ranked)}개만 선택됨", file=sys.stderr)
        probes = [item["probe_type"] for item in ranked[: args.top_n]]
        print(f"자동 선택된 probe_type(top {args.top_n}): {probes}")
    else:
        probes = args.probes

    rows = build_rows(args.floor_outdir, probes, args.ambients, args.n_resamples, args.seed)

    output = args.output or Path("ambient_compare.csv")
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, restval="")
        writer.writeheader()
        writer.writerows(rows)

    print(f"비교 결과 생성: {output} ({len(rows)}행)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
