"""호스트 공용 부분 — ZMQ 송수신과 제어 루프. lerobot 을 import 하지 않는다.

hw_host.py   (실제 하드웨어, lerobot env python 3.12)  ─┐
mock_host.py (가짜 팔, 시스템 python — lerobot 불필요) ─┴─▶ serve(장치, ...)

장치는 lerobot 의 Robot / Teleoperator 와 같은 모양이면 된다:
    connect(), disconnect(), 리더면 get_action(), 팔로워면 get_observation() / send_action(), 그리고 name.

ZMQ 프로토콜 (ROS 쪽 lerobot_bridge/zmq_link.py 와 맞춰야 함):
    state_port  PUB (호스트 bind)  멀티파트
        [b"state", json]                      json = {"t": unix초, "seq": int, "deg": bool, "pos": {모터: 값}}
        [b"img", name, meta_json, jpeg_bytes] meta = {"t": unix초, "w": int, "h": int}
    cmd_port    PULL (호스트 bind, CONFLATE)  단일 프레임 json = {"t": unix초, "pos": {모터: 값}}
    값의 단위는 lerobot 그대로 (관절 도, gripper 0~100). rad 변환은 ROS 쪽이 한다.

종료: Ctrl+C(SIGINT) 와 SIGTERM 모두 KeyboardInterrupt 로 받아 disconnect(토크 끄기) 후 끝난다.
ROS 노드가 비정상으로 죽어도 PR_SET_PDEATHSIG 로 SIGTERM 이 오므로 같은 경로로 정리된다.
"""

import contextlib
import json
import logging
import signal
import time

import numpy as np
import zmq

logger = logging.getLogger("host")

try:  # 카메라 JPEG 인코딩용. 없으면 카메라 영상만 안 보낸다
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


class Link:
    def __init__(self, bind: str, state_port: int, cmd_port: int | None):
        self.ctx = zmq.Context()
        self.state = self.ctx.socket(zmq.PUB)
        self.state.setsockopt(zmq.SNDHWM, 5)  # ROS 쪽이 느려도 쌓이지 않게 (최신 우선)
        self.state.setsockopt(zmq.LINGER, 0)
        self.state.bind(f"tcp://{bind}:{state_port}")
        self.cmd = None
        if cmd_port is not None:
            self.cmd = self.ctx.socket(zmq.PULL)
            self.cmd.setsockopt(zmq.CONFLATE, 1)  # 항상 마지막 명령만 (단일 프레임이어야 함)
            self.cmd.setsockopt(zmq.LINGER, 0)
            self.cmd.bind(f"tcp://{bind}:{cmd_port}")
        self.seq = 0

    def send_state(self, pos: dict[str, float], deg: bool):
        self.seq += 1
        msg = {"t": time.time(), "seq": self.seq, "deg": deg, "pos": pos}
        with contextlib.suppress(zmq.Again):  # ROS 쪽이 밀리면 이 프레임은 버린다
            self.state.send_multipart([b"state", json.dumps(msg).encode()], flags=zmq.NOBLOCK)

    def send_image(self, name: str, jpeg: bytes, w: int, h: int):
        meta = {"t": time.time(), "w": w, "h": h}
        with contextlib.suppress(zmq.Again):
            self.state.send_multipart(
                [b"img", name.encode(), json.dumps(meta).encode(), jpeg], flags=zmq.NOBLOCK
            )

    def recv_cmd(self) -> dict | None:
        """가장 최근 명령 하나 (없으면 None)."""
        try:
            return json.loads(self.cmd.recv_string(zmq.NOBLOCK))
        except zmq.Again:
            return None

    def close(self):
        self.state.close()
        if self.cmd is not None:
            self.cmd.close()
        self.ctx.term()


def strip_pos(d: dict) -> dict[str, float]:
    """{'shoulder_pan.pos': v} → {'shoulder_pan': v}. 카메라 배열 등 .pos 가 아닌 키는 버린다."""
    return {k.removesuffix(".pos"): float(v) for k, v in d.items() if k.endswith(".pos")}


def precise_sleep(seconds: float):
    """time.sleep 은 수 ms 늦게 깨므로 마지막 2 ms 는 바쁜 대기."""
    end = time.perf_counter() + seconds
    if seconds > 0.002:
        time.sleep(seconds - 0.002)
    while time.perf_counter() < end:
        pass


