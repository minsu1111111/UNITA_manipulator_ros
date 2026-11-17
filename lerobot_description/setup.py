import os

from setuptools import find_packages, setup

package_name = "lerobot_description"


def tree(src: str) -> list[tuple[str, list[str]]]:
    """src 폴더를 share/<pkg>/src 로 통째로 설치."""
    out = []
    for root, _, files in os.walk(src):
        if files:
            out.append((os.path.join("share", package_name, root), [os.path.join(root, f) for f in files]))
    return out


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "LICENSE"]),
        # xacro 의 $(find lerobot_description) / package://lerobot_description/meshes 가 이 위치를 가리킨다
        *tree("urdf"),
        *tree("meshes"),
        *tree("rviz"),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="UNITA Manipulation",
    maintainer_email="kms62197724@gmail.com",
    description="SO-101 URDF·메시·RViz 설정",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "state_publisher = lerobot_description.state_publisher:main",
        ],
    },
)
