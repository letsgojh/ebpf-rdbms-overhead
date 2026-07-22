# 실험설계 상세 — Group A, B

`docs/01_experiment_design.md`용 초안. Group A/B를 실행 가능한 수준까지 구체화했다. C~J는 같은 템플릿으로 이어서 채우면 된다. DB 내부 함수명은 버전마다 바뀌므로 전부 **"버전 확인 필요"**로 표시했다 — 실행 전 대상 버전 소스로 재확인.

---

## 0. 공통 사전 조건

### 0.1 결과 스키마 (공통 필드 — `common/schema/result_schema.json`과 동기화)

모든 결과 CSV는 최소한 아래 컬럼을 포함한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `system` | string | duckdb / postgresql / mysql / clickhouse / umbra |
| `group` | string | A / B / C ... |
| `sub_experiment` | string | A-1, A-2, B-scale 등 |
| `probe_type` | string | none / kprobe / kretprobe / fentry / fexit / tracepoint / raw_tracepoint |
| `probe_location` | string | query / operator / chunk / tuple (Group B 전용) |
| `sf` | int | 스케일 팩터 (해당 없으면 null) |
| `run_id` | int | 반복 번호 (0-indexed) |
| `throughput_qps` | float | 원시 처리량 |
| `throughput_degradation_pct` | float | (baseline−측정값)/baseline × 100, 항상 양수 |
| `latency_p50_ms`, `latency_p95_ms`, `latency_p99_ms`, `latency_p999_ms` | float | 절대값 |
| `latency_overhead_p50_pct` ... `_p999_pct` | float | baseline 대비, 항상 양수 |
| `cpu_overhead_pct` | float | task-clock 델타 기반 |
| `run_time_ns`, `run_cnt` | int | bpf_stats (Tier 2, 해당 시) |
| `cycles`, `instructions`, `ipc`, `cache_miss`, `dtlb_miss`, `ctx_switch` | float | perf stat (Tier 2, 해당 시) |
| `kernel_version`, `system_version_hash` | string | 재현성용 |
| `timestamp` | ISO8601 | 실행 시각 |

### 0.2 파일명 규칙

`results/<group>/<system>_<probe_type>_<sf 또는 na>_<probe_location 또는 na>_run<NN>.csv`

예: `results/group_a/duckdb_fentry_na_na_run042.csv`, `results/group_b/duckdb_kprobe_sf10_tuple_run007.csv`

### 0.3 실행 전 체크리스트

README의 "환경 통제 체크리스트" 그대로 (governor/cstate/pinning/bpf_stats_enabled/버전 lock 확인/warm-up/랜덤화). 아래 두 그룹 모두 이 체크리스트 통과 후에만 실행.

---

## Group A. 메커니즘 비용 분해

### A-0. 목적 · 가설 · Definition of Done

**목적.** eBPF probe family별 순수 attach 비용의 이론적 하한선을 구해, 이후 모든 실험(B~J)의 베이스라인 상수로 쓴다.

**가설(H1).** `tracepoint ≈ raw_tracepoint < fentry/fexit < kprobe/kretprobe` (호출당 ns 기준). 귀무가설(H0): probe family 간 평균 비용 차이가 없다.

**Definition of Done.**
- [ ] probe family 4종 × 반복 100회의 (Δns, run_time_ns, cycles/IPC) 표 확보
- [ ] family 간 평균 차이가 bootstrap 95% CI 기준으로 서로 겹치지 않음(통계적으로 유의) 확인, 또는 겹친다면 그 자체를 결과로 기록
- [ ] A-2(앰비언트 민감도) 결과와 비교해 "A-1이 시스템 종류와 무관하다"는 전제가 실제로 성립하는지 검증 완료

### A-1. 격리된 floor 측정

**대상 함수.** DB와 무관한 전용 타겟이 필요하다. 두 가지 옵션:
1. **커스텀 커널 모듈** — no-op에 가까운 함수 하나를 노출하고 이걸 커스텀 syscall(또는 `/proc` 인터페이스)로 유저스페이스에서 반복 호출. 실행 비용이 사실상 0에 수렴해서 가장 깨끗함.
2. **기존 초경량 syscall 재사용** (예: `getpid`) — 구현은 간단하지만 타겟 함수 자체의 비용이 노이즈로 섞임. 커널 모듈 빌드 권한이 없는 서버라면 이 대안으로 진행하되, baseline(probe 미부착) 자체의 분산이 커지지 않는지 반드시 확인.

**측정 하네스 (C, 개념 스켈레톤 — 실제 빌드 환경에 맞게 조정):**

```c
// harness_floor.c — probe 유무에 따른 syscall 1회당 cycle delta 측정
#include <stdint.h>
#include <x86intrin.h>

#define N 10000000UL

static inline uint64_t rdtscp_serialized(void) {
    unsigned aux;
    _mm_lfence();
    uint64_t t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

int main(void) {
    volatile long ret;
    uint64_t start, end;
    for (int warm = 0; warm < 100000; warm++) ret = target_syscall();  // warm-up, 폐기

    uint64_t deltas[N];
    for (uint64_t i = 0; i < N; i++) {
        start = rdtscp_serialized();
        ret = target_syscall();
        end = rdtscp_serialized();
        deltas[i] = end - start;
    }
    // deltas 배열을 파일로 덤프 → common/harness/bootstrap_ci.py 에서 후처리
}
```

