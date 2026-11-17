#!/usr/bin/env python
"""실제 하드웨어 호스트 — lerobot 으로 로봇(팔로워) 또는 텔레옵 장치(리더) 하나를 열고 ZMQ 로 ROS2 노드와 통신한다.
양팔이면 lerobot 의 bi_so_follower / bi_so_leader 를 그대로 쓴다 (모터 이름 left_* / right_* 12개, 데이터셋 순서와 동일).

왜 따로 프로세스인가: ROS2 Humble 의 rclpy 는 시스템 Python 3.10 전용 C 확장이고, lerobot 0.6.x 는
Python 3.12 (conda `lerobot` env) 가 필요하다. 한 프로세스에서 둘을 같이 import 할 수 없으므로
lerobot 쪽(이 파일)과 ROS2 쪽(`lerobot_bridge/hw_bridge.py`)을 ZMQ 로 잇는다 (LeKiwi 호스트와 같은 방식).
ZMQ 프로토콜과 루프는 host_core.py 에 있다 (mock_host.py 와 공유).

보통은 직접 실행하지 않는다. `ros2 run lerobot_bridge robot` / `leader` 노드가 config/robot.env 를 읽어
lerobot env 의 python 으로 이 파일을 자식 프로세스로 띄운다. 노드에 `-p dry_run:=true` 를 주면 실제 명령이 찍힌다.

손으로 띄울 때 (`ros2 run lerobot_bridge host ...` = lerobot python 으로 이 파일 exec, 인자는 lerobot-record 와 같다):
    ros2 run lerobot_bridge host --teleop.type=bi_so_leader --teleop.id=bimanual_leader \
        --teleop.left_arm_config.port=/dev/ttyACM2 --teleop.right_arm_config.port=/dev/ttyACM3 --state_port=5555
    ros2 run lerobot_bridge host --robot.type=bi_so_follower --robot.id=bimanual \
        --robot.left_arm_config.port=/dev/ttyACM0 --robot.right_arm_config.port=/dev/ttyACM1 \
        --state_port=5556 --cmd_port=5557
"""

# 주의: `from __future__ import annotations` 를 쓰면 parser.wrap() 이 설정 클래스를 못 찾는다 (문자열 annotation).

import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from pprint import pformat

from lerobot.cameras.opencv import OpenCVCameraConfig  # noqa: F401  (draccus 가 type=opencv 를 찾게 등록)
from lerobot.cameras.realsense import RealSenseCameraConfig  # noqa: F401
from lerobot.configs import parser
from lerobot.robots import (  # noqa: F401  (register_subclass 실행용)
    RobotConfig,
    bi_so_follower,
    koch_follower,
    make_robot_from_config,
    so_follower,
)
from lerobot.teleoperators import (  # noqa: F401
    TeleoperatorConfig,
    bi_so_leader,
    koch_leader,
    make_teleoperator_from_config,
    so_leader,
)
from lerobot.utils.import_utils import register_third_party_plugins
from lerobot.utils.utils import init_logging

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_core import serve  # noqa: E402


@dataclass
class HostConfig:
    # 둘 중 하나만 준다. robot → 팔로워 호스트, teleop → 리더 호스트.
    robot: RobotConfig | None = None
    teleop: TeleoperatorConfig | None = None

    # 제어 루프 주기. 리더는 읽기 주기, 팔로워는 쓰기+읽기 주기.
    fps: int = 60
    # ZMQ 바인드 주소. 다른 PC 의 ROS2 와 이으려면 0.0.0.0, 같은 PC 면 127.0.0.1 로 충분.
    bind: str = "127.0.0.1"
    state_port: int = 5555
    cmd_port: int = 5556
    # 명령이 이 시간(초) 이상 끊기면 경고만 하고 마지막 목표를 유지한다. 0 이면 검사 안 함.
    cmd_timeout_s: float = 0.5
    # 카메라 프레임 송신 주기(제어 루프보다 낮게). 0 이면 카메라 송신 안 함.
    camera_fps: int = 15
    jpeg_quality: int = 80
    # 콘솔에 주기(Hz) 출력
    verbose: bool = False

    def __post_init__(self):
        if (self.robot is None) == (self.teleop is None):
            raise ValueError("--robot.* (팔로워) 와 --teleop.* (리더) 중 정확히 하나만 지정")


def _uses_degrees(dev) -> bool:
    # SO/Koch: config.use_degrees. Bi-SO: 팔별 config. 없으면 lerobot 기본값 True 로 간주.
    cfg = getattr(dev, "config", None)
    if cfg is None:
        return True
    if hasattr(cfg, "use_degrees"):
        return bool(cfg.use_degrees)
    return bool(getattr(getattr(cfg, "left_arm_config", None), "use_degrees", True))


@parser.wrap()
def main_cfg(cfg: HostConfig):
    init_logging()
    logging.info(pformat(asdict(cfg)))
    is_follower = cfg.robot is not None
    dev = make_robot_from_config(cfg.robot) if is_follower else make_teleoperator_from_config(cfg.teleop)
    serve(
        dev,
        is_follower,
        deg=_uses_degrees(dev),
        fps=cfg.fps,
        bind=cfg.bind,
        state_port=cfg.state_port,
        cmd_port=cfg.cmd_port,
        camera_fps=cfg.camera_fps,
        jpeg_quality=cfg.jpeg_quality,
        cmd_timeout_s=cfg.cmd_timeout_s,
        verbose=cfg.verbose,
    )


def main():
    register_third_party_plugins()
    main_cfg()


if __name__ == "__main__":
    main()
