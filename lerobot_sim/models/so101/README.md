# SO-101 공식 모델 (수정하지 않음)

- 출처: https://github.com/TheRobotStudio/SO-ARM100/tree/main/Simulation/SO101 — Apache-2.0
- 파일: `so101_new_calib.xml` (new calibration: 각 관절 0 rad = 관절 범위 중앙 = lerobot 0도), `assets/*.stl`
- 위치 액추에이터 게인은 원본 그대로 (`kp=998.22`, `kv=2.731`). 실제 모터보다 빠르게 따라간다.
  lerobot_pac 에서는 실제 기록과 가장 비슷했던 `kp=17.8` 을 썼다 (그 폴더의 `joints_properties.xml` 옛 값).

이 파일은 고치지 말고, 장면(`../bimanual.xml`, `../single_arm.xml`)에서 붙여 쓴다.
