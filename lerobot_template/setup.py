from setuptools import find_packages, setup

package_name = "lerobot_template"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="UNITA Manipulation",
    maintainer_email="kms62197724@gmail.com",
    description="새 패키지를 만들 때 복사하는 예제",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # ros2 run lerobot_template joint_speed  →  lerobot_template/joint_speed.py 의 main()
            "joint_speed = lerobot_template.joint_speed:main",
        ],
    },
)
