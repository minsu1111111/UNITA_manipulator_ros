"""QoS 규칙: 발행은 RELIABLE, 구독은 BEST_EFFORT.

이렇게 하면 어떤 조합도 연결된다. RELIABLE 발행자는 BEST_EFFORT/RELIABLE 구독자 모두와 맞고,
BEST_EFFORT 구독자는 어떤 발행자와도 맞는다. (robot_state_publisher, RViz, rqt 처럼 기본 RELIABLE 로
구독하는 표준 도구가 우리 토픽을 그대로 받으려면 발행이 RELIABLE 이어야 한다.)

depth 는 작게 — 제어용 스트림은 최신 값만 의미 있다.
"""

from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

# 상태·명령·이미지 스트림을 발행할 때
PUB_STREAM = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5, reliability=ReliabilityPolicy.RELIABLE)

# 스트림을 구독할 때
SUB_STREAM = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)

# 놓치면 안 되는 드문 이벤트 (비상정지, 음성 명령 등) — 발행·구독 모두
EVENT = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10, reliability=ReliabilityPolicy.RELIABLE)
