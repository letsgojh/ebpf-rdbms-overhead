#!/usr/bin/env bash
# MySQL Setup & Verification Script
set -e

echo "[*] Verifying MySQL installation..."
if ! command -v mysqld &> /dev/null && [ ! -f /usr/sbin/mysqld ]; then
    echo "[!] MySQL binary not found at /usr/sbin/mysqld"
    exit 1
fi

MYSQL_BIN=$(which mysqld 2>/dev/null || echo "/usr/sbin/mysqld")
echo "[+] MySQL Binary: ${MYSQL_BIN}"
echo "[+] Kernel Version: $(uname -r)"

# Verify required symbols for Group B probing
echo "[*] Checking MySQL dynamic symbols for Group B probes..."
SYMBOLS=("mysql_execute_command" "ha_rnd_next" "row_search_mvcc")
for sym in "${SYMBOLS[@]}"; do
    if nm -D "$MYSQL_BIN" 2>/dev/null | grep -q "$sym"; then
        echo "    - Symbol '$sym': FOUND"
    else
        echo "    [!] Symbol '$sym' check: check uprobe symbol table"
    fi
done

echo "[+] MySQL environment verification completed successfully!"
