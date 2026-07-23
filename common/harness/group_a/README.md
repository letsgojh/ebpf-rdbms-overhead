# common/harness/group_a/

Group A-1(격리된 floor 측정, `docs/01_experiment_design.md` A-1절)만을 위한 하네스/오케스트레이션.
`common/harness/`의 다른 그룹(Group B 이후)은 여기 코드를 재사용하지 않는다 — Group B는 TPC-H
쿼리 실행·SF·probe_location을 축으로 하는 완전히 다른 측정이라 자기 하위 디렉토리(`group_b/` 등)에
따로 만든다. 이 디렉토리와 `common/harness/bootstrap_ci.py`(공통, 안 옮김)의 관계는
`common/harness/README.md` 참고.

## 빠른 시작 (Makefile)

빌드/실행/검증을 개별 명령으로 손으로 조합할 필요 없이 `Makefile` 타겟으로 묶어뒀다. **처음
직접 돌려서 검증해볼 때는 아래 한 줄이면 된다** (터미널에서 직접 실행해야 sudo 비밀번호 프롬프트가
뜬다):

```bash
cd common/harness/group_a
make smoke-test SYSTEM=duckdb
```

내부적으로 하는 일: probe 4종 + harness 빌드 → 소규모(N=100000, reps=3)로 none/kprobe/fentry/
tracepoint/raw_tracepoint 5종 전부 실행 → 스키마 검증 → `.xlsx` 리포트 생성. 마지막에
"스모크 테스트 통과"가 뜨면 이 harness가 이 서버에서 정상 동작한다는 뜻이다. `scratch/a1_smoke_test/
ebpf-rdbms-overhead_duckdb_groupA_<날짜>_<host>.xlsx`를 열어보면 5종 전체 요약을 한 번에 볼 수 있다.

문제없이 통과했으면 실제 규모로:
```bash
make run-all SYSTEM=duckdb                              # 5종 전부, REPS=100 N=10^7 (기본값)
make run SYSTEM=duckdb PROBE=kprobe REPS=100 N=10000000  # probe 1종만
make report SYSTEM=duckdb                                # 5종 요약 .xlsx (뒤에서 설명, OUTDIR은 SYSTEM에서 자동 계산)
```

`SYSTEM`은 duckdb/postgresql/mysql/clickhouse/umbra 중 **자기 담당 시스템**으로 지정한다(최상위
README "담당자 및 서버" 절 참고 — DB를 실제로 쓰지 않는 측정인데도 SYSTEM을 요구하는 이유는 아래
"결과 저장 위치" 참고). 안 넣으면 에러 메시지와 함께 즉시 종료한다.

그 외 개별 타겟(`build`/`validate`/`summarize`/`compare`/`clean`)은 `Makefile` 상단 주석에
사용법이 정리돼 있다.

## 결과 저장 위치

기본 `OUTDIR`은 `systems/<SYSTEM>/results/group_a`(최상위 README 디렉토리 구조와 동일,
`.gitignore`의 `systems/*/results/`에 걸려 로컬에만 남고 git에는 안 올라간다):

```
systems/<SYSTEM>/results/group_a/
├── <system>_<probe_type>_na_na_run<NN>.csv   ← run 1개 = 행 1개 = 파일 1개 (0.2 파일명 규칙)
└── raw/
    ├── none/run000.txt, run001.txt, ...       ← harness_floor가 TSC->ns 환산해서 덤프한 원시값
    ├── kprobe/run000.txt, ...
    └── ...
```

**왜 DB를 안 쓰는 측정에 `SYSTEM`이 필요한가.** A-1은 순수 커널 레벨 측정이라 어떤 DB도 실행하지
않지만, 문서(130행)는 "시스템별 동일 절차 반복"을 요구한다 — 서버마다 CPU/커널이 달라 floor 값
자체가 달라질 수 있어서, 어느 서버(=담당자)에서 잰 값인지 계속 구분해야 하기 때문이다. 즉 여기서
`SYSTEM`은 "DB 의존성"이 아니라 "이 측정이 딸린 서버/담당 트랙"을 나타내는 태그다.

