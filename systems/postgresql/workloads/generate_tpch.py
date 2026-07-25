#!/usr/bin/env python3
"""
TPC-H Data Generator Script for PostgreSQL
Generates .tbl files using dbgen and strips trailing '|' delimiters.
Usage: python3 generate_tpch.py --sf <scale_factor>
"""

import argparse
import os
import subprocess
import sys
import shutil

TABLES = ["region", "nation", "part", "supplier", "partsupp", "customer", "orders", "lineitem"]

def generate_data(sf, target_dir):
    workload_dir = os.path.dirname(os.path.abspath(__file__))
    dbgen_dir = os.path.join(workload_dir, "dbgen")
    dbgen_bin = os.path.join(dbgen_dir, "dbgen")

    if not os.path.exists(dbgen_bin):
        print(f"[*] Building dbgen in {dbgen_dir}...")
        subprocess.check_call(["make", "-C", dbgen_dir])

    print(f"[*] Cleaning up pre-existing .tbl files in {dbgen_dir}...")
    for f in os.listdir(dbgen_dir):
        if f.endswith(".tbl"):
            os.remove(os.path.join(dbgen_dir, f))

    print(f"[*] Generating TPC-H data for SF={sf} in {dbgen_dir}...")
    cmd = [dbgen_bin, "-f", "-v", "-s", str(sf)]
    subprocess.check_call(cmd, cwd=dbgen_dir)

    os.makedirs(target_dir, exist_ok=True)

    print(f"[*] Processing and moving .tbl files to {target_dir}...")
    for table in TABLES:
        tbl_file = os.path.join(dbgen_dir, f"{table}.tbl")
        out_file = os.path.join(target_dir, f"{table}.csv")

        if not os.path.exists(tbl_file):
            print(f"[!] Warning: {tbl_file} missing.")
            continue

        os.chmod(tbl_file, 0o664)
        print(f"    - Cleaning trailing '|' for {table} -> {out_file}")
        with open(tbl_file, "r", encoding="latin-1") as fin, open(out_file, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.rstrip()
                if line.endswith("|"):
                    line = line[:-1]
                fout.write(line + "\n")
        
        # Remove raw .tbl file in dbgen dir to save space
        os.remove(tbl_file)

    print(f"[+] TPC-H SF={sf} data generation complete at {target_dir}")

def main():
    parser = argparse.ArgumentParser(description="TPC-H Data Generator for PostgreSQL")
    parser.add_argument("--sf", type=float, required=True, help="Scale Factor (e.g. 1, 10, 100)")
    parser.add_argument("--outdir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    workload_dir = os.path.dirname(os.path.abspath(__file__))
    sf_str = str(int(args.sf)) if args.sf.is_integer() else str(args.sf)
    target_dir = args.outdir if args.outdir else os.path.join(workload_dir, "data", f"sf{sf_str}")

    generate_data(args.sf, target_dir)

if __name__ == "__main__":
    main()
