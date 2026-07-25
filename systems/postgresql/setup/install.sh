#!/usr/bin/env bash
# PostgreSQL Setup & Verification Script
set -e

echo "[*] Verifying PostgreSQL installation..."
if ! command -v /usr/lib/postgresql/16/bin/postgres &> /dev/null; then
    echo "[!] PostgreSQL 16 binary not found at /usr/lib/postgresql/16/bin/postgres"
    exit 1
fi

echo "[+] PostgreSQL Version: $(/usr/lib/postgresql/16/bin/postgres --version)"
echo "[+] Kernel Version: $(uname -r)"

# Verify required symbols for Group B probing
echo "[*] Checking PostgreSQL dynamic symbols for Group B probes..."
SYMBOLS=("ExecutorStart" "heap_getnextslot" "heap_getnext")
for sym in "${SYMBOLS[@]}"; do
    if nm -D /usr/lib/postgresql/16/bin/postgres | grep -q "$sym"; then
        echo "    - Symbol '$sym': FOUND"
    else
        echo "    [!] Warning: Symbol '$sym' not found in dynamic symbol table"
    fi
done

echo "[+] PostgreSQL environment verification completed successfully!"
