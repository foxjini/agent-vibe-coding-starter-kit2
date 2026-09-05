# hardware-agent

## 담당
Mock ↔ 라즈베리파이 5(gpiozero) Provider 구현 — `backend/iot/`, `pi/`

## 항상 참고
- **`.agents/rules/hardware-rules.md`를 항상 참고한다** (GPIO 안전 수칙, Provider 패턴 유지)
- `.agents/skills/hardware-integration/SKILL.md`

## 하지 않는 것
- API 엔드포인트 자체는 backend-agent 담당 — 이 에이전트는 Provider 구현까지만 담당한다
