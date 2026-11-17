## 무엇을

<!-- 한두 줄. 어떤 패키지에 무엇을 만들거나 고쳤나 -->

## 실행 방법

```bash
# 이 PR 을 확인하는 명령 (mock 으로 되는 범위)
```

## 확인

- [ ] `rosdep install` → `colcon build --symlink-install` → `colcon test` 통과
- [ ] `mock:=true` 로 돈다 (실기가 필요한 부분은 아래에 적음)
- [ ] 새 토픽은 `docs/TOPICS.md` 와 `lerobot_common/topics.py` 에 있음
- [ ] 새 의존성은 `package.xml` 에 있음 (pip 으로만 깐 것은 README 에 설치 명령)
- [ ] `config/robot.env`, 내 PC 경로(`/home/<이름>/…`) 가 들어가지 않음

## 실기 확인 / 남은 것

<!-- 실제 로봇이 있어야 확인되는 것, 아직 안 된 것 -->
