import math

import pytest

from lerobot_common.names import base_motor, joint_names
from lerobot_common.units import GRIPPER_HI, GRIPPER_LO, from_rad, to_rad


def test_joint_names():
    assert len(joint_names("bi")) == 12
    assert joint_names("bi")[0] == "left_shoulder_pan"
    assert joint_names("bi")[6] == "right_shoulder_pan"
    assert (
        joint_names("left")
        == joint_names("right")
        == [
            "shoulder_pan",
            "shoulder_lift",
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
            "gripper",
        ]
    )
    with pytest.raises(ValueError):
        joint_names("both")


def test_base_motor():
    assert base_motor("left_wrist_roll") == "wrist_roll"
    assert base_motor("right_gripper") == "gripper"
    assert base_motor("gripper") == "gripper"


def test_body_is_plain_degrees():
    assert to_rad("left_elbow_flex", 90.0) == pytest.approx(math.pi / 2)
    assert to_rad("shoulder_pan", -45.0) == pytest.approx(-math.pi / 4)


def test_gripper_maps_to_urdf_range():
    assert to_rad("right_gripper", 0.0) == pytest.approx(GRIPPER_LO)
    assert to_rad("gripper", 100.0) == pytest.approx(GRIPPER_HI)


@pytest.mark.parametrize("name", joint_names("bi"))
@pytest.mark.parametrize("value", [-120.0, -3.3, 0.0, 12.5, 100.0])
def test_round_trip(name, value):
    assert from_rad(name, to_rad(name, value)) == pytest.approx(value, abs=1e-9)
