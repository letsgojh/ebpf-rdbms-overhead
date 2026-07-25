#include "../../../common/probes/common.bpf.h"

SEC("uprobe/ExecProcNode")
int BPF_UPROBE(pg_operator_entry)
{
    bump_counter();
    return 0;
}
