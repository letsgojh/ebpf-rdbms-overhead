# common/probes/

Group A-1(격리된 floor 측정)에서 쓰는, DB와 무관한 4종 probe family(kprobe/fentry/tracepoint/
raw_tracepoint)의 커널 레벨 eBPF 프로그램. `docs/01_experiment_design.md` A-1절(96~116행)의
스켈레톤을 실제로 빌드되는 코드로 옮긴 것이다.

**중요한 제약 (A-1, 116행):** 네 파일의 본문 로직("맵 lookup + 카운터 증가")은 **완전히 동일하게
유지**해야 한다 — probe family 간에 측정되는 비용 차이가 "본문이 다르기 때문"이 아니라 순수하게
"attach 메커니즘 차이"임을 보장하기 위해서다. 그래서 실제 증가 로직은 `common.bpf.h`의
`bump_counter()` 하나로 통일해 4개 파일이 전부 그 함수만 호출하도록 만들었다 — 로직을 고치고
싶으면 `common.bpf.h` 한 곳만 고치면 나머지 세 파일도 자동으로 똑같이 바뀐다.

이 디렉토리도 `common/`이므로 수정 시 최상위 README의 "협업 워크플로우"(PR 리뷰 필요) 절이 적용된다.

## 파일별 역할

### `common.bpf.h`
4개 probe 파일이 공유하는 헤더.
- `counter_map`: 1-엔트리 `BPF_MAP_TYPE_ARRAY`, probe가 호출됐을 때마다 증가만 하는 카운터.
- `bump_counter()`: 맵 lookup 후 원자적으로 1 증가시키는 함수. **이 함수 시그니처와 내부 로직이
  4개 파일 간 "동일한 본문"의 실체**다.
- 라이선스 문자열(`Dual BSD/GPL`)도 여기서 한 번만 선언한다.

### `kprobe_empty.bpf.c` / `fentry_empty.bpf.c`
문서 스켈레톤 그대로, `TARGET_FUNC` 매크로(커널 심볼명 문자열)에 붙는 kprobe/fentry 프로그램.
Phase 1에서 target_syscall을 **getpid 재사용**(A-1 옵션 2, 61행)으로 확정했다. 이 서버(커널
6.8.0-31-generic)에서 실제로 확인한 결과, kprobe와 fentry가 붙는 심볼명이 서로 다르다:

- kprobe 기본값: `__x64_sys_getpid` — `/proc/kallsyms`에 global(`T`) 심볼로 노출됨.
- fentry 기본값: `__do_sys_getpid` — fentry는 BTF FUNC 목록에 있는 이름에만 붙는데, BTF에는
  `__x64_sys_getpid`(SYSCALL_DEFINE 매크로가 만드는 얇은 래퍼)는 없고 실제 구현체인
  `__do_sys_getpid`(static)만 노출돼 있다(`bpftool btf dump file /sys/kernel/btf/vmlinux`로 확인).

커널 버전이 바뀌면 이 심볼명들(특히 fentry 쪽 BTF 노출 여부)이 달라질 수 있어 재확인이 필요하다.
다른 syscall/타겟으로 바꾸려면:

```bash
make TARGET_FUNC='"실제_심볼명"'
```

### `tracepoint_empty.bpf.c` / `raw_tracepoint_empty.bpf.c`
kprobe/fentry와 달리 함수 심볼이 아니라 커널이 정의한 trace event에 붙는다.
- tracepoint 기본값: `syscalls/sys_enter_getpid` — 이름 있는 syscall마다 자동 생성되는 표준
  tracepoint라 존재할 것으로 보이지만, 이 서버는 tracefs 접근에 sudo가 필요해 직접 확인은 못 했다
  (`ls /sys/kernel/tracing/events/syscalls/sys_enter_getpid`로 Phase 1 실행 전 재확인할 것).
- raw_tracepoint 기본값: `sys_enter`. 이건 **모든 syscall에서 발화**하므로, getpid 호출만 세려면
  `ctx->args[1]`(syscall 번호)로 걸러야 한다 — `raw_tracepoint_empty.bpf.c`에
  `TARGET_SYSCALL_NR`(기본값 39 = x86_64 `__NR_getpid`) 체크를 추가해뒀다. 이 필터는
  raw_tracepoint 파일에만 있고 나머지 3개엔 없는데, kprobe/fentry/tracepoint는 애초에 getpid
  하나에만 붙어서 "같은 이벤트를 재는" 결과가 되고, raw_tracepoint만 대상을 좁히는 로직이 따로
  필요하기 때문이다 — `bump_counter()` 자체(카운터 증가 로직)는 여전히 4개 파일이 동일하다.

빌드 시 오버라이드:
```bash
make TARGET_TRACEPOINT='"syscalls/sys_enter_getpid"' \
     TARGET_RAW_TRACEPOINT='"sys_enter"' TARGET_SYSCALL_NR=39
```

### `Makefile`
4개 `.bpf.c`를 `.bpf.o`로 컴파일한다. `vmlinux.h`(커널 BTF를 C 헤더로 떠온 것)를 이 서버에서 처음
한 번 생성하고, 이후 `.bpf.o` 빌드에 재사용한다.

```bash
cd common/probes
make            # vmlinux.h 생성 + 4개 .bpf.o 빌드
make clean       # 빌드 산출물 삭제 (vmlinux.h, *.bpf.o — 둘 다 git-ignore 대상)
```

`vmlinux.h`와 `*.bpf.o`는 커널/서버마다 달라지므로 **git에 커밋하지 않는다**(`.gitignore`에 이미
포함됨). DuckDB/Umbra 서버(유재환)와 PostgreSQL/MySQL 서버(김형규)에서 각자 로컬로 빌드해서 쓴다.

빌드 확인(2026-07-22, 이 서버 기준): `bpftool`/`clang`/`libbpf-dev` 모두 설치돼 있어 4개 파일
전부 컴파일 성공. `readelf -S`로 확인한 결과 kprobe/fentry/tracepoint/raw_tracepoint 4개
프로그램의 섹션 크기가 전부 0x60바이트로 동일 — "본문 로직 동일" 제약이 바이트코드 수준에서도
지켜지고 있다는 뜻이다.

## Phase 1과의 연결

이 `.bpf.o` 파일들은 `common/harness/group_a1_runner.py`(`run_group_a1.sh`로 실행)가
`bpftool prog load ... autoattach`로 커널에 로드/부착하고, `bpftool prog show`로
`run_time_ns`/`run_cnt`를 읽는 데 쓴다(A-1 측정 절차 118~124행). 이 디렉토리 자체는 "4종 probe
프로그램"만 책임지고, 로드/attach/반복실행/통계 처리는 `common/harness/` 몫이다 — 자세한 사용법은
그쪽 README 참고.
