#!/usr/bin/env bash
# CPU frequency governor를 performance로 고정하고 적용 결과를 검증한다.
set -euo pipefail

GOVERNOR="performance"

if [[ $EUID -ne 0 ]]; then
    # $0가 슬래시 없는 맨 파일명이면 sudo가 $PATH에서 찾다 "command not found"로 실패한다
    # (예: `bash set_cpu_governor.sh`로 호출된 경우) — 항상 절대경로로 바꿔서 넘긴다.
    exec sudo -E "$(readlink -f "$0")" "$@"
fi

if ! command -v cpupower >/dev/null 2>&1; then
    echo "cpupower 명령을 찾을 수 없습니다. 설치: sudo apt install linux-tools-common linux-tools-$(uname -r)" >&2
    exit 1
fi

cpupower frequency-set -g "$GOVERNOR" >/dev/null

echo "== CPU governor 확인 =="
fail=0
for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
    gov_file="$cpu_dir/cpufreq/scaling_governor"
    [[ -f "$gov_file" ]] || continue
    current=$(cat "$gov_file")
    echo "  $(basename "$cpu_dir"): $current"
    if [[ "$current" != "$GOVERNOR" ]]; then
        fail=1
    fi
done

if [[ $fail -ne 0 ]]; then
    echo "일부 CPU에서 governor 설정이 반영되지 않았습니다." >&2
    exit 1
fi

echo "모든 CPU governor = $GOVERNOR"
