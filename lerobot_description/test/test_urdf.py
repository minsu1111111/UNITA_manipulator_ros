"""URDF 가 토픽 계약과 맞는지: 관절 이름, 그리퍼 범위, 카메라 프레임. xacro 를 고치면 이 테스트가 지켜 준다."""

import os

import pytest
import xacro
from ament_index_python.packages import get_package_share_directory
from urdf_parser_py.urdf import URDF

from lerobot_common.names import joint_names
from lerobot_common.units import GRIPPER_HI, GRIPPER_LO

URDF_DIR = os.path.join(get_package_share_directory("lerobot_description"), "urdf")


def load(name: str, **args) -> URDF:
    doc = xacro.process_file(os.path.join(URDF_DIR, name), mappings={k: str(v) for k, v in args.items()})
    return URDF.from_xml_string(doc.toxml())


@pytest.mark.parametrize("variant", ["follower", "leader"])
def test_bimanual_joint_names(variant):
    robot = load("so101_bimanual.urdf.xacro", variant=variant)
    movable = [j.name for j in robot.joints if j.type == "revolute"]
    assert sorted(movable) == sorted(joint_names("bi"))


@pytest.mark.parametrize("variant", ["follower", "leader"])
def test_single_joint_names(variant):
    robot = load("so101_single.urdf.xacro", variant=variant)
    movable = [j.name for j in robot.joints if j.type == "revolute"]
    assert sorted(movable) == sorted(joint_names("left"))


def test_gripper_range_matches_units():
    # 토픽의 gripper rad 는 lerobot 0~100 을 이 범위로 선형 변환한 값이다 (lerobot_common.units)
    robot = load("so101_bimanual.urdf.xacro")
    for side in ("left", "right"):
        j = next(j for j in robot.joints if j.name == f"{side}_gripper")
        assert j.limit.lower == pytest.approx(GRIPPER_LO, abs=1e-5)
        assert j.limit.upper == pytest.approx(GRIPPER_HI, abs=1e-5)


def test_camera_frames():
    # robot 노드가 내는 이미지 frame_id = <name>_camera_optical_frame
    bi = {link.name for link in load("so101_bimanual.urdf.xacro").links}
    for cam in ("top", "left_wrist", "right_wrist"):
        assert f"{cam}_camera_optical_frame" in bi
    single = {link.name for link in load("so101_single.urdf.xacro").links}
    for cam in ("top", "wrist"):
        assert f"{cam}_camera_optical_frame" in single
    assert not any(
        n.endswith("_camera_link")
        for n in (link.name for link in load("so101_bimanual.urdf.xacro", cameras="false").links)
    )


def test_spacing():
    robot = load("so101_bimanual.urdf.xacro", spacing=0.6)
    mounts = {j.name: j.origin.xyz[1] for j in robot.joints if j.name.endswith("_mount")}
    assert mounts == {"left_mount": pytest.approx(0.3), "right_mount": pytest.approx(-0.3)}
