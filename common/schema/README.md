# common/schema/

결과 CSV의 "계약(contract)"을 정의하는 곳. `docs/01_experiment_design.md` 0.1절(공통 필드 표)과
0.2절(파일명 규칙)을 실제로 실행 가능한 형태로 옮겨놓은 것이 이 디렉토리다. 최상위 README가
"협업의 유일한 접점"이라고 부르는 디렉토리이므로, 여기 두 파일을 수정하면 두 사람(유재환/김형규)
모두의 결과 CSV 형식이 동시에 바뀐다 — **수정 전 상대방에게 알리고 `feature/*` 브랜치 + PR로만
반영한다** (README "협업 워크플로우" 절 그대로).

## 파일별 역할

### `result_schema.json`
결과 CSV 한 행(row)이 만족해야 하는 [JSON Schema](https://json-schema.org/) (draft-07) 정의.
- `required`: 이 필드들은 모든 그룹(A~J) 공통으로 반드시 값이 있어야 한다 — `system`, `group`,
  `sub_experiment`, `probe_type`, `run_id`, `kernel_version`, `system_version_hash`, `timestamp`.
- 나머지 필드(레이턴시/처리량/Tier 2 카운터 등)는 타입에 `null`을 허용한다 — 예를 들어 Group A는
  `throughput_qps`를 측정하지 않으므로 비워두고(CSV에서는 빈 문자열), Tier 2 카운터(`cycles`,
  `ipc` 등)는 해당 실험에서 측정했을 때만 채운다.
- `probe_location`은 Group B 전용이라고 문서에 명시되어 있어 `enum`에 `null`을 포함시켜 A/C~J에서는
  비워도 되게 했다.
- `additionalProperties: true` — 0.1절이 "최소한 아래 컬럼을 포함한다"고 했지, "이 컬럼만 있어야
  한다"고 하지 않았기 때문에 시스템별로 컬럼을 더 추가하는 건 허용한다(단, 오타는
  `validate_schema.py`가 warning으로 잡아준다).

컬럼을 추가/변경할 일이 생기면 이 파일 하나만 고치면 되고, `validate_schema.py`는 이 파일을 그대로
읽어서 동작하므로 스크립트 쪽은 건드릴 필요가 없다.

### `validate_schema.py`
CSV 파일을 `result_schema.json`에 대해 실제로 검증하는 스크립트. `results/` 에서
`results_aggregated/` 로 결과를 옮기기 전 필수 관문이다(최상위 README "결과 스키마 규칙" 절).

```bash
python common/schema/validate_schema.py systems/duckdb/results/group_a/duckdb_fentry_na_na_run000.csv
# 여러 개/glob도 가능
python common/schema/validate_schema.py systems/duckdb/results/group_a/*.csv
```

동작:
1. CSV를 한 행씩 읽어 `csv.DictReader`로 dict화한다.
2. 빈 문자열은 스키마상 `null`이 허용되는 필드에 한해 `None`으로, `integer`/`number` 타입 필드는
   `int`/`float`로 캐스팅한다(캐스팅 실패 시엔 그대로 둬서 jsonschema가 타입 오류로 잡게 함).
3. 행마다 `jsonschema.Draft7Validator.iter_errors`로 **모든** 오류를 모아서 보여준다(첫 오류에서
   멈추지 않음 — 한 번에 고칠 수 있게).
4. 파일명이 0.2절 규칙(`<system>_<probe_type>_<sf|na>_<probe_location|na>_run<NN>.csv`)과
   다르면 warning을 낸다(하드 실패는 아님 — 디렉토리 구조로 이미 `group`을 구분하는 경우가 있어서).
   `probe_type`에 언더스코어가 들어가는 경우(`raw_tracepoint`)가 있어 정규식은 `[a-z_]+`를
   쓴다(처음엔 `[a-z]+`로 짰다가 `raw_tracepoint` 파일에서 오탐 warning이 나서 수정함 —
   뒤쪽 `sf`/`probe_location`/`run<NN>` 앵커 덕에 백트래킹으로 여전히 올바르게 갈린다).
5. 스키마에 없는 컬럼이 섞여 있으면 오타일 가능성이 높으므로 warning으로 알려준다.

종료 코드: 오류가 하나라도 있으면 1, 모두 통과하면 0 — CI나 pre-commit에서 그대로 게이트로 쓸 수 있다.

**의존성:** `jsonschema` (pip). 이 서버에는 이미 설치되어 있음(`python3 -c "import jsonschema"`로 확인).
