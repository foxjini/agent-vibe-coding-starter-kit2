/**
 * 관리자 세션 관리 (부록G §3-4)
 *
 * 기기 제어와 시나리오 강제 실행은 백엔드가 X-Admin-Token을 요구한다.
 * 이 모듈은 관리자 PIN으로 토큰을 받아 두고, 보호된 요청에 헤더를 붙여 준다.
 *
 * ⚠️ 관리자 PIN은 여기에도, 어떤 프론트엔드 파일에도 적지 않는다.
 *    검증은 전적으로 백엔드(.env의 ADMIN_PIN)가 한다.
 */

import { apiUrl } from "@/utils/apiConfig";

const STORAGE_KEY = "karaoke.adminToken.v1";

/** 저장된 관리자 토큰 (없으면 null) */
export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    // 시크릿 모드 등에서 접근이 막히면 인증되지 않은 것으로 본다
    return null;
  }
}

/* ── 구독 가능한 상태로 만들기 ─────────────────────────────────
 * 화면이 sessionStorage를 "단일 출처"로 삼도록 useSyncExternalStore용
 * 구독 API를 제공한다. 이렇게 하면 useEffect 안에서 setState를 호출해
 * 상태를 복원할 필요가 없고, 저장소와 화면이 어긋날 일도 없다.
 */
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

function setAdminToken(token: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (token) window.sessionStorage.setItem(STORAGE_KEY, token);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* 저장 실패는 무시 — 이번 탭에서만 인증이 유지되지 않을 뿐이다 */
  }
  notify();
}

/** useSyncExternalStore용 구독 함수 */
export function subscribeAdminSession(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** useSyncExternalStore용 스냅샷 (클라이언트) */
export function getAdminSnapshot(): boolean {
  return getAdminToken() !== null;
}

/** useSyncExternalStore용 스냅샷 (서버 렌더링 — 항상 미인증) */
export function getAdminServerSnapshot(): boolean {
  return false;
}

export function isAdminAuthenticated(): boolean {
  return getAdminToken() !== null;
}

/** 401을 받았을 때처럼 토큰만 즉시 버려야 할 때 */
export function clearAdminSession() {
  setAdminToken(null);
}

/**
 * 관리자 PIN으로 로그인한다.
 * 성공하면 토큰을 저장하고 true, 실패하면 오류 메시지를 반환한다.
 */
export async function adminLogin(pin: string): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const res = await fetch(apiUrl("/api/admin/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    const json = await res.json().catch(() => null);

    if (!res.ok) {
      return { ok: false, message: json?.error?.message ?? "관리자 인증에 실패했습니다." };
    }
    const token = json?.data?.token;
    if (!token) return { ok: false, message: "서버가 토큰을 돌려주지 않았습니다." };

    setAdminToken(token);
    return { ok: true };
  } catch {
    return { ok: false, message: "백엔드에 연결할 수 없습니다. 서버가 켜져 있는지 확인해 주세요." };
  }
}

/** 관리자 세션을 종료한다 */
export async function adminLogout(): Promise<void> {
  const token = getAdminToken();
  setAdminToken(null);
  if (!token) return;
  try {
    await fetch(apiUrl("/api/admin/logout"), {
      method: "POST",
      headers: { "X-Admin-Token": token },
    });
  } catch {
    /* 서버에 못 닿아도 로컬 토큰은 이미 지웠다 */
  }
}

/**
 * 관리자 전용 API 호출. X-Admin-Token을 자동으로 붙이고,
 * 토큰이 만료되어 401이 오면 저장된 토큰을 지운다.
 */
export async function adminFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAdminToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("X-Admin-Token", token);

  const res = await fetch(apiUrl(path), { ...init, headers });
  if (res.status === 401) {
    setAdminToken(null);
  }
  return res;
}