**eBPF 프로그램 스켈레톤 (libbpf, `common/probes/`에 위치 — 4종 공통 패턴):**

```c
// kprobe_empty.bpf.c
SEC("kprobe/target_syscall_entry")
int BPF_KPROBE(on_entry) {
    __u64 *cnt = bpf_map_lookup_elem(&counter_map, &(int){0});
    if (cnt) __sync_fetch_and_add(cnt, 1);
    return 0;
}
```
```c
// fentry_empty.bpf.c
SEC("fentry/target_syscall_entry")
int BPF_PROG(on_fentry) {
    __u64 *cnt = bpf_map_lookup_elem(&counter_map, &(int){0});
    if (cnt) __sync_fetch_and_add(cnt, 1);
    return 0;
}
```
tracepoint / raw_tracepoint도 동일 패턴(맵 증가 1줄)으로 작성해 `common/probes/`에 4개 파일로 보관. **네 프로그램의 본문 로직(맵 lookup + 증가)은 완전히 동일하게 유지** — probe family 간 차이가 "본문 차이"가 아니라 "attach 메커니즘 차이"임을 보장하기 위함.

**측정 절차:**
1. `sysctl kernel.bpf_stats_enabled=1`(통계 수집 활성화)
2. probe 미부착 상태로 `harness_floor` 실행 → baseline deltas 덤프
3. probe family 하나씩 부착(`bpftool prog load` + attach) 후 동일 실행 → per-family deltas 덤프
4. 매 family마다 `bpftool prog show`로 `run_time_ns`/`run_cnt` 기록
5. 5.3 4-way 통제: (무계측) / (perf stat만) / (eBPF만) / (perf+eBPF 동시) 각각 반복

**통계 처리:**
- 조건(4 family × 4-way)당 100회 반복 실행(각 실행이 위 N=10⁷ 루프 1세트)
- `common/harness/bootstrap_ci.py`로 BCa bootstrap 10,000 resample → 평균/P50/P99/P999 및 95% CI
- family 간 차이 검정: Mann-Whitney U (분포 비정규 가능성 대비) 또는 bootstrap CI 비겹침으로 판단

**산출:** `results/group_a/duckdb_<probe_type>_na_na_run<NN>.csv` (시스템별 동일 절차 반복, DuckDB/Umbra는 유재환, PostgreSQL/MySQL은 김형규)

### A-2. 앰비언트 부하 민감도

**목적.** A-1의 floor가 "어떤 DB가 백그라운드에 idle로 떠 있는가"에 따라 흔들리는지 확인. 여기서 처음으로 시스템 간 비교가 의미를 가짐.

**절차:** A-1과 동일한 하네스를, 아래 6가지 백그라운드 상태 각각에서 반복.
- 없음 (A-1과 동일, 대조군)
- DuckDB idle / PostgreSQL idle / MySQL idle / ClickHouse idle / Umbra idle

probe family는 A-1에서 family 간 차이가 가장 컸던 1~2종으로 축소(비용 절감).

**산출:** `results/group_a/<system>_<probe_type>_ambient_<bg시스템>_run<NN>.csv`

**해석 기준:** A-2 floor와 A-1 floor의 CI가 겹치면 → "메커니즘 비용은 DB 존재와 무관" 확정. 안 겹치면 → 어떤 백그라운드 상태가 얼마나 영향을 주는지 정량화(캐시 오염 등 Tier 2 카운터로 원인 추적, Group F와 연결).

---

## Group B. 스케일 팩터 × 호출 빈도 증폭 법칙

### B-0. 목적 · 가설 · Definition of Done

**목적.** 동일 probe의 오버헤드가 (a) 부착 위치의 호출 빈도, (b) 데이터 스케일에 따라 선형/초선형인지 규명. RQ0 threshold 산정의 핵심 입력.

**가설(H1).** 정규화된 오버헤드(튜플당 비용)의 log-log 회귀 기울기(elasticity)가 위치가 hot path에 가까워질수록(쿼리당→튜플당) 유의하게 커진다.

**Definition of Done.**
- [ ] 시스템별 "구현 가능한 probe 위치" 매트릭스 확정 (아래 B-2)
- [ ] 파일럿 3쿼리 × 3SF × 구현 가능한 위치 수 × 100회 결과 확보
- [ ] 위치별 log-log 회귀 기울기 표 + breakpoint regression 결과 확보
- [ ] 22개 쿼리 전체 확대 여부 결정(파일럿 소요시간 기반)

### B-1. 독립변수 1 — probe 위치 (4단계, 호출 빈도 오름차순)

