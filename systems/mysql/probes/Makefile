CLANG ?= clang
BPFTOOL ?= bpftool
COMMON_DIR := ../../../common/probes

SRCS := mysql_query.bpf.c mysql_operator.bpf.c mysql_tuple.bpf.c
OBJS := $(SRCS:.bpf.c=.bpf.o)

all: $(OBJS)

vmlinux.h:
	@if [ ! -f $(COMMON_DIR)/vmlinux.h ]; then \
		$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $(COMMON_DIR)/vmlinux.h; \
	fi

%.bpf.o: %.bpf.c vmlinux.h
	$(CLANG) -O2 -g -target bpf -I$(COMMON_DIR) -I. -c $< -o $@

clean:
	rm -f $(OBJS)

.PHONY: all clean vmlinux.h
