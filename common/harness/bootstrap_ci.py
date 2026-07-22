#!/usr/bin/env python3
"""common/harness/bootstrap_ci.py

Group A/B 공통 통계 후처리 도구.

harness(예: Phase 1의 harness_floor.c)가 반복(run)마다 덤프하는 raw 값 배열
(1행 1값 텍스트, 예: cycle delta 10,000,000개)을 입력으로 받는다.

전체 raw 값(예: N=10^7)에 직접 BCa bootstrap(jackknife 포함)을 돌리는 건 계산량이
감당되지 않으므로, 처리는 항상 2단계로 나눈다:
  1. run 하나(raw 배열 하나)에서 mean/P50/P99/P999를 "그냥" 계산한다 (bootstrap 아님).
  2. 조건(probe family 등)당 반복한 run 여러 개(보통 100개)에 대해, 위에서 나온
     run별 통계치 배열에 BCa bootstrap(10,000 resample)을 적용해 95% CI를 낸다.
     이 배열의 길이(=run 개수)가 실제 bootstrap 대상 표본 크기다.

01_experiment_design.md A-1 "통계 처리"(126~128행), B-6 절차와 대응.
"""
from __future__ import annotations

import argparse
import glob as glob_module
import sys
from pathlib import Path

import numpy as np
from scipy import stats

METRICS = {
    "mean": lambda x: float(np.mean(x)),
    "p50": lambda x: float(np.percentile(x, 50)),
    "p99": lambda x: float(np.percentile(x, 99)),
    "p999": lambda x: float(np.percentile(x, 99.9)),
}


def load_run(path: Path) -> np.ndarray:
    """1행 1값 텍스트 raw 값 덤프 파일을 float64 배열로 로드한다."""
    data = np.loadtxt(path, dtype=np.float64)
    if data.ndim == 0:
        data = data.reshape(1)
    if data.size == 0:
        raise ValueError(f"{path}: 빈 파일")
    return data


def per_run_metrics(paths: list[Path]) -> dict[str, np.ndarray]:
    """각 run 파일에서 mean/P50/P99/P999를 계산해, metric별로 run 개수만큼의 배열을 만든다."""
    out: dict[str, list[float]] = {name: [] for name in METRICS}
    for p in paths:
        data = load_run(p)
        for name, fn in METRICS.items():
            out[name].append(fn(data))
    return {name: np.array(vals) for name, vals in out.items()}


def bootstrap_ci(
    run_values: np.ndarray,
    confidence_level: float = 0.95,
    n_resamples: int = 10000,
    method: str = "BCa",
    random_state=None,
) -> dict:
    """run별 통계치 배열(길이 = 반복 횟수)에 대한 평균의 bootstrap CI."""
    if len(run_values) < 2:
        raise ValueError("bootstrap CI에는 최소 2개 이상의 run이 필요하다")
    if np.all(run_values == run_values[0]):
        # run 간 값이 완전히 동일(분산 0) — BCa의 가속 상수 계산이 0으로 나눠져 nan이 된다.
        # 통계적으로 문제가 아니라 "run 간 변동이 전혀 없다"는 정당한 결과이므로 CI 폭을 0으로 반환한다.
        point = float(run_values[0])
        return {"point": point, "ci_low": point, "ci_high": point, "n_runs": int(len(run_values))}
    res = stats.bootstrap(
        (run_values,),
        statistic=lambda x, axis=-1: np.mean(x, axis=axis),
        confidence_level=confidence_level,
        n_resamples=n_resamples,
        method=method,
        random_state=random_state,
    )
    return {
        "point": float(np.mean(run_values)),
        "ci_low": float(res.confidence_interval.low),
        "ci_high": float(res.confidence_interval.high),
        "n_runs": int(len(run_values)),
    }


def summarize(
    paths: list[Path],
    confidence_level: float = 0.95,
    n_resamples: int = 10000,
    random_state=None,
) -> dict[str, dict]:
    """조건 하나(예: 특정 probe family)의 run 파일들에서 mean/P50/P99/P999 + 95% CI를 낸다."""
    metrics = per_run_metrics(paths)
    return {
        name: bootstrap_ci(vals, confidence_level, n_resamples, random_state=random_state)
        for name, vals in metrics.items()
    }


