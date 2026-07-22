#!/usr/bin/env bash
# SMT(하이퍼스레딩) 형제 스레드를 통째로 offline시켜 스레드 경합을 없앤다.
# 사용법: sudo ./disable_smt.sh [유지할 논리 CPU 개수, 기본값 nproc --all의 절반]
#
# 이 서버(gaia1) 토폴로지: cpuN과 cpuN+(전체/2)가 형제(예: 0↔40, 1↔41, ..., 39↔79) — 그래서
# 뒤쪽 절반(KEEP번~끝)을 통째로 끄면 물리 코어당 스레드 1개씩만 남는다. 다른 서버는 코어 수/토폴로지가
# 다를 수 있으니 실행 전 `lscpu -e`로 형제 관계를 재확인할 것.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    # $0가 슬래시 없는 맨 파일명이면 sudo가 $PATH에서 찾다 "command not found"로 실패한다
    # (예: `bash disable_smt.sh`로 호출된 경우) — 항상 절대경로로 바꿔서 넘긴다.
    exec sudo -E "$(readlink -f "$0")" "$@"
fi

TOTAL=$(nproc --all)
KEEP="${1:-$((TOTAL / 2))}"

if (( KEEP < 1 || KEEP >= TOTAL )); then
    echo "잘못된 값: KEEP=${KEEP} (전체 논리 CPU ${TOTAL}개 중 1~$((TOTAL - 1)) 사이여야 함)" >&2
    exit 1
fi

echo "== SMT 형제 스레드 offline (cpu${KEEP}~$((TOTAL - 1)), 유지: cpu0~$((KEEP - 1))) =="
for ((cpu = KEEP; cpu < TOTAL; cpu++)); do
    online_file="/sys/devices/system/cpu/cpu${cpu}/online"
    [[ -f "$online_file" ]] || continue
    echo 0 > "$online_file"
done

echo "== 확인 =="
fail=0
for ((cpu = KEEP; cpu < TOTAL; cpu++)); do
    online_file="/sys/devices/system/cpu/cpu${cpu}/online"
    [[ -f "$online_file" ]] || continue
    val=$(cat "$online_file")
    if [[ "$val" != "0" ]]; then
        echo "  경고: cpu${cpu} 여전히 online" >&2
        fail=1
    fi
done

if [[ $fail -ne 0 ]]; then
    echo "일부 코어가 offline되지 않았습니다." >&2
    exit 1
fi

echo "cpu${KEEP}~$((TOTAL - 1)) 전부 offline 완료 (온라인: cpu0~$((KEEP - 1)), 총 ${KEEP}개)"
