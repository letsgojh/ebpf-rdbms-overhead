# systems/duckdb/setup/Makefile
# DuckDB 버전 확인/idle 배경 기동을 make 타겟으로 자동화. 사용법은 systems/duckdb/README.md 참고.
#
#   make install                 버전 확인 + VERSION.lock 기록 (install.sh)
#   make idle-start [DB=<경로>]  A-2용 "DuckDB idle" 배경 시작 (idle.sh start)
#   make idle-stop               idle 배경 종료 (idle.sh stop)
#   make idle-status             idle 배경 실행 여부 확인 (idle.sh status)

DB ?=

.PHONY: install idle-start idle-stop idle-status

install:
	bash install.sh

idle-start:
	bash idle.sh start $(DB)

idle-stop:
	bash idle.sh stop

idle-status:
	bash idle.sh status
