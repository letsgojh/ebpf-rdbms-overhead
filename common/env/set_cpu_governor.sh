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
skipped=0
for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
    # 의도적으로 offline시킨 코어(예: SMT 형제 스레드 전체 차단)는 건너뛴다 — cpu0은 보통 offline이
    # 불가능해서 online 파일 자체가 없으니, 파일이 없으면 "always online"으로 취급한다.
    online_file="$cpu_dir/online"
    if [[ -f "$online_file" ]] && [[ "$(cat "$online_file" 2>/dev/null)" == "0" ]]; then
        skipped=$((skipped + 1))
        continue
    fi

    gov_file="$cpu_dir/cpufreq/scaling_governor"
    [[ -f "$gov_file" ]] || continue

    # cpupower frequency-set 직후 특정 코어의 scaling_governor 읽기가 "Device or resource busy"로
    # 잠깐 실패하는 경우가 있다(드라이버가 방금 건 값을 적용 중일 때의 레이스로 추정) — 이 read 하나가
    # set -e로 스크립트 전체를 죽이지 않도록 재시도 후에도 실패하면 경고만 남기고 넘어간다.
    current=""
    for attempt in 1 2 3 4 5; do
        if current=$(cat "$gov_file" 2>/dev/null); then
            break
        fi
        current=""
        sleep 0.2
    done

    if [[ -z "$current" ]]; then
        echo "  $(basename "$cpu_dir"): 읽기 실패(5회 재시도 후에도 busy) — 수동 확인 필요" >&2
        fail=1
        continue
    fi

    echo "  $(basename "$cpu_dir"): $current"
    if [[ "$current" != "$GOVERNOR" ]]; then
        fail=1
    fi
done

if [[ $fail -ne 0 ]]; then
    echo "일부 CPU에서 governor 설정이 반영되지 않았습니다." >&2
    exit 1
fi

echo "모든 온라인 CPU governor = $GOVERNOR (offline로 건너뛴 코어: ${skipped}개)"
