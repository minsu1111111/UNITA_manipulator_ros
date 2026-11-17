"""`ros2 run lerobot_description state_publisher` — xacro 로 URDF 를 만들어 표준 robot_state_publisher 를 띄운다.

robot_state_publisher 는 URDF 를 파라미터(robot_description)로 받는데, URDF XML 을 명령줄 `-p` 로 넘기면
ROS 가 YAML 로 읽다가 실패한다. 그래서 파라미터 파일에 담아 넘겨 주는 일만 한다 (노드 자체는 표준 robot_state_publisher).

    ros2 run lerobot_description state_publisher                       # 양팔, robot/joint_states → TF
    ros2 run lerobot_description state_publisher single                # 단팔
    ros2 run lerobot_description state_publisher bimanual spacing:=0.5 cameras:=false
    ros2 run lerobot_description state_publisher bimanual variant:=leader topic:=/leader/joint_states \
        --ros-args -r __ns:=/leader -p frame_prefix:=leader/              # 리더 팔 (RViz Fixed Frame: leader/world)

인자:
    모델            bimanual (기본) | single
    이름:=값        xacro 인자 (variant, spacing, cameras — urdf/*.urdf.xacro 머리 주석 참고)
    topic:=이름     관절 상태 토픽 (기본 robot/joint_states). __ns 로 네임스페이스를 주면 / 로 시작하는 절대 이름을 쓸 것
    --ros-args …    그대로 robot_state_publisher 에 넘긴다
"""

import os
import sys
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_prefix, get_package_share_directory

MODELS = {"bimanual": "so101_bimanual.urdf.xacro", "single": "so101_single.urdf.xacro"}


def main():
    argv = sys.argv[1:]
    ros_args = []
    if "--ros-args" in argv:
        i = argv.index("--ros-args")
        argv, ros_args = argv[:i], argv[i + 1 :]

    model = "bimanual"
    if argv and ":=" not in argv[0]:
        model = argv.pop(0)
    if model not in MODELS:
        sys.exit(f"모델은 {list(MODELS)} 중 하나 (받은 값: {model!r})")
    mappings = dict(a.split(":=", 1) for a in argv)
    topic = mappings.pop("topic", "robot/joint_states")

    import xacro  # ROS 의 xacro 패키지 (python 모듈)

    path = os.path.join(get_package_share_directory("lerobot_description"), "urdf", MODELS[model])
    given = dict(mappings)  # xacro 가 기본값을 채워 넣으므로 사용자가 준 것만 따로 둔다
    urdf = xacro.process_file(path, mappings=mappings).toxml()

    # 실행할 때마다 덮어쓴다. "/**" 키라 노드 이름·네임스페이스를 바꿔도 적용된다
    params = Path.home() / ".ros" / "lerobot_description" / f"{model}.yaml"
    params.parent.mkdir(parents=True, exist_ok=True)
    params.write_text(yaml.safe_dump({"/**": {"ros__parameters": {"robot_description": urdf}}}))

    exe = os.path.join(
        get_package_prefix("robot_state_publisher"), "lib", "robot_state_publisher", "robot_state_publisher"
    )
    # 사용자가 준 --ros-args 를 먼저 둔다 (같은 이름의 리맵은 앞의 것이 이긴다)
    cmd = [exe, "--ros-args", *ros_args, "--params-file", str(params), "-r", f"joint_states:={topic}"]
    print(f"[state_publisher] {model} ({MODELS[model]}, {given or '기본 인자'}) ← {topic}", flush=True)
    os.execv(exe, cmd)


if __name__ == "__main__":
    main()
