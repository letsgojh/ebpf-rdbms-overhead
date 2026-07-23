# systems/duckdb/

DuckDB 실험 디렉토리. 담당자 전용(최상위 README "디렉토리 소유 원칙"). 이 서버(gaia1)는 DuckDB
전용이라 다른 시스템(PostgreSQL/MySQL/ClickHouse/Umbra)은 여기 설치하지 않는다 — 각 그룹 진행
상황/phase는 `notes.md` 참고.

## 빠른 시작 (`setup/Makefile`)

```bash
cd systems/duckdb/setup
make install                      # DuckDB 버전 확인 + VERSION.lock 기록
make idle-start                   # A-2용 "DuckDB idle" 배경 시작 (기본 DB: 아래 참고)
make idle-status                  # 지금 idle 배경이 떠 있는지 확인
make idle-stop                    # idle 배경 종료
make idle-start DB=/path/to.duckdb  # 다른 DB 파일로 띄우고 싶을 때
```

## 파일별 역할

### `setup/install.sh`
DuckDB CLI 버전을 확인하고 `VERSION.lock`에 기록한다. DuckDB는 PostgreSQL/MySQL과 달리 서버
데몬 없는 단일 정적 바이너리로 배포되는 임베디드 DB라 소스 빌드가 필요 없다 — 이미 설치돼 있으면
(`/home/jhyoo/bin/duckdb`, 이 서버 기준 `v1.4.1`) 그 버전만 확인/고정한다. 없으면 배포 파일명
규칙이 버전마다 달라 자동 다운로드는 하지 않고 https://duckdb.org/install 안내만 출력한다.

### `setup/idle.sh {start|stop|status} [DB경로]`
Group A-2(앰비언트 부하 민감도)의 "DuckDB idle" 배경 상태를 실제로 만드는 스크립트. DuckDB는
상시 서버 프로세스가 없어서 "띄운다"는 게 곧 "DB 파일을 로드한 커넥션을 유지한 프로세스 하나를
계속 살려둔다"는 뜻이다 — `duckdb` CLI의 stdin을 절대 끝나지 않는 파이프(`tail -f /dev/null`)에
연결해 프롬프트에서 쿼리를 안 받고 계속 대기하게 만드는 방식으로 구현했다. `-readonly`로 열어서
원본 DB 파일을 락/오염시키지 않는다.

기본 DB는 `/home/jhyoo/DuckDB/TPC-Benchmark-on-DuckDB/TPC_H/tpch_sf100.duckdb`(유재환의 별도
벤치마크 프로젝트에 이미 있는 TPC-H SF100, 27.6GB)를 재사용한다 — 빈 인메모리 DB보다 실제 데이터가
로드된 상태가 "배경 부하"로 더 현실적이라서다. PID는 `idle.pid`(git-ignore)에 저장해 중복 실행을
막고, 로그는 `idle.log`(git-ignore)에 남는다.

실제로 `start` → `lsof`로 DB 파일이 열려있는지 확인 → `stop`까지 검증 완료(2026-07-23).

### `setup/Makefile`
위 두 스크립트를 감싼 진입점(`install`/`idle-start`/`idle-stop`/`idle-status`). `idle-start`에
`DB=<경로>`를 붙이면 다른 DB 파일로 띄울 수 있다.

### `setup/VERSION.lock`
`install.sh`가 기록하는 1줄짜리 버전 문자열. 환경 통제 체크리스트의 "커널 버전·DB 버전이
`setup/VERSION.lock`과 일치하는지 확인" 항목과 대응 — git에 커밋해서 팀이 어떤 버전 기준으로
측정했는지 추적한다.

### `notes.md`
그룹(A-1, A-2, ...)별 진행 상황을 phase 체크리스트로 기록하는 로그. 진행할 때마다 여기에 계속
업데이트한다 — 자세한 내용/다음 할 일은 이 파일 참고.
