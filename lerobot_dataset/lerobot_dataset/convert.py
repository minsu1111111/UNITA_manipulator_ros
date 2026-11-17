"""`ros2 run lerobot_dataset convert` — 녹화한 rosbag 에피소드를 LeRobotDataset 으로.

    ros2 run lerobot_dataset convert ~/ros_episodes/pour_water --repo-id local/pour_water
    ros2 run lerobot_dataset convert ~/ros_episodes/pour_water --repo-id UNITAmanipulation/pour_water --push

원본 legalaspro/so101-ros-physical-ai (Apache-2.0) 의 rosbag_to_lerobot/converter.py·cli.py 를 바탕으로 다시 썼다.
원본과 다른 점:
  - 프로세스를 둘로 나눈다. 이 파일(ROS python 3.10)이 bag 을 읽고 시각을 맞춰 프레임을 만들고,
    lerobot env 의 lerobot_bridge/hosts/dataset_writer.py 가 데이터셋을 쓴다 (Humble 에서는 한 프로세스에 둘 수 없음)
  - 설정 YAML 대신 토픽 계약(docs/TOPICS.md)에서 특징을 정한다:
        observation.state      ← /robot/joint_states
        action                 ← /robot/command
        observation.images.<n> ← /robot/cam/<n>/image/compressed  (bag 에 있는 카메라 전부)
  - 프레임 기준: 원본은 기준 카메라 메시지 하나 = 프레임 하나. 여기서는 lerobot-record 처럼 고정 fps 간격으로
    그 시각 이전의 가장 최근 값을 모은다 (원본의 LastBuffer 를 그대로 씀 — 미래 값은 쓰지 않고, 오래된 값은 버린다)
  - 관절값은 토픽의 rad 를 lerobot 단위(도, gripper 0~100)로 되돌린다 → lerobot-record 데이터셋과 같은 단위·이름·형식

프레임 하나 = 시각 T 에서 각 토픽의 "T 이전 가장 최근 메시지". 어느 하나라도 없거나 max_age 보다 오래됐으면 그 프레임은 버린다.
"""

import argparse
import logging
import pickle
import re
import struct
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

from lerobot_bridge.host_process import host_command
from lerobot_common.units import from_rad

from .bag_reader import find_episode_dirs, get_custom_data, get_topic_types, open_reader
from .buffers import LastBuffer

log = logging.getLogger("convert")

STATE_TOPIC = "/robot/joint_states"
ACTION_TOPIC = "/robot/command"
CAM_RE = re.compile(r"^/robot/cam/([^/]+)/image/compressed$")
NS = 1_000_000_000


# ----------------------------------------------------------------------------- 특징 정하기
def episode_dirs(path: Path) -> list[Path]:
    """실험 폴더(episode_* 여러 개)나 에피소드 폴더 하나."""
    if (path / "metadata.yaml").exists():
        return [path]
    return find_episode_dirs(path)


def probe(bag_dir: Path) -> dict:
    """첫 에피소드에서 관절 이름 순서와 카메라 해상도를 읽는다."""
    reader = open_reader(bag_dir)
    types = get_topic_types(reader)
    for t in (STATE_TOPIC, ACTION_TOPIC):
        if t not in types:
            raise RuntimeError(f"{bag_dir.name}: bag 에 {t} 가 없다 (녹화 토픽: {sorted(types)})")
    cams = sorted(CAM_RE.match(t).group(1) for t in types if CAM_RE.match(t))
    names, shapes = None, {}
    js_cls, img_cls = get_message(types[STATE_TOPIC]), get_message("sensor_msgs/msg/CompressedImage")
    while reader.has_next() and (names is None or len(shapes) < len(cams)):
        topic, data, _ = reader.read_next()
        if topic == STATE_TOPIC and names is None:
            names = list(deserialize_message(data, js_cls).name)
        elif (m := CAM_RE.match(topic)) and m.group(1) not in shapes:
            img = cv2.imdecode(
                np.frombuffer(bytes(deserialize_message(data, img_cls).data), np.uint8), cv2.IMREAD_COLOR
            )
            shapes[m.group(1)] = list(img.shape)  # (H, W, 3)
    if names is None:
        raise RuntimeError(f"{bag_dir.name}: {STATE_TOPIC} 메시지가 없다")
    return {"names": names, "cameras": {c: shapes[c] for c in cams if c in shapes}}


