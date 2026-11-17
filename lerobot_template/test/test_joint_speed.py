"""로직 테스트 — ROS 를 띄우지 않고 순수 함수만 검사한다. `colcon test` 또는 pytest 로 실행."""

import pytest

from lerobot_template.joint_speed import max_speed


def test_fastest_joint():
    prev = {"shoulder_pan": 0.0, "elbow_flex": 0.0}
    cur = {"shoulder_pan": 0.1, "elbow_flex": -0.3}
    assert max_speed(prev, cur, 0.1) == pytest.approx(3.0)


def test_gripper_ignored():
    prev = {"left_gripper": 0.0, "left_wrist_roll": 0.0}
    cur = {"left_gripper": 1.0, "left_wrist_roll": 0.0}
    assert max_speed(prev, cur, 0.1) == 0.0


def test_bad_dt():
    assert max_speed({"a": 0.0}, {"a": 1.0}, 0.0) == 0.0
