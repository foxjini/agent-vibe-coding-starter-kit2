# 코딩 표준

## TypeScript (frontend/)
- `strict: true` 유지, `any` 사용 금지 (부득이하면 이유를 주석으로 남기고 `unknown` + 타입가드 사용)
- 컴포넌트 파일명/이름은 PascalCase (`DashboardPanel.tsx`)
- 커스텀 훅은 `use`로 시작 (`useSmartDeviceSocket.ts`)
- API 응답 타입은 `types/` 폴더에 별도 선언, 컴포넌트 안에서 인라인으로 만들지 않는다

## Python (backend/, vision/, pi/)
- 함수/변수는 snake_case, 클래스는 PascalCase
- 모든 함수에 타입힌트를 작성한다 (`def get_sensor_history(device_id: str, limit: int) -> list[dict]:`)
- 예외를 조용히 삼키지 않는다 — 최소한 로그로 남긴다

## 공통
- 매직 넘버/문자열은 상수로 분리한다
- 한 함수는 한 가지 일만 한다 — 길어지면 분리한다
