# umbra 진행 노트

Group/실험 단위 진행 상황을 여기 기록한다. 굵은 의사결정·사유는 `docs/decisions_log.md`,
세부 작업 단위(체크리스트·DoD·블로커)는 GitHub 이슈를 참고 — 여기는 "지금 어느 Phase까지
왔는지"를 한눈에 보는 용도.

## Group A — 메커니즘 비용 분해

### A-1. 격리된 floor 측정 — 완료 (2026-07-22)
- probe 5종(none/kprobe/fentry/tracepoint/raw_tracepoint) × 100회 × N=10^7 실행 완료.
- 결과: `systems/umbra/results/ebpf-rdbms-overhead_umbra_groupA_20260722_gaia2.tar.gz`
- `report.xlsx`는 아직 생성 안 함(필요 시 `make report SYSTEM=umbra`).

### A-2. 앰비언트 부하 민감도 — 진행 중 (이슈 #10)
- [x] Phase 0 — `rank-probes`로 A-1 floor 기준 순위 확인 → 상위 2종 `kprobe`, `tracepoint` 확정.
- [x] Phase 1 — 배경 Umbra(Docker, `umbradb/umbra`) 설치 및 idle 기동.
  `bash systems/umbra/setup/umbra_idle.sh {start|stop|status}`로 기동/정지(실험 중엔 계속 켜두고,
  재기동 불필요 — start는 이미 떠 있으면 그냥 넘어가고, 정지된 컨테이너는 재사용).
- [ ] Phase 2 — `make run-ambient SYSTEM=umbra AMBIENT=umbra PROBES="kprobe tracepoint"`.
- [ ] Phase 3 — `make ambient-compare SYSTEM=umbra TOP_N=2 AMBIENTS="umbra=..."`.
- [ ] Phase 4 — `ci_overlap`/`overhead_ns`/`overhead_pct` 해석 기록.
- [ ] Phase 5 — `make archive SYSTEM=umbra GROUP=group_a_ambient_umbra` 후 구글드라이브 업로드.
