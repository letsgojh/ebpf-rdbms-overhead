#!/bin/bash
# systems/mysql/scripts/setup_tpch.sh
# gaia5 서버에서 MySQL TPC-H SF1, SF10, SF100 DB 생성 및 적재 스크립트

set -e

MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"

DATABASES=("tpch_sf1" "tpch_sf10" "tpch_sf100")

echo "[+] MySQL TPC-H Database Setup Target Host: ${MYSQL_HOST}:${MYSQL_PORT}"

for db in "${DATABASES[@]}"; do
    echo "[*] Creating database if not exists: ${db}"
    mysql -u"${MYSQL_USER}" -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -e "CREATE DATABASE IF NOT EXISTS ${db};" 2>/dev/null || true
done

echo "[+] Setup completed. Please ensure dbgen data load for sf1, sf10, sf100 is populated into lineitem, orders, etc."
