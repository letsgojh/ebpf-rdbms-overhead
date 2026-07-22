# common/env/

실험 실행 전 매번 적용하는 환경 통제 스크립트. 전부 root 권한이 필요하며(내부에서 자동으로 `sudo`
재실행), 시스템 전역 설정을 변경하므로 **원상복구가 필요하면 재부팅하거나 값을 수동으로 되돌려야 한다.**
README 최상위 "환경 통제 체크리스트" 항목과 1:1로 대응된다.

## 실행 순서

```bash
make setup                          # 4개를 순서대로 실행 (기본: SMT 뒷절반 offline, 코어 2,3 고정)
make setup CORES=4,5                # 실험에 쓸 코어 목록을 바꾸고 싶을 때
make setup KEEP_CORES=40 CORES=2,3  # SMT로 살려둘 논리 CPU 개수를 명시하고 싶을 때
```
개별 스크립트를 손으로 하나씩 돌리고 싶으면:
```bash
sudo bash disable_smt.sh            # 인자: 살려둘 논리 CPU 개수, 기본값 nproc --all의 절반
sudo bash set_cpu_governor.sh
sudo bash disable_turbo_cstate.sh
sudo bash pin_cores.sh 2,3          # 인자: 실험에 사용할 코어 번호(콤마 구분), 기본값 2,3
```

**재부팅할 때마다 다시 실행해야 한다.** governor/turbo/cstate/IRQ affinity는 전부 sysfs·procfs
런타임 설정이라 재부팅하면 초기화된다 — 한 번 해두면 끝나는 게 아니라, **재부팅 후 실험 시작 전마다**
`make setup`을 돌려야 한다. 유일한 예외는 `pin_cores.sh`가 안내하는 `isolcpus` 커널 파라미터인데,
이건 스크립트가 자동으로 안 고쳐주고 안내 메시지만 띄운다 — `/etc/default/grub`에 직접 추가하고
`update-grub && reboot`을 한 번 해두면(수동), 그 이후로는 재부팅해도 계속 유지된다.

## 파일별 역할

### `disable_smt.sh [유지할 논리 CPU 개수]`
SMT(하이퍼스레딩) 형제 스레드를 통째로 offline시켜 스레드 경합 자체를 없앤다. gaia1 토폴로지는
`cpuN`과 `cpuN+(전체/2)`가 형제(0↔40, 1↔41, ..., 39↔79)라, 뒤쪽 절반을 통째로 끄면 물리 코어당
스레드 1개씩만 남는다 — 실험 코어(2,3)의 형제만 끄는 것보다 시스템 전체에서 스레드 경합을
없애는 더 확실한 방법이다. 기본값은 `nproc --all`(현재 online 여부와 무관하게 설치된 전체 논리
CPU 수)의 절반이며, 다른 서버는 코어 수·형제 관계가 다를 수 있으니 실행 전 `lscpu -e`로 재확인할 것.

**주의:** 이 offline 상태도 governor/turbo/cstate와 같은 런타임 설정이라 **재부팅하면 초기화된다**
(다시 전부 online으로 돌아옴) — 그래서 `make setup`의 첫 단계로 넣어뒀다.

### `set_cpu_governor.sh`
모든 CPU 코어의 frequency governor를 `performance`로 고정한다. `cpupower frequency-set -g
performance` 실행 후 `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`를 하나씩 읽어 실제로
반영됐는지 검증하고, 하나라도 다르면 실패로 종료한다. `cpupower`가 없으면 설치 안내 메시지를 띄우고
종료한다.
- 즉, CPU 클럭이 실험 중 오르/내리락으로 인해 측정값에 노이즈 생기는 걸 방지하기 위함.

**실기 이슈(gaia1, 2026-07-22):** `cpupower frequency-set` 직후 특정 코어의 `scaling_governor`를
읽으면 "Device or resource busy"가 뜨는 경우가 있었다. 이 read 하나가 `set -e` 때문에 스크립트
전체를 죽여서 뒤의 `disable_turbo_cstate.sh`/`pin_cores.sh`까지 못 도는 문제가 있었다 — 0.2초
간격으로 5회 재시도하고, 그래도 안 풀리면 그 코어만 경고로 남기고 나머지는 계속 진행하도록 고쳤다.

