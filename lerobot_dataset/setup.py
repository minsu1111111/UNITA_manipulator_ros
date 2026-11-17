from setuptools import find_packages, setup

package_name = "lerobot_dataset"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "LICENSE"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="UNITA Manipulation",
    maintainer_email="kms62197724@gmail.com",
    description="녹화한 rosbag 에피소드 → LeRobotDataset",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "convert = lerobot_dataset.convert:main",
        ],
    },
)
