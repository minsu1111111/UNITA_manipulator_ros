from lerobot_common.rig import DEFAULTS, parse_env, resolve_ports


def test_parse_env():
    text = """
    # 주석
    LEFT_PORT=/dev/ttyACM0
    TOP_CAM="/dev/v4l/by-id/usb-cam-video-index0"
    EMPTY=
    no_equal_sign_line
    """
    v = parse_env(text)
    assert v["LEFT_PORT"] == "/dev/ttyACM0"
    assert v["TOP_CAM"] == "/dev/v4l/by-id/usb-cam-video-index0"
    assert v["EMPTY"] == ""
    assert "no_equal_sign_line" not in v


def test_resolve_ports_by_serial():
    values = dict(DEFAULTS, LEFT_SERIAL="OLD123, NEW456", RIGHT_SERIAL="R1", LEADER_LEFT_SERIAL="MISSING")
    notes = []
    found = {"NEW456": "/dev/ttyACM3", "R1": "/dev/ttyACM1"}
    resolve_ports(values, notes, found=found)
    assert values["LEFT_PORT"] == "/dev/ttyACM3"  # 두 번째 시리얼로 찾음 (보드 교체 대응)
    assert values["RIGHT_PORT"] == "/dev/ttyACM1"
    assert values["LEADER_LEFT_PORT"] == DEFAULTS["LEADER_LEFT_PORT"]  # 못 찾으면 PORT 값 유지
    assert values["LEADER_RIGHT_PORT"] == DEFAULTS["LEADER_RIGHT_PORT"]  # 시리얼 비어 있으면 건드리지 않음
    assert any("MISSING" in n for n in notes)
