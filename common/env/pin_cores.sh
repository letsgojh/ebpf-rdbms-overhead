#!/usr/bin/env bash
# 실험 대상 코어를 격리 상태로 확인하고, 그 외 코어로 IRQ affinity를 몰아준다.
# 사용법: sudo ./pin_cores.sh [코어목록(콤마구분), 기본값 2,3]
set -euo pipefail

CORES="${1:-2,3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="$SCRIPT_DIR/pinned_cores.conf"

if [[ $EUID -ne 0 ]]; then
    # $0가 슬래시 없는 맨 파일명이면 sudo가 $PATH에서 찾다 "command not found"로 실패한다
    # (예: `bash pin_cores.sh`로 호출된 경우) — 항상 절대경로로 바꿔서 넘긴다.
    exec sudo -E "$(readlink -f "$0")" "$@"
fi

echo "== isolcpus 커널 파라미터 확인 =="
if grep -q "isolcpus=" /proc/cmdline; then
    echo "설정됨: $(grep -o 'isolcpus=[^ ]*' /proc/cmdline)"
else
    echo "경고: /proc/cmdline에 isolcpus가 없습니다." >&2
    echo "  /etc/default/grub의 GRUB_CMDLINE_LINUX에 isolcpus=${CORES} 추가 후" >&2
    echo "  update-grub && reboot 를 권장합니다 (지금 실행은 IRQ 이동만 적용됩니다)." >&2
fi

echo "== 대상 코어(${CORES}) 외 나머지로 IRQ affinity 이동 =="
IFS=',' read -ra CORE_ARR <<< "$CORES"
LAST_CPU=$(( $(nproc) - 1 ))
OTHER_CORES=""
for c in $(seq 0 "$LAST_CPU"); do
    is_target=0
    for tc in "${CORE_ARR[@]}"; do
        [[ "$c" == "$tc" ]] && is_target=1 && break
    done
    [[ $is_target -eq 0 ]] && OTHER_CORES+="${OTHER_CORES:+,}$c"
done

if [[ -z "$OTHER_CORES" ]]; then
    echo "경고: 대상 코어가 전체 코어를 덮어서 IRQ를 옮길 곳이 없습니다." >&2
else
    moved=0
    for irq_dir in /proc/irq/[0-9]*; do
        aff_file="$irq_dir/smp_affinity_list"
        [[ -w "$aff_file" ]] || continue
        if echo "$OTHER_CORES" > "$aff_file" 2>/dev/null; then
            moved=$((moved + 1))
        fi
    done
    echo "IRQ ${moved}개를 코어 ${OTHER_CORES}로 이동 완료"
fi

echo "$CORES" > "$CONF_FILE"
echo "== 완료 =="
echo "pinned core 목록(${CORES})을 ${CONF_FILE}에 저장했습니다."
echo "이후 실험 실행 시 harness를 다음과 같이 실행하세요: taskset -c ${CORES} <harness 실행파일>"
