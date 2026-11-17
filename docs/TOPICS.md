# 토픽 계약

모든 패키지는 이 문서만 보고 개발한다. 토픽을 **추가·변경할 때는 이 문서를 먼저 고치고**, 코드는
`lerobot_common/lerobot_common/topics.py` 의 상수를 쓴다 (문자열을 직접 쓰지 않는다).

토픽 이름은 전부 상대 이름이다. 기본은 `/robot/...` 이고, `--ros-args -r __ns:=/rig2` 로 통째로 옮길 수 있다.

## 지금 쓰는 토픽

| 토픽 | 타입 | 발행 | 구독 | 주기 |
|---|---|---|---|---|
| `robot/joint_states` | `sensor_msgs/JointState` | `lerobot_bridge robot` (나중에 sim 도) | 누구나 | fps (기본 60) |
| `robot/command` | `sensor_msgs/JointState` | `lerobot_bridge teleop` (나중엔 safety 만) | `lerobot_bridge robot` | 리더 주기 |
| `robot/cam/<name>/image/compressed` | `sensor_msgs/CompressedImage` (jpeg) | `lerobot_bridge robot` | 누구나 | 15 (`camera_fps`) |
| `leader/joint_states` | `sensor_msgs/JointState` | `lerobot_bridge leader` | `teleop` | fps (기본 60) |
| `template/max_joint_speed` | `std_msgs/Float64` | `lerobot_template joint_speed` | — | 관절 상태 주기 |

카메라 `<name>`: 양팔 `top`, `left_wrist`, `right_wrist` / 단팔 `wrist`. 해상도 top 640×480, 손목 320×240 (학습 데이터와 같음).

## 관절 이름과 단위

**이름** = lerobot 모터 이름. 순서도 lerobot 데이터셋(`observation.state`, `action`)과 같다.

| | 이름 (순서대로) |
|---|---|
| 양팔 (12) | `left_shoulder_pan, left_shoulder_lift, left_elbow_flex, left_wrist_flex, left_wrist_roll, left_gripper, right_…` |
| 단팔 (6) | `shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper` |

**단위** = 전부 **rad**, SO-101 URDF/MJCF (`so101_new_calib`) 관절각과 같다. 그래서 RViz·MuJoCo 에 변환 없이 넣는다.

| 관절 | 토픽 (rad) | lerobot / 데이터셋 |
|---|---|---|
| 몸통 5개 | `deg2rad(도)` | 도 |
| gripper | `-0.1745 + (값/100) × 1.9199` (URDF 범위 [-0.1745, 1.7453]) | 0~100 |

lerobot 단위가 필요한 곳(정책 입력, 데이터셋)에서만 `lerobot_common.units.from_rad` 로 되돌린다.
`JointState` 는 `name`, `position` 만 채운다 (`velocity`/`effort` 없음 — Feetech 버스에서 안 읽음).

## QoS

| 할 일 | QoS (`lerobot_common.qos`) |
|---|---|
| 스트림 발행 (관절·명령·이미지) | `PUB_STREAM` — RELIABLE, depth 5 |
| 스트림 구독 | `SUB_STREAM` — BEST_EFFORT, depth 5 |
| 드문 이벤트 (비상정지, 음성 명령) 발행·구독 | `EVENT` — RELIABLE, depth 10 |

발행 RELIABLE + 구독 BEST_EFFORT 면 어떤 조합도 연결된다. RViz, `robot_state_publisher`, `rqt_image_view` 같은 표준 도구(기본 RELIABLE 구독)도 그대로 받는다.

## 예약 (이름만 고정, 아직 발행하는 노드 없음)

| 토픽 | 타입 | 누가 | 용도 |
|---|---|---|---|
| `policy/action` | `sensor_msgs/JointState` (rad) | policy → safety | 정책 출력. 로봇에 직접 보내지 않는다 |
| `task/instruction` | `std_msgs/String` | task/operator/speech → policy | SmolVLA 지시문 |
| `safety/estop` | `std_msgs/Bool` (EVENT) | operator, speech → safety | 비상정지 |
| `speech/command` | `std_msgs/String` (EVENT) | speech | 인식한 명령 |
| `speech/say` | `std_msgs/String` (EVENT) | 누구나 → speech | 읽을 문구 |
| `perception/objects` | 미정 | perception | 인식 노드를 만들 때 타입을 정해 이 표에 적는다 |

## 규칙

1. `robot/command` 를 발행하는 노드는 한 번에 하나다. 지금은 `teleop`, 정책이 붙으면 `safety` 만 발행한다.
2. 새 토픽은 이 표에 먼저 적고, `topics.py` 에 상수를 추가한다.
3. 단위는 rad. 도나 0~100 을 토픽에 싣지 않는다.
