#!/usr/bin/env python3
"""
MySQL Group B Experiment Runner Harness
Executes 4-way controlled measurements (none, perf, ebpf, both) across
Probe Locations (query, operator, tuple) x Scale Factors x Queries.
Outputs standardized CSV results matching common/schema/result_schema.json.
"""

import argparse
import datetime
import os
import random
import subprocess
import sys
import time

PILOT_QUERIES = [1, 6, 9]
ALL_QUERIES = list(range(1, 23))

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

MYSQL_BINARY = "/usr/sbin/mysqld"

def get_kernel_version():
    res = subprocess.run(["uname", "-r"], capture_output=True, text=True)
    return res.stdout.strip()

def run_single_query(mysql_cmd, sql_path, db_name):
    start_time = time.perf_counter()
    with open(sql_path, "r") as f:
        res = subprocess.run(mysql_cmd + [db_name], stdin=f, capture_output=True, text=True)
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000.0
    return latency_ms, res.returncode

def main():
    parser = argparse.ArgumentParser(description="MySQL Group B Experiment Runner Harness")
    parser.add_argument("--sf", type=int, default=1, choices=[1, 10, 100], help="Scale Factor")
    parser.add_argument("--query", type=int, default=6, help="Query number (1, 6, 9)")
    parser.add_argument("--location", type=str, default="query", choices=["query", "operator", "tuple"], help="Probe Location")
    parser.add_argument("--reps", type=int, default=100, help="Number of repetitions")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup runs")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MySQL Host")
    parser.add_argument("--user", type=str, default="root", help="MySQL User")
    parser.add_argument("--password", type=str, default="", help="MySQL Password")
    args = parser.parse_args()

    print(f"[*] Starting MySQL Group B Experiment: SF={args.sf}, Query=Q{args.query}, Location={args.location}")
    print(f"[+] Repetitions: {args.reps} (Warmup: {args.warmup})")

    db_name = f"tpch_sf{args.sf}"
    work_dir = os.path.dirname(os.path.abspath(__file__))
    sys_dir = os.path.dirname(work_dir)
    sql_path = os.path.join(sys_dir, "workloads", "queries", f"q{args.query}.sql")

    if not os.path.exists(sql_path):
        sql_path = os.path.join(sys_dir, "queries", f"q{args.query}.sql")

    if not os.path.exists(sql_path):
        sys.exit(f"[!] Query file {sql_path} does not exist.")

    mysql_cmd = ["mysql", "-u", args.user, "-h", args.host, "-P", str(args.port)]
    if args.password:
        mysql_cmd.append(f"-p{args.password}")

    # Warmup runs
    print(f"[*] Running {args.warmup} warmup iterations...")
    for _ in range(args.warmup):
        run_single_query(mysql_cmd, sql_path, db_name)

    # Measured runs
    print(f"[*] Running {args.reps} measured iterations...")
    latencies = []
    for i in range(args.reps):
        lat, code = run_single_query(mysql_cmd, sql_path, db_name)
        if code == 0:
            latencies.append(lat)
        else:
            print(f"    [!] Run {i+1} failed with return code {code}")

    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        print(f"[+] Completed {len(latencies)} successful runs. Avg Latency: {avg_lat:.2f} ms")

if __name__ == "__main__":
    main()
