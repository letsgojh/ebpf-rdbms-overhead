# eBPF-RDBMS-Overhead

RDBMS 환경에서 eBPF probe가 유발하는 overhead를, 서로 다른 실행 아키텍처를 가진 5개 시스템(DuckDB, PostgreSQL, MySQL, ClickHouse, Umbra)에 걸쳐 정량적·기계론적으로 분석하는 연구 저장소입니다. 연구 배경·RQ·실험설계 전체는 `docs/`를 참고하세요.

## 담당자 및 서버

| 담당자 | 시스템 | 서버 | 비고 |
|---|---|---|---|
| 유재환 | DuckDB, Umbra | gaia2, gaia3 | Umbra는 심볼 접근성 미확정 — `docs/decisions_log.md` 참고 |
| 김형규 | MySQL, PostgreSQL | gaia1,gaia5 | |
| 미정 | ClickHouse | - | 담당자 확정 시 `systems/clickhouse/`에 착수 |

각자 자기 담당 시스템 디렉토리(`systems/<자기담당>/`)에서만 작업합니다. 서버는 물리적으로 분리되어 있고, 이 repo만 각자 clone해서 씁니다.

## 디렉토리 구조

```
ebpf-rdbms-overhead/
├── README.md                    # 이 문서
├── docs/                        # 연구계획서·실험설계·리뷰 문서
│   ├── 00_research_proposal.md
│   ├── 01_experiment_design.md
│   ├── 02_architecture_mapping.md
│   └── decisions_log.md
│
├── common/                      # 시스템 무관, 반드시 동일해야 하는 공통 코드 — 수정 시 반드시 PR 리뷰
│   ├── probes/                  # 커널 레벨 eBPF 프로그램 (Group A/F/I)
│   ├── harness/                 # 반복실행·bootstrap CI·breakpoint regression 공통 구현
│   ├── schema/                  # 결과 스키마 정의 및 검증 스크립트 (★ 협업의 유일한 접점)
│   └── env/                     # CPU governor/cstate/pinning 등 환경 통제 스크립트
│
├── systems/
│   ├── duckdb/                  # 유재환 담당
│   ├── umbra/                   # 유재환 담당
│   ├── postgresql/              # 김형규 담당
│   ├── mysql/                   # 김형규 담당
│   └── clickhouse/              # 담당 미정
│       └── (각 시스템 디렉토리 내부 구조는 동일)
│           ├── setup/           # 빌드/버전 고정, VERSION.lock
│           ├── probes/          # 이 시스템 전용 uprobe/USDT 타겟 (Group D/E)
│           ├── workloads/       # TPC-H/DS/JOB 데이터 생성·적재
│           ├── experiments/     # Group A~J 실행 스크립트
│           ├── results/         # 원본 결과 — git-ignore, 로컬 보관
│           └── notes.md
│
├── results_aggregated/          # 스키마 검증 통과한 요약 결과만 모아둔 곳 (분석 직전 단계)
│   └── duckdb/ umbra/ postgresql/ mysql/ clickhouse/
│
└── analysis/                    # 합친 결과로 그래프·표 생성
    ├── notebooks/
    └── figures/
```

## 시작하기

```bash
git clone <repo-url>
cd ebpf-rdbms-overhead/systems/<자기담당시스템>
cat README.md          # 이 시스템 전용 실행 방법
bash setup/install.sh  # 버전 고정 빌드 (없으면 새로 작성)
```

공통 환경 통제(코어 pinning, turbo/cstate 비활성화)는 재부팅할 때마다(설정이 런타임 값이라 재부팅
시 초기화됨) 실험 시작 전 매번 실행합니다:

```bash
make -C ../../common/env setup                # 3개 스크립트를 순서대로 실행 (기본 코어 2,3)
make -C ../../common/env setup CORES=4,5      # 코어 목록을 바꾸고 싶을 때
```
개별 스크립트를 손으로 하나씩 돌리려면 `common/env/README.md` 참고.

## 협업 워크플로우

**디렉토리 소유 원칙.** 본인은 `systems/duckdb/`, `systems/umbra/`만, 팀원은 `systems/postgresql/`, `systems/mysql/`만 수정합니다. 서로 다른 파일을 건드리는 이상 git이 자동으로 병합하므로 실시간 동기화는 필요 없습니다.

