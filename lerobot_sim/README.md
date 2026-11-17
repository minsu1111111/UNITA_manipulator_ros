# lerobot_sim — MuJoCo 시뮬

지금 있는 것은 **로봇팔을 불러오는 장면 파일**뿐이다. 노드(코드)는 아직 없다.

```
lerobot_sim/
├── models/
│   ├── bimanual.xml          양팔 장면: 테이블 + SO-101 두 대 (left_ / right_) + 고정 카메라 front/top/side
│   ├── single_arm.xml        단팔 장면: 테이블 + SO-101 한 대 (접두사 없음) + 카메라 front/top
│   └── so101/                공식 SO-101 MJCF + 메시 (수정 금지, 출처는 so101/README.md)
├── lerobot_sim/              노드를 여기에 만든다 (지금은 비어 있음)
├── package.xml, setup.py     models/ 를 share/lerobot_sim/models/ 로 설치
└── README.md
```

## 장면 보기

시스템 python 에 MuJoCo 를 깔고 (`docs/SETUP.md` 7번, conda 꺼진 터미널):

```bash
python3 -m pip install --user mujoco
```
```bash
python3 -m mujoco.viewer --mjcf="$(ros2 pkg prefix lerobot_sim)/share/lerobot_sim/models/bimanual.xml"
```

단팔은 `single_arm.xml`.

창 오른쪽 Control 패널의 슬라이더로 관절을 움직여 볼 수 있다.

## 이미 맞춰 둔 것

- **관절·액추에이터 이름 = 토픽 계약.** 양팔은 `left_shoulder_pan … right_gripper` 12개, 단팔은 접두사 없는 6개 (`docs/TOPICS.md`).
- **단위 = 토픽 단위.** MuJoCo 관절값(rad)이 `robot/joint_states` 의 rad 와 같은 값이다. 변환 없이 넣고 뺀다.
  그리퍼 범위 [-0.1745, 1.7453] rad 도 `lerobot_common.units` 와 같다.
- **양팔 배치**: 1자 — 두 팔이 같은 방향(정면 +x)을 보고 나란히, 받침 사이 0.45 m (간격은 실측 아님).
  실제 리그를 재면 `bimanual.xml` 의 `left_mount` / `right_mount` frame 의 `pos`(간격)·`euler`(회전)만 고친다.

## 할 일

1. **장면 다듬기** — 실제 리그를 재서 팔 배치, 테이블, 카메라 위치를 맞춘다. 소품(블록·컵)을 추가한다.
2. **시뮬 노드** — `lerobot_bridge robot` 노드 자리를 대신한다. 같은 토픽만 쓰면 나머지 노드는 실기인지 시뮬인지 모른다.

   | 방향 | 토픽 | 할 일 |
   |---|---|---|
   | 구독 | `robot/command` (JointState, rad) | 위치 액추에이터 목표(`data.ctrl`)로 |
   | 발행 | `robot/joint_states` (JointState, rad) | 관절값(`data.qpos`) |
   | 발행 | `robot/cam/<name>/image/compressed` | 렌더링 (2단계) |

   토픽 이름·QoS 는 `lerobot_common.topics` / `lerobot_common.qos` 를 쓴다. 장면 경로는
   `get_package_share_directory("lerobot_sim") + "/models/bimanual.xml"`.
3. **확인** — `leader` + `teleop` 노드를 같이 띄워 리더(또는 mock 리더)를 움직이면 시뮬 팔이 따라오는지.

시작 전에 알아둘 것:

- 시뮬 노드는 ROS 노드라 **시스템 python(3.10)** 에서 돈다. MuJoCo 도 거기에 깐다 (위 명령). lerobot env 는 필요 없다.
  MuJoCo 는 apt 패키지가 없어 `rosdep` 으로 깔리지 않는다 — 노드를 만들면 이 README 에 설치 명령을 꼭 남길 것.
- 손목 카메라는 MJCF 에 없다. 손목에 `<camera>` 를 직접 달아야 한다.
- 실제 영상으로 학습한 정책은 렌더링 영상에서 제대로 동작하지 않는다. 시뮬 영상은 시뮬에서 모은 데이터로 학습한 정책에만 의미가 있다.
- 기본 게인(`kp=998`)은 실제 모터보다 훨씬 빠르게 따라간다. 실기와 비슷하게 보려면 `so101/README.md` 참고.
