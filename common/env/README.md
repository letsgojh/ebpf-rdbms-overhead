# common/env/

실험 실행 전 매번 적용하는 환경 통제 스크립트. 전부 root 권한이 필요하며(내부에서 자동으로 `sudo`
재실행), 시스템 전역 설정을 변경하므로 **원상복구가 필요하면 재부팅하거나 값을 수동으로 되돌려야 한다.**
README 최상위 "환경 통제 체크리스트" 항목과 1:1로 대응된다.

## 실행 순서

```bash
make setup                # 3개를 순서대로 실행 (기본 코어 2,3)
make setup CORES=4,5      # 코어 목록을 바꾸고 싶을 때
```
개별 스크립트를 손으로 하나씩 돌리고 싶으면:
```bash
sudo bash set_cpu_governor.sh
sudo bash disable_turbo_cstate.sh
sudo bash pin_cores.sh 2,3   # 인자: 실험에 사용할 코어 번호(콤마 구분), 기본값 2,3
```

**재부팅할 때마다 다시 실행해야 한다.** governor/turbo/cstate/IRQ affinity는 전부 sysfs·procfs
런타임 설정이라 재부팅하면 초기화된다 — 한 번 해두면 끝나는 게 아니라, **재부팅 후 실험 시작 전마다**
`make setup`을 돌려야 한다. 유일한 예외는 `pin_cores.sh`가 안내하는 `isolcpus` 커널 파라미터인데,
이건 스크립트가 자동으로 안 고쳐주고 안내 메시지만 띄운다 — `/etc/default/grub`에 직접 추가하고
`update-grub && reboot`을 한 번 해두면(수동), 그 이후로는 재부팅해도 계속 유지된다.

## 파일별 역할

### `set_cpu_governor.sh`
모든 CPU 코어의 frequency governor를 `performance`로 고정한다. `cpupower frequency-set -g
performance` 실행 후 `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`를 하나씩 읽어 실제로
반영됐는지 검증하고, 하나라도 다르면 실패로 종료한다. `cpupower`가 없으면 설치 안내 메시지를 띄우고
종료한다.
- 즉, CPU 클럭이 실험 중 오르/내리락으로 인해 측정값에 노이즈 생기는 걸 방지하기 위함.

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
위 3개 스크립트를 순서대로(governor → turbo/cstate → pin_cores) 실행하는 `make setup` 타겟 하나뿐.
`CORES` 변수로 `pin_cores.sh`에 넘길 코어 목록을 바꿀 수 있다(기본값 `2,3`, 스크립트 자체 기본값과 동일).
각 스크립트가 알아서 필요할 때 `sudo`로 재실행되므로, 터미널에서 직접 `make setup`을 실행해야
비밀번호 프롬프트가 뜬다(비대화형 실행 불가).
