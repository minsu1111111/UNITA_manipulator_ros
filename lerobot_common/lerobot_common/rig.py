"""리그(PC 별 하드웨어) 설정 — config/robot.env 를 읽고, 보드 시리얼로 실제 포트를 찾는다.

robot.env 는 KEY=VALUE 텍스트 파일이다 (셸 문법 아님, 주석 #). 예시는 config/robot.env.example.
찾는 순서:
    1. 노드 파라미터 robot_env
    2. 환경변수 UNITA_ROBOT_ENV
    3. 이 저장소의 config/robot.env            (colcon build --symlink-install 일 때 소스 위치를 따라감)
    4. ~/UNITA_manipulator_ros/config/robot.env
없으면 DEFAULTS 로 돈다 (로봇 PC 가 아니면 robot.env 가 없어도 된다 — mock 은 읽지 않는다).

포트: *_SERIAL 에 보드 USB 시리얼(쉼표로 여러 개)이 있으면 /sys 에서 그 보드의 ttyACM 을 직접 찾는다.
udev 규칙이 틀리거나 /dev/ttyACM 번호가 바뀌어도 된다. 못 찾으면 *_PORT 값을 그대로 쓴다.
"""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    # 팔로워 (팀 확인 2026-10-04: 1 = 왼팔, 2 = 오른팔)
    "LEFT_SERIAL": "",
    "LEFT_PORT": "/dev/follower1",
    "RIGHT_SERIAL": "",
    "RIGHT_PORT": "/dev/follower2",
    "ROBOT_ID": "bimanual",
    "CALIB_LEFT": "follower1",
    "CALIB_RIGHT": "follower2",
    # 리더
    "LEADER_LEFT_SERIAL": "",
    "LEADER_LEFT_PORT": "/dev/leader1",
    "LEADER_RIGHT_SERIAL": "",
    "LEADER_RIGHT_PORT": "/dev/leader2",
    "LEADER_ID": "bimanual_leader",
    "LEADER_CALIB_LEFT": "leader1",
    "LEADER_CALIB_RIGHT": "leader2",
    # HF 캐시에 캘리 json 이 없을 때 복사해 올 폴더 (비우면 HF 캐시만 본다)
    "CALIB_DIR": "",
    # lerobot env 의 python. 비우면 자동으로 찾는다 (lerobot_bridge/host_process.py)
    "LEROBOT_PY": "",
    # 카메라 (OpenCV 경로. 비우면 그 카메라 없이)
    "TOP_CAM": "",
    "LEFT_CAM": "",
    "RIGHT_CAM": "",
    "CAM_FOURCC": "",
}

# (포트 키, 시리얼 키)
PORT_KEYS = (
    ("LEFT_PORT", "LEFT_SERIAL"),
    ("RIGHT_PORT", "RIGHT_SERIAL"),
    ("LEADER_LEFT_PORT", "LEADER_LEFT_SERIAL"),
    ("LEADER_RIGHT_PORT", "LEADER_RIGHT_SERIAL"),
)


@dataclass
class Rig:
    values: dict[str, str]
    source: Path | None  # 읽은 파일 (없으면 None = 기본값)
    notes: list[str] = field(default_factory=list)  # 사람이 볼 메시지 (포트를 시리얼로 바꿨다 등)

    def __getitem__(self, key: str) -> str:
        return self.values[key]


def _repo_config() -> Path | None:
    # <repo>/lerobot_common/lerobot_common/rig.py → <repo>
    try:
        repo = Path(__file__).resolve().parents[2]
    except IndexError:
        return None
    p = repo / "config" / "robot.env"
    return p if p.is_file() else None


def find_robot_env(explicit: str = "") -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    if os.environ.get("UNITA_ROBOT_ENV"):
        return Path(os.environ["UNITA_ROBOT_ENV"]).expanduser()
    candidates = [
        _repo_config(),
        Path("~/UNITA_manipulator_ros/config/robot.env").expanduser(),
    ]
    return next((p for p in candidates if p is not None and p.is_file()), None)