def _pace(t0: float, period: float, verbose: bool):
    precise_sleep(max(period - (time.perf_counter() - t0), 0.0))
    if verbose:
        loop = time.perf_counter() - t0
        print(f"\rloop {loop * 1e3:6.2f} ms ({1 / loop:5.0f} Hz)", end="", flush=True)


def _leader_loop(dev, link: Link, fps: int, deg: bool, verbose: bool):
    period = 1.0 / fps
    while True:
        t0 = time.perf_counter()
        link.send_state(strip_pos(dev.get_action()), deg)
        _pace(t0, period, verbose)


def _follower_loop(
    robot,
    link: Link,
    fps: int,
    deg: bool,
    camera_fps: int,
    jpeg_quality: int,
    cmd_timeout_s: float,
    verbose: bool,
):
    period = 1.0 / fps
    cam_period = (1.0 / camera_fps) if camera_fps > 0 else None
    last_cam, last_cmd_t, warned_cmd, warned_cv2 = 0.0, None, False, False
    enc = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)] if cv2 is not None else None

    while True:
        t0 = time.perf_counter()

        cmd = link.recv_cmd()
        if cmd is not None:
            last_cmd_t, warned_cmd = t0, False
            goal = {f"{k}.pos": float(v) for k, v in cmd.get("pos", {}).items()}
            if goal:
                robot.send_action(goal)
        elif (
            cmd_timeout_s > 0
            and last_cmd_t is not None
            and t0 - last_cmd_t > cmd_timeout_s
            and not warned_cmd
        ):
            logger.warning(f"{cmd_timeout_s}s 동안 명령 없음 — 마지막 목표 유지")
            warned_cmd = True

        obs = robot.get_observation()
        link.send_state(strip_pos(obs), deg)

        if cam_period is not None and t0 - last_cam >= cam_period:
            last_cam = t0
            # 관측에서 이미지(H,W,3 배열)만 골라 보낸다. robot.cameras 키를 쓰면 안 됨:
            # BiSOFollower 는 양팔 cameras 를 합쳐 둘 다 "wrist" 로 겹치고, 관측 키는 left_wrist / right_wrist 다.
            for name, img in obs.items():
                if not (isinstance(img, np.ndarray) and img.ndim == 3 and img.shape[2] == 3):
                    continue
                if cv2 is None:
                    if not warned_cv2:
                        logger.warning(
                            "opencv(cv2) 가 없어 카메라 영상을 보내지 않는다 (sudo apt install python3-opencv)"
                        )
                        warned_cv2 = True
                    break
                # lerobot 카메라는 RGB 로 준다 → JPEG 은 BGR 기준이므로 변환
                ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), enc)
                if ok:
                    link.send_image(name, buf.tobytes(), img.shape[1], img.shape[0])

        _pace(t0, period, verbose)


def _sigterm_as_interrupt(signum, frame):
    raise KeyboardInterrupt


def serve(
    dev,
    is_follower: bool,
    *,
    deg: bool,
    fps: int,
    bind: str,
    state_port: int,
    cmd_port: int,
    camera_fps: int = 15,
    jpeg_quality: int = 80,
    cmd_timeout_s: float = 0.5,
    verbose: bool = False,
):
    """장치를 열고 Ctrl+C / SIGTERM 까지 루프를 돈다. 끝날 때 반드시 disconnect (토크 끄기)."""
    signal.signal(signal.SIGTERM, _sigterm_as_interrupt)
    link = Link(bind, state_port, cmd_port if is_follower else None)
    dev.connect()
    role = "follower" if is_follower else "leader"
    logger.info(
        f"[{role}] {dev.name}: state PUB tcp://{bind}:{state_port}"
        + (f", cmd PULL tcp://{bind}:{cmd_port}" if is_follower else "")
    )
    try:
        if is_follower:
            _follower_loop(dev, link, fps, deg, camera_fps, jpeg_quality, cmd_timeout_s, verbose)
        else:
            _leader_loop(dev, link, fps, deg, verbose)
    except KeyboardInterrupt:
        pass
    finally:
        # 터미널 Ctrl+C 는 프로세스 그룹 전체(노드+호스트)에 가고, 노드도 종료하며 한 번 더 보낸다.
        # disconnect(토크 끄기) 가 끊기지 않게 정리 중엔 두 신호 모두 무시한다.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if verbose:
            print()
        dev.disconnect()
        link.close()
