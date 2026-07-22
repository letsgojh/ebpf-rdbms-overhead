#ifndef EBPF_RDBMS_OVERHEAD_COMMON_BPF_H
#define EBPF_RDBMS_OVERHEAD_COMMON_BPF_H

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

/*
 * Group A-1(격리된 floor 측정)용 4종 probe(kprobe/fentry/tracepoint/raw_tracepoint) 공통 맵.
 * A-1의 목적은 "attach 메커니즘 차이"만 순수하게 재는 것이므로(01_experiment_design.md A-1,
 * "네 프로그램의 본문 로직은 완전히 동일하게 유지"), 이 맵과 bump_counter()는
 * kprobe_empty.bpf.c / fentry_empty.bpf.c / tracepoint_empty.bpf.c / raw_tracepoint_empty.bpf.c
 * 네 파일 전부에서 절대 다르게 손대면 안 된다.
 */
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} counter_map SEC(".maps");

static __always_inline void bump_counter(void)
{
    __u32 key = 0;
    __u64 *cnt = bpf_map_lookup_elem(&counter_map, &key);

    if (cnt)
        __sync_fetch_and_add(cnt, 1);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";

#endif /* EBPF_RDBMS_OVERHEAD_COMMON_BPF_H */
