#!/usr/bin/env python3
"""common/harness/group_a/report_xlsx.py

Group A-1 결과(<outdir>/raw/<probe_type>/*.txt)를 모아 5종(none/kprobe/fentry/tracepoint/
raw_tracepoint) 전체를 한 번에 보는 .xlsx 리포트로 만든다. `make summarize`/`make compare`를
probe_type 쌍마다 손으로 돌리는 대신 한 번에 "완성된 표"로 뽑는 용도.

시트 구성:
  - summary  : probe_type별 mean/p50/p99/p999 (점추정 + 95% CI, 단위 ns)
  - vs_none  : baseline(none) 대비 나머지 4종의 overhead + Mann-Whitney U 유의성
               (probe_type × metric 전체 조합)
"""
from __future__ import annotations

import argparse
import socket
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bootstrap_ci import METRICS, compare_metrics, per_run_metrics, summarize_metrics  # noqa: E402

PROBE_TYPES = ["none", "kprobe", "fentry", "tracepoint", "raw_tracepoint"]


def _raw_paths(outdir: Path, probe_type: str) -> list[Path]:
    d = outdir / "raw" / probe_type
    return sorted(d.glob("*.txt")) if d.is_dir() else []


def _load_metrics_by_probe(outdir: Path) -> dict[str, dict | None]:
    """probe_type별 raw 파일을 한 번씩만 읽어 metric 배열을 계산한다.

    summary/vs_none 두 시트가 probe_type별 raw 데이터를 공유하는데, 예전엔 vs_none 시트가
    metric(4종) × probe_type(4종)마다 compare()를 새로 호출해 같은 raw 파일(반복당 최대
    10^7줄)을 최대 16번씩 다시 읽었다. raw 전체가 수십 GB라 이게 리포트 생성 시간의 대부분을
    차지했으므로, probe_type당 한 번만 읽어서 재사용한다.
    """
    result: dict[str, dict | None] = {}
    for probe_type in PROBE_TYPES:
        paths = _raw_paths(outdir, probe_type)
        result[probe_type] = per_run_metrics(paths) if paths else None
    return result


def build_summary_df(metrics_by_probe: dict[str, dict | None], n_resamples: int, seed) -> pd.DataFrame:
    rows = []
    for probe_type in PROBE_TYPES:
        metrics = metrics_by_probe[probe_type]
        if metrics is None:
            rows.append({"probe_type": probe_type, "n_runs": 0, "note": "raw 데이터 없음"})
            continue
        stats = summarize_metrics(metrics, n_resamples=n_resamples, random_state=seed)
        row = {"probe_type": probe_type, "n_runs": stats["mean"]["n_runs"]}
        for metric in METRICS:
            row[f"{metric}_ns"] = round(stats[metric]["point"], 3)
            row[f"{metric}_ci_low_ns"] = round(stats[metric]["ci_low"], 3)
            row[f"{metric}_ci_high_ns"] = round(stats[metric]["ci_high"], 3)
        rows.append(row)
    return pd.DataFrame(rows)


def build_vs_baseline_df(metrics_by_probe: dict[str, dict | None], n_resamples: int, seed) -> pd.DataFrame:
    baseline_metrics = metrics_by_probe["none"]
    rows = []
    for probe_type in PROBE_TYPES:
        if probe_type == "none":
            continue
        probe_metrics = metrics_by_probe[probe_type]
        for metric in METRICS:
            if baseline_metrics is None or probe_metrics is None:
                rows.append({
                    "probe_type": probe_type, "metric": metric,
                    "note": "raw 데이터 없음(none 또는 이 probe_type을 아직 안 돌림)",
                })
                continue
            result = compare_metrics(
                baseline_metrics[metric], probe_metrics[metric], metric=metric,
                random_state=seed, n_resamples=n_resamples,
            )
            baseline_point = result["ci_a"]["point"]
            probe_point = result["ci_b"]["point"]
            rows.append({
                "probe_type": probe_type,
                "metric": metric,
                "none_ns": round(baseline_point, 3),
                "none_ci_low_ns": round(result["ci_a"]["ci_low"], 3),
                "none_ci_high_ns": round(result["ci_a"]["ci_high"], 3),
                "probe_ns": round(probe_point, 3),
                "probe_ci_low_ns": round(result["ci_b"]["ci_low"], 3),
                "probe_ci_high_ns": round(result["ci_b"]["ci_high"], 3),
                "overhead_ns": round(probe_point - baseline_point, 3),
                "overhead_pct": round((probe_point - baseline_point) / baseline_point * 100, 2) if baseline_point else None,
                "mannwhitney_u": round(result["mannwhitney_u"], 2),
                "p_value": round(result["p_value"], 6),
                "significant": result["significant"],
                "ci_overlap": result["ci_overlap"],
            })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, required=True, help="group_a1_runner.py가 쓴 결과 디렉토리")
    parser.add_argument(
        "--system", required=True,
        choices=["duckdb", "postgresql", "mysql", "clickhouse", "umbra"],
        help="systems/README.md 압축 파일명 규칙과 맞추기 위한 시스템 이름",
    )
    parser.add_argument("--output", type=Path, default=None, help="출력 .xlsx 경로 (기본: <outdir>/ebpf-rdbms-overhead_<system>_groupA_<날짜>_<host>.xlsx)")
    parser.add_argument("--n-resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0, help="재현 가능한 리포트를 위한 기본 seed(0)")
    args = parser.parse_args()

    outdir = args.outdir
    if args.output:
        output = args.output
    else:
        stamp = date.today().strftime("%Y%m%d")
        host = socket.gethostname()
        output = outdir / f"ebpf-rdbms-overhead_{args.system}_groupA_{stamp}_{host}.xlsx"

    metrics_by_probe = _load_metrics_by_probe(outdir)
    summary_df = build_summary_df(metrics_by_probe, args.n_resamples, args.seed)
    vs_baseline_df = build_vs_baseline_df(metrics_by_probe, args.n_resamples, args.seed)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        vs_baseline_df.to_excel(writer, sheet_name="vs_none", index=False)

    print(f"리포트 생성: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
