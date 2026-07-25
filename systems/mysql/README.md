# systems/mysql/

gaia5 서버의 MySQL 8.0 환경 전용 실험 설정 및 결과 보관 디렉토리입니다.

## 1. 서버 및 시스템 사양 (gaia5)
- **DBMS**: MySQL `8.0.46-0ubuntu0.24.04.3` (x86_64)
- **Kernel**: `6.14.0-37-generic`
- **Host**: `gaia5`

## 2. Group B probe 부착 심볼 위치 (Hook Points)
| 단계 | 위치 정의 | MySQL Hook Symbol | 비고 |
|---|---|---|---|
| 쿼리당 1회 | 쿼리 진입 및 완료 | `mysql_execute_command` | Dispatcher 계층 |
| 오퍼레이터당 1회 | 물리 연산자 실행 1회 | `ha_rnd_next` / `ha_index_next` | Handler 인터페이스 계층 |
| 청크당 1회 | 벡터 배치 처리 | *(구현 곤란 / N/A)* | MySQL 특성상 스칼라 처리 구조 |
| 튜플당 1회 | 개별 Row Scan/Search | `row_search_mvcc` | InnoDB 스토리지 엔진 계층 |

## 3. TPC-H 파일럿 쿼리 (queries/)
- **Q6**: 단순 스캔 및 필터 (`q6.sql`)
- **Q1**: GROUP BY 집계 연산 (`q1.sql`)
- **Q9**: 다중 테이블 조인 (`q9.sql`)

## 4. 데이터베이스 및 스케일 팩터 (SF)
- `tpch_sf1`: TPC-H Scale Factor 1
- `tpch_sf10`: TPC-H Scale Factor 10
- `tpch_sf100`: TPC-H Scale Factor 100

## 5. 결과 저장 구조 (results/)
- `results/group_b/`: Group B 실험 결과 CSV 보관
- 압축 저장 규칙: `ebpf-rdbms-overhead_mysql_groupB_<YYYYMMDD>_gaia5.tar.gz`