`results_aggregated/`로 옮기는(스키마 검증 통과분만 모으는) 자동화는 아직 없다 — 필요해지면 추가.

## 파일별 역할

### `harness_floor.c`
A-1 "측정 하네스"(65~93행)를 실제로 실행되는 C 코드로 옮긴 것. `target_syscall`은 Phase 1에서
**getpid 재사용**으로 확정했다(커널 모듈 옵션 대신 — 커널 모듈 빌드 인프라는 이 서버에 있지만,
빠른 구현을 우선해 getpid를 선택). 반드시 `syscall(SYS_getpid)`로 직접 호출한다 — glibc의
`getpid()`는 fork 이후 pid를 캐시해 실제 syscall을 내지 않으므로 측정 대상이 사라진다.

**TSC → ns 환산.** rdtscp는 CPU cycle을 세지 시간을 세지 않는다. `result_schema.json`의
`latency_*_ms` 필드에 넣으려면 ns 단위가 필요해서, 실행 시작 시 `CLOCK_MONOTONIC` 대비 TSC 틱
수를 100ms 동안 재는 자체 캘리브레이션으로 cycle→ns 환산 비율을 구하고, 덤프하는 raw 값 자체를
이미 ns로 환산해서 쓴다(그래서 `bootstrap_ci.py`가 다루는 raw 파일의 단위는 ns). 이 환산은 CPU가
invariant TSC(`constant_tsc`/`nonstop_tsc`, `/proc/cpuinfo` flags)를 지원해야 유효하다 — 개발
서버(Xeon Gold 6230 @ 2.10GHz)는 확인 완료(2026-07-22, 캘리브레이션 결과 0.4773ns/cycle ≈
2.096GHz로 base clock과 일치). 다른 서버에서 돌릴 땐 `grep -o 'constant_tsc\|nonstop_tsc'
/proc/cpuinfo`로 먼저 확인할 것.

소규모(N=20000)로 직접 실행해본 결과: p50 ≈ 82ns, mean ≈ 90ns — 최신 x86_64에서 getpid 왕복
지연으로 흔히 보고되는 수십~백여 ns 대와 일치한다.

### `group_a1_runner.py` + `run_group_a1.sh`
probe 하나(또는 baseline `none`)를 attach하고 `harness_floor`를 `--reps`회 반복 실행해
run별 CSV를 만드는 오케스트레이션. A-1 "측정 절차"(118~124행) 그대로: probe 부착 → harness
반복 실행 → `bpftool prog show`로 `run_time_ns`/`run_cnt` 기록.

**`common/env/pinned_cores.conf`가 있으면 `harness_floor`를 `taskset -c <코어목록>`으로 감싸서
실행한다.** `common/env/pin_cores.sh`가 IRQ만 그 코어들에서 치워둘 뿐 어떤 프로세스도 실제로
pinning하지 않아서(그 시점엔 아직 harness가 없었으므로), 처음엔 이 스크립트가 그걸 빼먹고 있었다
— 환경 통제(governor/turbo/cstate/IRQ affinity/SMT 차단)를 다 해놔도 정작 측정 프로세스가
아무 코어에나 스케줄될 수 있어 의미가 없었던 것. 이제 `pinned_cores.conf`가 있으면 자동으로
`taskset`을 붙이고, 없으면 경고를 찍고 코어 고정 없이 진행한다(`common/env`에서 `make setup`을
먼저 실행하라는 안내와 함께).

