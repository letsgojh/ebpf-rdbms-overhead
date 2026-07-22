# common/harness/group_a/Makefile
# Group A-1: 빌드 + 실행 + 검증을 make 타겟 하나로 묶은 자동화 진입점.
# 개별 스크립트를 손으로 조합하는 대신 아래 타겟만 쓰면 된다. 배경은 이 디렉토리 README.md,
# 원 절차는 docs/01_experiment_design.md A-1 참고.
#
#   make build                                   probe .bpf.o 4개 + harness_floor 빌드
#   make smoke-test SYSTEM=duckdb                 소규모(N=100000,reps=3)로 5종 다 실행+검증 (원클릭)
#   make run SYSTEM=duckdb PROBE=kprobe           probe 1종, 실제 규모(REPS/N 조절 가능) 실행
#   make run-all SYSTEM=duckdb                    5종(none 포함) 전부, 실제 규모 실행
#   make validate OUTDIR=...                      결과 CSV 전부 스키마 검증
#   make summarize PROBE=kprobe OUTDIR=...         bootstrap CI 요약 출력 (probe 1종)
#   make compare A_PROBE=none B_PROBE=kprobe OUTDIR=...   두 조건 Mann-Whitney U 비교
#   make report SYSTEM=duckdb                     5종 전체 요약 + baseline 대비 비교를 .xlsx 하나로
#                                                  (OUTDIR은 SYSTEM에서 자동 계산, 커스텀 경로 쓸 때만 직접 지정)
#   make clean                                    빌드 산출물만 삭제 (결과 CSV는 안 건드림)
#
# run/run-all은 내부에서 run_group_a1.sh를 호출한다. 스크립트 전체가 root로 도는 게 아니라
# bpftool/rm 호출 몇 개만 개별적으로 sudo를 쓰므로(README 참고), 결과 CSV/raw 파일은 계속
# make를 실행한 사용자 소유로 남는다 — 첫 sudo 호출 때 터미널에서 비밀번호 프롬프트가 뜬다
# (비대화형 실행 불가).

PROBES_DIR := ../../probes
BOOTSTRAP_CI := ../bootstrap_ci.py
HARNESS := harness_floor
PROBE_TYPES := none kprobe fentry tracepoint raw_tracepoint

SYSTEM ?=
PROBE ?=
REPS ?= 100
N ?= 10000000
OUTDIR ?= ../../../systems/$(SYSTEM)/results/group_a

A_PROBE ?= none
B_PROBE ?= kprobe
METRIC ?= p99

TEST_REPS := 3
TEST_N := 100000
TEST_OUTDIR := ../../../scratch/a1_smoke_test

.PHONY: all build check-system check-probe run run-all validate summarize compare smoke-test clean

all: build

build:
	$(MAKE) -C $(PROBES_DIR)
	gcc -O2 -Wall -Wextra -o $(HARNESS) harness_floor.c

check-system:
	@if [ -z "$(SYSTEM)" ]; then \
		echo "SYSTEM을 지정하세요 (duckdb/postgresql/mysql/clickhouse/umbra). 예: make run SYSTEM=duckdb PROBE=kprobe" >&2; \
		exit 1; \
	fi

check-probe:
	@if [ -z "$(PROBE)" ]; then \
		echo "PROBE를 지정하세요 (none/kprobe/fentry/tracepoint/raw_tracepoint). 예: make run SYSTEM=duckdb PROBE=kprobe" >&2; \
		exit 1; \
	fi

# probe 1종 실행 (root 필요 — run_group_a1.sh가 자동으로 sudo 재실행)
run: build check-system check-probe
	bash run_group_a1.sh --system $(SYSTEM) --probe-type $(PROBE) --reps $(REPS) --n $(N) --outdir $(OUTDIR)

# 5종(none/kprobe/fentry/tracepoint/raw_tracepoint) 전부 순서대로 실행
run-all: build check-system
	@for p in $(PROBE_TYPES); do \
		echo "=== $(SYSTEM) / $$p (reps=$(REPS) n=$(N)) ==="; \
		bash run_group_a1.sh --system $(SYSTEM) --probe-type $$p --reps $(REPS) --n $(N) --outdir $(OUTDIR) || exit 1; \
	done

validate:
	python3 ../../schema/validate_schema.py $(OUTDIR)/*.csv

summarize: check-probe
	python3 $(BOOTSTRAP_CI) summarize "$(OUTDIR)/raw/$(PROBE)/*.txt"

compare:
	python3 $(BOOTSTRAP_CI) compare \
		--a "$(OUTDIR)/raw/$(A_PROBE)/*.txt" --b "$(OUTDIR)/raw/$(B_PROBE)/*.txt" --metric $(METRIC)

# 5종(none/kprobe/fentry/tracepoint/raw_tracepoint) 전체를 summary/vs_none 두 시트로 묶은 .xlsx 생성
# (파일명은 systems/README.md 압축 파일명 규칙과 맞춘 ebpf-rdbms-overhead_<system>_groupA_<날짜>_<host>.xlsx)
report: check-system
	python3 report_xlsx.py --outdir $(OUTDIR) --system $(SYSTEM)

# 소규모로 5종 전부 실행 + 스키마 검증 + 전체 요약 리포트(.xlsx)까지 한 번에 끝내는 원클릭 타겟.
# 처음 이 harness를 직접 돌려서 검증해볼 때 이것부터 실행할 것.
smoke-test: check-system
	$(MAKE) run-all SYSTEM=$(SYSTEM) REPS=$(TEST_REPS) N=$(TEST_N) OUTDIR=$(TEST_OUTDIR)
	$(MAKE) validate OUTDIR=$(TEST_OUTDIR)
	$(MAKE) report SYSTEM=$(SYSTEM) OUTDIR=$(TEST_OUTDIR)
	@echo "스모크 테스트 통과 — 결과: $(TEST_OUTDIR)"

clean:
	$(MAKE) -C $(PROBES_DIR) clean
	rm -f $(HARNESS)
	rm -rf __pycache__
