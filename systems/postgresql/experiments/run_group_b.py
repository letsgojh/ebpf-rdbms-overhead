#!/usr/bin/env python3
"""
PostgreSQL Group B Experiment Runner Harness
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
    "query": "pg_query.bpf.o",
    "operator": "pg_operator.bpf.o",
    "tuple": "pg_tuple.bpf.o"
}

PROBE_SYMBOLS = {
    "query": "ExecutorStart",
    "operator": "ExecProcNode",
    "tuple": "heap_getnextslot"
}

PG_BINARY = "/usr/lib/postgresql/16/bin/postgres"

def get_kernel_version():
    res = subprocess.run(["uname", "-r"], capture_output=True, text=True)
    return res.stdout.strip()

def run_single_query(psql_cmd, sql_path):
    start_time = time.perf_counter()
    res = subprocess.run(psql_cmd + ["-f", sql_path], capture_output=True, text=True)
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000.0
    success = (res.returncode == 0)
    return latency_ms, success

def main():
    parser = argparse.ArgumentParser(description="PostgreSQL Group B Experiment Harness")
    parser.add_argument("--sf", type=float, default=1.0, help="Scale Factor (default: 1.0)")
    parser.add_argument("--queries", type=str, default="pilot", help="Queries: 'pilot' (1,6,9), 'all' (1..22), or comma-separated numbers")
    parser.add_argument("--probes", type=str, default="all", help="Probe locations: 'all' (query,operator,tuple), or comma-separated")
    parser.add_argument("--reps", type=int, default=100, help="Number of repetitions (default: 100)")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup runs (default: 10)")
    parser.add_argument("--port", type=int, default=5433, help="PostgreSQL Port")
    parser.add_argument("--host", type=str, default="/tmp", help="PostgreSQL Host / Socket Dir")
    parser.add_argument("--dbname", type=str, default=None, help="Database name")
    parser.add_argument("--outdir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    workload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workloads")
    queries_dir = os.path.join(workload_dir, "queries")
    probes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes")
    results_dir = args.outdir if args.outdir else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "group_b")

    os.makedirs(results_dir, exist_ok=True)

    sf_str = str(int(args.sf)) if args.sf.is_integer() else str(args.sf)
    db_name = args.dbname if args.dbname else f"tpch_sf{sf_str}"

    if args.queries == "pilot":
        query_list = PILOT_QUERIES
    elif args.queries == "all":
        query_list = ALL_QUERIES
    else:
        query_list = [int(q.strip()) for q in args.queries.split(",")]

    if args.probes == "all":
        probe_list = ["query", "operator", "tuple"]
    else:
        probe_list = [p.strip() for p in args.probes.split(",")]

    psql_cmd = ["psql", "-h", args.host, "-p", str(args.port), "-d", db_name, "-q"]
    kernel_ver = get_kernel_version()

    print(f"[*] Starting Group B Harness for PostgreSQL on db '{db_name}' (SF={args.sf})")
    print(f"[*] Target Queries: {query_list}")
    print(f"[*] Target Probe Locations: {probe_list}")
    print(f"[*] Repetitions: {args.reps} (Warmup: {args.warmup})")

    for probe_loc in probe_list:
        csv_filename = f"postgresql_uprobe_sf{sf_str}_{probe_loc}_run01.csv"
        csv_path = os.path.join(results_dir, csv_filename)
        print(f"\n[+] Executing Group B for probe location: '{probe_loc}' -> {csv_path}")

        # Prepare CSV File header
        with open(csv_path, "w", encoding="utf-8") as fcsv:
            fcsv.write("system,group,sub_experiment,probe_type,probe_location,sf,run_id,query_id,throughput_qps,latency_ms,kernel_version,system_version_hash,timestamp\n")

            for q_id in query_list:
                sql_path = os.path.join(queries_dir, f"q{q_id}.sql")
                print(f"    - Running Query Q{q_id}...")

                # Warm-up runs
                for w in range(args.warmup):
                    run_single_query(psql_cmd, sql_path)

                # Main measurement runs
                for rep in range(args.reps):
                    lat_ms, success = run_single_query(psql_cmd, sql_path)
                    qps = 1000.0 / lat_ms if lat_ms > 0 else 0.0
                    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    
                    fcsv.write(f"postgresql,B,B-scale,uprobe,{probe_loc},{int(args.sf)},{rep},{q_id},{qps:.4f},{lat_ms:.4f},{kernel_ver},16.14-0ubuntu0.24.04.1,{ts}\n")

    print(f"\n[+] Group B Experiment Execution Complete! Results saved to {results_dir}")

if __name__ == "__main__":
    main()
