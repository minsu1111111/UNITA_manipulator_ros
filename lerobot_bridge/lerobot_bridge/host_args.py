"""robot.env(Rig) → lerobot 호스트 인자.

실제 하드웨어(hw_host.py) 인자는 lerobot-teleoperate / lerobot-record 와 같다 (draccus). 예:
    --robot.type=bi_so_follower --robot.id=bimanual --robot.left_arm_config.port=/dev/ttyACM0 ...
mock(mock_host.py) 은 --role / --bimanual 만 받고 robot.env 를 읽지 않는다.
노드에 `-p dry_run:=true` 를 주면 여기서 만든 명령이 그대로 찍힌다.
"""

import json
from dataclasses import dataclass, field

from lerobot_common.rig import Rig, usable_camera

# 기본 ZMQ 포트
LEADER_STATE_PORT = 5555
ROBOT_STATE_PORT = 5556
ROBOT_CMD_PORT = 5557

# lerobot_pac train/record.sh 와 같은 해상도 (학습 데이터와 같아야 함)
CAM_SIZE = {"top": (640, 480), "wrist": (320, 240)}


@dataclass
class HostPlan:
    args: list[str]  # 호스트에 넘길 인자
    script: str = "hw_host"  # hosts/<script>.py — hw_host (lerobot env) | mock_host (시스템 python)
    cameras: list[str] = field(default_factory=list)  # 켜질 카메라의 관측 이름 (= 토픽 이름)
    calib: list[tuple[str, str, str, str]] = field(default_factory=list)  # ensure_calibration 인자들
    notes: list[str] = field(default_factory=list)


def _cam_json(path: str, size: tuple[int, int], fourcc: str) -> str:
    cfg = {"type": "opencv", "index_or_path": path, "width": size[0], "height": size[1], "fps": 30}
    if fourcc:
        cfg["fourcc"] = fourcc
    return json.dumps(cfg, separators=(",", ":"))


def _common(fps: int, bind: str, state_port: int) -> list[str]:
    return [f"--fps={fps}", f"--bind={bind}", f"--state_port={state_port}"]


def robot_plan(
    arm: str,
    rig: Rig | None,
    *,
    mock: bool,
    cameras: bool,
    max_rel: float,
    fps: int,
    bind: str,
    state_port: int,
    cmd_port: int,
    camera_fps: int = 30,
    jpeg_quality: int = 90,
) -> HostPlan:
    tail = [
        *_common(fps, bind, state_port),
        f"--cmd_port={cmd_port}",
        f"--camera_fps={camera_fps}",
        f"--jpeg_quality={jpeg_quality}",
    ]
    if mock:
        bi = "true" if arm == "bi" else "false"
        cams = ["left_wrist", "right_wrist"] if arm == "bi" else ["wrist"]  # mock 팔로워의 가짜 카메라
        return HostPlan(["--role=follower", f"--bimanual={bi}", *tail], script="mock_host", cameras=cams)

    assert rig is not None
    plan = HostPlan([])
    fourcc = rig["CAM_FOURCC"]

    def cam(flag: str, key: str, env_key: str, size_key: str, obs_name: str) -> list[str]:
        """카메라 인자 하나. obs_name = 관측·토픽에 나오는 이름 (팔별 카메라는 left_/right_ 접두사가 붙음)."""
        path = rig[env_key]
        if not cameras:
            return []
        if not usable_camera(path):
            plan.notes.append(f"카메라 {obs_name} 생략 ({env_key}={path or '(빈 값)'})")
            return []
        plan.cameras.append(obs_name)
        return [f'{flag}={{"{key}":{_cam_json(path, CAM_SIZE[size_key], fourcc)}}}']

    if arm == "bi":
        rid = rig["ROBOT_ID"]
        plan.calib += [
            ("robots", "so_follower", rig["CALIB_LEFT"], f"{rid}_left"),
            ("robots", "so_follower", rig["CALIB_RIGHT"], f"{rid}_right"),
        ]
        plan.args = [
            "--robot.type=bi_so_follower",
            f"--robot.id={rid}",
            f"--robot.left_arm_config.port={rig['LEFT_PORT']}",
            f"--robot.right_arm_config.port={rig['RIGHT_PORT']}",
            *cam("--robot.cameras", "top", "TOP_CAM", "top", "top"),
            *cam("--robot.left_arm_config.cameras", "wrist", "LEFT_CAM", "wrist", "left_wrist"),
            *cam("--robot.right_arm_config.cameras", "wrist", "RIGHT_CAM", "wrist", "right_wrist"),
        ]
        if max_rel > 0:
            # BiSOFollowerConfig 최상위에는 max_relative_target 이 없다 — 팔별로 줘야 함
            plan.args += [
                f"--robot.left_arm_config.max_relative_target={max_rel}",
                f"--robot.right_arm_config.max_relative_target={max_rel}",
            ]
    else:
        side = arm.upper()  # LEFT | RIGHT
        fid = rig[f"CALIB_{side}"]
        plan.calib.append(("robots", "so_follower", fid, fid))
        plan.args = [
            "--robot.type=so101_follower",
            f"--robot.id={fid}",
            f"--robot.port={rig[f'{side}_PORT']}",
            *cam("--robot.cameras", "wrist", f"{side}_CAM", "wrist", "wrist"),
        ]
        if max_rel > 0:
            plan.args.append(f"--robot.max_relative_target={max_rel}")
    plan.args += tail
    return plan


def leader_plan(arm: str, rig: Rig | None, *, mock: bool, fps: int, bind: str, state_port: int) -> HostPlan:
    tail = _common(fps, bind, state_port)
    if mock:
        bi = "true" if arm == "bi" else "false"
        return HostPlan(["--role=leader", f"--bimanual={bi}", *tail], script="mock_host")

    assert rig is not None
    if arm == "bi":
        lid = rig["LEADER_ID"]
        return HostPlan(
            [
                "--teleop.type=bi_so_leader",
                f"--teleop.id={lid}",
                f"--teleop.left_arm_config.port={rig['LEADER_LEFT_PORT']}",
                f"--teleop.right_arm_config.port={rig['LEADER_RIGHT_PORT']}",
                *tail,
            ],
            calib=[
                ("teleoperators", "so_leader", rig["LEADER_CALIB_LEFT"], f"{lid}_left"),
                ("teleoperators", "so_leader", rig["LEADER_CALIB_RIGHT"], f"{lid}_right"),
            ],
        )
    side = arm.upper()
    lid = rig[f"LEADER_CALIB_{side}"]
    return HostPlan(
        [
            "--teleop.type=so101_leader",
            f"--teleop.id={lid}",
            f"--teleop.port={rig[f'LEADER_{side}_PORT']}",
            *tail,
        ],
        calib=[("teleoperators", "so_leader", lid, lid)],
    )