| 단계 | 정의 | 비고 |
|---|---|---|
| 쿼리당 1회 | 쿼리 시작/종료 | 모든 시스템에서 구현 가능 |
| 오퍼레이터당 1회 | 물리 연산자 실행 1회 | 모든 시스템 가능하나 연산자 경계 정의가 시스템마다 다름 |
| 청크/블록당 1회 | 벡터화 배치 단위 | DuckDB/ClickHouse만 자연스러움 |
| 튜플당 1회 | 개별 row | Postgres/MySQL만 자연스러움; DuckDB/ClickHouse는 구조적으로 어려울 수 있음 |

### B-2. 시스템별 hook 후보 (버전 확인 필요 — 실행 전 소스 재확인 필수)

| 시스템 | 쿼리당 | 오퍼레이터당 | 청크당 | 튜플당 |
|---|---|---|---|---|
| DuckDB | `Connection::Query` 진입/반환 | `PhysicalOperator::GetData` | `DataChunk` 처리 루프 (STANDARD_VECTOR_SIZE=2048) | 구현 곤란 — 벡터 내부 스칼라 루프, 별도 근사 필요 |
| PostgreSQL | `ExecutorStart`/`ExecutorEnd` | `ExecProcNode` | 구현 곤란 — 튜플단위가 기본 (일부 batch API 검토) | `table_scan_getnextslot` (신버전) / `heap_getnext` (구버전) |
| MySQL | `mysql_execute_command` | handler 계층 (`ha_rnd_next` 등) | 구현 곤란 | `row_search_mvcc` |
| ClickHouse | `executeQuery` | `IProcessor::work` | `Block` 처리 (max_block_size 기본값 확인 필요, granule 8,192행과 별개 개념) | 구조적으로 존재 안 할 수 있음 — "신호 없음"도 결과 |
| Umbra | 접근성 확정 전까지 커널 레벨만 (syscall 진입/종료로 근사) | 동일 제약 | 동일 제약 | 동일 제약 |

이 표에서 "구현 곤란" 칸은 실제로 시도해보고 안 되면 빈 셀로 남기고 그 자체를 결과로 보고한다(비대칭 매트릭스, Group A-2와 동일 논리).

### B-3. 독립변수 2 — 스케일 팩터: SF1 / SF10 / SF100

### B-4. 파일럿 대상 쿼리 (실행량 축소안)

- **Q6** (단순 스캔+필터, 조인 없음) — 스캔 hop 순수 신호
- **Q1** (집계 위주, GROUP BY) — 집계 연산자 추가 시 증폭 변화
- **Q9** (다중 테이블 조인) — 조인 연산자 튜플 산출 hop 신호

파일럿 규모: 3쿼리 × 3SF × (시스템별 구현 가능한 위치 수, 최대 4) × 100회 반복 = 시스템당 최대 3,600회. 이걸로 증폭 곡선 형태를 먼저 확인 후 22개 전체 확대 여부 결정.

### B-5. 종속 변수 및 정규화

Tier 1(처리량 저하율/레이턴시 오버헤드 P50~P999/CPU 오버헤드) + **정규화 지표: 튜플 100만 개 처리당 오버헤드(ms)**. 정규화 단위는 4장(아키텍처 정규화 매핑)과 동일 기준 사용 — "이벤트 1회당"이 아니라 "처리 튜플/바이트당".

### B-6. 통계 분석 절차

1. 조합(위치×SF)당 100회 반복, warm-up 10회 폐기, 실행 순서 랜덤화.
2. `common/harness/bootstrap_ci.py`로 각 조합의 평균 및 P50/P95/P99/P999 CI 산출.
3. **핵심 분석:** `log(정규화 오버헤드) ~ log(SF)` OLS 회귀(Python `statsmodels`)를 probe 위치별로 각각 적합. 기울기(elasticity) ≈1이면 선형, 유의하게 >1이면 초선형.
4. 위치별 기울기를 하나의 그래프(x축: 위치 4단계, y축: 회귀 기울기 + 95% CI)로 요약.
5. **RQ0 연계:** 이 기울기 데이터와 Group C의 동시성 데이터를 합쳐 Python `ruptures`(PELT 알고리즘)로 breakpoint 위치와 신뢰구간 산출 → RQ0의 "경계선" 주장의 통계적 근거로 사용.

### B-7. 산출

`results/group_b/<system>_<probe_type>_sf<N>_<위치>_run<NN>.csv`

### B-8. 리스크 및 대응

- 시스템별 "구현 곤란" 위치가 예상보다 많으면 → 비대칭 매트릭스로 투명하게 보고, 회귀분석은 구현 가능한 위치만으로 진행.
- SF100 × 22쿼리 × 100회가 파일럿 기준 너무 오래 걸리면 → 반복 횟수를 100회에서 낮추되(예: 30회) bootstrap CI 폭이 커지는 걸 감수, 혹은 SF100을 대표 쿼리에만 한정.

---

## 다음 단계

- Group C~J도 위와 동일한 템플릿(0. 목적/가설/DoD, 1. 독립변수, 2. hook 후보표, 3. 통계처리, 4. 산출/리스크)으로 이어서 작성.
- `common/schema/result_schema.json`을 위 0.1 표 그대로 실제 JSON으로 만들어 repo에 커밋하는 게 다음 실행 단계.