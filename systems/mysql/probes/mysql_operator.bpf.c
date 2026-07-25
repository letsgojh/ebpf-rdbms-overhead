#include "../../../common/probes/common.bpf.h"

SEC("uprobe/ha_rnd_next")
int BPF_UPROBE(mysql_operator_entry)
{
    bump_counter();
    return 0;
}
