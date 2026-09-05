---
name: dashboard-ui-design
description: >-
  센서 및 액추에이터 대시보드 UI 컴포넌트 패턴(카드 레이아웃, 상태 색상 유틸, 연결 상태 배지, 영상인식 로그 리스트, Next.js 개발 모드 설정, WebSocket 자동 재연결)을 구현할 때 사용하는 스킬.
---

# dashboard-ui-design

> 센서/액추에이터 대시보드 UI를 만들 때 이 스킬을 참고한다. ui-ux-rules.md의 디자인
> 시스템을 실제 컴포넌트 패턴으로 구체화한 것이다.

## 카드 레이아웃 패턴 (`components/dashboard/`)
- **SensorCard.tsx**: 상단에 디바이스 이름(작은 라벨) → 중앙에 큰 값(`text-3xl` 이상)
  + 단위 → 하단에 마지막 갱신 시각
- **ActuatorCard.tsx**: 상단에 디바이스 이름 → 중앙에 ON/OFF 토글 스위치 → 하단에
  마지막 조작자 표시(`user` 또는 `device`)
- **AlertCard.tsx** (경보성 디바이스 전용): 다른 카드보다 큰 크기(`col-span-2`), 감지
  시 배경/테두리가 빨간색으로 바뀌고, 수동 해제 버튼이 있어야 한다 (자동으로 꺼지지
  않는다 — db-rules.md 참고)

## 상태 색상 유틸
`frontend/components/dashboard/statusColor.ts`가 **이미 킷에 들어있다.** 새로 만들지 말고
`getStatusBadgeClass(status)`를 import해서 쓴다 (직접 Tailwind 색상을 적어 넣으면
ui-ux-rules.md의 색상 의미표와 어긋난다).

```tsx
import { getStatusBadgeClass, statusColor } from "@/components/dashboard/statusColor";

<span className={`rounded-full border px-2.5 py-1 text-xs ${getStatusBadgeClass(device.state)}`}>
  {device.state}
</span>
```
`statusColor`의 키는 `on` / `off` / `alert` / `warning` / `info` / `connecting` /
`disconnected` 7개다. `alert`(빨강 + `animate-pulse`)는 경보성 디바이스와 "감지됨"
상태 전용이다.

## 연결 상태 표시
WebSocket `connected` 값을 화면 상단에 항상 눈에 띄게 배지로 표시한다
("● 연결됨" 초록 / "● 연결 끊김" 회색). 연결이 끊긴 상태에서 마지막 값만 계속
보여주면 사용자가 실시간이라고 착각하므로 반드시 구분해서 표시한다.

## 레이아웃 예시 (Tailwind)
```tsx
<div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-6">
  {/* 경보성 디바이스 카드는 md:col-span-2로 더 크게 배치 */}
</div>
```

## 영상인식 감지 로그 (2주차 이후)
감지 이벤트(`vision_events`)는 별도 로그 리스트로 표시한다 (최근 N개, 시각 + 감지
여부). 카드형이 아니라 리스트형으로 — 카드가 너무 많아지면 대시보드가 산만해진다.

## Next.js 개발 모드 설정 (필수)
`next.config.mjs`(또는 `.ts`)에 `reactStrictMode: false`를 설정한다.
```js
const nextConfig = { reactStrictMode: false };
export default nextConfig;
```
Strict Mode가 켜진 상태(기본값)에서는 `useEffect` 안에서 여는 WebSocket 연결이
개발 모드에서 두 번 마운트되어 연결이 끊겼다 재연결되는 깜빡임이 발생한다. 이건
버그가 아니라 React의 의도된 개발 모드 동작이지만, 이 프로젝트에서는 꺼두는 게
낫다.

## SSR Hydration Mismatch 방지 규칙 (필수)
Next.js SSR 환경에서 서버 렌더링 시점과 브라우저 클라이언트 마운트 시점의 차이로 인해 발생하는 `Hydration failed` 오류를 방지하기 위해 다음 2가지 규칙을 반드시 준수한다:
1. **시간 렌더링**: `new Date().toLocaleTimeString()` 등 동적 시간을 렌더링하는 태그에는 반드시 `suppressHydrationWarning` 속성을 부여하거나, `useEffect` 마운트 이후(`mounted === true`)에만 시간을 표시한다.
2. **사전 탑재 컴포넌트 활용**: 상단 연결 상태 배지는 사전 탑재된 `components/dashboard/ConnectionBadge.tsx`를 가져와 사용한다.

## WebSocket 자동 재연결
`useSmartDeviceSocket` 같은 훅에서 연결이 끊기면(`onclose`) 일정 시간(예: 2~3초)
후 자동으로 재연결을 시도하는 로직을 넣는다. 연결 시도 중에는 상단 배지를
"● 연결 끊김" 또는 "● 연결 대기 중"으로 표시한다(dashboard-ui-design의 연결 상태 표시 규칙 참고).

## 참고
`ui-ux-rules.md`의 Anti-Slop 체크와 배포 전 체크리스트를 항상 함께 적용한다.