`/sys/fs/bpf`가 `root:root` 700(sticky)이라 pin 생성/삭제·조회(`bpftool prog load`,
`bpftool link/prog show`, 그 pin 경로의 `rm`)만 root가 필요하다 — **스크립트 전체를 sudo로 감싸지
않는다.** `attach_probe()`/`detach_probe()`/`bpf_stats()` 안에서 그 호출들에만 개별적으로 `sudo`를
붙였고, harness 실행과 CSV/raw 파일 쓰기는 이 스크립트를 부른 사용자 권한 그대로 돈다 — 그래서
결과 파일이 항상 그 사용자 소유로 남고, 이후 `make report`/`make validate`를 sudo 없이 그대로
돌려도 된다. (처음엔 스크립트 전체를 `run_group_a1.sh`가 자기 자신째 `sudo`로 재실행하는 방식으로
짰었는데, 그러면 CSV/raw까지 root 소유가 돼서 다음 단계가 못 쓰는 문제가 있어 이렇게 바꿨다.)

`run_group_a1.sh`는 `sysctl kernel.bpf_stats_enabled=1`(전체 측정에 공통으로 필요, A-1 절차
1번)만 `sudo`로 한 번 켜고 나머지는 그대로 넘기는 얇은 wrapper다. 첫 `sudo` 호출 시 터미널에서
비밀번호를 물어본다(그 뒤로는 sudo 자격 캐시가 살아있는 동안 재입력 없이 넘어간다).

보통은 위 "빠른 시작"의 `make run`/`make run-all`로 실행하면 되고, 아래는 그 타겟들이 내부적으로
호출하는 실제 명령이다(직접 손볼 일이 있으면 참고):

```bash
bash run_group_a1.sh \
    --system duckdb --probe-type kprobe --reps 100 --n 10000000 --outdir <outdir>
```

