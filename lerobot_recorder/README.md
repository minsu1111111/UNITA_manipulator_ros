# lerobot_recorder — 에피소드 녹화 (rosbag2)

토픽을 에피소드 단위로 rosbag 에 녹화한다. 키보드로 시작·저장·버리기. 녹화한 에피소드는 `lerobot_dataset` 으로 LeRobotDataset 으로 바꾼다.

## 실행

텔레옵(`robot` + `leader` + `teleop`, 또는 `mock:=true`)이 떠 있는 상태에서:

```bash
ros2 run lerobot_recorder record --ros-args -p experiment_name:=pour_water -p task:="Pick up the cup and pour water"
```

`record` 는 recorder 를 뒤에서 띄우고 키보드 화면을 앞에 띄운다. 인자는 전부 recorder 로 간다.
recorder 로그는 화면을 가리지 않게 `~/.ros/log/lerobot_recorder/record_<시각>.log` 로 간다 (시작할 때 경로를 출력).
`q` 나 Ctrl+C 로 끝내면 recorder 도 정리하고, 이번에 저장한 에피소드 목록을 보여 준다.

둘을 따로 띄우려면 (recorder 로그를 직접 보고 싶을 때):

```bash
ros2 run lerobot_recorder recorder --ros-args -p experiment_name:=pour_water -p task:="Pick up the cup and pour water"
```
```bash
ros2 run lerobot_recorder keyboard
```

| 키 | 동작 |
|---|---|
| `r` 또는 `→` | 녹화 시작 |
| `s` 또는 `←` | 멈추고 저장 |
| `d` 또는 Backspace | 지금 에피소드 버리기 (번호는 다시 씀) |
| `t` | task 문장 바꾸기 |
| `h` | 도움말 |
| `q` | 끝내기 (`record` 면 recorder 도 같이 끝남. `keyboard` 를 따로 띄웠으면 recorder 는 계속 돔) |

에피소드는 `~/ros_episodes/<experiment_name>/episode_000000/` 처럼 저장된다. 이미 있는 번호 다음부터 이어서 센다.

**task 는 SmolVLA 같은 언어 조건 정책의 입력이다.** 에피소드마다 bag 메타데이터에 저장되고, 변환할 때 데이터셋의 task 가 된다.

## 무엇을 녹화하나

`topics` 를 주지 않으면 토픽 계약의 기본값을 녹화한다:

| 토픽 | 데이터셋에서 |
|---|---|
| `/robot/joint_states` | `observation.state` |
| `/robot/command` | `action` (텔레옵이면 리더 자세, 나중엔 정책 출력) |
| `/robot/cam/<name>/image/compressed` | `observation.images.<name>` — 그래프에 있는 카메라를 자동으로 찾는다 |

카메라는 `robot` 노드가 첫 프레임을 받을 때 생기므로, 녹화를 시작할 때마다 다시 찾는다. 시작할 때 모든 토픽이 0.5 s 안에 들어오고 있어야 한다
(카메라가 빠졌으면 시작을 거부한다 — `start_gate_max_age_s`).

## 파라미터 (`-p 이름:=값`)

| 파라미터 | 기본 | 설명 |
|---|---|---|
| `task` | (없음) | 과제 문장. 녹화 시작 전에 있어야 한다 (키보드 `t` 로도 넣을 수 있음) |
| `experiment_name` | (없음) | 저장 폴더 이름. 데이터셋 하나 = 실험 하나 |
| `root_dir` | `~/ros_episodes` | 저장 위치 |
| `topics` | (기본값) | 녹화할 토픽 목록. 주면 카메라 자동 탐색은 하지 않는다 |
| `storage_id` | `sqlite3` | `mcap` 은 `sudo apt install ros-humble-rosbag2-storage-mcap` 후 |
| `max_episode_duration` | `0` | 이 시간(초)이 지나면 자동 저장. 0 = 제한 없음 |
| `start_gate_max_age_s` | `0.5` | 시작할 때 모든 토픽이 이 시간 안에 들어와 있어야 함. 0 = 검사 안 함 |

키보드 없이 서비스로도 된다 (`std_srvs/srv/Trigger`):

```bash
ros2 service call /episode_recorder/start_recording std_srvs/srv/Trigger
```

`/episode_recorder/stop_recording`, `/episode_recorder/discard_episode` 도 같은 방식.

## 출처

[legalaspro/so101-ros-physical-ai](https://github.com/legalaspro/so101-ros-physical-ai) 의 `episode_recorder`
(Apache-2.0, 커밋 58318c9, 저작자 Dmitri Manajev). 라이선스 원문은 [`LICENSE`](LICENSE). 바꾼 곳은 각 파일 머리에 적었다. 요약:

- 시작하자마자 configure → activate (원본은 launch 가 해 줌. 우리는 `ros2 run` 만 쓴다)
- `topics` 를 비우면 토픽 계약의 기본값 + 카메라 자동 탐색
- `task` 가 비어도 시작은 하고, 녹화를 시작할 때 검사 (원본은 시작 자체를 거부)
- 기본값: 저장 위치 `/tmp/episode_recorder` → `~/ros_episodes`, 저장 형식 `mcap` → `sqlite3` (Humble 기본 플러그인)
- 패키지 이름 `lerobot_recorder`, 실행 파일 `recorder` / `keyboard`. 키보드(`teleop_episode_keyboard.cpp`)는 원본 그대로
- 새로 씀: `scripts/record` (recorder + keyboard 를 명령 하나로)