**`disable_smt.sh`로 offline된 코어는 검사에서 제외한다.** `cpuN/online` 값이 `0`인 코어까지
검사하면 매번 "읽기 실패" 경고가 offline된 코어 수만큼 뜨는데, 이건 버그가 아니라 의도한 상태라
오히려 헷갈린다 — `cpuN/online`이 `0`이면 검사 자체를 건너뛴다(`cpu0`처럼 `online` 파일이 아예
없는 코어는 "항상 online"으로 취급). 마지막 출력에 몇 개를 건너뛰었는지 개수도 같이 찍는다.

### `disable_turbo_cstate.sh`
클럭/유휴상태 변동을 없애기 위해 두 가지를 끈다.
1. **Turbo Boost** — `intel_pstate/no_turbo=1` 또는 (해당 인터페이스가 없는 환경에서는) `cpufreq/boost=0`.
2. **딥 C-state** — 각 코어의 `cpuidle/state1` 이후 모든 state를 `disable=1`로 설정한다. `state0`
   (POLL/C0)는 그대로 둔다.

둘 다 적용 후 cpu0 기준으로 현재 상태를 표로 출력해 눈으로 확인할 수 있게 한다.
- Turbo Boost : CPU가 쉬고 있을때 기존 클럭보다 더 빠르게 작동하는 기능
- C-stae : CPU 할 일 없을때 들어가는 절전,수면 단계

### `pin_cores.sh [코어목록]`
실험에 사용할 코어를 격리 상태로 만드는 스크립트. 커널 부팅 파라미터로 `isolcpus`를 직접 설정할 수는
없으므로(재부팅 필요), 다음만 수행한다.
1. `/proc/cmdline`에 `isolcpus=`가 이미 있는지 확인하고 없으면 `/etc/default/grub` 수정 + 재부팅을
   안내한다.
2. 지정한 코어를 제외한 나머지 코어로 모든 IRQ의 `smp_affinity_list`를 이동시켜, 인터럽트가 실험 대상
   코어를 방해하지 않게 한다.
3. 지정한 코어 목록을 `pinned_cores.conf`에 저장한다. 이후 harness 실행 시 이 파일을 참고해
   `taskset -c <코어목록> <harness 실행파일>`로 직접 pinning해서 실행한다(이 스크립트 자체는 프로세스를
   pinning하지 않는다 — 아직 실행할 harness가 없는 시점이기 때문).

- CPU 논리 코어가 특정 작업만 하도록 고정시키기 위해 사용 (실험 프로그램 실행되는 도중 키보드 마우스 입력, 타이머 인터럽트 등 다른 작업 실행가능)
- IRQ : 장치가 CPU에게 보내는 알림
```
   ex) 
   실험 프로그램 → CPU 6에서만 실행
   키보드·랜카드·디스크 등의 인터럽트 → CPU 0~5, 7에서 처리
   일반 프로그램과 커널 작업 → 가능하면 CPU 6을 피함
```
### `pinned_cores.conf` (스크립트가 생성하는 파일, git-ignore 대상)
`pin_cores.sh` 실행 결과로 생성되는 1줄짜리 설정 파일. 예: `2,3`. Phase 3 이후의 harness/실행
스크립트가 이 값을 읽어 `taskset` 대상 코어를 결정하는 데 쓴다.

- 사용자가 sudo ./pin_cores.sh 6,7 과 같이 실행한다면, pinned_cores.conf에 6,7을 저장한다.
- 이후 taskset 명령어(논리 CPU n에서만 실행시키도록 하는 명령어)를 통해 실험을 진행할 논리 cpu pinned

### `Makefile`
위 4개 스크립트를 순서대로(SMT 차단 → governor → turbo/cstate → pin_cores) 실행하는 `make setup`
타겟 하나뿐. `CORES` 변수로 `pin_cores.sh`에 넘길 코어 목록을(기본값 `2,3`), `KEEP_CORES` 변수로
`disable_smt.sh`에 넘길 "살려둘 논리 CPU 개수"를(기본값 비워두면 스크립트가 `nproc --all`의
절반을 자동 계산) 바꿀 수 있다. 각 스크립트가 알아서 필요할 때 `sudo`로 재실행되므로, 터미널에서
직접 `make setup`을 실행해야 비밀번호 프롬프트가 뜬다(비대화형 실행 불가).
