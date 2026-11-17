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
└── lerobot_sim/              MuJoCo 장면 (SO-101 단팔·양팔, 이름·단위가 토픽 계약과 같음). 노드는 시뮬 담당
```

앞으로 붙을 패키지 (각자 `lerobot_template` 을 복사해서 시작, [CONTRIBUTING.md](docs/CONTRIBUTING.md)):

| 패키지 | 담당 | 내용 |
|---|---|---|
| `lerobot_sim` | 시뮬 | 장면은 있음. `robot/joint_states`·카메라를 내고 `robot/command` 를 받는 노드 ([lerobot_sim/README.md](lerobot_sim/README.md)) |
| `lerobot_description` | 모델링 | SO-101 URDF·메시·RViz 설정, `robot_state_publisher` |
| `lerobot_perception` | 비전 | 카메라 토픽 → 물체 인식 결과 |
| `lerobot_speech` | 음성 | STT → `speech/command`, `speech/say` → TTS |
| `lerobot_safety` | 기본 틀 | 정책과 로봇 사이 안전 게이트 (스텝 제한, 비상정지) |
| `lerobot_task` / `lerobot_operator` / `lerobot_interfaces` | 기본 틀 | 과제 흐름·성공 판정 / 시작·정지 입력 / 커스텀 메시지 |

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
| `fps` | `60` | 호스트 루프 주기 |
| `spawn_host` / `zmq_host` / `bind` | `true` / `127.0.0.1` / `127.0.0.1` | 호스트를 다른 PC 에서 돌릴 때 (`ros2 run lerobot_bridge host …` + `spawn_host:=false zmq_host:=<IP>`) |

## lerobot 명령과의 대응

| lerobot | 여기서 | 상태 |
|---|---|---|
| `lerobot-teleoperate` | `robot` + `leader` + `teleop` | ✅ |
| `lerobot-replay` | `robot` + `replay` (데이터셋을 로봇처럼 재생 — 로봇 없이 실제 영상으로 개발) | 다음 |
| `lerobot-rollout` (SmolVLA·ACT 등) | `robot` + `policy` + `safety` | 다음 |
| `lerobot-record` | `robot` + `leader` + `teleop` + `record` | 마지막 (수집은 당분간 `lerobot-record` 그대로) |
| `lerobot-calibrate`, `lerobot-setup-motors`, `lerobot-train` | lerobot 그대로 | ROS 화하지 않음 |

## 규칙

1. lerobot 을 import 하는 코드는 `lerobot_bridge/hosts/` 에만 둔다.
2. `robot/command` 를 발행하는 노드는 하나뿐이다 (지금 `teleop`, 정책이 붙으면 `safety`).
3. 토픽을 추가·변경하면 `docs/TOPICS.md` 를 먼저 고친다. 단위는 rad.

## 검증 기록

2026-11-17, 리그 미연결 상태에서:

- `mock:=true` 텔레옵 (robot, leader, teleop) — **lerobot 이 없는 시스템 python 만으로** 관절 토픽 각 ≈60 Hz, 카메라 15 Hz
- 단위: 몸통 ±0.524 rad (= mock ±30°), gripper [-0.175, 1.745] rad (= URDF 범위). 리더→로봇 잔차 0, 지연 최대 17 ms
- Ctrl+C: 노드·호스트 모두 정상 종료. 노드를 SIGKILL 해도 호스트가 따라 종료 (토크 남지 않음)
- 다른 PC 흉내: lerobot env 가 없을 때, 캘리 파일이 없을 때 → Traceback 없이 해결 방법 한 줄로 멈춤 (모터는 열지 않음)
- `rosdep install` 이 모든 의존성을 풀어냄, XML 파일 전부 well-formed, `colcon test` 통과
- 시뮬 장면: 단팔·양팔 모두 MuJoCo 3.8.1 에서 열리고 관절·액추에이터 이름이 토픽 계약과 같음

실제 모터로는 아직 안 돌려봄. 첫 실기: `-p arm:=left -p cameras:=false -p max_rel:=20` 부터 ([SETUP.md 6번](docs/SETUP.md#6-로봇-pc-만--lerobot-robotenv-캘리브레이션)).
