#include "../../../common/probes/common.bpf.h"

SEC("uprobe/heap_getnextslot")
int BPF_UPROBE(pg_tuple_entry)
{
    bump_counter();
    return 0;
}
