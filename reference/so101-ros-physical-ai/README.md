# so101-ros-physical-ai (참고용 원본 코드)

- 출처: https://github.com/legalaspro/so101-ros-physical-ai
- 커밋: `58318c905a2c61289fa907de85cb8473322fbe68` (2026-05-11)
- 저작자: Dmitri Manajev
- 라이선스: Apache License 2.0 — 원문은 이 폴더의 [`LICENSE`](LICENSE)

SO-101 리더·팔로워를 ROS2 로 돌리는 스택에서 우리에게 참고가 될 패키지만 가져왔다.
**빌드에 들어가지 않는다** (`reference/COLCON_IGNORE`). 쓸 때는 필요한 부분을 우리 패키지로 옮겨서 고치고, 옮긴 것은 여기서 지운다.

이미 옮긴 것:

| 원본 | 우리 패키지 |
|---|---|
| `so101_description` | [`lerobot_description`](../../lerobot_description/) (양팔용 prefix, 카메라 프레임, `state_publisher`) |
| `episode_recorder` | [`lerobot_recorder`](../../lerobot_recorder/) (`ros2 run` 으로 바로 활성화, 기본 토픽·카메라 자동 탐색) |
| `rosbag_to_lerobot` | [`lerobot_dataset`](../../lerobot_dataset/) (ROS 읽기 / lerobot 쓰기 분리, lerobot-record 와 같은 형식) |

## 원본에서 바꾼 것

- 남아 있는 파일은 원본 그대로다.
- 옮긴 패키지에서 바꾼 내용은 그 패키지 README 의 "출처" 절에 있다.
- 가져오지 않은 것: `feetech_ros2_driver` (서브모듈, C++ 모터 드라이버), `so101_teleop`, `so101_camera_calibration`, `docs/`, `scripts/`, pixi 설정.

## 원본과 우리의 차이

| | 원본 | 우리 |
|---|---|---|
| OS / ROS | Ubuntu 24.04 + Jazzy (Python 3.12) | Ubuntu 22.04 + Humble (Python 3.10) |
| 모터 구동 | 자체 C++ ros2_control 드라이버 | lerobot 그대로 (`lerobot_bridge`) |
| 팔 구성 | 리더 1 + 팔로워 1 | 양팔 기본, 단팔도 |
| ROS 노드 안에서 lerobot | import 한다 (Jazzy 는 같은 Python 3.12) | 못 한다 → 호스트를 따로 띄워 ZMQ 로 잇는다 |
| 실행 | launch 파일 | `ros2 run` |

## 패키지별 상태

Humble(이 저장소 기준 PC)에서 확인한 것만 적었다. "빌드" 는 Humble 워크스페이스에서 `colcon build` 가 통과했다는 뜻이다.

| 패키지 | 내용 | Humble | 우리 쪽에서 쓸 곳 |
|---|---|---|---|
| `so101_bringup` | ros2_control 컨트롤러 설정, 카메라(USB·RealSense 등) 설정과 TF 배치, 녹화 설정, launch 모음 | 빌드 ✅. launch 대부분이 `feetech_ros2_driver` 를 띄우므로 그대로는 실행 안 됨 | 카메라 설정·TF 배치 (`config/cameras`, `launch/camera_tf.launch.py`, `launch/layout_tf.launch.py`) |
| `so101_moveit_config` | MoveIt 2 설정 (SRDF, OMPL, 관절 제한, 컨트롤러) | 빌드 ✅. 실행에 `moveit_py`, `pick_ik` 필요 — 이 PC 의 Humble 에 없음 | MoveIt 연습 |
| `so101_kinematics` (+ `so101_kinematics_msgs`) | IK 제어, 직교 좌표 이동, 궤적 실행 노드 | 빌드 ✅. 실행에 `robokin`, `viser` (pip) 와 `so101_bringup` 필요 | IK 연습 |
| `so101_inference` | ACT·SmolVLA 추론 노드 (동기), 원격 서버에 붙는 비동기 클라이언트 (ZMQ·gRPC) | 빌드 ✅. ROS 노드 안에서 lerobot 을 import 하므로 Humble 에서는 그대로 못 돈다 | `policy` 노드 설계 — 우리 구조에선 lerobot 부분을 호스트로 분리 |
| `policy_server` | 원격 GPU 에서 lerobot 정책을 띄워 ZMQ·gRPC 로 행동을 주는 서버 (ROS 아님) | 의존성: torch·pyzmq·grpcio 는 우리 lerobot env 에 있고 `msgpack` 만 없음. 실행은 확인 안 함 | `policy` — 원격 GPU 추론 쪽 |

## 가져다 쓸 때

1. 이 폴더의 파일을 고치지 말고, 우리 패키지로 복사해서 고친다 (원본은 비교용으로 남긴다).
2. 복사한 파일 머리나 그 패키지 README 에 출처를 남긴다. 예:
   `원본: legalaspro/so101-ros-physical-ai (Apache-2.0), so101_description/urdf/so101_arm.urdf.xacro 에서 가져와 수정`
3. 토픽 이름·단위는 우리 계약(`docs/TOPICS.md`)으로 바꾼다. 원본 토픽(`/follower/joint_states` 등)과 다르다.
4. lerobot 을 import 하는 코드는 `lerobot_bridge/hosts/` 쪽으로 옮긴다 (우리 규칙 1).
