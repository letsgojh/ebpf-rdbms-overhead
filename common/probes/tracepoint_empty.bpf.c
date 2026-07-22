#include "common.bpf.h"

/*
 * TARGET_TRACEPOINT: Phase 1에서 target_syscall로 getpid를 채택하면서 확정
 * (A-1 옵션 2, 59~61행). "syscalls/sys_enter_<syscall명>"은 이름이 있는 모든 syscall에
 * 자동 생성되는 표준 tracepoint라 존재할 것으로 보이지만, 이 서버에서는 tracefs 접근에
 * sudo가 필요해 `ls /sys/kernel/tracing/events/syscalls/sys_enter_getpid`로 직접 확인은
 * 못 했다 — Phase 1 실행 전 sudo로 재확인 필요.
 * 빌드 시 -DTARGET_TRACEPOINT='"실제/카테고리_이름"' 으로 덮어써서 사용한다.
 */
#ifndef TARGET_TRACEPOINT
#define TARGET_TRACEPOINT "syscalls/sys_enter_getpid"
#endif

SEC("tracepoint/" TARGET_TRACEPOINT)
int on_tracepoint(void *ctx)
{
    bump_counter();
    return 0;
}
