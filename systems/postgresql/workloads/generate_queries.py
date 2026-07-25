#!/usr/bin/env python3
"""
TPC-H Query Generator and Validator for PostgreSQL
Generates q1.sql to q22.sql using qgen, fixes PostgreSQL-specific syntax (e.g. Q15 CTE rewrite),
and verifies each query against PostgreSQL tpch_sf1 database.
Usage: python3 generate_queries.py [--port 5433] [--host /tmp] [--dbname tpch_sf1]
"""

import argparse
import os
import subprocess
import sys

import re

def clean_pg_sql(q, raw_sql):
    lines = [line for line in raw_sql.split("\n") if not line.strip().startswith("--") and line.strip()]
    sql = "\n".join(lines).strip()

    # Fix interval syntax: interval '90' day (3) -> interval '90 day'
    sql = re.sub(r"interval\s+'(\d+)'\s+(day|month|year)(\s*\(\d+\))?", r"interval '\1 \2'", sql, flags=re.IGNORECASE)

    # Fix rownum syntax: ;\nwhere rownum <= 100; -> LIMIT 100;
    def replace_rownum(match):
        limit_val = int(match.group(1))
        if limit_val > 0:
            return f"\nLIMIT {limit_val};"
        return ";"

    sql = re.sub(r";?\s*where\s+rownum\s*<=\s*(-?\d+)\s*;?", replace_rownum, sql, flags=re.IGNORECASE)

    # Handle Q15 specifically: rewrite CREATE VIEW ... SELECT ... DROP VIEW as CTE
    if q == 15:
        sql = """WITH revenue0 AS (
    SELECT
        l_suppkey AS supplier_no,
        sum(l_extendedprice * (1 - l_discount)) AS total_revenue
    FROM
        lineitem
    WHERE
        l_shipdate >= date '1996-01-01'
        AND l_shipdate < date '1996-01-01' + interval '3 month'
    GROUP BY
        l_suppkey
)
SELECT
    s_suppkey,
    s_name,
    s_address,
    s_phone,
    total_revenue
FROM
    supplier,
    revenue0
WHERE
    s_suppkey = supplier_no
    AND total_revenue = (
        SELECT
            max(total_revenue)
        FROM
            revenue0
    )
ORDER BY
    s_suppkey;"""

    if not sql.endswith(";"):
        sql += ";"

    return sql

def generate_queries(queries_dir):
    workload_dir = os.path.dirname(os.path.abspath(__file__))
    dbgen_dir = os.path.join(workload_dir, "dbgen")
    qgen_bin = os.path.join(dbgen_dir, "qgen")

    if not os.path.exists(qgen_bin):
        print(f"[*] Building qgen in {dbgen_dir}...")
        subprocess.check_call(["make", "-C", dbgen_dir])

    os.makedirs(queries_dir, exist_ok=True)
    env = os.environ.copy()
    env["DSS_QUERY"] = "queries"

    for q in range(1, 23):
        out_sql_path = os.path.join(queries_dir, f"q{q}.sql")
        
        # Run qgen for query q
        res = subprocess.run([qgen_bin, "-d", str(q)], cwd=dbgen_dir, env=env, capture_output=True, text=True, check=True)
        raw_sql = res.stdout

        clean_sql = clean_pg_sql(q, raw_sql)

        # Write to q<N>.sql
        with open(out_sql_path, "w", encoding="utf-8") as f:
            f.write(f"-- TPC-H Query Q{q}\n" + clean_sql + "\n")
        
        print(f"    - Generated {out_sql_path}")

    print(f"[+] All 22 TPC-H query files generated in {queries_dir}")

def validate_queries(queries_dir, port, host, dbname):
    print(f"[*] Validating 22 queries against PostgreSQL database '{dbname}' on {host}:{port}...")
    psql_cmd = ["psql", "-h", host, "-p", str(port), "-d", dbname, "-c"]

    success_count = 0
    for q in range(1, 23):
        sql_path = os.path.join(queries_dir, f"q{q}.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        explain_sql = f"EXPLAIN {sql_content}"
        res = subprocess.run(psql_cmd + [explain_sql], capture_output=True, text=True)

        if res.returncode == 0:
            print(f"    - Q{q:02d}: EXPLAIN SUCCESS")
            success_count += 1
        else:
            print(f"    [!] Q{q:02d}: EXPLAIN FAILED")
            print(res.stderr)

    print(f"[+] Validation Summary: {success_count}/22 queries passed EXPLAIN check.")

def main():
    parser = argparse.ArgumentParser(description="TPC-H Query Generator and Validator")
    parser.add_argument("--port", type=int, default=5433, help="PostgreSQL Port")
    parser.add_argument("--host", type=str, default="/tmp", help="PostgreSQL Host / Socket Dir")
    parser.add_argument("--dbname", type=str, default="tpch_sf1", help="PostgreSQL Database Name")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing queries")
    args = parser.parse_args()

    workload_dir = os.path.dirname(os.path.abspath(__file__))
    queries_dir = os.path.join(workload_dir, "queries")

    if not args.validate_only:
        generate_queries(queries_dir)

    validate_queries(queries_dir, args.port, args.host, args.dbname)

if __name__ == "__main__":
    main()
