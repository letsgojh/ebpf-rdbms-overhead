#include "../../../common/probes/common.bpf.h"

SEC("uprobe/row_search_mvcc")
int BPF_UPROBE(mysql_tuple_entry)
{
    bump_counter();
    return 0;
}