**`bpf_stats()`가 실제로 겪은 문제들 (실기 테스트로 발견/수정).** `autoattach`로 로드하면
pin 경로에는 **prog가 아니라 link**가 pin된다(`bpftool-prog(8)`: "only the link ... is pinned,
not the program as such"). 그래서:
1. `bpftool prog show pinned <path>`를 바로 걸면 실패한다 — `link show pinned <path>`로 먼저
   `prog_id`를 얻고, 그 id로 `prog show id <id>`를 다시 조회해야 한다.
2. 그런데 `link show pinned <path>`가 **유효한 JSON을 stdout에 이미 다 찍어놓고도** exit code
   255를 내는 경우가 실제로 있었다(원인 불명 — pid 보유자 목록 등 부가 정보 조회가 실패해도 주
   결과는 이미 flush된 뒤라서로 추정). 그래서 exit code가 아니라 "stdout이 유효한 JSON이고
   필요한 키가 있는가"를 성공 기준으로 판단하도록(`_bpftool_json()`) 바꿨다.

이 두 가지를 다 반영한 뒤 실제 서버(gaia1)에서 `make smoke-test`로 5종(none/kprobe/fentry/
tracepoint/raw_tracepoint) 전부 정상 실행 + `validate_schema.py` 통과까지 확인했다(2026-07-22).
`REPS=3`짜리 스모크 테스트라 `bootstrap_ci.py compare`의 Mann-Whitney U는 유의하게 안 나오는데,
이는 표본이 3개뿐이라 당연한 것이고(n=3 vs n=3은 이 검정에서 사실상 유의성이 안 나옴) 버그가
아니다 — 실제 결론은 `REPS=100`으로 돌려야 한다.

**아직 확인 안 한 것:** tracepoint 대상 `syscalls/sys_enter_getpid`가 실제로 존재하는지
(`sudo ls /sys/kernel/tracing/events/syscalls/sys_enter_getpid`) — smoke-test는 통과했으니
존재하는 것으로 보이지만 명시적으로 확인한 적은 없다.

**아직 구현 안 한 것 (범위 밖으로 명시적으로 미룸):** A-1 측정 절차 5번의 "4-way 통제"
((무계측)/(perf stat만)/(eBPF만)/(perf+eBPF 동시)) 축은 이번 구현에 없다. 지금은 probe family
축(none/kprobe/fentry/tracepoint/raw_tracepoint)만 구현했고, `perf stat`으로 감싸는 추가 축은
후속 작업이다.

### `report_xlsx.py`
`make summarize`/`make compare`를 probe_type 쌍마다 손으로 돌리는 대신, `<outdir>/raw/<probe_type>/
*.txt` 전체를 모아 5종을 한 번에 보는 `.xlsx` 리포트로 만든다(통계 로직은 `bootstrap_ci.py`의
`summarize_metrics`/`compare_metrics`를 그대로 재사용, raw 파일은 probe_type당 한 번만 읽어서
summary/vs_none 두 시트에 재사용 — raw가 수십 GB라 안 그러면 시트마다 파일을 다시 읽어 느려짐).
시트 2개:
- **summary**: probe_type별 mean/p50/p99/p999 (점추정 + 95% CI, ns 단위) — raw 데이터가 없는
  probe_type은 `n_runs=0`으로 표시.
- **vs_none**: baseline(`none`) 대비 나머지 4종의 overhead(ns, %) + Mann-Whitney U/유의성/CI 비겹침,
  4종 × 4지표(mean/p50/p99/p999) = 16행.

```bash
python3 report_xlsx.py --outdir <outdir> --system duckdb   # <outdir>/ebpf-rdbms-overhead_duckdb_groupA_<날짜>_<host>.xlsx 생성
python3 report_xlsx.py --outdir <outdir> --system duckdb --seed 0   # 재현 가능한 resample (기본값도 0)
python3 report_xlsx.py --outdir <outdir> --system duckdb --output my_report.xlsx  # 파일명 직접 지정
```
`--system`은 `systems/README.md`의 압축 파일명 규칙(`ebpf-rdbms-overhead_<system>_<group>_<날짜>_<host>.tar.gz`)과
맞추기 위한 필수 인자다 — group_a 결과 디렉토리는 그대로 `tar.gz`로 묶이므로, 안에 든 `.xlsx`도 같은 이름
규칙을 따라야 나중에 파일 하나만 따로 꺼내 봐도 어떤 시스템/그룹/날짜/서버산인지 알 수 있다.

합성 데이터(none~raw_tracepoint 평균이 서로 다른 정규분포)로 시트 구조와 값 계산 확인함 —
실제 서버 데이터로는 아직 안 돌려봄.

### `ambient_compare.py` (A-2)
A-1 floor(배경 DB 없음)와 배경 DB를 idle로 띄운 채 다시 측정한 결과를 비교하는 도구
(`docs/01_experiment_design.md` A-2절). `report_xlsx.py`의 `vs_none` 시트는 "같은 outdir
안에서 probe_type vs none"만 비교하므로, "같은 probe_type을 outdir이 다른 두 조건(배경
있음/없음)"으로 비교하는 A-2에는 못 쓴다 — 그래서 별도 스크립트로 뺐다.

**모든 단계는 시스템(서버)별로 각자 돌린다.** `systems/<system>/results/`는 git-ignore라
서버 4곳(gaia1/2/3/5)에 있는 raw 데이터는 서로 안 보인다 — 담당자가 자기 서버에서 자기 시스템에
대해 아래 0~2단계를 반복하면 되고, 서버 간에 데이터를 합칠 필요는 없다(A-2 비교 자체가 "같은
시스템의 A-1 floor vs A-2 ambient"라 시스템별로 순위·선택 probe가 달라도 문제 없음).

**0단계 — probe 축소 (비용 절감).** A-2는 5종 전부 다시 돌리지 않고, A-1에서 family 간 차이가
가장 컸던 1~2종만 배경상태별로 재실행한다. "차이가 가장 컸다"를 사람이 report.xlsx를 보고 눈으로
고르는 대신, A-1 floor 데이터에서 직접 계산한다(none 대비 p99 overhead_pct 기준 — p99를 쓰는 건
mean이 tail 차이를 덮어버리기 때문):
```bash
make rank-probes SYSTEM=duckdb
```
콘솔에 순위를 출력하고, `systems/README.md` 압축 파일명 규칙과 맞춘
`FLOOR_OUTDIR/ebpf-rdbms-overhead_<system>_groupA_ambientrank_<날짜>_<host>.xlsx`도 같이 생성한다
(같은 디렉토리의 `report.xlsx`와 이름이 겹치지 않도록 `ambientrank` 태그를 붙임). `rank` 시트에는
`overhead_pct`뿐 아니라 실제 절대 수치(`none_ns`/`probe_ns`/`overhead_ns`, 각각 CI 포함)와
Mann-Whitney U/p-value/유의성/CI 비겹침까지 다 들어있다 — %만 보여주면 안 된다는 피드백을 받은
경우를 위함. 이 순위에서 상위 1~2종(예: kprobe, fentry)을 실제 배경상태별 재실행 대상으로 정한다.

**1단계 — 배경상태별 재실행.** 위에서 고른 probe만, 배경상태(DuckDB/PostgreSQL/MySQL/ClickHouse/
Umbra idle)별로 A-1과 **똑같은 하네스를 outdir만 다르게** 돌린다:
```bash
make run-ambient SYSTEM=duckdb AMBIENT=duckdb PROBES="kprobe fentry"
```
`AMBIENT`는 배경상태 라벨(자유 문자열)이고, 결과는 `systems/<SYSTEM>/results/group_a_ambient_<AMBIENT>`에
쌓인다(A-1과 다른 경로라 `run000.txt`가 덮어써질 걱정 없음). **이 타겟은 배경 DB를 이 서버에 idle로
띄우는 것까지는 대신 해주지 않는다** — 시스템마다 기동 방법이 다르고(`systems/<system>/setup/` 참고)
담당자도 나뉘어 있어서, 배경 DB(위 예시면 DuckDB)가 idle로 떠 있는 상태를 직접 만들어둔 뒤 실행해야
한다. 배경상태 개수만큼(`AMBIENT` 값을 바꿔서) 반복한다.

**2단계 — 비교.** 0단계에서 고른 probe를 `PROBES`(직접 지정) 또는 `TOP_N`(자동 선택, 0단계와
동일한 계산을 다시 해서 상위 N개를 고름 — 결과는 항상 같음)으로 넘긴다:
```bash
make ambient-compare SYSTEM=duckdb TOP_N=2 \
    AMBIENTS="duckdb=../../../systems/duckdb/results/group_a_ambient_duckdb postgresql=../../../systems/duckdb/results/group_a_ambient_postgresql"
# 또는 probe를 이미 알고 있으면 직접 지정 (TOP_N과 동시 사용 불가):
make ambient-compare SYSTEM=duckdb PROBES="kprobe fentry" AMBIENTS="..."
```
`FLOOR_OUTDIR`(기본 `systems/<SYSTEM>/results/group_a`, A-1 결과) 대 `AMBIENTS`로 넘긴 배경상태별
outdir(1단계가 쌓아둔 `group_a_ambient_<AMBIENT>` 경로들)을 비교해, probe_type × 배경 × metric(4종)
조합별로 한 행씩인 `ambient_compare.csv`를 낸다(기본 위치는 `FLOOR_OUTDIR/ambient_compare.csv`).
raw 파일은 조건(floor 1개 + 배경 N개)당 한 번만 읽고 metric 4개 비교에 재사용한다 —
`bootstrap_ci.py compare`를 metric마다 CLI로 따로 부르면 같은 raw를 최대 4번씩 다시 읽게 되므로
그렇게 하지 않는다.

**해석 기준(A-2):** 한 행의 `ci_overlap=True`면 그 probe_type·배경 조합은 "메커니즘 비용이 DB
존재와 무관"을 지지. `False`면 `diff_ns`/`diff_pct`로 그 배경이 얼마나 영향을 주는지 정량화.

### `Makefile`
`build`/`smoke-test`/`run`/`run-all`/`validate`/`summarize`/`compare`/`report`/`rank-probes`/
`run-ambient`/`ambient-compare`/`clean` 타겟으로 위 과정 전체를 감싼 진입점. `SYSTEM`/`PROBE`/
`REPS`/`N`/`OUTDIR` 등은 `make VAR=값 타겟`으로 넘긴다.
