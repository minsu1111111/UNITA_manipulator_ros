#!/usr/bin/env python3
"""가짜 팔 호스트 — 하드웨어도 lerobot 도 없이 robot / leader 노드를 시험한다.

ROS 노드가 `-p mock:=true` 일 때 시스템 python 으로 이 파일을 띄운다 (lerobot env 불필요).
필요한 것: numpy, pyzmq (카메라 영상까지 보려면 opencv).

    리더   : 사인파로 움직이는 관절
    팔로워 : 받은 목표를 즉시 현재 위치로 되돌림 + 움직이는 줄무늬 손목 카메라 (320x240)

손으로 띄울 때:
    python3 mock_host.py --role follower --bimanual true --state_port 5556 --cmd_port 5557
"""

import argparse
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_core import serve  # noqa: E402

logger = logging.getLogger("host")
SO_MOTORS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")


class MockLeader:
    name = "mock_leader"

    def __init__(self, motors: tuple[str, ...]):
        self.motors = motors
        self.t0 = time.perf_counter()

    def connect(self):
        logger.info(f"mock leader connected ({len(self.motors)} motors)")

    def disconnect(self):
        pass

    def get_action(self) -> dict[str, float]:
        t = time.perf_counter() - self.t0
        act = {}
        for i, m in enumerate(self.motors):
            if m.endswith("gripper"):
                act[f"{m}.pos"] = 50.0 + 50.0 * math.sin(0.7 * t + i)  # 0~100
            else:
                act[f"{m}.pos"] = 30.0 * math.sin(0.5 * t + i)  # ±30 도
        return act


class MockFollower:
    name = "mock_follower"

    def __init__(self, motors: tuple[str, ...]):
        self.pos = {f"{m}.pos": 0.0 for m in motors}
        # 양팔이면 left_wrist / right_wrist, 단팔이면 wrist — 실제 bi_so_follower 관측 이름과 같다
        sides = sorted({m.split("_")[0] for m in motors if m.startswith(("left_", "right_"))})
        self.cam_names = [f"{s}_wrist" for s in sides] or ["wrist"]
        self.t0 = time.perf_counter()

    def _frame(self, i: int) -> np.ndarray:
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        x = int((time.perf_counter() - self.t0) * 60) % 320  # 움직이는 세로줄
        img[:, max(0, x - 8) : x + 8, i % 3] = 255
        return img

    def connect(self):
        logger.info(f"mock follower connected ({len(self.pos)} motors, cameras {self.cam_names})")

    def disconnect(self):
        pass

    def get_observation(self) -> dict:
        obs = dict(self.pos)
        for i, name in enumerate(self.cam_names):
            obs[name] = self._frame(i)
        return obs

    def send_action(self, action: dict) -> dict:
        self.pos.update({k: float(v) for k, v in action.items() if k in self.pos})
        return action


def _bool(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "yes", "on")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", choices=("leader", "follower"), required=True)
    ap.add_argument("--bimanual", type=_bool, default=False)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--state_port", type=int, default=5556)
    ap.add_argument("--cmd_port", type=int, default=5557)
    ap.add_argument("--camera_fps", type=int, default=15)
    ap.add_argument("--jpeg_quality", type=int, default=80)
    ap.add_argument("--cmd_timeout_s", type=float, default=0.5)
    ap.add_argument("--verbose", type=_bool, default=False)
    a = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(asctime)s %(name)s: %(message)s")
    # bi_so_* 와 같은 이름·순서: left_* 6개 다음 right_* 6개
    motors = tuple(f"{s}_{m}" for s in ("left", "right") for m in SO_MOTORS) if a.bimanual else SO_MOTORS
    is_follower = a.role == "follower"
    dev = MockFollower(motors) if is_follower else MockLeader(motors)
    serve(
        dev,
        is_follower,
        deg=True,
        fps=a.fps,
        bind=a.bind,
        state_port=a.state_port,
        cmd_port=a.cmd_port,
        camera_fps=a.camera_fps,
        jpeg_quality=a.jpeg_quality,
        cmd_timeout_s=a.cmd_timeout_s,
        verbose=a.verbose,
    )


if __name__ == "__main__":
    main()
