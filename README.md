# UNITA_manipulator_ros

LeRobot 으로 학습한 정책을 ROS2 시스템에 통합해, 인식부터 실행·판정까지 노드 단위로 나눠 동작하게 만드는 저장소.
수집과 학습은 LeRobot 그대로 두고, 로봇 실행을 ROS2 노드로 구조화한다. 각자 노드 하나씩 맡아 개발하고,
시뮬레이터(MuJoCo)·비전·음성을 같은 토픽에 붙인다.

대상: SO-101 양팔(`bi_so_follower`) 기본, 단팔도 같은 코드. Ubuntu 22.04 + ROS2 Humble, lerobot 0.6.1.

**처음이면 [docs/SETUP.md](docs/SETUP.md) 부터.** 로봇 없이 개발하는 사람은 ROS 만 있으면 된다 (lerobot 불필요).

## 구조

```
UNITA_manipulator_ros/
├── config/
│   ├── robot.env.example     로봇 PC 설정 예시 (보드 시리얼, 포트, 카메라 경로, 캘리 id, lerobot 위치)
│   └── robot.env             그 PC 의 실제 값 (깃 제외, 로봇 PC 에만)
├── docs/
│   ├── SETUP.md              환경 준비 — 설치, conda 와 ROS 분리, ROS_DOMAIN_ID, 문제 해결
│   ├── TOPICS.md             토픽 계약 — 이름·타입·단위(rad)·QoS. 모두가 이것만 보고 개발
│   └── CONTRIBUTING.md       패키지 하나 맡는 법 (템플릿 복사 → 빌드 → mock 으로 개발 → 테스트 → 올리기)
│
├── lerobot_common/           공용 모듈 (노드 없음): 관절 이름, 토픽 이름, QoS, lerobot↔rad 변환, robot.env 읽기
├── lerobot_bridge/           lerobot 기능을 ROS 노드로. lerobot 과 만나는 유일한 패키지
│   ├── lerobot_bridge/       ROS 노드: robot, leader, teleop
│   └── hosts/                모터·카메라를 실제로 다루는 쪽: hw_host (lerobot env), mock_host (lerobot 불필요)
├── lerobot_template/         새 패키지를 만들 때 복사하는 예제 (joint_speed 노드 + 테스트)
├── lerobot_description/      SO-101 URDF·메시·카메라 프레임·RViz 설정. robot/joint_states → TF (state_publisher)
├── lerobot_recorder/         에피소드 녹화 (rosbag2) + 키보드 시작·저장·버리기
├── lerobot_dataset/          녹화한 에피소드 → LeRobotDataset (lerobot-record 와 같은 형식)
├── lerobot_sim/              MuJoCo 장면 (SO-101 단팔·양팔, 이름·단위가 토픽 계약과 같음). 노드는 아직 없음
└── reference/                외부 참고 코드 원본 (빌드 제외). 가져다 쓸 때 우리 패키지로 옮겨서 고친다
```

앞으로 붙을 패키지 (각자 `lerobot_template` 을 복사해서 시작, [CONTRIBUTING.md](docs/CONTRIBUTING.md)):

| 패키지 | 내용 |
|---|---|
| `lerobot_sim` | 장면은 있음. `robot/joint_states`·카메라를 내고 `robot/command` 를 받는 노드 ([lerobot_sim/README.md](lerobot_sim/README.md)) |
| `lerobot_perception` | 카메라 토픽 → 물체 인식 결과 |
| `lerobot_speech` | STT → `speech/command`, `speech/say` → TTS |
| `lerobot_safety` | 정책과 로봇 사이 안전 게이트 (스텝 제한, 비상정지) |
| `lerobot_task` / `lerobot_operator` / `lerobot_interfaces` | 과제 흐름·성공 판정 / 시작·정지 입력 / 커스텀 메시지 |

## 노드 그래프

```
 [hw_host 또는 mock_host] ◀─ZMQ─▶ [robot 노드] ──▶ robot/joint_states, robot/cam/*        (rad)
                                               ◀── robot/command
                                                        ▲
                                                 [teleop 노드]
 [hw_host 또는 mock_host] ──ZMQ─▶ [leader 노드] ──▶ leader/joint_states ─┘
```

ROS2 Humble 의 `rclpy` 는 시스템 Python **3.10** 전용이고 lerobot 0.6.1 은 Python **3.12**(conda `lerobot` env)가 필요해서
한 프로세스에 둘을 넣을 수 없다. 그래서 `robot`/`leader` 노드가 호스트를 자식 프로세스로 띄우고 ZMQ 로 주고받는다.
실제 팔이면 lerobot env 의 python 으로 `hw_host`, `mock:=true` 면 시스템 python 으로 `mock_host` 를 띄운다.
사용자는 신경 쓸 필요 없다 — `ros2 run` 한 번이면 둘 다 뜨고 같이 꺼진다.

## 텔레옵 (= `lerobot-teleoperate`)

터미널 3개 (conda 꺼진 터미널):

```bash
ros2 run lerobot_bridge robot
```
```bash
ros2 run lerobot_bridge leader
```
```bash
ros2 run lerobot_bridge teleop
```

