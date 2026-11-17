"""호스트(hosts/hw_host.py)와 주고받는 ZMQ. 프로토콜은 hw_host.py 머리 주석과 같다.

    state_port  호스트 PUB → 여기 SUB   [b"state", json] / [b"img", name, meta_json, jpeg]
    cmd_port    여기 PUSH → 호스트 PULL  json {"t", "pos": {모터: lerobot 값}}

값은 lerobot 단위 그대로 오간다. rad 변환은 노드(hw_bridge.py)가 lerobot_common.units 로 한다.
"""

import json
import threading
import time
from collections.abc import Callable

import zmq


class StateReceiver:
    """백그라운드 스레드에서 호스트 state/img 를 받아 콜백을 부른다. 밀린 프레임은 버리고 최신 것만."""

    def __init__(
        self,
        ctx: zmq.Context,
        addr: str,
        on_state: Callable[[dict], None],
        on_image: Callable[[str, dict, bytes], None],
    ):
        self.sub = ctx.socket(zmq.SUB)
        self.sub.setsockopt(zmq.RCVHWM, 5)
        self.sub.setsockopt(zmq.LINGER, 0)
        self.sub.setsockopt(zmq.SUBSCRIBE, b"")
        self.sub.connect(addr)
        self.on_state, self.on_image = on_state, on_image
        self.last_rx = 0.0  # time.monotonic() — 0 이면 아직 못 받음
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="zmq_rx", daemon=True)
        self._thread.start()

    def _loop(self):
        poller = zmq.Poller()
        poller.register(self.sub, zmq.POLLIN)
        while not self._stop.is_set():
            if not poller.poll(100):
                continue
            state, imgs = None, {}
            while True:
                try:
                    frames = self.sub.recv_multipart(zmq.NOBLOCK)
                except zmq.Again:
                    break
                if frames[0] == b"state":
                    state = frames[1]
                elif frames[0] == b"img" and len(frames) == 4:
                    imgs[frames[1].decode()] = (frames[2], frames[3])
            self.last_rx = time.monotonic()
            if state is not None:
                self.on_state(json.loads(state))
            for name, (meta, jpeg) in imgs.items():
                self.on_image(name, json.loads(meta), jpeg)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.sub.close()


class CommandSender:
    """목표 위치를 호스트로. CONFLATE 라 호스트는 항상 마지막 명령 하나만 본다."""

    def __init__(self, ctx: zmq.Context, addr: str):
        self.push = ctx.socket(zmq.PUSH)
        self.push.setsockopt(zmq.CONFLATE, 1)
        self.push.setsockopt(zmq.LINGER, 0)
        self.push.connect(addr)

    def send(self, pos: dict[str, float]) -> bool:
        try:
            self.push.send_string(json.dumps({"t": time.time(), "pos": pos}), zmq.NOBLOCK)
            return True
        except zmq.Again:
            return False

    def close(self):
        self.push.close()
