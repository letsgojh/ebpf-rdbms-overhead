# MySQL Overhead Benchmark Notes

## 1. 서버 및 환경
- **담당자**: 김형규 (Kimhyunggue)
- **서버**: gaia5 (MySQL 전용)
- **MySQL 버전**: `8.0.46 (Ubuntu 8.0.46-0ubuntu0.24.04.3)`
- **바이너리 위치**: `/usr/sbin/mysqld` (또는 `/usr/bin/mysql`)
- **커널 버전**: `6.14.0-37-generic`

## 2. MySQL Hook 타겟 심볼 (Group B)
- **Query Level (`query`)**: `mysql_execute_command`
- **Operator Level (`operator`)**: `ha_rnd_next` / `ha_rnd_init`
- **Tuple Level (`tuple`)**: `row_search_mvcc`

## 3. 로컬 및 DB 구동법 및 TPC-H 워크로드 적재
```bash
# SF1 데이터 적재
python3 systems/mysql/workloads/load_tpch.py --sf 1 --port 3306 --host 127.0.0.1 --user root

# 파일럿 쿼리 EXPLAIN 검증
python3 systems/mysql/workloads/generate_queries.py --port 3306 --host 127.0.0.1 --user root --dbname tpch_sf1
```
