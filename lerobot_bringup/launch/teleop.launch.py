"""텔레옵 한 번에 — robot + leader + teleop (+ RViz, + 녹화 노드).

    ros2 launch lerobot_bringup teleop.launch.py                          # 양팔
    ros2 launch lerobot_bringup teleop.launch.py arm:=left max_rel:=20 cameras:=false   # 왼팔만, 처음 붙일 때
    ros2 launch lerobot_bringup teleop.launch.py mock:=true rviz:=true    # 로봇 없이, RViz 까지
    ros2 launch lerobot_bringup teleop.launch.py record:=true experiment_name:=pour_water task:="Pick up the cup"
        → 다른 터미널에서  ros2 run lerobot_recorder keyboard   (r 시작, s 저장, d 버리기)

인자:
    arm             bi | left | right                (기본 bi)
    mock            true 면 하드웨어·lerobot 없이     (기본 false)
    cameras         false 면 카메라 없이              (기본 true)
    max_rel         스텝당 최대 변화(도), 0 = 끔       (기본 0. 처음 붙일 땐 20)
    teleop_enabled  false 면 teleop 을 멈춘 채로 시작 (기본 true)
                    → 리더 자세를 맞춘 뒤  ros2 param set /teleop enabled true
    rviz            true 면 로봇 모델 + RViz          (기본 false)
    record          true 면 녹화 노드(recorder)도     (기본 false). 키보드는 따로: ros2 run lerobot_recorder keyboard
    experiment_name, task   record 일 때 녹화 노드에 넘김

ros2 run 으로 하나씩 띄우는 것과 같은 노드다 (README 의 "텔레옵" 참고). 끌 때는 Ctrl+C 한 번 — 모든 노드가 같이 꺼지고,
robot 이 꺼지면 토크가 꺼지니 팔을 받칠 것.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

ARGS = {
    "arm": "bi",
    "mock": "false",
    "cameras": "true",
    "max_rel": "0",
    "teleop_enabled": "true",
    "rviz": "false",
    "record": "false",
    "experiment_name": "",
    "task": "",
}


def _true(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "yes", "on")


def model_nodes(arm: str) -> list:
    """robot/joint_states → TF (robot_state_publisher) + RViz. view.launch.py 와 같은 내용."""
    model, rviz_cfg = ("bimanual", "bimanual.rviz") if arm == "bi" else ("single", "single.rviz")
    share = FindPackageShare("lerobot_description")
    urdf = Command(["xacro ", share, f"/urdf/so101_{model}.urdf.xacro"])
    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"robot_description": ParameterValue(urdf, value_type=str)}],
            remappings=[("joint_states", "robot/joint_states")],
            output="log",
        ),
        Node(
            package="rviz2", executable="rviz2", arguments=["-d", [share, f"/rviz/{rviz_cfg}"]], output="log"
        ),
    ]


def _setup(context):
    a = {k: LaunchConfiguration(k).perform(context) for k in ARGS}
    arm, mock = a["arm"], _true(a["mock"])
    nodes = [
        Node(
            package="lerobot_bridge",
            executable="robot",
            parameters=[
                {
                    "arm": arm,
                    "mock": mock,
                    "cameras": _true(a["cameras"]),
                    "max_rel": float(a["max_rel"]),
                }
            ],  # fmt: skip
            output="screen",
            emulate_tty=True,
        ),
        Node(
            package="lerobot_bridge",
            executable="leader",
            parameters=[{"arm": arm, "mock": mock}],
            output="screen",
            emulate_tty=True,
        ),
        Node(
            package="lerobot_bridge",
            executable="teleop",
            parameters=[{"enabled": _true(a["teleop_enabled"])}],
            output="screen",
            emulate_tty=True,
        ),
    ]
    if _true(a["rviz"]):
        nodes += model_nodes(arm)
    if _true(a["record"]):
        params = {
            k: a[k] for k in ("experiment_name", "task") if a[k]
        }  # 빈 값은 넘기지 않는다 (recorder 기본값)
        # 노드 이름은 그대로 둔다 — keyboard 가 /episode_recorder 로 찾는다
        nodes.append(
            Node(package="lerobot_recorder", executable="recorder", parameters=[params], output="screen")
        )
    return nodes


def generate_launch_description():
    return LaunchDescription([
        # conda(base) 가 켜진 셸에서 띄워도 rviz 같은 python 도구가 시스템 python 을 쓰게
        SetEnvironmentVariable("PATH", "/usr/bin:" + os.environ.get("PATH", "")),
        *[DeclareLaunchArgument(k, default_value=v) for k, v in ARGS.items()],
        OpaqueFunction(function=_setup),
    ])  # fmt: skip
