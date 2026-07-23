#!/usr/bin/env bash
# systems/duckdb/setup/idle.sh
# A-2(앰비언트 부하 민감도)의 "DuckDB idle" 배경 상태를 만든다.
#
# DuckDB는 PostgreSQL/MySQL처럼 항상 떠 있는 서버 데몬이 없는 임베디드 DB라, "idle 상태로 띄운다"는
# 게 곧 "DB 파일을 로드한 커넥션을 유지한 프로세스가 하나 떠 있다"는 뜻이다. duckdb CLI의 stdin을
# 절대 끝나지 않는 파이프(tail -f /dev/null)에 연결해, 프롬프트에서 쿼리를 안 받고 계속 대기하게
# 만드는 방식으로 흉내낸다. -readonly로 열어서 실제 벤치마크용 DB 파일을 락/오염시키지 않는다.
#
# 사용법:
#   bash idle.sh start [DB경로]   # 기본 DB: 아래 DEFAULT_DB
#   bash idle.sh stop
#   bash idle.sh status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/idle.pid"
LOG_FILE="$SCRIPT_DIR/idle.log"
# TPC-H SF100 DB(이미 이 서버에 존재, 유재환의 별도 벤치마크 프로젝트). 실제 데이터가 로드된 채로
# idle이어야 "빈 인메모리 DB"보다 현실적인 배경 부하가 되므로 재사용한다. Group B용 workloads/에
# 자체 TPC-H 데이터를 만들게 되면 그쪽으로 옮기는 게 더 낫다(지금은 중복 생성 비용 절감 목적).
DEFAULT_DB="/home/jhyoo/DuckDB/TPC-Benchmark-on-DuckDB/TPC_H/tpch_sf100.duckdb"
DB_PATH="${2:-$DEFAULT_DB}"
DUCKDB_BIN="${DUCKDB_BIN:-duckdb}"

status() {
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "실행 중 (PID $(cat "$PID_FILE"))"
        return 0
    fi
    echo "실행 중 아님"
    return 1
}

start() {
    if status >/dev/null 2>&1; then
        echo "이미 실행 중 (PID $(cat "$PID_FILE")) — 중복 실행 안 함"
        exit 0
    fi
    if [[ ! -f "$DB_PATH" ]]; then
        echo "DB 파일 없음: $DB_PATH" >&2
        exit 1
    fi
    nohup bash -c "tail -f /dev/null | '$DUCKDB_BIN' -readonly '$DB_PATH'" \
        > "$LOG_FILE" 2>&1 &
    disown
    echo $! > "$PID_FILE"
    sleep 1
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "DuckDB idle 시작됨 (PID $(cat "$PID_FILE"), DB: $DB_PATH)"
    else
        echo "시작 실패 — $LOG_FILE 확인" >&2
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if [[ -f "$PID_FILE" ]]; then
        pid="$(cat "$PID_FILE")"
        pkill -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "DuckDB idle 종료됨 (PID $pid)"
    else
        echo "실행 중인 게 없음"
    fi
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    *) echo "사용법: $0 {start|stop|status} [DB경로]" >&2; exit 1 ;;
esac
