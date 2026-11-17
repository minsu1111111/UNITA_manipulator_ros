# 환경 준비

처음 받은 PC 에서 위에서부터 따라 한다. 맡은 일에 따라 필요한 것이 다르다.

| 단계 | 모두 | 로봇 PC (실제 팔 연결) | 시뮬 작업 |
|---|---|---|---|
| [1. Ubuntu 22.04 + ROS2 Humble](#1-ubuntu-2204--ros2-humble) | ✅ | ✅ | ✅ |
| [2. conda 와 ROS 안 꼬이게](#2-conda-와-ros-안-꼬이게) | ✅ (conda 가 있으면) | ✅ | ✅ |
| [3. 저장소 받기와 빌드](#3-저장소-받기와-빌드) | ✅ | ✅ | ✅ |
| [4. ROS_DOMAIN_ID](#4-ros_domain_id--다른-사람-로봇과-섞이지-않게) | ✅ | ✅ | ✅ |
| [5. 확인 (mock)](#5-확인--로봇-없이-텔레옵) | ✅ | ✅ | ✅ |
| [6. lerobot · robot.env · 캘리브레이션](#6-로봇-pc-만--lerobot-robotenv-캘리브레이션) | | ✅ | |
| [7. MuJoCo](#7-시뮬-작업--mujoco) | | | ✅ |

**로봇 없이 개발하는 사람(비전·시뮬·음성 등)은 lerobot 을 설치하지 않아도 된다.** `mock:=true` 는 ROS 만으로 돈다.

검증한 조합: Ubuntu 22.04, ROS2 Humble, lerobot 0.6.1 (동아리 fork), MuJoCo 3.8.1.

---

## 1. Ubuntu 22.04 + ROS2 Humble

ROS2 공식 설치 문서(Ubuntu deb packages)대로 `ros-humble-desktop` 을 설치한다: https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html

그다음 빌드 도구:

```bash
sudo apt install python3-colcon-common-extensions python3-rosdep python3-pip
```

## 2. conda 와 ROS 안 꼬이게

conda 가 깔린 PC 는 터미널을 열 때마다 conda `base` 가 켜진다. 그러면 `python3` 가 conda 것을 가리켜서 ROS 가 깨진다
(`No module named 'rclpy._rclpy_pybind11'`). 자동으로 켜지지 않게 한 번만 설정한다:

```bash
conda config --set auto_activate_base false
```

이후 규칙은 하나다:

| 터미널 | 할 일 |
|---|---|
| 그냥 연 터미널 (conda 꺼짐) | `ros2`, `colcon`, `rqt`, `rosdep`, 시뮬 노드 — **이 저장소의 모든 것** |
| `conda activate lerobot` 한 터미널 | `lerobot-record`, `lerobot-train`, `lerobot-calibrate` — lerobot 명령만 |

conda 를 켠 터미널에서 `ros2` 나 `colcon build` 를 하지 않는다. 우리 노드는 lerobot 이 필요할 때 lerobot env 의 python 을
직접 찾아 부르므로, ROS 터미널에서 conda 를 켤 일이 없다.

## 3. 저장소 받기와 빌드

```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src && git clone https://github.com/minsu1111111/UNITA_manipulator_ros.git
```

의존성 설치 (`rosdep init` 은 PC 마다 처음 한 번, 이미 했으면 에러가 나도 무시):

```bash
sudo rosdep init
```
```bash
rosdep update
```
```bash
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && rosdep install --from-paths src --ignore-src -y --rosdistro humble
```

빌드 — **반드시 `--symlink-install`** (python 파일을 고칠 때마다 다시 빌드하지 않아도 되고, `config/robot.env` 를 찾는 데도 필요하다):

```bash
cd ~/ros2_ws && colcon build --symlink-install
```

새 터미널마다 ROS 와 이 워크스페이스를 불러와야 한다. `~/.bashrc` 끝에 한 번 넣어 두면 편하다:

```bash
echo 'source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash' >> ~/.bashrc
```

새 노드(`setup.py` 의 `entry_points`)나 새 파일을 추가했을 때만 다시 `colcon build --symlink-install`.

## 4. ROS_DOMAIN_ID — 다른 사람 로봇과 섞이지 않게

ROS2 는 **같은 네트워크(동아리 와이파이)의 모든 PC 가 서로의 토픽을 본다.** 두 사람이 동시에 텔레옵을 띄우면
한 사람의 `teleop` 이 다른 사람의 로봇을 움직일 수 있다. 사람마다 다른 번호를 쓴다:

```bash
echo 'export ROS_DOMAIN_ID=<0~101 중 내 번호>' >> ~/.bashrc
```

혼자 내 PC 안에서만 돌릴 거면 대신 `export ROS_LOCALHOST_ONLY=1` 도 된다 (다른 PC 와 통신하려면 다시 지운다).
같은 로봇을 여러 PC 에서 같이 볼 때만 그 PC 들끼리 번호를 맞춘다.

## 5. 확인 — 로봇 없이 텔레옵

터미널 3개 (모두 conda 꺼진 터미널):

```bash
ros2 run lerobot_bridge robot --ros-args -p mock:=true
```
```bash
ros2 run lerobot_bridge leader --ros-args -p mock:=true
```
```bash
ros2 run lerobot_bridge teleop
```

네 번째 터미널에서 확인:

```bash
ros2 topic hz /robot/joint_states
```

`average rate: 59.x` 가 나오면 된다 (가짜 리더가 사인파로 움직이고 가짜 로봇이 따라온다). 가짜 손목 카메라도 볼 수 있다:

```bash
ros2 run rqt_image_view rqt_image_view /robot/cam/left_wrist/image/compressed
```

테스트:

```bash
cd ~/ros2_ws && colcon test && colcon test-result --verbose
```

---

## 6. 로봇 PC 만 — lerobot, robot.env, 캘리브레이션

### lerobot 설치

동아리 lerobot fork (0.6.1) 를 conda env `lerobot` (Python 3.12) 에 설치한다. lerobot 명령은 conda 를 켠 터미널에서:

```bash
conda create -y -n lerobot python=3.12
```
```bash
conda activate lerobot && conda install -y -c conda-forge ffmpeg
```
```bash
git clone https://github.com/minsu1111111/Unita_lerobot.git ~/lerobot && cd ~/lerobot && pip install -e ".[feetech]"
```

녹화한 에피소드를 데이터셋으로 바꾸는 PC(`ros2 run lerobot_dataset convert`)에도 lerobot 이 필요하다 — 로봇 PC 에서 바꾸는 게 보통이다.

노드는 lerobot env 의 python 을 자동으로 찾는다 (conda 의 `envs/lerobot`). 다른 이름·위치에 설치했으면 robot.env 의 `LEROBOT_PY` 에 적는다
(`conda activate lerobot && which python` 으로 경로 확인).

### 시리얼 포트 권한

팔 보드(`/dev/ttyACM*`)를 열려면 `dialout` 그룹이어야 한다. 넣은 뒤 **로그아웃 후 다시 로그인**:

```bash
sudo usermod -aG dialout $USER
```

### robot.env

```bash
cp ~/ros2_ws/src/UNITA_manipulator_ros/config/robot.env.example ~/ros2_ws/src/UNITA_manipulator_ros/config/robot.env
```

채울 것 (자세한 설명은 파일 안 주석):

- `*_SERIAL`: 팔 보드 USB 시리얼. 보드를 하나씩 꽂으며 `udevadm info -q property -n /dev/ttyACM0 | grep SERIAL_SHORT` 로 확인.
  적어 두면 `/dev/ttyACM` 번호가 바뀌어도 노드가 그 보드를 찾는다.
- `*_CAM`: 카메라 경로. 같은 모델 손목 카메라 두 대는 `/dev/v4l/by-path/...` (꽂는 USB 포트를 고정할 것).
- `CALIB_*`, `ROBOT_ID`, `LEADER_ID`: 캘리브레이션 id (아래).

`robot.env` 는 PC 마다 다르므로 깃에 올라가지 않는다.

### 캘리브레이션

캘리브레이션은 **팔 하드웨어에 묶여 있다** — 그 팔을 직접 캘리브레이션한 json 만 쓴다. 팔마다 한 번 (lerobot 터미널에서):

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=follower1
```
```bash
lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/ttyACM2 --teleop.id=leader1
```

(포트·id 는 팔마다 바꿔서 4번.) 결과는 `~/.cache/huggingface/lerobot/calibration/` 에 저장된다.
양팔 모드는 `bimanual_left.json` 처럼 다른 이름을 찾는데, 없으면 노드가 `follower1.json` 등을 그 이름으로 복사해 준다
(robot.env 의 `CALIB_LEFT` 등). 다른 PC 에서 캘리한 json 을 받아 쓰려면 그 폴더를 `CALIB_DIR` 에 적는다.

### 확인

모터를 움직이기 전에, 노드가 쓸 포트·카메라·lerobot 명령만 찍어 본다:

```bash
ros2 run lerobot_bridge robot --ros-args -p dry_run:=true
```

첫 실기는 한 팔, 카메라 없이, 스텝 제한을 걸고:

```bash
ros2 run lerobot_bridge robot --ros-args -p arm:=left -p cameras:=false -p max_rel:=20
```

리더를 로봇과 비슷한 자세로 둔 뒤 `leader`(같은 `arm:=left`)와 `teleop` 을 띄운다. **robot 을 Ctrl+C 하면 토크가 꺼지니 팔을 받칠 것.**

---

## 7. 시뮬 작업 — MuJoCo

시뮬 노드는 ROS 노드라 시스템 python 에 MuJoCo 가 필요하다 (conda 꺼진 터미널에서):

```bash
python3 -m pip install --user mujoco
```

장면 보기:

```bash
python3 -m mujoco.viewer --mjcf="$(ros2 pkg prefix lerobot_sim)/share/lerobot_sim/models/bimanual.xml"
```

장면 파일은 MuJoCo 의 `<attach>` 를 쓰므로 최근 버전이 필요하다 (3.8.1 에서 확인. 옛 버전에서 `unrecognized element 'attach'` 가 나오면 `pip install --user -U mujoco`). 자세한 건 `lerobot_sim/README.md`.

---

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `No module named 'rclpy._rclpy_pybind11'` | conda 가 켜진 터미널 | `conda deactivate` 후 다시. [2번](#2-conda-와-ros-안-꼬이게) |
| `rqt_image_view` 가 바로 죽음 | 위와 같음 | 위와 같음 |
| `No module named 'zmq'` / `'cv2'` | 의존성 미설치 | [3번](#3-저장소-받기와-빌드)의 `rosdep install` |
| `Package 'lerobot_bridge' not found` | 빌드 안 했거나 `install/setup.bash` 를 안 불러옴 | `colcon build --symlink-install` 후 `source ~/ros2_ws/install/setup.bash` |
| conda 켠 채로 빌드했더니 노드가 이상함 | conda python 으로 빌드됨 | conda 끄고 `rm -rf ~/ros2_ws/build ~/ros2_ws/install` 후 다시 빌드 |
| `lerobot python 을 못 찾음` | 이 PC 에 lerobot env 가 없거나 다른 위치 | 로봇 없이 개발 중이면 `-p mock:=true`. 로봇 PC 면 [6번](#lerobot-설치), 또는 robot.env `LEROBOT_PY` |
| `캘리브레이션 없음: …json` | 이 팔의 캘리 파일이 없음 | [캘리브레이션](#캘리브레이션) |
| `Could not connect on port` / `Permission denied: '/dev/ttyACM…'` | 보드가 안 꽂힘, 포트가 틀림, `dialout` 아님 | `dry_run:=true` 로 포트 확인, [시리얼 포트 권한](#시리얼-포트-권한) |
| `…보드 없음 → …_PORT 사용` | robot.env 의 시리얼 보드가 안 꽂혀 있음 | 보드 연결 확인 (mock 이면 무시) |
| 카메라 토픽이 안 나옴 | 경로가 틀림 / `cameras:=false` | `dry_run:=true` 의 `카메라 … 생략` 줄 확인 |
| 손목 카메라 좌우가 바뀜 | by-path 로 고정한 USB 포트가 바뀜 | 에러가 안 나므로 처음에 꼭 영상으로 확인. robot.env `LEFT_CAM`/`RIGHT_CAM` 교체 |
| 남의 토픽이 보이거나 내 로봇이 혼자 움직임 | 같은 `ROS_DOMAIN_ID` | [4번](#4-ros_domain_id--다른-사람-로봇과-섞이지-않게) |
| `InvalidParameterTypeException … INTEGER … DOUBLE` | 실수 파라미터에 정수를 줌 | `-p 이름:=1.0` 처럼 소수점을 붙인다 |
