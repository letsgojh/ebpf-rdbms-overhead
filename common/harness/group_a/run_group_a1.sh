#!/usr/bin/env bash
# common/harness/group_a/run_group_a1.sh
# group_a1_runner.py는 일반 사용자 권한으로 돈다 — 그 안에서 bpftool/rm 호출 몇 개만 각자
# sudo를 붙여 쓴다(스크립트 전체를 root로 올리면 CSV/raw 파일까지 root 소유가 돼서 이후
# `make report`/`make validate` 등이 못 쓰는 문제가 있었음). 이 스크립트는 bpf_stats_enabled만
# 한 번 sudo로 켜고, 나머지는 그대로 넘긴다.
#
# 사용법:
#   bash common/harness/group_a/run_group_a1.sh --system duckdb --probe-type kprobe \
#       --reps 100 --n 10000000 --outdir systems/duckdb/results/group_a
set -euo pipefail

sudo sysctl -w kernel.bpf_stats_enabled=1 >/dev/null

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/group_a1_runner.py" "$@"
