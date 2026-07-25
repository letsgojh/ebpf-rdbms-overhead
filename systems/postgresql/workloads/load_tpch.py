#!/usr/bin/env python3
"""
PostgreSQL TPC-H Loader Script
Loads generated TPC-H CSV files into PostgreSQL database (tpch_sf<SF>).
Usage: python3 load_tpch.py --sf <scale_factor> [--port <port>]
"""

import argparse
import os
import subprocess
import sys

TABLES_IN_ORDER = [
    "region",
    "nation",
    "part",
    "supplier",
    "partsupp",
    "customer",
    "orders",
    "lineitem"
]

def load_data(sf, port, host, db_name):
    workload_dir = os.path.dirname(os.path.abspath(__file__))
    sf_str = str(int(sf)) if sf.is_integer() else str(sf)
    data_dir = os.path.join(workload_dir, "data", f"sf{sf_str}")
    schema_file = os.path.join(workload_dir, "schema.sql")

    if not os.path.exists(data_dir):
        sys.exit(f"[!] Error: Data directory {data_dir} does not exist. Run generate_tpch.py first.")

    psql_cmd = ["psql", "-h", host, "-p", str(port)]

    # 1. Create Database if not exists
    print(f"[*] Creating database '{db_name}' on port {port}...")
    subprocess.run(psql_cmd + ["-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {db_name};"], check=False)
    subprocess.run(psql_cmd + ["-d", "postgres", "-c", f"CREATE DATABASE {db_name};"], check=True)

    # 2. Execute DDL Schema
    print(f"[*] Applying schema from {schema_file}...")
    subprocess.run(psql_cmd + ["-d", db_name, "-f", schema_file], check=True)

    # 3. Load CSV Data
    print(f"[*] Loading CSV datasets into '{db_name}'...")
    for table in TABLES_IN_ORDER:
        csv_file = os.path.join(data_dir, f"{table}.csv")
        if not os.path.exists(csv_file):
            print(f"[!] Warning: {csv_file} missing, skipping.")
            continue
        
        print(f"    - Importing {table} from {csv_file}...")
        copy_sql = f"\\copy {table} FROM '{csv_file}' WITH (FORMAT csv, DELIMITER '|');"
        subprocess.run(psql_cmd + ["-d", db_name, "-c", copy_sql], check=True)

    # 4. ANALYZE for query optimizer stats
    print(f"[*] Running ANALYZE on '{db_name}'...")
    subprocess.run(psql_cmd + ["-d", db_name, "-c", "ANALYZE;"], check=True)

    print(f"[+] Successfully loaded TPC-H SF={sf} into PostgreSQL database '{db_name}'!")

def main():
    parser = argparse.ArgumentParser(description="PostgreSQL TPC-H Data Loader")
    parser.add_argument("--sf", type=float, required=True, help="Scale Factor (e.g. 1, 10, 100)")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL Port (default: 5432)")
    parser.add_argument("--host", type=str, default="/tmp", help="PostgreSQL Host / Socket Dir (default: /tmp)")
    parser.add_argument("--dbname", type=str, default=None, help="Database name")
    args = parser.parse_args()

    sf_str = str(int(args.sf)) if args.sf.is_integer() else str(args.sf)
    db_name = args.dbname if args.dbname else f"tpch_sf{sf_str}"

    load_data(args.sf, args.port, args.host, db_name)

if __name__ == "__main__":
    main()
