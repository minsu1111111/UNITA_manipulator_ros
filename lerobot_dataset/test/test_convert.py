"""변환 로직 테스트 — 작은 bag 을 직접 만들어 시각 맞춤·단위·이미지를 검사한다 (lerobot 불필요)."""

import math
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import rosbag2_py
from builtin_interfaces.msg import Time
from lerobot_dataset.convert import convert_episode, probe, robot_type
from rclpy.serialization import serialize_message
from sensor_msgs.msg import CompressedImage, JointState

from lerobot_common.names import joint_names
from lerobot_common.units import to_rad

NS = 1_000_000_000
NAMES = joint_names("bi")


def make_bag(path, seconds=1.0, joint_hz=60, cam_hz=30, start_cmd_s=0.0):
    """joint_states·command 값 = 시각(초)을 lerobot 도로 쓴 값 → 프레임 값으로 '언제의 값인지' 알 수 있다."""
    w = rosbag2_py.SequentialWriter()
    w.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    for name, typ in (
        ("/robot/joint_states", "sensor_msgs/msg/JointState"),
        ("/robot/command", "sensor_msgs/msg/JointState"),
        ("/robot/cam/top/image/compressed", "sensor_msgs/msg/CompressedImage"),
    ):
        w.create_topic(rosbag2_py.TopicMetadata(name=name, type=typ, serialization_format="cdr"))
    jpeg = cv2.imencode(".jpg", np.zeros((48, 64, 3), np.uint8))[1].tobytes()
    t0 = 1_000 * NS
    events = []
    for i in range(int(seconds * joint_hz)):
        t = i / joint_hz
        js = JointState(name=NAMES, position=[to_rad(n, 50.0 if "gripper" in n else t) for n in NAMES])
        events.append((t0 + int(t * NS), "/robot/joint_states", js))
        if t >= start_cmd_s:
            cmd = JointState(name=NAMES, position=[to_rad(n, 50.0 if "gripper" in n else -t) for n in NAMES])
            events.append((t0 + int(t * NS) + 1000, "/robot/command", cmd))
    for i in range(int(seconds * cam_hz)):
        img = CompressedImage(format="jpeg", data=jpeg)
        img.header.stamp = Time(sec=0, nanosec=0)
        events.append((t0 + int(i / cam_hz * NS) + 2000, "/robot/cam/top/image/compressed", img))
    for ts, topic, msg in sorted(events, key=lambda e: e[0]):
        w.write(topic, serialize_message(msg), ts)
    del w
    return t0


class FakeWriter:
    def __init__(self):
        self.msgs = []

    def send(self, msg):
        self.msgs.append(msg)

    def frames(self):
        return [m for m in self.msgs if m["kind"] == "frame"]


ARGS = SimpleNamespace(task="pour", fps=30, max_age=0.1)


def test_probe(tmp_path):
    make_bag(tmp_path / "ep")
    info = probe(tmp_path / "ep")
    assert info["names"] == NAMES
    assert info["cameras"] == {"top": [48, 64, 3]}
    assert robot_type(info["names"]) == "bi_so_follower"
    assert robot_type(joint_names("left")) == "so_follower"


def test_frames_units_and_no_future(tmp_path):
    make_bag(tmp_path / "ep", seconds=1.0)
    w = FakeWriter()
    frames, dropped = convert_episode(tmp_path / "ep", probe(tmp_path / "ep"), ARGS, w)
    assert w.msgs[-1]["kind"] == "episode_end"
    assert 28 <= frames <= 30 and dropped == 0
    times = []
    for f in w.frames():
        st = dict(zip(NAMES, f["state"]))
        # 단위: 몸통은 도(= 기록 시각 초), 그리퍼는 0~100
        assert st["left_gripper"] == pytest.approx(50.0, abs=1e-6)
        times.append(st["left_shoulder_pan"])
        assert f["action"][0] == pytest.approx(-st["left_shoulder_pan"], abs=1 / 60 + 1e-6)
        assert f["images"]["top"][:2] == b"\xff\xd8"  # JPEG 그대로
        assert f["task"] == "pour"
    # 미래 값 없음: k 번째 프레임(시각 = 첫 프레임 + k/30 s)의 상태는 그 시각 이전 값
    t_first = times[0]
    for k, t in enumerate(times):
        assert t <= t_first + k / 30 + 1e-9
        assert t >= t_first + k / 30 - 1 / 60 - 1e-9  # 그리고 한 틱(60 Hz) 이상 오래되지 않음


def test_starts_when_all_topics_ready(tmp_path):
    # 명령이 0.5 s 부터 들어오면 그 전 프레임은 만들지 않는다
    make_bag(tmp_path / "ep", seconds=1.0, start_cmd_s=0.5)
    w = FakeWriter()
    frames, _ = convert_episode(tmp_path / "ep", probe(tmp_path / "ep"), ARGS, w)
    first_t = dict(zip(NAMES, w.frames()[0]["state"]))["left_shoulder_pan"]
    assert first_t >= 0.5 - 1 / 30
    assert frames == pytest.approx(15, abs=2)


def test_stale_camera_drops_frames(tmp_path):
    # 카메라가 2 Hz 면 max_age 0.1 s 를 넘는 프레임은 버린다
    make_bag(tmp_path / "ep", seconds=1.0, cam_hz=2)
    w = FakeWriter()
    frames, dropped = convert_episode(tmp_path / "ep", probe(tmp_path / "ep"), ARGS, w)
    assert dropped > frames > 0


def test_task_required(tmp_path):
    make_bag(tmp_path / "ep")
    with pytest.raises(RuntimeError, match="task"):
        convert_episode(
            tmp_path / "ep",
            probe(tmp_path / "ep"),
            SimpleNamespace(task="", fps=30, max_age=0.1),
            FakeWriter(),
        )


def test_math_sanity():
    assert to_rad("left_shoulder_pan", 30.0) == pytest.approx(math.radians(30.0))
