"""로봇 모델 + RViz 만 — 이미 떠 있는 로봇(또는 리더)을 볼 때.

    ros2 launch lerobot_bringup view.launch.py                  # 팔로워 양팔 (robot/joint_states)
    ros2 launch lerobot_bringup view.launch.py arm:=left        # 팔로워 단팔
    ros2 launch lerobot_bringup view.launch.py who:=leader      # 리더 양팔 (leader/joint_states)

인자:
    arm   bi | left | right       (기본 bi. left/right 는 단팔 모델)
    who   robot | leader          (기본 robot)

리더를 볼 때는 TF 이름 앞에 leader/ 를 붙여 팔로워와 섞이지 않게 하고, RViz 도 그에 맞춘 설정
(rviz/bimanual_leader.rviz: Fixed Frame leader/world, TF Prefix leader)으로 연다. 두 개를 같이 띄워도 된다.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _setup(context):
    arm = LaunchConfiguration("arm").perform(context)
    who = LaunchConfiguration("who").perform(context)
    if arm not in ("bi", "left", "right") or who not in ("robot", "leader"):
        raise RuntimeError(f"arm 은 bi|left|right, who 는 robot|leader (받은 값: arm={arm}, who={who})")
    model = "bimanual" if arm == "bi" else "single"
    share = FindPackageShare("lerobot_description")
    xacro_args = " variant:=leader" if who == "leader" else ""
    urdf = Command(["xacro ", share, f"/urdf/so101_{model}.urdf.xacro{xacro_args}"])
    rsp_params = {"robot_description": ParameterValue(urdf, value_type=str)}

    if who == "robot":
        rviz_cfg = "bimanual.rviz" if arm == "bi" else "single.rviz"
        return [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[rsp_params],
                remappings=[("joint_states", "robot/joint_states")],
                output="log",
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", [share, f"/rviz/{rviz_cfg}"]],
                output="log",
            ),
        ]

    # 리더: /leader 네임스페이스, TF 이름 앞에 leader/
    if arm != "bi":
        raise RuntimeError("리더 보기는 지금 양팔(arm:=bi)만 RViz 설정이 있다")
    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            namespace="leader",
            parameters=[rsp_params, {"frame_prefix": "leader/"}],
            remappings=[("joint_states", "/leader/joint_states")],  # 네임스페이스 안이므로 절대 이름
            output="log",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz_leader",
            arguments=["-d", [share, "/rviz/bimanual_leader.rviz"]],
            output="log",
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        SetEnvironmentVariable("PATH", "/usr/bin:" + os.environ.get("PATH", "")),
        DeclareLaunchArgument("arm", default_value="bi"),
        DeclareLaunchArgument("who", default_value="robot"),
        OpaqueFunction(function=_setup),
    ])  # fmt: skip
