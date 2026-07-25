#include "../../../common/probes/common.bpf.h"

SEC("uprobe/mysql_execute_command")
int BPF_UPROBE(mysql_query_entry)
{
    bump_counter();
    return 0;
}
