#!/usr/bin/env bash
# systems/duckdb/setup/install.sh
# DuckDB CLI 버전을 확인하고 VERSION.lock에 기록한다.
#
# DuckDB는 별도 서버 데몬 없이 단일 정적 바이너리로 배포되는 임베디드 DB라, PostgreSQL/MySQL처럼
# 소스 빌드가 필요 없다 — 이미 설치돼 있으면(이 서버는 /home/jhyoo/bin/duckdb) 버전만 확인/고정한다.
# 없으면 공식 설치 방법(https://duckdb.org/install)으로 직접 설치 후 재실행할 것 — 배포 파일명 규칙이
# 버전마다 바뀔 수 있어 이 스크립트가 자동 다운로드는 하지 않는다.
set -euo pipefail

DUCKDB_BIN="${DUCKDB_BIN:-duckdb}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v "$DUCKDB_BIN" >/dev/null 2>&1; then
    echo "duckdb 실행파일을 찾을 수 없습니다 (\$DUCKDB_BIN=$DUCKDB_BIN)." >&2
    echo "https://duckdb.org/install 에서 CLI를 설치한 뒤 재실행하세요." >&2
    exit 1
fi

version="$("$DUCKDB_BIN" --version)"
echo "$version" > "$SCRIPT_DIR/VERSION.lock"
echo "확인됨: $version"
echo "VERSION.lock 기록 완료: $SCRIPT_DIR/VERSION.lock"
