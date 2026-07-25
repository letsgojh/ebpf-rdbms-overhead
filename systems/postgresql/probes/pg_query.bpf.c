#include "../../../common/probes/common.bpf.h"

SEC("uprobe/ExecutorStart")
int BPF_UPROBE(pg_query_entry)
{
    bump_counter();
    return 0;
}
