#!/usr/bin/env python3
"""
MySQL TPC-H Loader Script
Loads generated TPC-H CSV files into MySQL database (tpch_sf<SF>).
Usage: python3 load_tpch.py --sf <scale_factor> [--port <port>] [--user <user>]
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

def load_data(sf, port, host, user, password, db_name):
    workload_dir = os.path.dirname(os.path.abspath(__file__))
    sf_str = str(int(sf)) if sf.is_integer() else str(sf)
    data_dir = os.path.join(workload_dir, "data", f"sf{sf_str}")
    schema_file = os.path.join(workload_dir, "schema.sql")

    mysql_cmd = ["mysql", "-u", user, "-h", host, "-P", str(port)]
    if password:
        mysql_cmd.append(f"-p{password}")

    # 1. Create Database if not exists
    print(f"[*] Creating database '{db_name}' on {host}:{port}...")
    subprocess.run(mysql_cmd + ["-e", f"DROP DATABASE IF EXISTS {db_name};"], check=False)
    subprocess.run(mysql_cmd + ["-e", f"CREATE DATABASE {db_name};"], check=True)

    # 2. Execute DDL Schema
    print(f"[*] Applying schema from {schema_file}...")
    with open(schema_file, "r") as f:
        subprocess.run(mysql_cmd + [db_name], stdin=f, check=True)

    # 3. Load Data
    if os.path.exists(data_dir):
        print(f"[*] Loading CSV datasets into '{db_name}'...")
        for table in TABLES_IN_ORDER:
            csv_file = os.path.join(data_dir, f"{table}.csv")
            if not os.path.exists(csv_file):
                print(f"[!] Warning: {csv_file} missing, skipping.")
                continue
            
            print(f"    - Importing {table} from {csv_file}...")
            load_sql = f"LOAD DATA LOCAL INFILE '{csv_file}' INTO TABLE {table} FIELDS TERMINATED BY '|';"
            subprocess.run(mysql_cmd + ["--local-infile=1", db_name, "-e", load_sql], check=True)
    else:
        print(f"[*] Data directory {data_dir} not populated yet. Database schema initialized.")

    print(f"[+] Successfully initialized MySQL TPC-H database '{db_name}'!")

def main():
    parser = argparse.ArgumentParser(description="MySQL TPC-H Data Loader")
    parser.add_argument("--sf", type=float, required=True, help="Scale Factor (e.g. 1, 10, 100)")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Port (default: 3306)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MySQL Host (default: 127.0.0.1)")
    parser.add_argument("--user", type=str, default="root", help="MySQL User")
    parser.add_argument("--password", type=str, default="", help="MySQL Password")
    parser.add_argument("--dbname", type=str, default=None, help="Database name")
    args = parser.parse_args()

    sf_str = str(int(args.sf)) if args.sf.is_integer() else str(args.sf)
    db_name = args.dbname if args.dbname else f"tpch_sf{sf_str}"

    load_data(args.sf, args.port, args.host, args.user, args.password, db_name)

if __name__ == "__main__":
    main()
