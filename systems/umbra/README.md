# systems/umbra/

Umbra 담당(유재환) 전용 실행 방법. 공통 하네스/통계 도구는 `common/harness/group_a/README.md`
참고 — 여기는 umbra 디렉토리에만 있는 것만 적는다. 진행 상황은 `notes.md`, 큰 의사결정은
`docs/decisions_log.md` 참고.

## `setup/umbra_idle.sh` — A-2 배경상태("Umbra idle")용 컨테이너

A-2(`docs/01_experiment_design.md` A-2절)에서 배경에 Umbra를 idle로 띄워놓고 floor를 재는 데
쓴다. Docker Hub 공식 이미지(`umbradb/umbra`) 기반.

```bash
cd systems/umbra/setup
bash umbra_idle.sh start     # 이미지 pull + 컨테이너 기동 (이미 떠 있으면 아무것도 안 함)
bash umbra_idle.sh status    # 기동 상태 확인
bash umbra_idle.sh stop      # 정지 (삭제는 안 함 — 다시 켤 땐 start)
```

**사용 순서:** 실험(`make run-ambient`) 시작 전에 `start` 한 번만 실행해서 켜두고, 그 배경상태로
할 실험이 다 끝날 때까지는 켜놓은 채로 둔다 — probe(kprobe/tracepoint)를 여러 번 돌려도 재기동
필요 없다. 다 끝나면 `stop`.

포트 `5432`, 볼륨 `umbra-db`를 쓴다. 예전에 다른 버전 이미지로 만든 DB 파일이 볼륨에 남아있으면
`unable to open ... incompatible version` 에러가 난다 — 이 경우 그 볼륨을 쓰던 컨테이너를 전부
지우고(`docker rm`) `docker volume rm umbra-db`로 밀고 `start`를 다시 실행하면 새 DB로 다시
만들어진다.
