#!/usr/bin/env python3
"""
MySQL TPC-H Dataset Generator & Automated Loader Script (SF1, SF10, SF100)
Supports nohup background execution logging.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

TABLES = [
    "region",
    "nation",
    "part",
    "supplier",
    "partsupp",
    "customer",
    "orders",
    "lineitem"
]

DBGEN_DIR = "/home/hgkim/TPC_Benchmark/TPC-H V3.0.1/dbgen"

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}", flush=True)

def run_cmd(cmd, cwd=None, check=True):
    log(f"Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if res.returncode != 0 and check:
        log(f"[ERROR] Command failed with code {res.returncode}: {res.stderr}")
        raise RuntimeError(f"Command failed: {res.stderr}")
    return res

def setup_database_schema(mysql_cmd, db_name, schema_file):
    log(f"Initializing database '{db_name}' schema...")
    run_cmd(mysql_cmd + ["-e", f"DROP DATABASE IF EXISTS {db_name};"])
    run_cmd(mysql_cmd + ["-e", f"CREATE DATABASE {db_name};"])
    with open(schema_file, "r") as f:
        subprocess.run(mysql_cmd + [db_name], stdin=f, check=True)

def load_tbl_data(mysql_cmd, db_name, tbl_dir):
    log(f"Loading .tbl/.csv datasets from {tbl_dir} into database '{db_name}'...")
    for table in TABLES:
        tbl_file = os.path.join(tbl_dir, f"{table}.tbl")
        if not os.path.exists(tbl_file):
            tbl_file = os.path.join(tbl_dir, f"{table}.csv")
        if not os.path.exists(tbl_file):
            log(f"[WARNING] Table file for '{table}' not found in {tbl_dir}, skipping.")
            continue
        
        log(f"  -> Loading table '{table}' from {os.path.basename(tbl_file)}...")
        load_sql = f"LOAD DATA LOCAL INFILE '{tbl_file}' INTO TABLE {table} FIELDS TERMINATED BY '|' LINES TERMINATED BY '\\n';"
        run_cmd(mysql_cmd + ["--local-infile=1", db_name, "-e", load_sql])
    log(f"[SUCCESS] Database '{db_name}' load complete!")

def process_sf(sf, mysql_cmd, schema_file):
    sf_str = str(int(sf)) if float(sf).is_integer() else str(sf)
    db_name = f"tpch_sf{sf_str}"
    log(f"=== Processing TPC-H SF={sf_str} (Target DB: {db_name}) ===")

    setup_database_schema(mysql_cmd, db_name, schema_file)

    if sf == 100:
        # SF100 files are already present in DBGEN_DIR
        log("Using pre-generated SF100 data files in DBGEN_DIR...")
        load_tbl_data(mysql_cmd, db_name, DBGEN_DIR)
    else:
        # Generate data for SF1 or SF10
        log(f"Generating SF={sf_str} data files via dbgen in {DBGEN_DIR}...")
        run_cmd(f"./dbgen -f -s {sf_str}", cwd=DBGEN_DIR)
        load_tbl_data(mysql_cmd, db_name, DBGEN_DIR)

def main():
    parser = argparse.ArgumentParser(description="Automated MySQL TPC-H SF1/SF10/SF100 Loader")
    parser.add_argument("--host", default="127.0.0.1", help="MySQL Host")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Port")
    parser.add_argument("--user", default="root", help="MySQL User")
    parser.add_argument("--password", default="", help="MySQL Password")
    parser.add_argument("--sf", nargs="+", type=float, default=[1, 10, 100], help="Scale factors to build (e.g. 1 10 100)")
    args = parser.parse_args()

    workload_dir = os.path.dirname(os.path.abspath(__file__))
    schema_file = os.path.join(workload_dir, "schema.sql")

    mysql_cmd = ["mysql", "-u", args.user, "-h", args.host, "-P", str(args.port)]
    if args.password:
        mysql_cmd.append(f"-p{args.password}")

    log("Starting TPC-H Automated Dataset Generation & Import Job...")
    start_time = time.time()

    for sf in args.sf:
        process_sf(sf, mysql_cmd, schema_file)

    total_time = time.time() - start_time
    log(f"=== ALL TPC-H Datasets Processed Successfully in {total_time:.2f} seconds ===")

if __name__ == "__main__":
    main()
