"""robot / leader 노드 — lerobot 하드웨어를 ROS 토픽으로.

    ros2 run lerobot_bridge robot     팔로워: robot/joint_states, robot/cam/<name>/image/compressed 발행
                                              robot/command 구독 → 모터
    ros2 run lerobot_bridge leader    리더:   leader/joint_states 발행

노드가 하는 일:
  1. config/robot.env 를 읽고 보드 시리얼로 포트를 찾는다 (lerobot_common.rig)
  2. HF 캐시에 캘리브레이션이 없으면 복사한다
  3. lerobot env 의 python 으로 hosts/hw_host.py 를 자식 프로세스로 띄운다 (lerobot 이 모터·카메라를 다룸)
  4. ZMQ 로 받은 lerobot 값(도, gripper 0~100)을 rad 로 바꿔 발행하고, 받은 명령은 반대로 바꿔 보낸다

파라미터 (`--ros-args -p 이름:=값`):
  arm         bi | left | right                  (기본 bi)
  mock        true 면 하드웨어 없이 가짜 팔        (기본 false)
  robot_env   robot.env 경로 (비우면 자동 탐색, lerobot_common/rig.py 참고)
  find_ports  보드 시리얼로 포트 찾기              (기본 true)
  dry_run     호스트 명령만 출력하고 종료          (기본 false)
  spawn_host  false 면 호스트를 띄우지 않고 zmq_host 로 접속만 (호스트가 다른 PC 에 있을 때)
  zmq_host    호스트 주소                          (기본 127.0.0.1)
  bind        호스트가 bind 할 주소                 (기본 127.0.0.1, 다른 PC 에서 붙으려면 0.0.0.0)
  fps         호스트 루프 주기                      (기본 60)
  state_port / cmd_port   ZMQ 포트 (robot 5556/5557, leader 5555)
  cameras     robot 만: false 면 카메라 없이       (기본 true)
  max_rel     robot 만: 스텝당 최대 변화(도). 0 이면 끔. 처음 붙일 땐 20 권장
"""

import contextlib
import shlex
import signal
import sys
import time

import rclpy
import zmq
from builtin_interfaces.msg import Time as TimeMsg
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.task import Future
from sensor_msgs.msg import CompressedImage, JointState

from lerobot_common import qos, topics
from lerobot_common.names import ARMS, joint_names
from lerobot_common.rig import ensure_calibration, load_rig
from lerobot_common.units import from_rad, to_rad

from .host_args import LEADER_STATE_PORT, ROBOT_CMD_PORT, ROBOT_STATE_PORT, leader_plan, robot_plan
from .host_process import HostProcess, host_command
from .zmq_link import CommandSender, StateReceiver


def _stamp(t: float) -> TimeMsg:
    sec = int(t)
    return TimeMsg(sec=sec, nanosec=int((t - sec) * 1e9))