def compare(
    paths_a: list[Path],
    paths_b: list[Path],
    metric: str = "mean",
    alpha: float = 0.05,
    n_resamples: int = 10000,
    random_state=None,
) -> dict:
    """두 조건(probe family A vs B 등)을 Mann-Whitney U + CI 비겹침으로 비교한다.

    A-1 "family 간 차이 검정" 절: 분포가 정규분포가 아닐 수 있어 Mann-Whitney U를 쓰고,
    보조적으로 두 조건 각각의 bootstrap CI가 겹치는지도 같이 본다.
    """
    if metric not in METRICS:
        raise ValueError(f"알 수 없는 metric: {metric} (선택 가능: {list(METRICS)})")
    a = per_run_metrics(paths_a)[metric]
    b = per_run_metrics(paths_b)[metric]
    u_stat, p_value = stats.mannwhitneyu(a, b, alternative="two-sided")
    ci_a = bootstrap_ci(a, 1 - alpha, n_resamples, random_state=random_state)
    ci_b = bootstrap_ci(b, 1 - alpha, n_resamples, random_state=random_state)
    ci_overlap = not (ci_a["ci_high"] < ci_b["ci_low"] or ci_b["ci_high"] < ci_a["ci_low"])
    return {
        "metric": metric,
        "mannwhitney_u": float(u_stat),
        "p_value": float(p_value),
        "significant": bool(p_value < alpha),
        "ci_a": ci_a,
        "ci_b": ci_b,
        "ci_overlap": ci_overlap,
    }


def _expand_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            matched = [Path(p) for p in sorted(glob_module.glob(pattern))]
        else:
            matched = [Path(pattern)]
        if not matched:
            raise FileNotFoundError(f"패턴에 매치되는 파일 없음: {pattern}")
        paths.extend(matched)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n-resamples", type=int, default=10000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=None, help="재현 가능한 resample을 위한 random seed")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sum = sub.add_parser("summarize", help="조건 하나의 run 파일들에서 mean/P50/P99/P999 + 95%% CI 산출")
    p_sum.add_argument("runs", nargs="+", help="run별 raw 값 덤프 파일(들) 또는 glob 패턴")

    p_cmp = sub.add_parser("compare", help="두 조건의 run 결과를 Mann-Whitney U + CI 비겹침으로 비교")
    p_cmp.add_argument("--a", nargs="+", required=True, help="조건 A의 run 파일들/패턴")
    p_cmp.add_argument("--b", nargs="+", required=True, help="조건 B의 run 파일들/패턴")
    p_cmp.add_argument("--metric", choices=list(METRICS), default="mean")

    args = parser.parse_args()
    rng = np.random.default_rng(args.seed) if args.seed is not None else None

    try:
        if args.command == "summarize":
            paths = _expand_paths(args.runs)
            result = summarize(paths, args.confidence, args.n_resamples, random_state=rng)
            for name, stat_result in result.items():
                print(
                    f"{name:>5}: point={stat_result['point']:.4f}  "
                    f"{args.confidence:.0%} CI=[{stat_result['ci_low']:.4f}, {stat_result['ci_high']:.4f}]  "
                    f"(n_runs={stat_result['n_runs']})"
                )
        elif args.command == "compare":
            paths_a = _expand_paths(args.a)
            paths_b = _expand_paths(args.b)
            result = compare(paths_a, paths_b, args.metric, 1 - args.confidence, args.n_resamples, random_state=rng)
            print(
                f"metric={result['metric']}  U={result['mannwhitney_u']:.2f}  "
                f"p={result['p_value']:.6f}  significant={result['significant']}"
            )
            print(f"  A: point={result['ci_a']['point']:.4f}  CI=[{result['ci_a']['ci_low']:.4f}, {result['ci_a']['ci_high']:.4f}]")
            print(f"  B: point={result['ci_b']['point']:.4f}  CI=[{result['ci_b']['ci_low']:.4f}, {result['ci_b']['ci_high']:.4f}]")
            print(f"  CI overlap: {result['ci_overlap']}")
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
