#!/usr/bin/env bash
# systems/umbra/setup/umbra_idle.sh
# A-2 배경상태("Umbra idle") 조건용 Umbra 컨테이너 기동/정지 (Docker Hub umbradb/umbra 이미지).
#
#   bash umbra_idle.sh start    이미지 pull + 컨테이너 기동 (이미 떠 있으면 그대로, 정지 상태면 재시작)
#   bash umbra_idle.sh stop     컨테이너 정지 (삭제는 안 함 — 다시 켤 땐 start)
#   bash umbra_idle.sh status   기동 상태 확인
set -euo pipefail

NAME="umbra-idle"
IMAGE="umbradb/umbra:latest"
VOLUME="umbra-db"
PORT="5432"

start() {
    if docker ps --filter "name=^${NAME}$" --filter status=running -q | grep -q .; then
        echo "이미 떠 있음: ${NAME}"
        return 0
    fi
    if docker ps -a --filter "name=^${NAME}$" -q | grep -q .; then
        docker start "$NAME"
        echo "재시작: ${NAME}"
        return 0
    fi
    docker pull "$IMAGE"
    docker run -d --name "$NAME" \
        -v "${VOLUME}:/var/db" -p "${PORT}:5432" \
        --ulimit nofile=1048576:1048576 --ulimit memlock=8388608:8388608 \
        "$IMAGE"
    echo "새로 기동: ${NAME}"
}

stop() {
    if docker ps --filter "name=^${NAME}$" --filter status=running -q | grep -q .; then
        docker stop "$NAME"
        echo "정지: ${NAME}"
    else
        echo "이미 안 떠 있음: ${NAME}"
    fi
}

status() {
    docker ps -a --filter "name=^${NAME}$"
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    *)
        echo "사용법: bash $0 {start|stop|status}" >&2
        exit 1
        ;;
esac
