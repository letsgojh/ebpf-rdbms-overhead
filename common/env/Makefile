# common/env/Makefile
# 실험 시작 전 환경 통제 4종(SMT 차단 -> governor -> turbo/cstate -> IRQ affinity)을 순서대로
# 실행하는 자동화 진입점. 넷 다 재부팅하면 초기화되는 런타임 설정이라, 재부팅할 때마다 다시
# 실행해야 한다(README "재부팅 시 유지되나" 절 참고). isolcpus 커널 파라미터만 예외로 한 번
# 설정해두면 재부팅해도 유지되지만, 그건 이 Makefile이 자동으로 해주지 않는다(수동으로
# /etc/default/grub 수정 + update-grub + reboot 필요 — pin_cores.sh 실행 시 안내 메시지로 확인 가능).
#
#   make setup [CORES=2,3] [KEEP_CORES=40]   4개 스크립트를 순서대로 실행 (각자 필요시 sudo로 재실행됨)

CORES ?= 2,3
KEEP_CORES ?=

.PHONY: setup

setup:
	bash disable_smt.sh $(KEEP_CORES)
	bash set_cpu_governor.sh
	bash disable_turbo_cstate.sh
	bash pin_cores.sh $(CORES)
