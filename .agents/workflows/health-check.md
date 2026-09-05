# health-check

전체 규칙 준수 여부를 점검할 때 사용한다:
- api-rules.md의 사용자향/디바이스향 인증 분리가 지켜졌는가
- `.gitignore`에 `.env`(및 `.env.local` 등), `venv/`가 포함되어 있는가 —
  단, `.env.example`은 커밋되어야 하므로 `.env*`처럼 통째로 무시하면 안 된다
- `backend/main.py`의 CORS `allow_origins`가 `["*"]`로 열려 있지 않은가
  (`allow_credentials=True`와 같이 쓰면 교차출처 보호가 사실상 사라진다)
- 프론트엔드 소켓 연결이 한 곳(`app/page.tsx` 등)에서만 열리는가
- vision-rules.md의 개인정보 원칙(얼굴 저장 금지 등)이 지켜졌는가
- hardware-rules.md의 Provider 패턴이 유지되고 있는가 (하드코딩된 GPIO 호출이
  `backend/iot/` 밖에 있지 않은가)

발견한 문제는 🔴지금 고칠 것 / 🟡설계 부채 / 🟠눈으로 확인 안 한 것 / ⚪사소한 것으로
분류해서 보고만 먼저 받는다. 한 번에 다 고치라고 하지 말고 하나씩 요청한다.
