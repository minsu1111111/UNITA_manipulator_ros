import os
from glob import glob

from setuptools import find_packages, setup

package_name = "lerobot_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        # lerobot env(py3.12) 에서 도는 호스트. ROS 쪽 python 으로는 import 하지 않으므로 데이터 파일로 설치한다
        (os.path.join("share", package_name, "hosts"), glob("hosts/*.py")),
    ],
    install_requires=["setuptools", "pyzmq"],
    zip_safe=True,
    maintainer="UNITA Manipulation",
    maintainer_email="kms62197724@gmail.com",
    description="lerobot 기능을 ROS 노드로 (robot, leader, teleop)",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "robot = lerobot_bridge.hw_bridge:robot_main",
            "leader = lerobot_bridge.hw_bridge:leader_main",
            "teleop = lerobot_bridge.teleop_node:main",
            "host = lerobot_bridge.host_exec:main",
        ],
    },
)
