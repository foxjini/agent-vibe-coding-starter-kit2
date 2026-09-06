/**
 * 백엔드 접속 주소 한 곳에서 관리
 *
 * ── 왜 필요한가 ────────────────────────────────────────────────────
 * 기존에는 컴포넌트마다 "http://localhost:8000"을 직접 적어 두고,
 * 환경변수를 쓰는 두 곳은 이름이 서로 달랐다.
 *
 *   .env.example  : NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_WS_URL
 *   코드(카라오케): NEXT_PUBLIC_API_BASE        ← 이름 불일치
 *   코드(웹소켓)  : NEXT_PUBLIC_WS_HOST         ← 이름 불일치
 *
 * 그래서 .env를 안내대로 채워도 값이 적용되지 않았고, Vercel에 배포하면
 * 브라우저가 자기 자신(localhost)으로 요청을 보내 전부 실패했다.
 * (로드맵 4단계 클라우드 배포가 이 상태로는 진행되지 않는다)
 *
 * ⚠️ Next.js는 NEXT_PUBLIC_* 를 빌드 시점에 문자열로 치환한다.
 *    반드시 process.env.NEXT_PUBLIC_XXX 형태로 "직접" 써야 하며,
 *    변수로 만들어 동적으로 접근하면 치환되지 않는다.
 */

const DEFAULT_API_BASE = "http://localhost:8000";

/** 백엔드 REST API 기본 주소 (끝의 / 는 제거) */
export const API_BASE: string = (
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE
).replace(/\/+$/, "");

/** REST 경로를 붙여 전체 URL을 만든다. 예: apiUrl("/api/songs") */
export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * WebSocket 주소.
 * NEXT_PUBLIC_WS_URL이 있으면 그대로 쓰고, 없으면 API 주소에서 유도한다
 * (학생이 API 주소만 채워도 동작하도록).
 * HTTPS 페이지에서는 ws:// 가 브라우저에 차단되므로 wss:// 로 올려 준다.
 */
export function getWebSocketUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return explicit;

  const derived = API_BASE.replace(/^http/, "ws") + "/ws";

  // 페이지가 HTTPS면 ws:// 는 차단된다 (Mixed Content)
  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    return derived.replace(/^ws:/, "wss:");
  }
  return derived;
}
