#include "common.bpf.h"

/*
 * TARGET_FUNC: Phase 1에서 target_syscall로 getpid를 채택(A-1 옵션 2, 59~61행)하면서 확정.
 * __x64_sys_getpid는 /proc/kallsyms에 global 심볼로 노출되므로 kprobe 부착 가능
 * (커널 6.8.0-31-generic에서 확인, 2026-07-22). 커널 버전이 바뀌면 재확인 필요 —
 * fentry_empty.bpf.c의 TARGET_FUNC(__do_sys_getpid)와 이름이 다른 이유는 그 파일 주석 참고.
 * 빌드 시 -DTARGET_FUNC='"실제_심볼명"' 으로 덮어써서 사용한다.
 */
#ifndef TARGET_FUNC
#define TARGET_FUNC "__x64_sys_getpid"
#endif

SEC("kprobe/" TARGET_FUNC)
int BPF_KPROBE(on_entry)
{
    bump_counter();
    return 0;
}
