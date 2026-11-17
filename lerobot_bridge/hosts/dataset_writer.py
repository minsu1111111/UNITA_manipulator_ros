#!/usr/bin/env python
"""데이터셋 쓰기 호스트 — lerobot env(3.12)에서 돈다. `ros2 run lerobot_dataset convert` 가 띄운다.

stdin 으로 [8바이트 길이 + pickle] 메시지를 받아 LeRobotDataset 을 쓴다 (값은 내장 타입만):
    {"kind": "create", repo_id, root, fps, robot_type, names, cameras: {이름: [H, W, 3]}, use_videos, overwrite}
    {"kind": "frame", task, state: [lerobot 단위], action: [lerobot 단위], images: {이름: JPEG bytes}}
    {"kind": "episode_end"} / {"kind": "episode_discard"}
    {"kind": "finish", push}

특징 정의와 프레임은 lerobot-record 와 같은 lerobot 함수로 만든다 (기본 프로세서 = 그대로 통과)
→ 키·이름·dtype·shape 이 lerobot-record 데이터셋과 같다:
    observation.state / action          float32 [관절 수], 이름 "<관절>.pos"
    observation.images.<카메라>          video [H, W, 3]
"""

import logging
import pickle
import shutil
import struct
import sys
from pathlib import Path

import cv2
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.pipeline_features import aggregate_pipeline_dataset_features, create_initial_features
from lerobot.processor import make_default_processors
from lerobot.utils.constants import ACTION, HF_LEROBOT_HOME, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts

log = logging.getLogger("dataset_writer")


def read_messages(stream):
    while True:
        head = stream.read(8)
        if len(head) < 8:
            return
        (n,) = struct.unpack("<Q", head)
        yield pickle.loads(stream.read(n))


def make_features(names: list[str], cameras: dict[str, list[int]], use_videos: bool) -> dict:
    """lerobot-record 의 dataset_features 와 같은 방법 (record 의 기본 프로세서)."""
    teleop_action_processor, _, robot_observation_processor = make_default_processors()
    joints = {f"{n}.pos": float for n in names}
    obs = {**joints, **{c: tuple(shape) for c, shape in cameras.items()}}
    return combine_feature_dicts(
        aggregate_pipeline_dataset_features(
            pipeline=teleop_action_processor,
            initial_features=create_initial_features(action=joints),
            use_videos=use_videos,
        ),
        aggregate_pipeline_dataset_features(
            pipeline=robot_observation_processor,
            initial_features=create_initial_features(observation=obs),
            use_videos=use_videos,
        ),
    )


def main():
    logging.basicConfig(level=logging.INFO, format="[dataset_writer] %(message)s")
    msgs = read_messages(sys.stdin.buffer)
    first = next(msgs, None)
    if not first or first["kind"] != "create":
        sys.exit("첫 메시지가 create 가 아니다")
    c = first
    target = Path(c["root"]) if c["root"] else HF_LEROBOT_HOME / c["repo_id"]
    if target.exists():
        if not c["overwrite"]:
            sys.exit(f"이미 있다: {target} (--overwrite 로 지우고 새로 만들거나 다른 --repo-id)")
        log.info("지움: %s", target)
        shutil.rmtree(target)

    names = c["names"]
    keys = [f"{n}.pos" for n in names]
    features = make_features(names, c["cameras"], c["use_videos"])
    ds = LeRobotDataset.create(
        c["repo_id"],
        c["fps"],
        root=c["root"],
        robot_type=c["robot_type"],
        features=features,
        use_videos=c["use_videos"],
        image_writer_threads=4 * max(1, len(c["cameras"])),
    )
    log.info("만듦: %s (%s, %d fps) → %s", c["repo_id"], c["robot_type"], c["fps"], ds.root)

    episodes, frames = 0, 0
    for m in msgs:
        kind = m["kind"]
        if kind == "frame":
            obs = dict(zip(keys, m["state"]))
            for cam, jpeg in m["images"].items():
                bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                obs[cam] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)  # lerobot 카메라와 같은 RGB
            frame = {
                **build_dataset_frame(ds.features, obs, prefix=OBS_STR),
                **build_dataset_frame(ds.features, dict(zip(keys, m["action"])), prefix=ACTION),
                "task": m["task"],
            }
            ds.add_frame(frame)
            frames += 1
        elif kind == "episode_end":
            ds.save_episode()
            episodes += 1
            log.info("에피소드 %d 저장 (누적 프레임 %d)", episodes - 1, frames)
        elif kind == "episode_discard":
            ds.clear_episode_buffer()
        elif kind == "finish":
            ds.finalize()
            log.info("완료: 에피소드 %d개, 프레임 %d개 → %s", episodes, frames, ds.root)
            if m.get("push"):
                ds.push_to_hub()
                log.info("Hub 에 올림: https://huggingface.co/datasets/%s", c["repo_id"])
            return
    sys.exit("finish 없이 입력이 끝남 (변환이 중간에 멈춤)")


if __name__ == "__main__":
    main()
