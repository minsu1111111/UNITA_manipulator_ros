# 패키지 하나 맡기

시뮬·비전·음성·모델링처럼 새 패키지를 맡았을 때의 절차. **로봇도 lerobot 도 없이** 개발하고, `docs/TOPICS.md` 만 지키면 된다.
환경이 아직이면 [SETUP.md](SETUP.md) 1~5번부터.

## 1. 템플릿 복사

`lerobot_perception` 을 만든다고 하면:

```bash
cd ~/ros2_ws/src/UNITA_manipulator_ros
```
```bash
cp -r lerobot_template lerobot_perception && cd lerobot_perception && mv lerobot_template lerobot_perception && mv resource/lerobot_template resource/lerobot_perception
```

이름을 바꿀 곳 (전부 `lerobot_template` → `lerobot_perception`):

| 파일 | 바꿀 것 |
|---|---|
| `package.xml` | `<name>`, `<description>`, `<maintainer>`, 필요한 `<depend>` |
| `setup.py` | `package_name`, `description`, `entry_points` |
| `setup.cfg` | 두 줄의 경로 |
| `test/*.py` | import 경로 |

예제 노드 `joint_speed.py` 는 지우거나 고쳐 쓴다. 노드를 추가하면 `setup.py` 의 `entry_points` 에 한 줄 넣는다.
새 의존성(apt 패키지)은 `package.xml` 에 적어야 다른 사람 PC 에서 `rosdep install` 로 깔린다.
(`pip install` 로만 깔고 적지 않으면 내 PC 에서만 돈다.)

## 2. 빌드

conda 꺼진 터미널에서:

```bash
cd ~/ros2_ws && colcon build --symlink-install && source install/setup.bash
```

`--symlink-install` 이라 python 파일을 고칠 때마다 다시 빌드할 필요는 없다. 새 노드(entry_points)·새 파일을 추가했을 때만 다시 빌드한다.

## 3. 로봇 없이 돌리기

터미널을 나눠서:

```bash
ros2 run lerobot_bridge robot --ros-args -p mock:=true
```
```bash
ros2 run lerobot_perception <노드 이름>
```

mock 로봇은 lerobot 없이 돌고, 관절 상태(사인파를 따라가는 가짜 팔)와 가짜 손목 카메라 2대(`robot/cam/left_wrist`, `right_wrist`)를 낸다.
텔레옵 흐름까지 보려면 `ros2 run lerobot_bridge leader --ros-args -p mock:=true` 와 `ros2 run lerobot_bridge teleop` 도 띄운다.

자주 쓰는 확인 명령:

```bash
ros2 node list
```
```bash
ros2 topic list
```
```bash
ros2 topic echo /robot/joint_states
```
```bash
ros2 topic info -v /robot/joint_states
```
```bash
ros2 run rqt_image_view rqt_image_view /robot/cam/left_wrist/image/compressed
```

## 4. 테스트

계산 로직은 ROS 와 떼어서 순수 함수로 두고 `test/` 에서 검사한다 (`lerobot_template/test/test_joint_speed.py` 참고).

```bash
cd ~/ros2_ws && colcon test --packages-select lerobot_perception && colcon test-result --verbose
```

## 5. 올리기

이 저장소(https://github.com/minsu1111111/UNITA_manipulator_ros)에 **협업자로 초대받아** 같은 저장소에 브랜치를 올리고 PR 로 합친다.
GitHub 초대 메일(또는 저장소 페이지의 알림)에서 수락해야 push 할 수 있다. `main` 에는 직접 push 하지 않는다 — PR 과 리뷰를 거쳐서만 들어간다.

작업 시작 (최신 `main` 에서 브랜치를 딴다):

```bash
cd ~/ros2_ws/src/UNITA_manipulator_ros && git checkout main && git pull
```
```bash
git checkout -b perception/<할 일>
```

브랜치 이름은 `<패키지 줄임>/<할 일>` — 예: `sim/joint-node`, `perception/blob-detect`, `speech/stt-node`. 브랜치 하나에 할 일 하나.

올리기:

```bash
git add lerobot_perception && git commit -m "perception: 블록 색 인식 노드"
```
```bash
git push -u origin perception/<할 일>
```

push 하면 터미널에 PR 만드는 링크가 나온다. 거기서 PR 을 열면 체크리스트가 자동으로 뜬다 (`.github/pull_request_template.md`).
리뷰에서 고치라고 하면 같은 브랜치에 커밋하고 다시 push — PR 에 자동으로 더해진다.

- 다른 사람 패키지(특히 `lerobot_common`, `lerobot_bridge`)를 고쳐야 하면 먼저 이야기하고 따로 PR 을 연다.
- `config/robot.env` 는 올리지 않는다 (PC 마다 다름, `.gitignore` 에 있음). `git status` 로 올라갈 파일을 꼭 확인할 것.
- 오래 걸리는 작업이면 중간중간 `git pull origin main` 으로 최신 `main` 을 받아 둔다.

올리기 전 확인 (PR 템플릿과 같음):

- [ ] 새 PC 에서처럼 `rosdep install` → `colcon build --symlink-install` → `colcon test` 가 통과한다
- [ ] `mock:=true` 로 노드가 돈다 (실기가 필요한 부분은 그렇다고 적는다)
- [ ] 새 토픽은 `docs/TOPICS.md` 와 `lerobot_common/topics.py` 에 있다
- [ ] 새 의존성은 `package.xml` 에 있다 (pip 으로만 깐 것은 README 에 설치 명령)
- [ ] 패키지 README 에 실행 명령 두세 줄

## 지켜야 할 것

1. 토픽 이름·QoS 는 `lerobot_common` 의 상수를 쓴다. 새 토픽은 `docs/TOPICS.md` 에 먼저 적는다.
2. 단위는 rad. 변환은 `lerobot_common.units` 로만.
3. lerobot 을 import 하지 않는다. lerobot 이 필요하면 `lerobot_bridge/hosts/` 쪽 일이다.
4. `robot/command` 를 발행하지 않는다 (지금은 `teleop`, 나중엔 `safety` 만).
5. 내 PC 경로(`/home/<이름>/…`)를 코드에 쓰지 않는다. 설치된 파일은 `get_package_share_directory("패키지")` 로 찾는다.
