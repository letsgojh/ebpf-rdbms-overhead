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
- [x] Phase 2 — `make run-ambient SYSTEM=umbra AMBIENT=umbra PROBES="kprobe tracepoint"`.
  결과: `systems/umbra/results/group_a_ambient_umbra/`(kprobe/tracepoint 각 100 run).
- [x] Phase 3 — `make ambient-compare SYSTEM=umbra TOP_N=2 AMBIENTS="umbra=..."`.
  결과: `systems/umbra/results/group_a/ebpf-rdbms-overhead_umbra_groupA_ambientcompare_20260723_gaia2.xlsx`
  (`compare` 시트, 8행 — probe 2종 × metric 4종).
- [ ] Phase 4 — `ci_overlap`/`overhead_ns`/`overhead_pct` 해석 기록.
  초안: 8행 전부 `significant=True`(run 100개라 검정력 매우 높음)지만 `overhead_pct`는
  전부 1% 미만(0.12~0.94%) — 통계적으로는 유의해도 실질적 영향은 미미. `ci_overlap`은
  kprobe mean/p999만 True, 나머지 6개는 False. 최종 해석 확정 필요.
- [ ] Phase 5 — `make archive SYSTEM=umbra GROUP=group_a_ambient_umbra` 후 구글드라이브 업로드.
