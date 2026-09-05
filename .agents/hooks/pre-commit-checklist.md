# pre-commit-checklist

커밋 전 확인 목록 (자동 실행되지 않는다 — 커밋 전에 AI에게 "이 체크리스트로 확인해줘"라고
직접 요청하거나, 학생이 직접 확인한다):
- [ ] `.env` 계열 파일이 diff에 없는가 (`git diff --cached --name-only`)
- [ ] `console.log`/`print` 디버그 코드가 남아있지 않은가
- [ ] 타입 에러가 없는가
- [ ] 하드코딩된 API 키/비밀번호가 없는가
