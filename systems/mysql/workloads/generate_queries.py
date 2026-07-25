#!/usr/bin/env python3
"""
TPC-H Query Validator for MySQL
Verifies query files (q1.sql ~ q22.sql) against MySQL tpch_sf1 database using EXPLAIN.
Usage: python3 generate_queries.py [--port 3306] [--host 127.0.0.1] [--dbname tpch_sf1]
"""

import argparse
import os
import subprocess
import sys

def validate_queries(queries_dir, port, host, user, password, dbname):
    print(f"[*] Validating 22 queries against MySQL database '{dbname}' on {host}:{port}...")
    mysql_cmd = ["mysql", "-u", user, "-h", host, "-P", str(port)]
    if password:
        mysql_cmd.append(f"-p{password}")

    success_count = 0
    for q in range(1, 23):
        sql_path = os.path.join(queries_dir, f"q{q}.sql")
        if not os.path.exists(sql_path):
            continue
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        explain_sql = f"EXPLAIN {sql_content}"
        res = subprocess.run(mysql_cmd + [dbname, "-e", explain_sql], capture_output=True, text=True)

        if res.returncode == 0:
            print(f"    - Q{q:02d}: EXPLAIN SUCCESS")
            success_count += 1
        else:
            print(f"    [!] Q{q:02d}: EXPLAIN FAILED")

    print(f"[+] Validation Summary: {success_count} queries passed EXPLAIN check.")

def main():
    parser = argparse.ArgumentParser(description="TPC-H Query Validator for MySQL")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MySQL Host")
    parser.add_argument("--user", type=str, default="root", help="MySQL User")
    parser.add_argument("--password", type=str, default="", help="MySQL Password")
    parser.add_argument("--dbname", type=str, default="tpch_sf1", help="MySQL Database Name")
    args = parser.parse_args()

    workload_dir = os.path.dirname(os.path.abspath(__file__))
    queries_dir = os.path.join(workload_dir, "queries")

    validate_queries(queries_dir, args.port, args.host, args.user, args.password, args.dbname)

if __name__ == "__main__":
    main()
