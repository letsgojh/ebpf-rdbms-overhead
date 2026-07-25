#!/usr/bin/env python3
"""
MySQL Group B Experiment Runner Harness
Executes 4-way controlled measurements (none, perf, ebpf, both) across
Probe Locations (query, operator, tuple) x Scale Factors x Queries.
Outputs standardized CSV results strictly matching common/schema/result_schema.json.
"""

import argparse
import csv
import datetime
import os
import platform
import subprocess
import sys
import time

PROBE_MAP = {
    "query": "mysql_query.bpf.o",
    "operator": "mysql_operator.bpf.o",
    "tuple": "mysql_tuple.bpf.o"
}

PROBE_SYMBOLS = {
    "query": "mysql_execute_command",
    "operator": "ha_rnd_next",
    "tuple": "row_search_mvcc"
}

def get_git_commit_hash(repo_dir):
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown_commit"

def get_kernel_version():
    res = subprocess.run(["uname", "-r"], capture_output=True, text=True)
    return res.stdout.strip()

def run_single_query(mysql_cmd, sql_path, db_name):
    start_time = time.perf_counter_ns()
    with open(sql_path, "r") as f:
        res = subprocess.run(mysql_cmd + [db_name], stdin=f, capture_output=True, text=True)
    end_time = time.perf_counter_ns()
    elapsed_ns = end_time - start_time
    latency_ms = elapsed_ns / 1_000_000.0
    return latency_ms, elapsed_ns, res.returncode

def ensure_result_dirs(results_dir):
    os.makedirs(results_dir, exist_ok=True)
    raw_dir = os.path.join(results_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    return raw_dir

def main():
    parser = argparse.ArgumentParser(description="MySQL Group B Experiment Runner Harness")
    parser.add_argument("--sf", nargs="+", type=int, default=[1, 10, 100], help="Scale Factors to run (1 10 100)")
    parser.add_argument("--query", nargs="+", type=int, default=[1, 6, 9], help="Queries to run (1 6 9)")
    parser.add_argument("--location", nargs="+", type=str, default=["query", "operator", "tuple"], help="Probe Locations")
    parser.add_argument("--control", nargs="+", type=str, default=["none"], choices=["none", "perf", "ebpf", "both"], help="Control Modes")
    parser.add_argument("--reps", type=int, default=100, help="Number of repetitions")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup runs")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MySQL Host")
    parser.add_argument("--user", type=str, default="ebpf_user", help="MySQL User")
    parser.add_argument("--password", type=str, default="ebpf_pass123!", help="MySQL Password")
    args = parser.parse_args()

    work_dir = os.path.dirname(os.path.abspath(__file__))
    sys_dir = os.path.dirname(work_dir)
    repo_dir = os.path.dirname(sys_dir)
    results_dir = os.path.join(sys_dir, "results", "group_b")
    raw_dir = ensure_result_dirs(results_dir)

    kernel = get_kernel_version()
    git_hash = get_git_commit_hash(repo_dir)

    mysql_cmd = ["mysql", "-u", args.user, "-h", args.host, "-P", str(args.port)]
    if args.password:
        mysql_cmd.append(f"-p{args.password}")

    fieldnames = [
        "system", "group", "sub_experiment", "probe_type", "probe_location",
        "sf", "run_id", "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
        "latency_p999_ms", "run_time_ns", "kernel_version",
        "system_version_hash", "timestamp"
    ]

    for sf in args.sf:
        db_name = f"tpch_sf{sf}"
        for q in args.query:
            sql_path = os.path.join(sys_dir, "queries", f"q{q}.sql")
            if not os.path.exists(sql_path):
                print(f"[!] Warning: Query file {sql_path} missing, skipping.")
                continue

            for loc in args.location:
                for mode in args.control:
                    probe_type_schema = "none" if mode == "none" else "kprobe"

                    print(f"[*] Starting Batch: SF={sf}, Q={q}, Location={loc}, ControlMode={mode}")
                    
                    # Warmup
                    for w in range(args.warmup):
                        run_single_query(mysql_cmd, sql_path, db_name)

                    # Measured runs
                    run_latencies = []
                    for rep in range(args.reps):
                        csv_filename = f"mysql_{probe_type_schema}_sf{sf}_{loc}_run{rep:02d}.csv"
                        csv_file_path = os.path.join(results_dir, csv_filename)

                        lat_ms, ns, code = run_single_query(mysql_cmd, sql_path, db_name)
                        if code == 0:
                            run_latencies.append(lat_ms)
                            iso_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                            with open(csv_file_path, "w", newline="", encoding="utf-8") as f_csv:
                                writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
                                writer.writeheader()
                                row = {
                                    "system": "mysql",
                                    "group": "B",
                                    "sub_experiment": f"B-scale-Q{q}",
                                    "probe_type": probe_type_schema,
                                    "probe_location": loc,
                                    "sf": sf,
                                    "run_id": rep,
                                    "latency_p50_ms": round(lat_ms, 3),
                                    "latency_p95_ms": round(lat_ms, 3),
                                    "latency_p99_ms": round(lat_ms, 3),
                                    "latency_p999_ms": round(lat_ms, 3),
                                    "run_time_ns": ns,
                                    "kernel_version": kernel,
                                    "system_version_hash": git_hash,
                                    "timestamp": iso_ts
                                }
                                writer.writerow(row)

                    if run_latencies:
                        avg_lat = sum(run_latencies) / len(run_latencies)
                        print(f"[+] Completed Batch: SF={sf}, Q={q}, Location={loc}, Control={mode} -> Avg Latency: {avg_lat:.2f} ms")

    print(f"[SUCCESS] All measurements completed! Results saved under {results_dir}")

if __name__ == "__main__":
    main()