- 로봇 없이: `robot`, `leader` 에 `--ros-args -p mock:=true`.
- **teleop 을 켜는 순간 로봇이 리더 자세로 한 번에 움직인다.** 리더를 로봇과 비슷한 자세로 두고 켤 것. 처음엔 `robot` 에 `-p max_rel:=20` (스텝당 최대 20°).
- 잠깐 멈추기: `ros2 param set /teleop enabled false` (다시 `true`).
- 끄기: 각 터미널 Ctrl+C. **robot 을 끄면 토크가 꺼지니 팔을 받칠 것.**
- 단팔: `robot`, `leader` 에 `-p arm:=left` (또는 `right`). `teleop` 은 그대로.
- 실제로 쓸 포트·카메라·lerobot 명령만 보기: `ros2 run lerobot_bridge robot --ros-args -p dry_run:=true`

보기:

```bash
ros2 run rqt_image_view rqt_image_view /robot/cam/left_wrist/image/compressed
```
```bash
ros2 topic echo /robot/joint_states
```

카메라 좌우가 바뀌어도 에러는 안 난다. 처음 띄울 때 왼손목/오른손목 영상을 눈으로 확인할 것.

### 노드 파라미터 (`robot`, `leader`)

| 파라미터 | 기본 | 설명 |
|---|---|---|
| `arm` | `bi` | `bi` / `left` / `right` |
| `mock` | `false` | 하드웨어·lerobot 없이 가짜 팔 (robot 은 가짜 손목 카메라도) |
| `dry_run` | `false` | 호스트 명령만 출력하고 끝 |
| `robot_env` | (자동) | robot.env 경로. 찾는 순서는 `lerobot_common/rig.py` |
| `find_ports` | `true` | robot.env 의 `*_SERIAL` 로 ttyACM 을 직접 찾기 |
| `cameras` | `true` | robot 만. `false` 면 카메라 없이 |
| `max_rel` | `0` | robot 만. 스텝당 최대 변화(도), 0 = 끔 |
| `camera_fps` / `jpeg_quality` | `30` / `90` | robot 만. 카메라 토픽 주기와 JPEG 품질 (녹화하려면 30 = 데이터셋 fps) |
| `fps` | `60` | 호스트 루프 주기 |
| `spawn_host` / `zmq_host` / `bind` | `true` / `127.0.0.1` / `127.0.0.1` | 호스트를 다른 PC 에서 돌릴 때 (`ros2 run lerobot_bridge host …` + `spawn_host:=false zmq_host:=<IP>`) |

## 로봇 모델 보기 (RViz)

로봇(또는 mock)이 떠 있는 상태에서:

```bash
ros2 run lerobot_description state_publisher
```
```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix lerobot_description)/share/lerobot_description/rviz/bimanual.rviz
```

단팔은 `state_publisher single` + `single.rviz`. 리더 팔 보기, 팔 간격·카메라 옵션은 [lerobot_description/README.md](lerobot_description/README.md).

## 녹화 → 데이터셋 (= `lerobot-record`)

텔레옵이 떠 있는 상태에서:

```bash
ros2 run lerobot_recorder record --ros-args -p experiment_name:=pour_water -p task:="Pick up the cup and pour water"
```

`r` 녹화 시작, `s` 저장, `d` 버리기, `q` 끝내기. 에피소드는 `~/ros_episodes/pour_water/episode_*` 에 쌓인다. 다 모으면 (lerobot env 가 있는 PC 에서):

```bash
ros2 run lerobot_dataset convert ~/ros_episodes/pour_water --repo-id local/pour_water
```

결과는 `lerobot-record` 로 모은 데이터셋과 같은 형식이라 `lerobot-train` 에 바로 넣는다. 자세한 건 [lerobot_recorder](lerobot_recorder/README.md), [lerobot_dataset](lerobot_dataset/README.md).

## lerobot 명령과의 대응

| lerobot | 여기서 | 상태 |
|---|---|---|
| `lerobot-teleoperate` | `robot` + `leader` + `teleop` | ✅ |
| `lerobot-replay` | `robot` + `replay` (데이터셋을 로봇처럼 재생 — 로봇 없이 실제 영상으로 개발) | 다음 |
| `lerobot-rollout` (SmolVLA·ACT 등) | `robot` + `policy` + `safety` | 다음 |
| `lerobot-record` | `robot` + `leader` + `teleop` + `lerobot_recorder` → `lerobot_dataset convert` | ✅ (mock 으로 검증, 실기 전) |
| `lerobot-calibrate`, `lerobot-setup-motors`, `lerobot-train` | lerobot 그대로 | ROS 화하지 않음 |

## 규칙

1. lerobot 을 import 하는 코드는 `lerobot_bridge/hosts/` 에만 둔다.
2. `robot/command` 를 발행하는 노드는 하나뿐이다 (지금 `teleop`, 정책이 붙으면 `safety`).
3. 토픽을 추가·변경하면 `docs/TOPICS.md` 를 먼저 고친다. 단위는 rad.

