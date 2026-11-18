# lerobot_description — SO-101 로봇 모델 (URDF·메시·RViz)

SO-101 단팔·양팔 URDF(xacro), 메시, 카메라 프레임, RViz 설정. `robot/joint_states` 를 받아 TF 를 내고 RViz 에 팔을 그린다.

```
lerobot_description/
├── urdf/
│   ├── so101_bimanual.urdf.xacro    양팔 (world → left_/right_ 접두사 팔 두 대 + 카메라 프레임)
│   ├── so101_single.urdf.xacro      단팔 (base_link 부터, 접두사 없음)
│   ├── so101_arm_common.xacro       어깨~손목 (원본 + prefix)
│   ├── end_effectors/               손끝: follower(집게) / leader(손잡이·방아쇠) (원본 + prefix)
│   ├── so101_cameras.xacro          카메라 프레임 매크로
│   └── so101_macros.xacro, so101_materials.xacro
├── meshes/                          STL 16개
├── rviz/                            bimanual.rviz (world), single.rviz (base_link), bimanual_leader.rviz (리더 팔 보기)
└── lerobot_description/state_publisher.py   xacro → robot_state_publisher 실행
```

## 실행

로봇(또는 mock)이 떠 있는 상태에서 터미널 2개:

```bash
ros2 run lerobot_description state_publisher
```
```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix lerobot_description)/share/lerobot_description/rviz/bimanual.rviz
```

로봇 없이 보려면 먼저 `ros2 run lerobot_bridge robot --ros-args -p mock:=true` (mock 팔이 움직이는 걸 보려면 `leader`, `teleop` 도).

| 하고 싶은 것 | 명령 |
|---|---|
| 단팔 | `ros2 run lerobot_description state_publisher single` (RViz 는 `single.rviz`) |
| 팔 간격 바꾸기 | `ros2 run lerobot_description state_publisher bimanual spacing:=0.5` |
| 카메라 프레임 빼기 | `… cameras:=false` |
| 리더 팔 보기 | `ros2 run lerobot_description state_publisher bimanual variant:=leader topic:=/leader/joint_states --ros-args -r __ns:=/leader -p frame_prefix:=leader/` 후 RViz 는 `bimanual_leader.rviz` (아래) |
| URDF 만 보기 | `xacro $(ros2 pkg prefix lerobot_description)/share/lerobot_description/urdf/so101_bimanual.urdf.xacro` |

리더 팔 RViz:

```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix lerobot_description)/share/lerobot_description/rviz/bimanual_leader.rviz
```

리더 모델은 TF 이름 앞에 `leader/` 를 붙여 내므로(`frame_prefix`), RViz 쪽도 Fixed Frame `leader/world`,
RobotModel 의 Description Topic `/leader/robot_description`, **TF Prefix `leader`** 세 가지를 맞춰야 한다 — `bimanual_leader.rviz` 에 들어 있다.
TF Prefix 가 비어 있으면 RobotModel 이 접두사 없는 링크(`left_base_link`)를 찾다가 Status Error 가 나고 팔이 하얗게 멈춰 보인다.

`state_publisher` 는 URDF 를 만들어 표준 `robot_state_publisher` 에 넘겨 주기만 한다.
(URDF XML 을 `ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(xacro …)"` 처럼
명령줄로 넘기면 ROS 가 YAML 로 읽다가 실패한다 — 그래서 파라미터 파일로 넘긴다.)

## 토픽 계약과의 관계

- **관절 이름** = 토픽 계약. 양팔 `left_shoulder_pan … right_gripper`, 단팔 접두사 없음.
- **관절값** = `robot/joint_states` 의 rad 그대로. lerobot 0도 = 관절 범위 중앙 (new calibration).
- **lerobot_sim 과 같은 모델이다.** 같은 관절값에서 단팔·양팔 모두 링크 위치가 MuJoCo 장면과 0.002 mm 안에서 같다.
- **카메라**: `<name>_camera_link`, `<name>_camera_optical_frame` (`top`, `left_wrist`, `right_wrist` / 단팔 `top`, `wrist`).
  robot 노드가 내는 이미지의 `frame_id` 가 이 optical frame 이다. **카메라 위치·방향은 실측값이 아니다** — 리그를 재서
  `so101_bimanual.urdf.xacro` / `so101_single.urdf.xacro` 의 `so101_camera` 줄을 고칠 것.
- **양팔 배치**: 1자, 받침 사이 `spacing` (기본 0.45 m, 실측 아님) — `lerobot_sim/models/bimanual.xml` 과 같게 유지할 것.

## 출처

[legalaspro/so101-ros-physical-ai](https://github.com/legalaspro/so101-ros-physical-ai) 의 `so101_description`
(Apache-2.0, 커밋 58318c9, 저작자 Dmitri Manajev) 에서 가져와 고쳤다. 라이선스 원문은 [`LICENSE`](LICENSE).
바꾼 파일은 각 파일 머리에 원본 경로와 변경 내용을 적었다. 요약:

- 링크·관절 이름에 `prefix` 매개변수 추가 (양팔용 `left_` / `right_`). 접두사가 없으면 원본과 구조·수치가 같다 (검증함)
- 카메라 매크로를 이름을 받는 하나로 합치고, 손목 카메라를 움직이는 집게가 아니라 손목(`gripper_link`)에 붙임
- 원본의 정의되지 않은 `${actuator_prefix}` 를 쓰던 gripper 전동 이름을 `motor6` 으로
- 새로 쓴 것: `so101_bimanual.urdf.xacro`, `so101_single.urdf.xacro`, `state_publisher.py`. 원본 ros2_control xacro, launch 는 가져오지 않았다
- RViz 설정은 원본 `display.rviz` 에서 Fixed Frame 만 바꿨다