def robot_type(names: list[str]) -> str:
    # lerobot-record 가 쓰는 값 (Robot.name)
    return "bi_so_follower" if any(n.startswith("left_") for n in names) else "so_follower"


# ----------------------------------------------------------------------------- dataset_writer 로 보내기
class Writer:
    """lerobot env 의 dataset_writer.py 에 길이+pickle 로 메시지를 흘려보낸다 (내장 타입만 → 파이썬 버전 무관)."""

    def __init__(self, lerobot_py: str):
        self.proc = subprocess.Popen(host_command("dataset_writer", [], lerobot_py), stdin=subprocess.PIPE)

    def send(self, msg: dict):
        payload = pickle.dumps(msg, protocol=4)
        try:
            self.proc.stdin.write(struct.pack("<Q", len(payload)) + payload)
        except BrokenPipeError:
            raise RuntimeError(
                f"dataset_writer 가 먼저 끝남 (exit {self.proc.wait()}) — 위 로그를 볼 것"
            ) from None

    def close(self) -> int:
        self.proc.stdin.close()
        return self.proc.wait()


# ----------------------------------------------------------------------------- 에피소드 하나
def convert_episode(bag_dir: Path, info: dict, args, writer: Writer) -> tuple[int, int]:
    custom = get_custom_data(bag_dir)
    task = args.task or str(custom.get("task") or "")
    if not task:
        raise RuntimeError(
            f"{bag_dir.name}: task 가 없다 (녹화 때 -p task:=… 를 안 줬으면 --task 로 넣을 것)"
        )

    names, cams = info["names"], info["cameras"]
    reader = open_reader(bag_dir)
    types = get_topic_types(reader)
    topics = [STATE_TOPIC, ACTION_TOPIC] + [f"/robot/cam/{c}/image/compressed" for c in cams]
    missing = [t for t in topics if t not in types]
    if missing:
        raise RuntimeError(f"{bag_dir.name}: 첫 에피소드와 토픽이 다르다 — 없는 토픽 {missing}")
    classes = {t: get_message(types[t]) for t in topics}
    max_age = int(args.max_age * NS)
    bufs = {t: LastBuffer(max_age_ns=max_age) for t in topics}

    def joints(msg) -> list[float]:
        pos = dict(zip(msg.name, msg.position))
        lack = [n for n in names if n not in pos]
        if lack:
            raise RuntimeError(f"{bag_dir.name}: 관절 {lack} 가 메시지에 없다")
        return [from_rad(n, pos[n]) for n in names]  # rad → lerobot 단위, 데이터셋 순서

    def emit(tick_ns: int) -> bool:
        vals = {t: b.asof(tick_ns) for t, b in bufs.items()}
        if any(v is None for v in vals.values()):
            return False
        writer.send({
            "kind": "frame",
            "task": task,
            "state": vals[STATE_TOPIC],
            "action": vals[ACTION_TOPIC],
            "images": {c: vals[f"/robot/cam/{c}/image/compressed"] for c in cams},
        })  # fmt: skip
        return True

    dt = NS // args.fps
    next_tick, frames, dropped, last_ts = None, 0, 0, None
    while reader.has_next():
        topic, data, ts = reader.read_next()
        if topic not in bufs:
            continue
        # ts 보다 앞선 틱은 이제 확정된다 (이후 메시지는 모두 ts 이후이므로)
        while next_tick is not None and next_tick < ts:
            ok = emit(next_tick)
            frames, dropped = frames + ok, dropped + (not ok)
            next_tick += dt
        msg = deserialize_message(data, classes[topic])
        value = (
            joints(msg) if topic in (STATE_TOPIC, ACTION_TOPIC) else bytes(msg.data)
        )  # 이미지는 JPEG 그대로
        bufs[topic].push(ts, value)
        last_ts = ts
        if next_tick is None and all(b.item is not None for b in bufs.values()):
            next_tick = ts  # 모든 토픽이 한 번씩 들어온 순간부터 시작
    while next_tick is not None and next_tick <= last_ts:
        ok = emit(next_tick)
        frames, dropped = frames + ok, dropped + (not ok)
        next_tick += dt

    if frames == 0:
        log.error("%s: 프레임 0개 — 건너뜀 (토픽이 비었거나 모두 오래됨)", bag_dir.name)
        writer.send({"kind": "episode_discard"})
        return 0, dropped
    writer.send({"kind": "episode_end"})
    log.info(
        "%s: %d 프레임 (%.1f s), 버린 프레임 %d, task=%r",
        bag_dir.name,
        frames,
        frames / args.fps,
        dropped,
        task,
    )
    for t, b in bufs.items():
        s = b.summary()
        log.info("    %-45s 맞춤 %5.1f%%  평균 지연 %5.1f ms  최대 %5.1f ms",
                 t, 100 * s.get("match_rate", 0), 1e3 * s.get("mean_dt_s", 0), 1e3 * s.get("max_dt_s", 0))  # fmt: skip
    return frames, dropped


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="ros2 run lerobot_dataset convert", description=__doc__.split("\n")[0])
    ap.add_argument(
        "input",
        type=Path,
        help="에피소드 폴더들이 있는 실험 폴더 (예: ~/ros_episodes/pour_water) 또는 에피소드 폴더 하나",
    )
    ap.add_argument(
        "--repo-id", required=True, help="데이터셋 이름 (예: local/pour_water, UNITAmanipulation/pour_water)"
    )
    ap.add_argument(
        "--root", type=Path, default=None, help="저장 위치 (기본: ~/.cache/huggingface/lerobot/<repo-id>)"
    )
    ap.add_argument("--fps", type=int, default=30, help="데이터셋 fps (기본 30, lerobot-record 와 같음)")
    ap.add_argument("--task", default="", help="과제 문장. 비우면 녹화 때 넣은 task (bag 메타데이터)")
    ap.add_argument(
        "--max-age", type=float, default=0.1, help="이보다 오래된 값이 있으면 그 프레임을 버림 [s] (기본 0.1)"
    )
    ap.add_argument("--no-videos", action="store_true", help="이미지를 mp4 대신 png 로 저장")
    ap.add_argument("--overwrite", action="store_true", help="같은 이름의 데이터셋이 있으면 지우고 새로 만듦")
    ap.add_argument(
        "--push", action="store_true", help="다 쓴 뒤 Hugging Face Hub 에 올림 (hf auth login 필요)"
    )
    ap.add_argument("--lerobot-py", default="", help="lerobot env 의 python (기본: 자동으로 찾음)")
    args = ap.parse_args(sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="[convert] %(message)s")

    eps = episode_dirs(args.input.expanduser())
    if not eps:
        sys.exit(f"에피소드가 없다: {args.input} (episode_* 폴더 안에 metadata.yaml 이 있어야 함)")
    info = probe(eps[0])
    log.info("에피소드 %d개, 관절 %d개, 카메라 %s, %d fps → %s",
             len(eps), len(info["names"]), info["cameras"] or "없음", args.fps, args.repo_id)  # fmt: skip

    writer = Writer(args.lerobot_py)
    writer.send({
        "kind": "create",
        "repo_id": args.repo_id,
        "root": str(args.root.expanduser()) if args.root else None,
        "fps": args.fps,
        "robot_type": robot_type(info["names"]),
        "names": info["names"],
        "cameras": info["cameras"],
        "use_videos": not args.no_videos,
        "overwrite": args.overwrite,
    })  # fmt: skip
    total = 0
    try:
        for i, ep in enumerate(eps, 1):
            log.info("(%d/%d) %s", i, len(eps), ep)
            total += convert_episode(ep, info, args, writer)[0]
        writer.send({"kind": "finish", "push": args.push})
    finally:
        code = writer.close()
    if code != 0:
        sys.exit(f"dataset_writer 실패 (exit {code})")
    log.info("끝: 프레임 %d개 (%.1f s)", total, total / args.fps)


if __name__ == "__main__":
    main()
