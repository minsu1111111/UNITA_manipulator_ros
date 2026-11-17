# lerobot_dataset — rosbag 에피소드 → LeRobotDataset

`lerobot_recorder` 로 녹화한 에피소드를 LeRobotDataset 으로 바꾼다. 결과는 **`lerobot-record` 로 모은 데이터셋과 같은 형식**이라
`lerobot-train` 으로 바로 학습하고, 기존 데이터셋·모델과 섞어 쓸 수 있다.

## 실행

```bash
ros2 run lerobot_dataset convert ~/ros_episodes/pour_water --repo-id local/pour_water
```

데이터셋은 `~/.cache/huggingface/lerobot/local/pour_water` 에 생긴다 (`--root` 로 바꿈). 확인과 학습은 lerobot 그대로:

```bash
lerobot-dataset-viz --repo-id local/pour_water --episode-index 0
```

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--repo-id` | (필수) | 데이터셋 이름. Hub 에 올릴 거면 `UNITAmanipulation/<이름>` |
| `--root` | HF 캐시 | 저장 위치 |
| `--fps` | `30` | 데이터셋 fps (lerobot-record 와 같게) |
| `--task` | 녹화 때 넣은 것 | 과제 문장을 덮어쓴다 |
| `--max-age` | `0.1` | 프레임 시각보다 이만큼(초) 이상 오래된 값이 있으면 그 프레임을 버린다 |
| `--overwrite` | | 같은 이름이 있으면 지우고 새로 만든다 |
| `--no-videos` | | 이미지를 mp4 대신 png 로 |
| `--push` | | 다 쓴 뒤 Hugging Face Hub 에 올린다 (`hf auth login` 필요) |
| `--lerobot-py` | 자동 | lerobot env 의 python |

**lerobot env 가 있는 PC 에서 돌린다** (데이터셋 쓰기는 lerobot 이 한다). ROS 쪽이 bag 을 읽어 시각을 맞추고,
lerobot env 의 `lerobot_bridge/hosts/dataset_writer.py` 가 데이터셋을 쓴다 — 명령은 하나다.

## 어떻게 바꾸나

| 데이터셋 | 토픽 | 변환 |
|---|---|---|
| `observation.state` | `/robot/joint_states` | rad → lerobot 단위 (몸통 도, gripper 0~100), 이름 `<관절>.pos` |
| `action` | `/robot/command` | 위와 같음 |
| `observation.images.<name>` | `/robot/cam/<name>/image/compressed` | JPEG → RGB, bag 에 있는 카메라 전부 |
| `task` | bag 메타데이터의 task (`--task` 가 있으면 그것) | |

**시각 맞추기** — `lerobot-record` 처럼 고정 fps 간격의 시각 T 마다, 각 토픽에서 **T 이전의 가장 최근 메시지**를 모아 프레임 하나를 만든다.
T 이후의 값(미래)은 절대 쓰지 않고, `--max-age` 보다 오래된 값이 하나라도 있으면 그 프레임은 버린다.
모든 토픽이 한 번씩 들어온 시각부터 시작한다. 에피소드마다 토픽별로 맞춘 비율과 지연을 출력한다:

```
episode_000000: 134 프레임 (4.5 s), 버린 프레임 0, task='Pick up the cup and pour water'
    /robot/joint_states            맞춤 100.0%  평균 지연   1.6 ms  최대  17.4 ms
    /robot/cam/left_wrist/...      맞춤 100.0%  평균 지연   8.3 ms  최대  34.1 ms
```

버린 프레임이 많으면 카메라가 끊겼거나 `camera_fps` 가 30 보다 낮은 것 (`robot` 노드 파라미터).

## lerobot-record 와 같은지 확인한 것

mock 으로 녹화 → 변환한 데이터셋의 `meta/info.json` 을 `lerobot-record` 로 모은 양팔 데이터셋과 비교했다:
`robot_type` (`bi_so_follower`), fps, 버전 (v3.0), 파일 경로 규칙, 그리고 `action` · `observation.state` · `observation.images.*` ·
인덱스 특징의 정의(dtype, shape, 이름, 영상 인코딩 정보)가 모두 같다. 단위(도·0~100), action–state 대응, 영상 색 순서(RGB)도 확인했다.

다른 점: `lerobot-record` 는 30 fps 루프에서 카메라를 직접 읽지만, 여기서는 JPEG(기본 품질 90)으로 한 번 압축된 영상을 쓴다.

## 출처

[legalaspro/so101-ros-physical-ai](https://github.com/legalaspro/so101-ros-physical-ai) 의 `rosbag_to_lerobot`
(Apache-2.0, 커밋 58318c9, 저작자 Dmitri Manajev). 라이선스 원문은 [`LICENSE`](LICENSE).

- `buffers.py`, `bag_reader.py`: 원본 그대로
- `convert.py`: 원본 `converter.py`·`cli.py` 를 바탕으로 다시 씀 — 프로세스 분리(ROS 읽기 / lerobot 쓰기), 설정 YAML 대신 토픽 계약,
  기준 카메라 대신 고정 fps 시각, rad → lerobot 단위, 관절이 빠진 메시지는 0 으로 채우지 않고 오류
- `lerobot_bridge/hosts/dataset_writer.py`: 새로 씀. 특징·프레임은 lerobot-record 와 같은 lerobot 함수로 만든다
