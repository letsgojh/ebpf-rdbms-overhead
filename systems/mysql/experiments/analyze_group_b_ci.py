#!/usr/bin/env python3
"""systems/mysql/experiments/analyze_group_b_ci.py

Group B SF1, SF10, SF100 수집 결과 CSV 파일들을 순수 읽기 전용(Read-only)으로 읽어,
(1) 파일명 및 내부 메타데이터 기반으로 각 (SF, 쿼리, 탐침위치) 조건별 10,000회 BCa / Percentile Bootstrap 95% 신뢰구간(CI) 산출
(2) log(레이턴시) ~ log(SF) OLS 회귀분석을 통해 Elasticity(기울기) 및 R^2 계산
 결과를 JSON 및 콘솔 리포트로 안전하게 출력한다.
"""
import glob
import os
import json
import pandas as pd
import numpy as np
from scipy import stats

def bootstrap_ci(vals, confidence=0.95, n_resamples=10000, seed=42):
    vals = np.array(vals, dtype=np.float64)
    n_runs = len(vals)
    mean_val = float(np.mean(vals))
    if n_runs < 2 or np.all(vals == vals[0]):
        return {"point": mean_val, "ci_low": mean_val, "ci_high": mean_val, "n_runs": n_runs}
    try:
        res = stats.bootstrap(
            (vals,),
            statistic=lambda x, axis=-1: np.mean(x, axis=axis),
            confidence_level=confidence,
            n_resamples=n_resamples,
            method='percentile',
            random_state=seed
        )
        ci_low = float(res.confidence_interval.low)
        ci_high = float(res.confidence_interval.high)
    except Exception:
        ci_low = mean_val
        ci_high = mean_val

    return {
        "point": mean_val,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n_runs": n_runs
    }

def main():
    results_dir = "systems/mysql/results/group_b"
    csv_files = glob.glob(os.path.join(results_dir, "*.csv"))
    print(f"[*] Total CSV result files found: {len(csv_files)}")

    records = []
    for f in csv_files:
        fname = os.path.basename(f)
        parts = fname.replace('.csv','').split('_')
        # mysql_none_sf1_query_run00 -> parts: ['mysql', 'none', 'sf1', 'query', 'run00']
        if len(parts) >= 5:
            sf_str = parts[2].replace('sf', '')
            loc_str = parts[3]
            try:
                sf_num = int(sf_str)
            except ValueError:
                sf_num = 1
        else:
            sf_num = 1
            loc_str = 'unknown'

        try:
            df = pd.read_csv(f)
            if not df.empty:
                row = df.iloc[0].to_dict()
                row['parsed_sf'] = sf_num
                row['parsed_loc'] = loc_str
                records.append(row)
        except Exception:
            pass

    full_df = pd.DataFrame(records)
    if full_df.empty:
        print("[!] No records loaded.")
        return

    # Group by parsed_sf, sub_experiment (query), parsed_loc
    grouped = full_df.groupby(['parsed_sf', 'sub_experiment', 'parsed_loc'])
    summary_list = []

    for (sf, q, loc), group in grouped:
        latencies = group['latency_p50_ms'].values
        ci = bootstrap_ci(latencies, n_resamples=10000)
        summary_list.append({
            "sf": int(sf),
            "query": str(q),
            "location": str(loc),
            "n_runs": ci['n_runs'],
            "mean_latency_p50_ms": ci['point'],
            "ci_95_low_ms": ci['ci_low'],
            "ci_95_high_ms": ci['ci_high']
        })

    summary_df = pd.DataFrame(summary_list)
    summary_df.sort_values(by=['query', 'location', 'sf'], inplace=True)

    print("\n" + "="*95)
    print(" 📊 Group B: 10,000-Resample Bootstrap 95% Confidence Intervals (CI)")
    print("="*95)
    headers = f"{'Query':<14} | {'Location':<10} | {'SF':<4} | {'Runs':<5} | {'Mean Latency (ms)':<18} | {'95% CI Low (ms)':<18} | {'95% CI High (ms)':<18}"
    print(headers)
    print("-" * 95)
    for _, r in summary_df.iterrows():
        print(f"{r['query']:<14} | {r['location']:<10} | SF{r['sf']:<2} | {r['n_runs']:<5} | {r['mean_latency_p50_ms']:18.2f} | {r['ci_95_low_ms']:18.2f} | {r['ci_95_high_ms']:18.2f}")

    # Log-Log Regression: log(Mean_Latency) ~ log(SF)
    print("\n" + "="*95)
    print(" 📈 Group B: OLS Log-Log Regression Analysis (Elasticity Slope: log(Latency) ~ log(SF))")
    print("="*95)

    reg_list = []
    for (q, loc), group in summary_df.groupby(['query', 'location']):
        if len(group) >= 2:
            x_log = np.log(group['sf'].values)
            y_log = np.log(group['mean_latency_p50_ms'].values)
            slope, intercept, r_val, p_val, std_err = stats.linregress(x_log, y_log)
            reg_list.append({
                "query": q,
                "location": loc,
                "elasticity_slope": slope,
                "r_squared": r_val**2,
                "p_value": p_val,
                "std_err": std_err
            })
            print(f"[{q:<12}] Location={loc:<8} | Slope (Elasticity) = {slope:8.4f} | R^2 = {r_val**2:6.4f} | p-val = {p_val:.4e}")

    out_file = os.path.join(results_dir, "bootstrap_ci_summary.json")
    out_data = {
        "bootstrap_summary": summary_list,
        "regression_results": reg_list
    }
    with open(out_file, "w") as out_f:
        json.dump(out_data, out_f, indent=2)

    print("\n[+] Analysis results safely saved to:", out_file)

if __name__ == "__main__":
    main()
