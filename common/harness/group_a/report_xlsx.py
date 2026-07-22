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
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bootstrap_ci import METRICS, compare, summarize  # noqa: E402

PROBE_TYPES = ["none", "kprobe", "fentry", "tracepoint", "raw_tracepoint"]


def _raw_paths(outdir: Path, probe_type: str) -> list[Path]:
    d = outdir / "raw" / probe_type
    return sorted(d.glob("*.txt")) if d.is_dir() else []


def build_summary_df(outdir: Path, n_resamples: int, seed) -> pd.DataFrame:
    rows = []
    for probe_type in PROBE_TYPES:
        paths = _raw_paths(outdir, probe_type)
        if not paths:
            rows.append({"probe_type": probe_type, "n_runs": 0, "note": "raw 데이터 없음"})
            continue
        stats = summarize(paths, n_resamples=n_resamples, random_state=seed)
        row = {"probe_type": probe_type, "n_runs": stats["mean"]["n_runs"]}
        for metric in METRICS:
            row[f"{metric}_ns"] = round(stats[metric]["point"], 3)
            row[f"{metric}_ci_low_ns"] = round(stats[metric]["ci_low"], 3)
            row[f"{metric}_ci_high_ns"] = round(stats[metric]["ci_high"], 3)
        rows.append(row)
    return pd.DataFrame(rows)


def build_vs_baseline_df(outdir: Path, n_resamples: int, seed) -> pd.DataFrame:
    baseline_paths = _raw_paths(outdir, "none")
    rows = []
    for probe_type in PROBE_TYPES:
        if probe_type == "none":
            continue
        paths = _raw_paths(outdir, probe_type)
        for metric in METRICS:
            if not baseline_paths or not paths:
                rows.append({
                    "probe_type": probe_type, "metric": metric,
                    "note": "raw 데이터 없음(none 또는 이 probe_type을 아직 안 돌림)",
                })
                continue
            result = compare(baseline_paths, paths, metric=metric, random_state=seed, n_resamples=n_resamples)
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
    parser.add_argument("--output", type=Path, default=None, help="출력 .xlsx 경로 (기본: <outdir>/report.xlsx)")
    parser.add_argument("--n-resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0, help="재현 가능한 리포트를 위한 기본 seed(0)")
    args = parser.parse_args()

    outdir = args.outdir
    output = args.output or (outdir / "report.xlsx")

    summary_df = build_summary_df(outdir, args.n_resamples, args.seed)
    vs_baseline_df = build_vs_baseline_df(outdir, args.n_resamples, args.seed)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        vs_baseline_df.to_excel(writer, sheet_name="vs_none", index=False)

    print(f"리포트 생성: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
