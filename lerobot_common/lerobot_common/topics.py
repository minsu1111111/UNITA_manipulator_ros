"""토픽 이름. docs/TOPICS.md 와 같아야 한다 — 바꿀 땐 문서를 먼저 고친다.

전부 상대 이름(앞에 / 없음)이라 `--ros-args -r __ns:=/rig2` 로 통째로 다른 네임스페이스에 띄울 수 있다.
"""

# ---- 지금 쓰는 것 ----------------------------------------------------------------------------
ROBOT_JOINT_STATES = "robot/joint_states"  # JointState, rad (robot 노드 / 나중에 sim 노드가 발행)
ROBOT_COMMAND = "robot/command"  # JointState, rad (teleop 노드 / 나중에 safety 노드가 발행)
LEADER_JOINT_STATES = "leader/joint_states"  # JointState, rad (leader 노드가 발행)


def robot_camera(name: str) -> str:
    """sensor_msgs/CompressedImage (jpeg). name = top | left_wrist | right_wrist | wrist(단팔)"""
    return f"robot/cam/{name}/image/compressed"


# ---- 예약 (아직 발행하는 노드 없음. 이름만 먼저 고정) -------------------------------------------
POLICY_ACTION = "policy/action"  # sensor_msgs/JointState, rad   policy → safety
TASK_INSTRUCTION = "task/instruction"  # std_msgs/String           SmolVLA 같은 언어 조건 정책의 지시문
SAFETY_ESTOP = "safety/estop"  # std_msgs/Bool                    operator/speech → safety
SPEECH_COMMAND = "speech/command"  # std_msgs/String              STT 가 인식한 명령
SPEECH_SAY = "speech/say"  # std_msgs/String                      TTS 가 읽을 문구
PERCEPTION_OBJECTS = "perception/objects"  # 타입 미정 (비전 담당이 TOPICS.md 에 제안)
