# PostgreSQL Overhead Benchmark Notes

## 1. 서버 및 환경
- **담당자**: 김형규
- **서버**: gaia1 / gaia5
- **PostgreSQL 버전**: `16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)`
- **바이너리 위치**: `/usr/lib/postgresql/16/bin/postgres`
- **커널 버전**: `6.17.0-14-generic`

## 2. PostgreSQL Hook 타겟 심볼 (Group B)
- **Query Level (`query`)**: `ExecutorStart` (`0x00355d80`) / `ExecutorEnd`
- **Operator Level (`operator`)**: `ExecProcNode` (`0x003560f0` - `ExecSetExecProcNode` / `MultiExecProcNode`)
- **Tuple Level (`tuple`)**: `heap_getnextslot` (`0x001ad010`) / `heap_getnext` (`0x001acb90`)

## 3. 로컬 독립 데이터베이스 실행 구동법
```bash
# 독립 데이터 디렉토리 초기화
/usr/lib/postgresql/16/bin/initdb -D /home/hgkim/pgdata --auth-local=trust --auth-host=trust

# 구동 (포트 5433, /tmp 소켓)
/usr/lib/postgresql/16/bin/pg_ctl -D /home/hgkim/pgdata -o "-p 5433 -k /tmp" -l /home/hgkim/pgdata/pg.log start
```

## 4. TPC-H 워크로드 적재
```bash
# SF1 데이터 생성 및 적재
python3 systems/postgresql/workloads/generate_tpch.py --sf 1
python3 systems/postgresql/workloads/load_tpch.py --sf 1 --port 5433 --host /tmp

# 22개 전체 쿼리 생성 및 EXPLAIN 검증
python3 systems/postgresql/workloads/generate_queries.py --port 5433 --host /tmp --dbname tpch_sf1
```
