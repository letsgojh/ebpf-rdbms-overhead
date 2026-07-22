#include "common.bpf.h"

/*
 * TARGET_RAW_TRACEPOINT: raw tracepoint 이벤트 이름(카테고리 없음). "sys_enter"는 모든
 * syscall에서 발화하므로, target_syscall로 getpid를 쓰는 이상(Phase 1, A-1 옵션 2) 이 프로그램만
 * ctx->args[1](syscall 번호)로 걸러내야 다른 3개 family와 "같은 이벤트(getpid 호출)"를 재는 셈이
 * 된다. kprobe/fentry/tracepoint는 애초에 getpid에만 붙어서 이 필터가 필요 없다 — 그래서
 * TARGET_SYSCALL_NR 체크만 raw_tracepoint에만 있고, 그 아래 "카운터 증가" 로직 자체는 여전히
 * bump_counter() 하나로 나머지 3개와 동일하다.
 * 빌드 시 -DTARGET_RAW_TRACEPOINT='"실제_이벤트명"' -DTARGET_SYSCALL_NR=번호 로 덮어써서 사용한다.
 */
#ifndef TARGET_RAW_TRACEPOINT
#define TARGET_RAW_TRACEPOINT "sys_enter"
#endif

/* __NR_getpid (x86_64). 커널 버전 무관하게 고정된 ABI 번호지만, 대상 syscall이 바뀌면 같이 바꿀 것. */
#ifndef TARGET_SYSCALL_NR
#define TARGET_SYSCALL_NR 39
#endif

SEC("raw_tracepoint/" TARGET_RAW_TRACEPOINT)
int on_raw_tracepoint(struct bpf_raw_tracepoint_args *ctx)
{
    long syscall_nr = ctx->args[1];

    if (syscall_nr != TARGET_SYSCALL_NR)
        return 0;

    bump_counter();
    return 0;
}
