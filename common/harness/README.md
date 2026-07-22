# common/harness/

반복실행 결과의 통계 후처리를 담당하는 공통 코드. Group A/B 모두 "조건당 100회 반복 → 각 반복의
raw 값 배열 → 통계 요약" 흐름을 그대로 따르므로(A-1 126~128행, B-6 절), 그 통계 처리 로직(`bootstrap_ci.py`)
을 여기 한 곳에 모아뒀다. 이 디렉토리도 `common/`이라 수정 시 최상위 README의 PR 리뷰 절차가 적용된다.

## 디렉토리 구조

```
common/harness/
├── bootstrap_ci.py   ← 모든 실험 그룹이 공유하는 통계 처리 (아래 참고)
└── group_a/          ← Group A-1 전용 하네스/오케스트레이션 (자세한 건 group_a/README.md)
```

**컨벤션: 그룹별로 하위 디렉토리를 둔다.** Group A-1과 Group B(TPC-H 쿼리 실행·SF·probe_location
축)는 측정 방식 자체가 완전히 다르다 — Group A-1의 `harness_floor.c`/`group_a1_runner.py` 같은
코드를 Group B가 재사용할 수 없다. 그래서 그룹마다 `group_a/`, `group_b/`, ... 하위 디렉토리를
두고 그 안에서 자기 그룹에 맞는 하네스·러너·Makefile을 독립적으로 갖는다 — Makefile도 그룹마다
따로 둔다(Group A의 변수는 `SYSTEM/PROBE/REPS/N`, Group B는 `SYSTEM/QUERY/SF/PROBE_LOCATION` 등
파라미터 형태 자체가 달라서, 억지로 하나의 공통 인터페이스로 묶으면 오히려 더 복잡해진다). 그룹
간에 진짜 공유되는 건 `bootstrap_ci.py`(통계 처리)뿐이라 이것만 최상위에 남겨뒀다.

## 파일별 역할

### `bootstrap_ci.py`
run(반복)별로 덤프된 raw 값 배열에서 mean/P50/P99/P999를 계산하고, **BCa bootstrap**으로 95%
신뢰구간(CI)을 내고, 두 조건(예: kprobe vs fentry)을 **Mann-Whitney U** 검정으로 비교하는 CLI 겸
라이브러리.

**처리를 2단계로 나누는 이유.** harness 하나(예: Group A-1의 `harness_floor.c`)가 한 번 실행될 때
raw 값이 N=10^7개씩 나온다(A-1 70행). 이 10^7개 전체에 BCa(내부적으로 leave-one-out jackknife
필요)를 직접 돌리면 계산량이 감당 안 된다. 그래서:
1. run 파일 하나(raw 10^7개)에서 mean/P50/P99/P999를 **그냥 계산**한다(bootstrap 아님, `numpy`로
   즉시 계산).
2. 조건 하나당 반복한 run 100개에 대해, 위에서 나온 "run별 통계치 100개"에 BCa bootstrap
   (10,000 resample)을 적용해 최종 95% CI를 낸다. 이때 bootstrap의 표본 크기는 10^7이 아니라
   반복 횟수(보통 100)다 — 이래야 계산이 실용적인 시간 안에 끝난다.

**입력 파일 형식.** 1행 1값 텍스트(정수/실수), 한 run(한 번의 harness 실행)당 파일 하나. 이 형식은
이 스크립트가 정한 계약이므로, 각 그룹의 하네스가 raw 값을 덤프할 때 이 형식으로 써야 한다.

**사용법.**
```bash
# 조건 하나(예: kprobe family, run 100개)의 통계 요약
python common/harness/bootstrap_ci.py summarize "systems/duckdb/results/group_a/raw/kprobe/*.txt"

# 두 조건 비교 (Mann-Whitney U + CI 비겹침)
python common/harness/bootstrap_ci.py compare \
    --a "systems/duckdb/results/group_a/raw/none/*.txt" \
    --b "systems/duckdb/results/group_a/raw/kprobe/*.txt" \
    --metric p99
```

옵션: `--n-resamples`(기본 10,000, A-1/B-6과 동일), `--confidence`(기본 0.95),
`--seed`(재현 가능한 resample을 위한 random seed — 없으면 매번 다른 resample 순서로 CI가 미세하게
흔들리니, 결과를 논문/보고서에 남길 때는 반드시 지정할 것).

**degenerate 케이스 처리.** 반복 run 간 통계치가 완전히 동일(분산 0)하면 BCa의 가속 상수 계산이
0으로 나눠져 `nan`이 나온다 — 이건 버그가 아니라 "run 간 변동이 아예 없다"는 정당한 결과라서,
이 경우엔 CI를 점추정치와 동일한 폭 0으로 반환하도록 처리해뒀다.

**의존성:** `numpy`, `scipy`(`scipy.stats.bootstrap`, `scipy.stats.mannwhitneyu`) — 둘 다 이 서버에
설치되어 있음.

### `group_a/`
Group A-1 전용 하네스/오케스트레이션/Makefile. 자세한 사용법과 검증 내역은
`common/harness/group_a/README.md` 참고.

## Phase B와의 연결 (아직 미구현)

B-6절의 `log(정규화 오버헤드) ~ log(SF)` OLS 회귀(`statsmodels`)와 `ruptures` PELT breakpoint
분석은 아직 없다. 이 서버에는 아직 `statsmodels`가 설치돼 있지 않으니 그 전에
`pip install statsmodels ruptures`가 필요하다. Group B 하네스 자체는 `common/harness/group_b/`로
새로 만들 예정(위 "디렉토리 구조" 컨벤션 참고).