**push/pull 리듬.**
- 작업 시작 시 `git pull` 1회
- 작업 마무리 시 `git push` 1회
- 하루 여러 번 동기화할 필요 없음 — 자기 디렉토리 안에서는 로컬 커밋을 원하는 만큼 쌓아둬도 무방

**`common/` 또는 `docs/` 수정 시 예외.** 이 두 곳은 둘 다 영향을 받으므로:
1. 수정 전 상대방에게 먼저 알림
2. 브랜치 생성 후 PR로 반영 (main 직접 push 금지)
3. 상대방 리뷰·승인 후 merge

이 두 곳이 실행 중간에 조용히 달라지면 두 사람의 측정 결과가 비교 불가능해지므로, 여기만큼은 반드시 절차를 지킵니다.

**커밋 메시지 컨벤션:** `[시스템][그룹] 설명`
예: `[duckdb][GroupA] kprobe floor 측정 하네스 추가`, `[common][schema] result_schema.json v1.1 — CPU overhead 컬럼 단위 수정`

**브랜치 전략:** 자기 담당 디렉토리는 `main`에 직접 커밋 가능(충돌 없음이 보장되므로). `common/`, `docs/` 변경만 `feature/*` 브랜치 + PR.

## 결과 스키마 규칙

모든 결과 CSV는 `common/schema/result_schema.json`을 따릅니다. `results_aggregated/`에 올리기 전 반드시 검증합니다:

```bash
python common/schema/validate_schema.py systems/<시스템>/results/<파일>.csv
```

**파일명 규칙:** `results/<group>/<system>_<probe종류>_<sf>_<위치또는동시성>_<run번호>.csv`
예: `results/group_b/duckdb_fentry_sf10_tuple_run03.csv`

**부호 규칙(5.4 기준):** 저하율·오버헤드율은 항상 양수. throughput은 `(baseline − 측정값)/baseline`, latency/CPU/하드웨어 카운터는 `(측정값 − baseline)/baseline`.

## 환경 통제 체크리스트 (실험 실행 전 매번 확인)

- [ ] CPU governor `performance` 고정
- [ ] Turbo Boost / C-state 비활성화
- [ ] 대상 코어 isolcpus + pinning
- [ ] `sysctl kernel.bpf_stats_enabled=1` 설정 (Tier 2 측정 시)
- [ ] 커널 버전·DB 버전이 `setup/VERSION.lock`과 일치하는지 확인
- [ ] warm-up 10회 후 측정 시작, 실행 순서 랜덤화

## 실험 그룹 진행 현황

| Group | 내용 | Phase | 담당 | 상태 |
|---|---|---|---|---|
| A | 메커니즘 비용 분해 (A-1 floor, A-2 앰비언트) | 1 | 공통(각자 실행) | 대기 |
| B | 스케일×빈도 증폭 법칙 | 1 | 공통(각자 실행) | 대기 |
| C | 동시성 증폭 (CH-benCHmark 필수) | 1 | PostgreSQL/MySQL 중심 | 대기 |
| D | 유저스페이스 vs 커널스페이스 위치 | 2 | 공통 | 대기 |
| E | 쿼리 플랜 민감도 | 2 | 공통 | 대기 |
| F | 하드웨어 카운터 원인 분석 | 1 | 공통 | 대기 |
| G | 데이터 수집 채널 비교 | 2 | 공통 | 대기 |
| H | 완화 전략 | 2 | 공통 | 대기 |
| I | 커널 버전 비교 | 2 | 공통 | 대기 |
| J | 종합 사례 연구 | 2 | 공통 | 대기 |

(각 실험 완료 시 상태를 대기→진행중→완료로 업데이트하고, 결과 커밋 해시를 여기에 링크하는 걸 권장)

## 문서

- [연구계획서](docs/00_research_proposal.md)
- [실험설계 상세](docs/01_experiment_design.md)
- [아키텍처 정규화 매핑](docs/02_architecture_mapping.md)
- [의사결정 로그](docs/decisions_log.md) (Umbra go/no-go, 벤치마크 변경 이력 등)

## 미정 사항

- [ ] ClickHouse 담당자 확정
- [ ] git hosting 선택 (GitHub private / 학내 GitLab)
- [ ] Git LFS 사용 여부 (raw perf 덤프 보관 방식에 따라 결정)