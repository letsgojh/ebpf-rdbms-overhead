# systems/Makefile
# systems/README.md의 압축 파일명 규칙
#   ebpf-rdbms-overhead_<system>_<group>_<YYYYMMDD>_<host>.tar.gz
# 을 자동화하는 진입점. 반드시 systems/ 디렉토리에서 실행할 것.
#
#   make archive SYSTEM=duckdb GROUP=group_a
#   make archive SYSTEM=postgresql GROUP=group_b
#   make archive SYSTEM=duckdb GROUP=group_a INCLUDE_RAW=1   # raw/ 원시값(수십 GB)까지 포함하고 싶을 때
#
# 기본은 raw/(반복당 N=10^7줄짜리 원시 delta 텍스트, 수십 GB)를 뺀다 — CSV에 이미 run별
# mean/p50/p99/p999가 다 계산돼 들어있고, raw는 필요하면 harness를 다시 돌려 재생성 가능하다.

SYSTEM ?=
GROUP ?=
INCLUDE_RAW ?= 0
HOST := $(shell hostname)
DATE := $(shell date +%Y%m%d)
# group_a -> groupA, group_b -> groupB, ...
GROUP_LABEL := group$(shell echo $(GROUP) | sed 's/^group_//' | tr '[:lower:]' '[:upper:]')

.PHONY: archive check-system check-group

check-system:
	@if [ -z "$(SYSTEM)" ]; then \
		echo "SYSTEM을 지정하세요 (duckdb/postgresql/mysql/clickhouse/umbra). 예: make archive SYSTEM=duckdb GROUP=group_a" >&2; \
		exit 1; \
	fi

check-group:
	@if [ -z "$(GROUP)" ]; then \
		echo "GROUP을 지정하세요 (group_a, group_b, ...). 예: make archive SYSTEM=duckdb GROUP=group_a" >&2; \
		exit 1; \
	fi

archive: check-system check-group
	@resultdir="$(SYSTEM)/results"; \
	if [ ! -d "$$resultdir/$(GROUP)" ]; then \
		echo "결과 디렉토리 없음: $$resultdir/$(GROUP)" >&2; \
		exit 1; \
	fi; \
	name="ebpf-rdbms-overhead_$(SYSTEM)_$(GROUP_LABEL)_$(DATE)_$(HOST).tar.gz"; \
	if [ "$(INCLUDE_RAW)" = "1" ]; then \
		tar -czf "$$resultdir/$$name" -C "$$resultdir" "$(GROUP)"; \
	else \
		tar --exclude="$(GROUP)/raw" -czf "$$resultdir/$$name" -C "$$resultdir" "$(GROUP)"; \
	fi; \
	echo "생성됨: $$resultdir/$$name ($$(du -h "$$resultdir/$$name" | cut -f1))"
