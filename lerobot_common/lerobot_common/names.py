"""관절 이름. lerobot 모터 이름을 그대로 쓴다 (데이터셋 observation.state / action 순서와 같음).

단팔  : shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper            (6)
양팔  : left_shoulder_pan … left_gripper, right_shoulder_pan … right_gripper                 (12)
"""

SO_MOTORS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
SIDES = ("left", "right")

ARMS = ("bi", "left", "right")  # bi = 양팔, left/right = 그 팔 한 쌍만


def joint_names(arm: str) -> list[str]:
    """arm 에 따른 관절 이름 목록. bi 면 12개 (left_* 다음 right_*), 단팔이면 접두사 없는 6개."""
    if arm not in ARMS:
        raise ValueError(f"arm 은 {ARMS} 중 하나 (받은 값: {arm!r})")
    if arm == "bi":
        return [f"{side}_{m}" for side in SIDES for m in SO_MOTORS]
    return list(SO_MOTORS)


def base_motor(name: str) -> str:
    """'left_wrist_roll' → 'wrist_roll'. 접두사 없으면 그대로."""
    for side in SIDES:
        if name.startswith(side + "_"):
            return name[len(side) + 1 :]
    return name


def is_gripper(name: str) -> bool:
    return base_motor(name) == "gripper"
