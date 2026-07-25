# systems/duckdb/notes.md

DuckDB 실험 진행 로그. 그룹(A, B, ...)별로 섹션을 나누고, 그 안에 phase 체크리스트로 진행상황을
기록한다. 새 그룹 시작할 때 이 파일에 같은 형식으로 섹션만 추가해서 계속 쓴다.

---

## Group A-1 — 격리된 floor 측정

**상태: 완료** (실제 규모 실행 2026-07-22, gaia1)

### Phase 로그
- [x] Phase 1: 공통 하네스 구현 — `common/harness/group_a/`(`harness_floor.c`, `group_a1_runner.py`,
      `run_group_a1.sh`, `report_xlsx.py`, `Makefile`). getpid를 target_syscall로 확정.
- [x] Phase 2: 소규모 스모크 테스트(`make smoke-test SYSTEM=duckdb`, REPS=3)로 5종(none/kprobe/
      fentry/tracepoint/raw_tracepoint) 파이프라인 검증
- [x] Phase 3: 실제 규모 실행 — `make run-all SYSTEM=duckdb`(REPS=100, N=10^7) → 5종 × 100 CSV +
      raw 덤프(`systems/duckdb/results/group_a/`)
- [x] Phase 4: 스키마 검증(`make validate`) 통과, 결과 백업(`systems` → `make archive SYSTEM=duckdb
      GROUP=group_a`, raw 제외 압축) → 구글드라이브 업로드

### 핵심 결과 (baseline `none` p99 = 247.84ns, `make rank-probes` 계산 기준)
| probe_type | p99 overhead |
|---|---|
| kprobe | +67.3% |
| tracepoint | +65.2% |
| raw_tracepoint | +33.4% |
| fentry | +29.7% |

H1 가설("tracepoint≈raw_tracepoint < fentry < kprobe")과 다르게 tracepoint가 raw_tracepoint/fentry보다
훨씬 높게 나옴 — A-2/추가 분석에서 원인 짚어볼 것 (아직 조사 안 함).

### 남은 것
- [ ] tracepoint 대상(`syscalls/sys_enter_getpid`) 실존 여부 명시적 확인 (지금까지 정상 동작으로
      간접 확인만 됨 — `sudo ls /sys/kernel/tracing/events/syscalls/sys_enter_getpid`)
- [ ] A-1 측정 절차의 "4-way 통제"(무계측/perf stat만/eBPF만/perf+eBPF 동시) 축 — 범위 밖으로 미룸

---

## Group A-2 — 앰비언트 부하 민감도

**상태: 진행 중** — 0단계 완료, 1단계(배경상태별 재실행) 착수 전

### Phase 로그
- [x] Phase 0: 도구 구현 — `common/harness/group_a/ambient_compare.py` + `Makefile`의
      `rank-probes`/`run-ambient`/`ambient-compare` 타겟
- [x] Phase 1: probe 축소 — `make rank-probes SYSTEM=duckdb` 실행 완료. A-1 실데이터 기준(none 대비
      p99 overhead_pct) 상위 2종 확정: **kprobe, tracepoint**
      (결과: `systems/duckdb/results/group_a/ebpf-rdbms-overhead_duckdb_groupA_ambientrank_20260723_gaia1.xlsx`)
- [ ] Phase 2: 배경상태별 재실행 — **이 서버(gaia1)는 DuckDB 전용이라 실제로 만들 수 있는 배경은
      DuckDB idle뿐이다.** 디렉토리/서버를 시스템별로 나눠서 관리하는 것과 같은 이유로,
      PostgreSQL/MySQL/ClickHouse/Umbra를 이 서버에 따로 설치하지 않는다(아래 "범위" 참고).
      ```bash
      make run-ambient SYSTEM=duckdb AMBIENT=duckdb PROBES="kprobe tracepoint"
      ```
  - [ ] DuckDB idle
- [ ] Phase 3: 비교 — `make ambient-compare SYSTEM=duckdb TOP_N=2
      AMBIENTS="duckdb=../../../systems/duckdb/results/group_a_ambient_duckdb"` 실행 →
      `ambient_compare.csv`
- [ ] Phase 4: 해석 — 각 행 `ci_overlap`으로 "메커니즘 비용이 DB 존재와 무관인지" 판정, `False`면
      `diff_ns`/`diff_pct`로 어떤 배경이 얼마나 영향 주는지 정리

### 범위 (이 트랙에서 안 하는 것)
A-2 문서(01_experiment_design.md)는 배경 6종(없음 + DB 5개 idle)을 다 재보라고 하지만, 이 저장소는
시스템별로 서버·디렉토리를 분리해서 관리한다(README "디렉토리 소유 원칙") — gaia1엔 DuckDB만 있고
PostgreSQL/MySQL/ClickHouse/Umbra는 없다. 그래서 이 트랙(duckdb, gaia1)에서는 **DuckDB idle 배경
하나만** 재본다. 나머지 배경(PostgreSQL/MySQL/ClickHouse/Umbra idle)을 어떻게 처리할지(각자 담당
서버에서 자기 시스템 기준으로 따로 돌릴지, 아예 스코프에서 뺄지)는 팀 차원의 별도 결정 사항이지
이 노트/이 서버가 막고 있는 게 아니다.

### 막힌 것 / 확인 필요
- [ ] `systems/duckdb/setup/`가 비어있어서 "DuckDB idle" 자체를 아직 실제로 못 띄움 — Phase 2
      시작 전에 DuckDB를 이 서버에 빌드/기동하는 절차부터 필요(최상위 README "시작하기" 참고,
      `setup/install.sh` 아직 미작성)
