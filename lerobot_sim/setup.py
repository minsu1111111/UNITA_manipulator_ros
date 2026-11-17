import os

from setuptools import find_packages, setup

package_name = "lerobot_sim"


def tree(src: str, dst: str) -> list[tuple[str, list[str]]]:
    """src 폴더를 share/<pkg>/dst 로 통째로 설치 (MJCF + 메시)."""
    out = []
    for root, _, files in os.walk(src):
        if files:
            out.append(
                (os.path.join(dst, os.path.relpath(root, src)), [os.path.join(root, f) for f in files])
            )
    return out


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        # 노드에서 찾을 때: get_package_share_directory("lerobot_sim") + "/models/bimanual.xml"
        *tree("models", f"share/{package_name}/models"),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="UNITA Manipulation",
    maintainer_email="kms62197724@gmail.com",
    description="MuJoCo 시뮬: SO-101 단팔·양팔 장면",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # 시뮬 노드를 만들면 여기에 추가:  "sim = lerobot_sim.sim_node:main",
        ],
    },
)
