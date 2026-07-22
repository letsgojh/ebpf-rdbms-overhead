# systems/

DuckDB/PostgreSQL/MySQL/ClickHouse/Umbra 5개 시스템 디렉토리의 공통 규칙. 각 하위 디렉토리
(`systems/<system>/`) 자체는 담당자 전용이지만(최상위 README "디렉토리 소유 원칙"), 결과 보관
방식은 팀 전체가 같은 규칙을 따라야 나중에 서로 헷갈리지 않으므로 여기 공통으로 적어둔다.

## 결과 원본 보관 (구글드라이브 업로드용 압축 파일명 규칙)

`systems/<system>/results/`는 git-ignore 대상이라 로컬에만 남는다. 원본 값을 잃어버리지 않으려면
실험 배치 하나가 끝날 때마다 압축해서 구글드라이브에 올려둔다. 나중에 몇 달 뒤에도 파일명만 보고
바로 찾을 수 있어야 하므로 담당자 관계없이 아래 템플릿을 고정으로 쓴다.

```
ebpf-rdbms-overhead_<system>_<group>_<YYYYMMDD>_<host>.tar.gz
```

| 자리 | 값 | 왜 넣는가 |
|---|---|---|
| `<system>` | `duckdb`/`postgresql`/`mysql`/`clickhouse`/`umbra` | 5개 시스템 중 뭔지 |
| `<group>` | `groupA`, `groupB`, ... | 세부실험(`A-1`/`A-2`)까지 안 박고 그룹 단위로 통일 — 같은 `results/group_a/` 폴더에 A-1, A-2가 같이 쌓이므로 폴더를 통째로 다시 압축해도 이름 규칙이 안 바뀜 |
| `<YYYYMMDD>` | 예: `20260722` | 환경 고치고 재실행하는 등 같은 조합을 여러 번 돌리게 되는데, 이 형식이면 파일 목록 **이름순 정렬 = 날짜순 정렬** |
| `<host>` | `gaia1`, `gaia3` 등 | A-1 문서 자체가 "서버마다 floor 값이 다를 수 있다"고 전제 — 나중에 어느 서버산 데이터인지 구분 필요 |

N/REPS/probe_type 같은 세부 파라미터는 파일명에 안 넣는다 — 이미 CSV 파일명(`duckdb_kprobe_na_na_run042.csv`)과 컬럼(`run_id`, `timestamp`, `kernel_version`)에 다 들어있어서, 압축 파일명까지 길어지면 오히려 못 알아본다.

**예시 (DuckDB, Group A, 2026-07-22, gaia1):**
```bash
cd systems/duckdb/results
tar -czf ebpf-rdbms-overhead_duckdb_groupA_20260722_gaia1.tar.gz group_a/
```

**예시 (PostgreSQL, Group B, 2026-08-01, gaia5):**
```bash
cd systems/postgresql/results
tar -czf ebpf-rdbms-overhead_postgresql_groupB_20260801_gaia5.tar.gz group_b/
```

**구글드라이브 정리:** 시스템별로 폴더를 하나씩 만들어둔다(`duckdb/`, `postgresql/`, ...) — 파일명 안 열어봐도 폴더만 보고 바로 찾을 수 있게.
