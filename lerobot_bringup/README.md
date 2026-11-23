# lerobot_bringup — launch 파일

여러 노드를 한 번에 띄운다. 각 노드를 `ros2 run` 으로 하나씩 띄우는 것과 같다 (노드가 무엇을 하는지는 루트 README).

## teleop.launch.py — 텔레옵 한 번에

```bash
ros2 launch lerobot_bringup teleop.launch.py
```

robot + leader + teleop. 옵션으로 RViz(`rviz:=true`)와 녹화 노드(`record:=true`)도 같이 띄운다.

| 인자 | 기본 | 설명 |
|---|---|---|
| `arm` | `bi` | `bi` / `left` / `right` |
| `mock` | `false` | 하드웨어·lerobot 없이 |
| `cameras` | `true` | `false` 면 카메라 없이 |
| `max_rel` | `0` | 스텝당 최대 변화(도). 처음 붙일 땐 `20` |
| `teleop_enabled` | `true` | `false` 면 teleop 을 멈춘 채로 시작 → 리더 자세를 맞춘 뒤 `ros2 param set /teleop enabled true` |
| `rviz` | `false` | 로봇 모델 + RViz |
| `record` | `false` | 녹화 노드도. 키보드는 다른 터미널에서 `ros2 run lerobot_recorder keyboard` |
| `experiment_name`, `task` | | `record:=true` 일 때 녹화 노드에 넘김 |

자주 쓰는 조합:

```bash
ros2 launch lerobot_bringup teleop.launch.py arm:=left cameras:=false max_rel:=20
```
```bash
ros2 launch lerobot_bringup teleop.launch.py teleop_enabled:=false rviz:=true
```
```bash
ros2 launch lerobot_bringup teleop.launch.py record:=true experiment_name:=pour_water task:="Pick up the cup and pour water"
```

`record:=true` 일 때 키보드 (다른 터미널. `lerobot-record` 와 같은 조작 — `→` 다음 · `←` 다시 녹화 · `Esc` 저장하고 끝):

```bash
ros2 run lerobot_recorder keyboard --ros-args -p num_episodes:=10 -p episode_time_s:=30 -p reset_time_s:=10
```

**끄기: Ctrl+C 한 번** — 모든 노드가 같이 꺼진다. robot 이 꺼지면 토크가 꺼지니 팔을 받칠 것.
녹화 중에 Ctrl+C 를 눌러도 그 에피소드는 끝까지 저장된다.

## view.launch.py — 로봇 모델 + RViz 만

이미 떠 있는 로봇(또는 리더)을 볼 때.

```bash
ros2 launch lerobot_bringup view.launch.py
```
```bash
ros2 launch lerobot_bringup view.launch.py who:=leader
```

| 인자 | 기본 | 설명 |
|---|---|---|
| `arm` | `bi` | `bi` / `left` / `right` (left/right 는 단팔 모델) |
| `who` | `robot` | `robot` (robot/joint_states) / `leader` (leader/joint_states, 양팔만) |

리더는 TF 이름 앞에 `leader/` 를 붙여 팔로워와 섞이지 않게 하고, RViz 도 맞는 설정(`bimanual_leader.rviz`)으로 연다.

## launch 에서 알아둘 것

- 터미널에서 Ctrl+C 하면 SIGINT 가 **두 번** 온다 (터미널이 그룹 전체에, launch 가 각 노드에). 우리 노드는 정리하는 동안
  두 번째 신호를 무시하게 만들어 두었다 — 새 노드를 만들 때도 `lerobot_template` 처럼 `finally` 에서 SIGINT 를 무시할 것.
- launch 에서는 노드들이 **동시에** 뜬다. 다른 노드가 늦게 만드는 토픽(예: 카메라 토픽은 robot 노드가 첫 프레임을 받을 때 생김)을
  처음 한 번만 찾고 끝내면 놓친다.