## 참고 자료

### so101-ros-physical-ai

https://github.com/legalaspro/so101-ros-physical-ai (Apache-2.0)

SO-101 리더·팔로워를 ROS2 로 돌리는 스택. 모터를 lerobot 대신 자체 C++ ros2_control 드라이버로 구동하고,
MoveIt 2·녹화·데이터셋 변환·정책 추론까지 있다. 구조를 그대로 쓰지 않고, 해당 부분을 만들 때 설계를 참고한다.

아래 패키지의 원본 코드가 [`reference/so101-ros-physical-ai/`](reference/so101-ros-physical-ai/) 에 있다 (빌드 제외).
패키지마다 Humble 에서 빌드·실행되는지, 가져다 쓸 때의 절차는 그 폴더 README 에 있다.

우리와 다른 점 (가져올 때 주의):

- Ubuntu 24.04 + ROS2 Jazzy 기준 (우리는 22.04 + Humble)
- 리더 1 + 팔로워 1 만 지원 (우리는 양팔이 기본)
- lerobot 을 모터 구동에 쓰지 않는다 → 관절값 단위·캘리브레이션이 lerobot 데이터셋과 같은지 따로 확인해야 한다
- 수집은 ROS 녹화 → 변환 방식 (우리는 이걸 `lerobot_recorder` / `lerobot_dataset` 으로 옮겼고, `lerobot-record` 도 그대로 쓸 수 있다)

| 그쪽 패키지 | 볼 만한 것 | 우리 쪽 |
|---|---|---|
| `so101_description` | SO-101 URDF/Xacro·메시 | `lerobot_description` 으로 옮김 ✅ |
| `episode_recorder` | MCAP 녹화, 키보드로 시작·저장·버리기 | `lerobot_recorder` 로 옮김 ✅ |
| `rosbag_to_lerobot` | rosbag(MCAP) → LeRobotDataset v3.0 변환 | `lerobot_dataset` 으로 옮김 ✅ |
| `so101_inference`, `policy_server` | ACT·SmolVLA 추론, 원격 GPU 추론 서버 (ZMQ / gRPC) | `policy` |
| `so101_bringup` | ros2_control 설정, 카메라(USB·RealSense) TF 배치 | `lerobot_description`, `lerobot_perception` |
| `so101_moveit_config`, `so101_kinematics` | MoveIt 2 설정, IK | 매니퓰레이션 (MoveIt) |

`reference/` 의 파일은 고치지 않고, 필요한 부분을 우리 패키지로 복사해서 고친다. Apache-2.0 이므로 복사한 곳에 출처를 남긴다.

### 그 밖에

- lerobot 의 `async_inference` (`policy_server.py`, `robot_client.py`): 정책을 원격 GPU 에서 돌리고 로봇 PC 로 행동을 받는 lerobot 자체 구현. `policy` 노드의 기본 재료.
- SO-101 공식 모델 (TheRobotStudio/SO-ARM100, Apache-2.0): MJCF·메시가 `lerobot_sim/models/so101/` 에 들어 있다. URDF 는 `lerobot_description` (위 저장소에서 가져옴, MuJoCo 모델과 같은 자세임을 확인).

## 검증 기록

리그를 연결하지 않은 상태에서 확인한 것:

- `mock:=true` 텔레옵 (robot, leader, teleop) — **lerobot 이 없는 시스템 python 만으로** 관절 토픽 각 ≈60 Hz, 카메라 30 Hz
- 단위: 몸통 ±0.524 rad (= mock ±30°), gripper [-0.175, 1.745] rad (= URDF 범위). 리더→로봇 잔차 0, 지연 최대 17 ms
- Ctrl+C: 노드·호스트 모두 정상 종료. 노드를 SIGKILL 해도 호스트가 따라 종료 (토크 남지 않음)
- 다른 PC 흉내: lerobot env 가 없을 때, 캘리 파일이 없을 때 → Traceback 없이 해결 방법 한 줄로 멈춤 (모터는 열지 않음)
- `rosdep install` 이 모든 의존성을 풀어냄, XML 파일 전부 well-formed, `colcon test` 통과
- 시뮬 장면: 단팔·양팔 모두 MuJoCo 3.8.1 에서 열리고 관절·액추에이터 이름이 토픽 계약과 같음
- 로봇 모델: URDF 와 MuJoCo 장면이 같은 관절값에서 링크 위치 0.002 mm 이내로 같음 (단팔·양팔). mock 로봇 + `state_publisher` 로 TF 가 관절을 따라 움직임
- 녹화·변환: mock 텔레옵을 키보드로 녹화(저장·버리기) → 변환한 데이터셋의 `info.json` 특징 정의가 `lerobot-record` 양팔 데이터셋과 같음. 단위(도·0~100)·영상 색(RGB)·미래 값 미사용 확인

실제 모터로는 아직 안 돌려봄. 첫 실기: `-p arm:=left -p cameras:=false -p max_rel:=20` 부터 ([SETUP.md 6번](docs/SETUP.md#6-로봇-pc-만--lerobot-robotenv-캘리브레이션)).