class HwBridge(Node):
    def __init__(self, role: str):
        assert role in ("robot", "leader")
        super().__init__(role)
        self.role = role
        is_robot = role == "robot"

        p = self.declare_parameter
        arm = p("arm", "bi").value
        mock = p("mock", False).value
        robot_env = p("robot_env", "").value
        find_ports = p("find_ports", True).value
        dry_run = p("dry_run", False).value
        spawn_host = p("spawn_host", True).value
        zmq_host = p("zmq_host", "127.0.0.1").value
        bind = p("bind", "127.0.0.1").value
        fps = p("fps", 60).value
        state_port = p("state_port", ROBOT_STATE_PORT if is_robot else LEADER_STATE_PORT).value
        if is_robot:
            cmd_port = p("cmd_port", ROBOT_CMD_PORT).value
            cameras = p("cameras", True).value
            # `-p max_rel:=20` 은 INTEGER 로 들어오는데 0.0 으로 선언하면 DOUBLE 이라 거부된다 → 둘 다 받게
            max_rel = float(p("max_rel", 0.0, ParameterDescriptor(dynamic_typing=True)).value)
        if arm not in ARMS:
            raise ValueError(f"arm 은 {ARMS} 중 하나 (받은 값: {arm!r})")

        self.expected_names = joint_names(arm)
        self.known_names: set[str] | None = None  # 첫 state 에서 정해짐. 그 전엔 명령을 보내지 않는다
        self.done = Future()  # 결과 = 프로세스 종료 코드. 설정되면 main 이 끝낸다
        self.host: HostProcess | None = None
        self.receiver: StateReceiver | None = None
        self.sender: CommandSender | None = None
        self.ctx: zmq.Context | None = None
        log = self.get_logger()

        # ---- 1~3. 호스트 준비/실행 ---------------------------------------------------------------
        if spawn_host or dry_run:
            # mock 은 robot.env 도 lerobot 도 쓰지 않는다 (시스템 python 으로 mock_host.py)
            rig = None if mock else load_rig(robot_env, find_ports=find_ports)
            if is_robot:
                plan = robot_plan(
                    arm, rig, mock=mock, cameras=cameras, max_rel=max_rel,
                    fps=fps, bind=bind, state_port=state_port, cmd_port=cmd_port,
                )  # fmt: skip
            else:
                plan = leader_plan(arm, rig, mock=mock, fps=fps, bind=bind, state_port=state_port)
            for note in (rig.notes if rig else ["mock: robot.env·lerobot 안 씀"]) + plan.notes:
                log.info(note)
            try:
                cmd = host_command(plan.script, plan.args, rig["LEROBOT_PY"] if rig else "")
                if dry_run:
                    log.info("host: " + shlex.join(cmd))
                    if is_robot:
                        log.info("camera topics: " + ", ".join(topics.robot_camera(c) for c in plan.cameras))
                    self.done.set_result(0)
                    return
                for kind, typ, src, dst in plan.calib:
                    msg = ensure_calibration(kind, typ, src, dst, rig["CALIB_DIR"])
                    if msg:
                        log.info(msg)
            except (RuntimeError, FileNotFoundError) as e:
                # 설정 문제는 Traceback 대신 해결 방법이 담긴 한 줄로 알리고 끝낸다
                log.error(str(e))
                self.done.set_result(1)
                return
            self.host = HostProcess(cmd)
            what = "mock 호스트" if mock else "lerobot 호스트 (lerobot import 에 10초쯤 걸린다)"
            log.info(f"{what} 시작, pid {self.host.pid}")

        # ---- 4. ZMQ ↔ 토픽 --------------------------------------------------------------------
        js_topic = topics.ROBOT_JOINT_STATES if is_robot else topics.LEADER_JOINT_STATES
        self.pub_js = self.create_publisher(JointState, js_topic, qos.PUB_STREAM)
        self.pub_img: dict[str, rclpy.publisher.Publisher] = {}
        self.ctx = zmq.Context()
        self.receiver = StateReceiver(
            self.ctx, f"tcp://{zmq_host}:{state_port}", self._on_state, self._on_image
        )
        if is_robot:
            self.sender = CommandSender(self.ctx, f"tcp://{zmq_host}:{cmd_port}")
            self.create_subscription(JointState, topics.ROBOT_COMMAND, self._on_command, qos.SUB_STREAM)
        self.create_timer(1.0, self._watchdog)
        log.info(
            f"[{role}] arm={arm} mock={mock} → {self.pub_js.topic_name}"
            + (f", ← {topics.ROBOT_COMMAND}" if is_robot else "")
            + f" (zmq {zmq_host}:{state_port}"
            + (f"/{cmd_port})" if is_robot else ")")
        )

    # ------------------------------------------------------------------ host → ROS
    def _on_state(self, msg: dict):
        if not msg.get("deg", True):
            self.get_logger().error("호스트가 도 단위가 아님 (use_degrees=False). rad 변환 불가", once=True)
            return
        pos: dict[str, float] = msg["pos"]
        if self.known_names is None:
            self.known_names = set(pos)
            if list(pos) != self.expected_names:
                self.get_logger().warn(
                    f"관절 이름이 arm 설정과 다름: {list(pos)} (예상 {self.expected_names})"
                )
            self.get_logger().info(f"첫 상태 수신: 관절 {len(pos)}개")
        js = JointState()
        js.header.stamp = _stamp(msg["t"])
        js.name = list(pos)
        js.position = [to_rad(n, float(v)) for n, v in pos.items()]
        self._publish(self.pub_js, js)

    def _on_image(self, name: str, meta: dict, jpeg: bytes):
        pub = self.pub_img.get(name)
        if pub is None:
            pub = self.create_publisher(CompressedImage, topics.robot_camera(name), qos.PUB_STREAM)
            self.pub_img[name] = pub
            self.get_logger().info(f"카메라 '{name}' {meta.get('w')}x{meta.get('h')} → {pub.topic_name}")
        img = CompressedImage()
        img.header.stamp = _stamp(meta["t"])
        img.header.frame_id = f"{name}_camera_optical_frame"  # lerobot_description 의 카메라 프레임
        img.format = "jpeg"
        img.data = jpeg
        self._publish(pub, img)

    @staticmethod
    def _publish(pub, msg):
        # ZMQ 스레드에서 발행한다. Ctrl+C 때 rclpy 가 먼저 닫히면 publish 가 실패하는데, 그건 정상 종료라 조용히 넘긴다
        try:
            pub.publish(msg)
        except Exception:
            if rclpy.ok():
                raise

    # ------------------------------------------------------------------ ROS → host
    def _on_command(self, js: JointState):
        if self.known_names is None:
            return  # 호스트가 아직 안 떴다 — 모터에 아무것도 쓰지 않는다
        if len(js.name) != len(js.position):
            self.get_logger().warn("command: name/position 길이 다름, 무시", throttle_duration_sec=2.0)
            return
        unknown = [n for n in js.name if n not in self.known_names]
        if unknown:
            self.get_logger().warn(f"command 에 모르는 관절: {unknown} (무시)", throttle_duration_sec=2.0)
        pos = {n: from_rad(n, p) for n, p in zip(js.name, js.position) if n in self.known_names}
        if pos:
            self.sender.send(pos)

    # ------------------------------------------------------------------ misc
    def _watchdog(self):
        if self.done.done():
            return
        if self.host is not None and (code := self.host.poll()) is not None:
            self.get_logger().error(f"호스트가 종료됨 (exit {code}) — 위의 호스트 로그를 볼 것")
            self.done.set_result(code or 1)
            return
        rx = self.receiver.last_rx
        if rx == 0.0:
            self.get_logger().info("호스트 상태 기다리는 중…", throttle_duration_sec=5.0)
        elif time.monotonic() - rx > 1.0:
            self.get_logger().warn(
                f"호스트 상태 끊김 ({time.monotonic() - rx:.1f}s)", throttle_duration_sec=5.0
            )

    def close(self):
        """호스트 → ZMQ 순서로 정리. 호스트는 SIGINT 를 받아 토크를 끄고 끝난다."""
        if self.host is not None:
            code = self.host.stop()
            self.get_logger().info(f"호스트 종료 (exit {code})")
        if self.receiver is not None:
            self.receiver.close()
        if self.sender is not None:
            self.sender.close()
        if self.ctx is not None:
            self.ctx.term()


def _run(role: str, args=None):
    rclpy.init(args=args)
    node = HwBridge(role)
    code = 0
    try:
        rclpy.spin_until_future_complete(node, node.done)
        code = node.done.result() if node.done.done() else 0
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # 터미널 Ctrl+C 는 노드·호스트에 같이 간다. 호스트가 토크를 끄는 동안 노드가 다시 끊기지 않게 무시
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.close()
        with contextlib.suppress(Exception):
            node.destroy_node()
        with contextlib.suppress(Exception):
            rclpy.try_shutdown()
    sys.exit(code)


def robot_main(args=None):
    _run("robot", args)


def leader_main(args=None):
    _run("leader", args)