def parse_env(text: str) -> dict[str, str]:
    """KEY=VALUE 줄들 → dict. 빈 줄·# 주석 무시, 값 양쪽 따옴표 제거."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("'\"")
    return out


def tty_serials() -> dict[str, str]:
    """{보드 USB 시리얼: /dev/ttyXXX}. ttyACM(STS 보드)·ttyUSB 모두. 시리얼은 sysfs 의 USB 장치 폴더에 있다."""
    out = {}
    for pattern in ("ttyACM*", "ttyUSB*"):
        for dev in sorted(Path("/sys/class/tty").glob(pattern)):
            d = (dev / "device").resolve()
            for _ in range(4):  # 인터페이스 → USB 장치 쪽으로 올라가며 serial 파일을 찾는다
                f = d / "serial"
                if f.is_file():
                    out[f.read_text().strip()] = f"/dev/{dev.name}"
                    break
                d = d.parent
    return out


def resolve_ports(values: dict[str, str], notes: list[str], found: dict[str, str] | None = None) -> None:
    """*_SERIAL 로 찾은 tty 로 *_PORT 를 덮어쓴다 (제자리 수정)."""
    found = tty_serials() if found is None else found
    for port_key, serial_key in PORT_KEYS:
        serials = [s.strip() for s in values.get(serial_key, "").split(",") if s.strip()]
        if not serials:
            continue
        hit = next((found[s] for s in serials if s in found), None)
        if hit is None:
            notes.append(f"{serial_key}={','.join(serials)} 보드 없음 → {port_key}={values[port_key]} 사용")
            continue
        if values.get(port_key) != hit:
            notes.append(f"{port_key}: {values.get(port_key) or '(빈 값)'} → {hit} (시리얼로 찾음)")
        values[port_key] = hit


def load_rig(explicit: str = "", find_ports: bool = True) -> Rig:
    path = find_robot_env(explicit)
    values = dict(DEFAULTS)
    notes = []
    if path is not None and path.is_file():
        values.update(parse_env(path.read_text()))
        notes.append(f"robot.env: {path}")
    else:
        path = None
        notes.append("robot.env 없음 → 기본값 (config/robot.env.example 을 복사해 채울 것)")
    if find_ports:
        resolve_ports(values, notes)
    return Rig(values, path, notes)


def usable_camera(path: str) -> bool:
    """비었거나 자리표시자(REPLACE)거나 장치가 없으면 False."""
    return bool(path) and "REPLACE" not in path and Path(path).exists()


def ensure_calibration(kind: str, typ: str, src_id: str, dst_id: str, calib_dir: str) -> str | None:
    """lerobot 이 읽는 HF 캐시에 dst_id.json 이 없으면 src_id.json 을 복사한다 (캐시 → calib_dir 순으로 찾음).

    kind: robots | teleoperators, typ: so_follower | so_leader.
    반환: 복사했으면 메시지, 이미 있으면 None. 원본이 없으면 FileNotFoundError.
    양팔(bi_so_*)은 팔별 id 를 "{id}_left"/"{id}_right" 로 찾기 때문에 follower1.json → bimanual_left.json 처럼 복사가 필요하다.
    """
    cache = Path(os.environ.get("HF_LEROBOT_CALIBRATION", "~/.cache/huggingface/lerobot/calibration"))
    d = cache.expanduser() / kind / typ
    dst = d / f"{dst_id}.json"
    if dst.is_file():
        return None
    src = d / f"{src_id}.json"
    if not src.is_file() and calib_dir:
        src = Path(calib_dir).expanduser() / f"{src_id}.json"
    if not src.is_file():
        raise FileNotFoundError(
            f"캘리브레이션 없음: {src_id}.json (HF 캐시 {d} 에도, CALIB_DIR={calib_dir or '(빈 값)'} 에도). "
            f"이 팔을 lerobot-calibrate 로 캘리브레이션하거나 (id={src_id}), "
            "받은 json 이 있는 폴더를 robot.env 의 CALIB_DIR 에 적을 것"
        )
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    return f"calib {src} → {dst}"
