"""호스트 프로세스 띄우기/정리.

실제 하드웨어 호스트(hosts/hw_host.py)는 lerobot env 의 python(3.12)으로, mock 호스트(hosts/mock_host.py)는
이 노드와 같은 시스템 python 으로 띄운다 — mock 은 lerobot 이 없는 PC 에서도 돈다.

lerobot python 찾는 순서:
    1. robot.env 의 LEROBOT_PY
    2. 환경변수 LEROBOT_PY
    3. conda 가 설치돼 있으면 그 conda 의 envs/lerobot   (환경변수 CONDA_EXE 로 위치를 안다)
    4. 흔한 설치 위치들 (miniconda3, miniforge3, anaconda3, mambaforge, ~/.conda) 의 envs/lerobot
"""

import ctypes
import os
import signal
import subprocess
import sys
from pathlib import Path

from ament_index_python.packages import get_package_share_directory

COMMON_PREFIXES = ("~/miniconda3", "~/miniforge3", "~/anaconda3", "~/mambaforge", "~/.conda")
ENV_NAME = "lerobot"


def _candidates(preferred: str) -> list[str]:
    out = []
    if preferred:
        out.append(os.path.expanduser(preferred))
    if os.environ.get("LEROBOT_PY"):
        out.append(os.path.expanduser(os.environ["LEROBOT_PY"]))
    if os.environ.get("CONDA_EXE"):  # <conda>/bin/conda → <conda>/envs/lerobot/bin/python
        out.append(
            str(Path(os.environ["CONDA_EXE"]).resolve().parents[1] / "envs" / ENV_NAME / "bin" / "python")
        )
    out += [os.path.expanduser(f"{p}/envs/{ENV_NAME}/bin/python") for p in COMMON_PREFIXES]
    return list(dict.fromkeys(out))  # 순서 유지 중복 제거


def lerobot_python(preferred: str = "") -> str:
    """lerobot 이 설치된 python 실행 파일. 못 찾으면 RuntimeError (해결 방법을 담은 메시지)."""
    cands = _candidates(preferred)
    for c in cands:
        if Path(c).is_file():
            return c
    raise RuntimeError(
        "lerobot python 을 못 찾음. config/robot.env 에 LEROBOT_PY=<lerobot env 의 python 경로> 를 적을 것 "
        "(확인: conda activate lerobot && which python). 로봇 없이 개발 중이면 -p mock:=true 로 띄우면 lerobot 이 필요 없다. "
        "찾아본 곳: " + ", ".join(cands)
    )


def host_script(name: str) -> str:
    """share/lerobot_bridge/hosts/<name>.py"""
    return os.path.join(get_package_share_directory("lerobot_bridge"), "hosts", f"{name}.py")


def host_command(script: str, args: list[str], lerobot_py: str = "") -> list[str]:
    """mock_host 는 이 노드의 python 으로, 나머지는 lerobot python 으로."""
    python = sys.executable if script == "mock_host" else lerobot_python(lerobot_py)
    return [python, host_script(script), *args]


def _die_with_parent():
    # 부모(ROS 노드)가 어떻게 죽든 호스트에 SIGTERM → 호스트는 KeyboardInterrupt 로 받아 토크를 끄고 끝낸다
    PR_SET_PDEATHSIG = 1
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)


class HostProcess:
    """자식 호스트 프로세스 하나. stdout/stderr 는 노드 터미널에 그대로 나온다."""

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self.proc = subprocess.Popen(cmd, preexec_fn=_die_with_parent, stdout=sys.stdout, stderr=sys.stderr)

    @property
    def pid(self) -> int:
        return self.proc.pid

    def poll(self) -> int | None:
        """끝났으면 종료 코드, 살아 있으면 None."""
        return self.proc.poll()

    def stop(self, timeout_s: float = 8.0) -> int | None:
        """SIGINT → (timeout) → SIGTERM → (2 s) → SIGKILL. 모터 disconnect 시간을 넉넉히 준다."""
        if self.proc.poll() is not None:
            return self.proc.returncode
        for sig, wait in ((signal.SIGINT, timeout_s), (signal.SIGTERM, 2.0)):
            try:
                self.proc.send_signal(sig)
                return self.proc.wait(wait)
            except subprocess.TimeoutExpired:
                continue
        self.proc.kill()
        return self.proc.wait()
