---
name: deployment
description: >-
  FastAPI 백엔드를 Render에, Next.js 프론트엔드를 Vercel에 배포하고 환경변수 설정 및 배포 후 동작 검증을 수행할 때 사용하는 스킬.
---

# deployment (Render + Vercel)

## 백엔드 → Render
1. Render에 새 Web Service를 생성하고 GitHub 저장소(backend/)를 연결한다
2. 환경변수(Supabase URL/service_role 키 등)를 Render 대시보드에 등록한다 (코드에 넣지 않는다)
3. 배포 후 `https://{서비스명}.onrender.com/docs` 등으로 정상 기동을 확인한다

## 프론트엔드 → Vercel
1. Vercel에 새 프로젝트를 생성하고 GitHub 저장소(frontend/)를 연결한다
2. `NEXT_PUBLIC_API_BASE_URL`을 Render 백엔드 URL로, `NEXT_PUBLIC_WS_URL`을
   `wss://{서비스명}.onrender.com/ws`로 설정한다 (배포는 https이므로 `ws://`가 아니라
   `wss://`를 쓴다 — 브라우저가 https 페이지에서 ws:// 연결을 차단한다)
3. 배포 후 실제 브라우저로 접속해 데이터가 표시되는지 확인한다

## 배포 후 CORS 설정 (빠뜨리기 쉬움)
Vercel 배포가 끝나면 Render 대시보드의 백엔드 환경변수 `CORS_ALLOW_ORIGINS`에
Vercel URL을 추가한다. 안 하면 대시보드에서 API 호출이 전부 CORS 오류로 막힌다.
```
CORS_ALLOW_ORIGINS=http://localhost:3000,https://our-team.vercel.app
```
`*`로 열어두지 않는다 — 인증이 붙은 API에서는 교차출처 보호가 무력화된다
(`security-rules.md`).

## 배포 후 확인
"Deployed" 표시만 믿지 않는다 — 실제 URL에 접속해 기능이 동작하는지 반드시 확인한다.
