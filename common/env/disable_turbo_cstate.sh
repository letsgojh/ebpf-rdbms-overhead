#!/usr/bin/env bash
# Turbo Boost와 딥 C-state(C1 초과)를 비활성화해 클럭/유휴상태 변동을 제거한다.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    # $0가 슬래시 없는 맨 파일명이면 sudo가 $PATH에서 찾다 "command not found"로 실패한다
    # (예: `bash disable_turbo_cstate.sh`로 호출된 경우) — 항상 절대경로로 바꿔서 넘긴다.
    exec sudo -E "$(readlink -f "$0")" "$@"
fi

echo "== Turbo Boost 비활성화 =="
if [[ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
    echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo
    echo "intel_pstate/no_turbo = $(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
elif [[ -f /sys/devices/system/cpu/cpufreq/boost ]]; then
    echo 0 > /sys/devices/system/cpu/cpufreq/boost
    echo "cpufreq/boost = $(cat /sys/devices/system/cpu/cpufreq/boost)"
else
    echo "경고: turbo 제어 인터페이스를 찾지 못함 — BIOS에서 수동 확인 필요" >&2
fi

echo "== C-state 비활성화 (state1 이상 전부 disable, state0=POLL/C0는 유지) =="
shopt -s nullglob
for cpu_idle_dir in /sys/devices/system/cpu/cpu[0-9]*/cpuidle; do
    for state_dir in "$cpu_idle_dir"/state[1-9]*; do
        [[ -f "$state_dir/disable" ]] || continue
        echo 1 > "$state_dir/disable"
    done
done
shopt -u nullglob

echo "== 확인 (cpu0 기준) =="
for state_dir in /sys/devices/system/cpu/cpu0/cpuidle/state*; do
    name=$(cat "$state_dir/name" 2>/dev/null || echo "?")
    disabled=$(cat "$state_dir/disable" 2>/dev/null || echo "?")
    echo "  $(basename "$state_dir") ($name): disable=$disabled"
done
