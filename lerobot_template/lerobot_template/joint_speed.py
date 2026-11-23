"""예제 노드 — 새 패키지를 만들 때 이 파일을 복사해서 시작한다.

하는 일: 로봇 관절 상태를 받아 가장 빠른 관절의 속도(rad/s)를 발행하고, 너무 빠르면 경고한다.

    robot/joint_states  ──▶ [joint_speed] ──▶  template/max_joint_speed  (std_msgs/Float64)

실행 (로봇 없이: 다른 터미널에서 `ros2 run lerobot_bridge robot --ros-args -p mock:=true`):
    ros2 run lerobot_template joint_speed
    ros2 run lerobot_template joint_speed --ros-args -p warn_speed:=1.5
    ros2 topic echo /template/max_joint_speed

이 파일에서 볼 것:
  - 토픽 이름·QoS 는 직접 쓰지 않고 lerobot_common 에서 가져온다
  - 계산(max_speed)은 ROS 와 떼어 놓은 순수 함수 → test/ 에서 ROS 없이 테스트한다
  - 파라미터는 declare_parameter 로 선언하고 --ros-args -p 로 바꾼다
"""

import contextlib
import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

from lerobot_common import qos, topics
from lerobot_common.names import is_gripper

OUT_TOPIC = "template/max_joint_speed"  # 새 토픽은 docs/TOPICS.md 에 먼저 적는다


def max_speed(prev: dict[str, float], cur: dict[str, float], dt: float) -> float:
    """두 관절 상태 사이 가장 빠른 관절 속도 (rad/s). 그리퍼는 뺀다. dt<=0 이면 0."""
    if dt <= 0:
        return 0.0
    speeds = [abs(cur[n] - prev[n]) / dt for n in cur if n in prev and not is_gripper(n)]
    return max(speeds, default=0.0)


class JointSpeed(Node):
    def __init__(self):
        super().__init__("joint_speed")
        self.warn_speed = self.declare_parameter("warn_speed", 3.0).value  # rad/s

        self.pub = self.create_publisher(Float64, OUT_TOPIC, qos.PUB_STREAM)
        self.create_subscription(JointState, topics.ROBOT_JOINT_STATES, self._on_joints, qos.SUB_STREAM)
        self.prev: dict[str, float] | None = None
        self.prev_t = 0.0
        self.get_logger().info(
            f"{topics.ROBOT_JOINT_STATES} → {OUT_TOPIC} (warn_speed={self.warn_speed} rad/s)"
        )

    def _on_joints(self, msg: JointState):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        cur = dict(zip(msg.name, msg.position))
        if self.prev is not None:
            speed = max_speed(self.prev, cur, t - self.prev_t)
            self.pub.publish(Float64(data=speed))
            if speed > self.warn_speed:
                self.get_logger().warn(f"관절 속도 {speed:.2f} rad/s", throttle_duration_sec=1.0)
        self.prev, self.prev_t = cur, t


def main(args=None):
    rclpy.init(args=args)
    node = JointSpeed()
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
