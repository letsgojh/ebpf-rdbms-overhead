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
#   --- A-2(앰비언트 부하 민감도, docs/01_experiment_design.md A-2절) ---
#   make rank-probes SYSTEM=duckdb                0단계: A-1 floor에서 none 대비 p99 overhead_pct 순위만 확인
#                                                  (배경상태별로 재실행할 probe 1~2종을 이 결과 보고 정함)
#   make run-ambient SYSTEM=duckdb AMBIENT=duckdb PROBES="kprobe fentry"
#                                                  1단계: 배경상태(AMBIENT) 라벨 하나에 대해 PROBES를 재실행
#                                                  *** 배경 DB를 이 서버에 idle로 띄우는 건 시스템마다 방법이
#                                                      다르므로 이 타겟이 대신 해주지 않음 — 직접 띄워둔 뒤 실행 ***
#   make ambient-compare SYSTEM=duckdb TOP_N=2 \
#        AMBIENTS="duckdb=../../../systems/duckdb/results/group_a_ambient_duckdb"
#                                                  2단계: A-1 floor 대 배경상태별 결과를 probe×배경×metric별 CSV로 비교
#                                                  (probe는 TOP_N=<N>으로 A-1 none 대비 p99 overhead_pct 상위 N개 자동 선택,
#                                                   또는 PROBES="kprobe fentry"로 직접 지정 — 둘 중 하나만)
#   make clean                                    빌드 산출물만 삭제 (결과 CSV는 안 건드림)
#
# run/run-all/run-ambient은 내부에서 run_group_a1.sh를 호출한다. 스크립트 전체가 root로 도는 게
# 아니라 bpftool/rm 호출 몇 개만 개별적으로 sudo를 쓰므로(README 참고), 결과 CSV/raw 파일은 계속
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

FLOOR_OUTDIR ?= ../../../systems/$(SYSTEM)/results/group_a
PROBES ?=
TOP_N ?=
AMBIENTS ?=
AMBIENT_OUTPUT ?= $(FLOOR_OUTDIR)/ambient_compare.csv

AMBIENT ?=
AMBIENT_DIR ?= ../../../systems/$(SYSTEM)/results/group_a_ambient_$(AMBIENT)

TEST_REPS := 3
TEST_N := 100000
TEST_OUTDIR := ../../../scratch/a1_smoke_test

.PHONY: all build check-system check-probe check-probes check-ambients check-ambient check-ambient-probes run run-all validate summarize compare rank-probes run-ambient ambient-compare smoke-test clean

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

check-probes:
	@if [ -z "$(PROBES)" ] && [ -z "$(TOP_N)" ]; then \
		echo 'PROBES 또는 TOP_N 중 하나를 지정하세요 (동시 사용 불가). 예: PROBES="kprobe fentry" 또는 TOP_N=2(A-1 none 대비 p99 overhead_pct 상위 N개 자동 선택)' >&2; \
		exit 1; \
	fi
	@if [ -n "$(PROBES)" ] && [ -n "$(TOP_N)" ]; then \
		echo 'PROBES와 TOP_N을 동시에 지정할 수 없습니다.' >&2; \
		exit 1; \
	fi

check-ambients:
	@if [ -z "$(AMBIENTS)" ]; then \
		echo 'AMBIENTS를 지정하세요 (공백구분 이름=결과디렉토리). 예: AMBIENTS="duckdb=../../../systems/duckdb/results/group_a_ambient_duckdb"' >&2; \
		exit 1; \
	fi

check-ambient:
	@if [ -z "$(AMBIENT)" ]; then \
		echo 'AMBIENT를 지정하세요 (배경상태 라벨, 예: duckdb) — 결과가 systems/<SYSTEM>/results/group_a_ambient_<AMBIENT>에 쌓입니다.' >&2; \
		exit 1; \
	fi

check-ambient-probes:
	@if [ -z "$(PROBES)" ]; then \
		echo 'PROBES를 지정하세요 (공백구분, make rank-probes SYSTEM=... 결과의 상위 1~2종). 예: PROBES="kprobe fentry"' >&2; \
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

# A-2 0단계: A-1 floor에서 none 대비 p99 overhead_pct 순위만 확인 — 배경상태별로 재실행할
# probe 1~2종을 고르는 근거(ambient_compare.py --rank-only 그대로).
rank-probes: check-system
	python3 ambient_compare.py --floor-outdir $(FLOOR_OUTDIR) --rank-only

# A-2 1단계: 배경상태(AMBIENT) 라벨 하나에 대해 PROBES(공백구분, 보통 rank-probes 상위 1~2종)를
# 재실행해 systems/<SYSTEM>/results/group_a_ambient_<AMBIENT>에 raw를 쌓는다.
# *** 배경 DB를 이 서버에 idle로 띄우는 절차는 시스템마다 다르므로(systems/<SYSTEM>/setup 참고,
# 담당자별로 디렉토리도 다름) 이 타겟이 대신 해주지 않는다 — 배경 DB가 idle로 떠 있는지 직접
# 확인한 뒤 실행할 것. AMBIENT=none으로 배경 없이 재현성만 확인하는 것도 가능. ***
run-ambient: build check-system check-ambient check-ambient-probes
	@echo "=== $(SYSTEM) 배경=$(AMBIENT) — 이 서버에 배경 DB($(AMBIENT))가 idle로 떠 있는지 직접 확인했는지? ==="
	@for p in $(PROBES); do \
		echo "--- $(SYSTEM) / $$p (배경=$(AMBIENT), reps=$(REPS) n=$(N)) ---"; \
		bash run_group_a1.sh --system $(SYSTEM) --probe-type $$p --reps $(REPS) --n $(N) --outdir $(AMBIENT_DIR) || exit 1; \
	done
	@echo "완료 — 결과: $(AMBIENT_DIR)"

# A-2 2단계: A-1 floor(FLOOR_OUTDIR, 기본은 SYSTEM의 A-1 OUTDIR) 대 배경상태별 결과(AMBIENTS)를
# PROBES(공백구분, A-1에서 차이 가장 컸던 1~2종)마다 비교해 probe×배경×metric별 한 행짜리 CSV로 낸다.
# 배경상태별 raw는 A-1과 절대 같은 outdir을 쓰면 안 된다(run000.txt가 덮어써짐) — 배경상태별로
# --outdir을 따로 지정해서 run_group_a1.sh로 미리 실행해둔 결과 디렉토리를 AMBIENTS에 넘긴다.
ambient-compare: check-system check-probes check-ambients
	python3 ambient_compare.py --floor-outdir $(FLOOR_OUTDIR) \
		$(if $(TOP_N),--top-n $(TOP_N),$(foreach p,$(PROBES),--probe $(p))) \
		$(foreach a,$(AMBIENTS),--ambient $(a)) \
		--output $(AMBIENT_OUTPUT)

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
