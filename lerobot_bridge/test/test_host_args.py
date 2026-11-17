from lerobot_bridge.host_args import leader_plan, robot_plan
from lerobot_common.rig import DEFAULTS, Rig


def _rig(**kw) -> Rig:
    return Rig(dict(DEFAULTS, **kw), source=None)


COMMON = dict(fps=60, bind="127.0.0.1", state_port=5556, cmd_port=5557)


def test_bimanual_robot_args():
    plan = robot_plan(
        "bi",
        _rig(LEFT_PORT="/dev/ttyACM0", RIGHT_PORT="/dev/ttyACM1"),
        mock=False,
        cameras=True,
        max_rel=0,
        **COMMON,
    )
    a = plan.args
    assert "--robot.type=bi_so_follower" in a
    assert "--robot.left_arm_config.port=/dev/ttyACM0" in a
    assert "--robot.right_arm_config.port=/dev/ttyACM1" in a
    assert plan.cameras == []  # 카메라 경로가 비어 있으면 생략
    assert ("robots", "so_follower", "follower1", "bimanual_left") in plan.calib


def test_bimanual_max_rel_goes_per_arm():
    # BiSOFollowerConfig 최상위에 max_relative_target 을 주면 lerobot 이 인자 오류로 죽는다 (실기에서 겪음)
    a = robot_plan("bi", _rig(), mock=False, cameras=False, max_rel=20, **COMMON).args
    assert "--robot.left_arm_config.max_relative_target=20" in a
    assert "--robot.right_arm_config.max_relative_target=20" in a
    assert not any(x.startswith("--robot.max_relative_target") for x in a)


def test_camera_json_is_one_argument(tmp_path):
    cam = tmp_path / "video-index0"
    cam.touch()
    plan = robot_plan("bi", _rig(LEFT_CAM=str(cam)), mock=False, cameras=True, max_rel=0, **COMMON)
    assert plan.cameras == ["left_wrist"]
    arg = next(x for x in plan.args if x.startswith("--robot.left_arm_config.cameras="))
    assert " " not in arg and '"wrist"' in arg and '"width":320' in arg


def test_single_arm():
    plan = robot_plan(
        "right", _rig(RIGHT_PORT="/dev/ttyACM1"), mock=False, cameras=False, max_rel=0, **COMMON
    )
    assert "--robot.type=so101_follower" in plan.args
    assert "--robot.port=/dev/ttyACM1" in plan.args
    assert "--robot.id=follower2" in plan.args
    lp = leader_plan("right", _rig(), mock=False, fps=60, bind="127.0.0.1", state_port=5555)
    assert "--teleop.type=so101_leader" in lp.args and "--teleop.id=leader2" in lp.args


def test_mock_needs_no_rig():
    plan = robot_plan("bi", None, mock=True, cameras=True, max_rel=0, **COMMON)
    assert plan.script == "mock_host"  # lerobot 없이 시스템 python 으로 도는 호스트
    assert plan.args[:2] == ["--role=follower", "--bimanual=true"]
    assert plan.cameras == ["left_wrist", "right_wrist"]
    lp = leader_plan("left", None, mock=True, fps=60, bind="127.0.0.1", state_port=5555)
    assert lp.script == "mock_host" and lp.args[:2] == ["--role=leader", "--bimanual=false"]


def test_real_hardware_uses_lerobot_host():
    assert robot_plan("bi", _rig(), mock=False, cameras=False, max_rel=0, **COMMON).script == "hw_host"
