# Git 규칙

## 브랜치
- `main`: 항상 동작하는 상태를 유지한다
- `feature/{역할}-{기능}` 형태 (예: `feature/vision-person-detect`, `feature/hardware-gpiozero-led`)

## 커밋 메시지
- `[역할] 무엇을 했는지` 형태 (예: `[backend] 영상인식 이벤트 수신 엔드포인트 추가`)

## PR 전 체크리스트
- [ ] 로컬에서 직접 실행해 동작을 확인했는가
- [ ] `.env` 등 시크릿 파일이 diff에 없는가
- [ ] 관련 없는 파일 변경이 섞이지 않았는가

## 업로드 방법 (토큰 절약)
- AI 채팅에 git 명령을 시키지 않는다 — Antigravity 좌측 "소스 제어(Ctrl+Shift+G)" GUI
  메뉴로 직접 클릭해서 커밋/푸시한다 (토큰 0 소모)
