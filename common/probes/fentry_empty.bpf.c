#include "common.bpf.h"

/*
 * TARGET_FUNC: fentry는 BTF FUNC 목록에 있는 이름에만 붙는다. 커널 6.8.0-31-generic BTF를
 * 실제로 덤프해보면(bpftool btf dump file /sys/kernel/btf/vmlinux) getpid의 SYSCALL_DEFINE
 * 래퍼 __x64_sys_getpid는 없고 실구현체인 __do_sys_getpid(static)만 노출된다 — 그래서
 * kprobe_empty.bpf.c의 TARGET_FUNC(__x64_sys_getpid)와 이름이 다르다. 커널 버전이 바뀌면
 * BTF 노출 여부도 달라질 수 있으니 재확인 필요.
 */
#ifndef TARGET_FUNC
#define TARGET_FUNC "__do_sys_getpid"
#endif

SEC("fentry/" TARGET_FUNC)
int BPF_PROG(on_fentry)
{
    bump_counter();
    return 0;
}
