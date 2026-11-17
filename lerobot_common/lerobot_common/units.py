"""lerobot 단위 ↔ ROS 토픽 단위(rad).

토픽의 관절값은 전부 rad 이고, SO-101 URDF/MJCF (so101_new_calib) 의 관절각과 같다.
그래서 robot_state_publisher, RViz, MuJoCo 에 변환 없이 바로 넣을 수 있다.

    몸통 5관절 : rad = deg2rad(lerobot 도)                      (부호 반전 없음)
    gripper    : rad = LO + (lerobot 0~100) / 100 * (HI - LO)  (URDF 범위로 선형)

근거: lerobot 의 new calib 는 0 도 = 관절 범위 중앙이고 MJCF 도 0 rad = 범위 중앙이다.
부호는 lerobot_pac/sim 에서 데이터셋 영상과 FK 를 비교해 전부 +1 로 확인했다 (실기로 한 번 더 확인할 것).
lerobot 단위가 필요한 곳(정책 입력, 데이터셋)에서만 이 모듈로 되돌린다.
"""

import math

from .names import is_gripper

# so101_new_calib.xml / .urdf 의 gripper 관절 범위 (rad)
GRIPPER_LO = -0.17453297762778586
GRIPPER_HI = 1.7453291995659765


def to_rad(name: str, value: float) -> float:
    """lerobot 값 하나 → rad. name 은 lerobot 모터 이름 (접두사 있어도 됨)."""
    if is_gripper(name):
        return GRIPPER_LO + value / 100.0 * (GRIPPER_HI - GRIPPER_LO)
    return math.radians(value)


def from_rad(name: str, value: float) -> float:
    """rad 하나 → lerobot 값 (몸통은 도, gripper 는 0~100)."""
    if is_gripper(name):
        return (value - GRIPPER_LO) / (GRIPPER_HI - GRIPPER_LO) * 100.0
    return math.degrees(value)


def dict_to_rad(values: dict[str, float]) -> dict[str, float]:
    return {n: to_rad(n, v) for n, v in values.items()}


def dict_from_rad(values: dict[str, float]) -> dict[str, float]:
    return {n: from_rad(n, v) for n, v in values.items()}
