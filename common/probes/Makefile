CLANG ?= clang
BPFTOOL ?= bpftool
BPF_INCLUDE ?= /usr/src/linux-headers-$(shell uname -r)/tools/bpf/resolve_btfids/libbpf/include/

SRCS := kprobe_empty.bpf.c fentry_empty.bpf.c tracepoint_empty.bpf.c raw_tracepoint_empty.bpf.c
OBJS := $(SRCS:.bpf.c=.bpf.o)

all: $(OBJS)

# 커널 BTF를 유저스페이스 C 헤더로 떠와서 vmlinux.h로 저장 (커널/서버마다 새로 생성해야 함)
vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

%.bpf.o: %.bpf.c common.bpf.h vmlinux.h
	$(CLANG) -O2 -g -target bpf -I$(BPF_INCLUDE) -I. -c $< -o $@

clean:
	rm -f $(OBJS) vmlinux.h

.PHONY: all clean
