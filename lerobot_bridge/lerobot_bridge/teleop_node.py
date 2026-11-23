"""teleop 노드 — 리더 관절 상태를 그대로 로봇 명령으로 넘긴다.

    leader/joint_states  ──▶ [teleop] ──▶  robot/command

lerobot-teleoperate 의 루프(teleop.get_action → robot.send_action)를 ROS 로 나눈 것이다.
리더와 로봇이 같은 관절 이름을 써야 한다 (둘 다 arm:=bi 거나 둘 다 같은 단팔).

    ros2 run lerobot_bridge teleop
    ros2 param set /teleop enabled false     # 잠깐 멈춤 (로봇은 마지막 목표에서 멈춰 있다)

주의: 시작하는 순간 로봇이 리더 자세로 한 번에 움직인다. 리더를 로봇과 비슷한 자세로 두고 켤 것.
(시작 자세 검사·스텝 제한 같은 안전 장치는 나중에 lerobot_safety 가 맡는다)
"""

import contextlib
import signal

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState

from lerobot_common import qos, topics


class Teleop(Node):
    def __init__(self):
        super().__init__("teleop")
        self.enabled = self.declare_parameter("enabled", True).value
        self.add_on_set_parameters_callback(self._on_params)

        self.pub = self.create_publisher(JointState, topics.ROBOT_COMMAND, qos.PUB_STREAM)
        self.create_subscription(JointState, topics.LEADER_JOINT_STATES, self._on_leader, qos.SUB_STREAM)
        self.n_sent = 0
        self.get_logger().info(
            f"{topics.LEADER_JOINT_STATES} → {topics.ROBOT_COMMAND} (enabled={self.enabled})"
        )

    def _on_leader(self, msg: JointState):
        if not self.enabled:
            return
        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.name = list(msg.name)
        cmd.position = list(msg.position)
        self.pub.publish(cmd)
        self.n_sent += 1
        if self.n_sent == 1:
            self.get_logger().info(f"텔레옵 시작: 관절 {len(cmd.name)}개")

    def _on_params(self, params) -> SetParametersResult:
        for prm in params:
            if prm.name == "enabled":
                self.enabled = bool(prm.value)
                self.get_logger().info("텔레옵 " + ("켬" if self.enabled else "멈춤"))
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    node = Teleop()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # launch 에서 Ctrl+C 하면 SIGINT 가 두 번 온다 (터미널 + launch). 정리하는 동안 두 번째는 무시
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        with contextlib.suppress(Exception):
            node.destroy_node()
        with contextlib.suppress(Exception):
            rclpy.try_shutdown()


if __name__ == "__main__":
    main()
