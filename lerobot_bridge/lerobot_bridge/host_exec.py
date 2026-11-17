"""`ros2 run lerobot_bridge host <lerobot 인자…>` — 호스트만 손으로 띄울 때.

lerobot env 의 python 으로 hosts/hw_host.py 를 exec 한다 (ROS 노드 없음). 인자는 lerobot-teleoperate 와 같다.
호스트를 로봇 PC 에서 띄우고 노드는 다른 PC 에서 `-p spawn_host:=false -p zmq_host:=<IP>` 로 붙을 때 쓴다.
정확한 인자는 노드에 `-p dry_run:=true` 를 주면 찍힌다.
"""

import os
import sys

from .host_process import host_command


def main():
    cmd = host_command("hw_host", sys.argv[1:])
    os.execv(cmd[0], cmd)


if __name__ == "__main__":
    main()
