/**
 * 백엔드 통신 공통 유틸리티.
 *
 * - 에러 응답은 api-rules.md 규격({"error": {"code", "message"}})으로 통일되어 있지만,
 *   구버전 백엔드({"detail": {"error": ...}})도 함께 읽을 수 있게 처리한다.
 * - MySQL JSON 컬럼은 상황에 따라 문자열로 올 수 있으므로 안전하게 객체로 되돌린다.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

/** 백엔드 에러 응답에서 사람이 읽을 메시지를 뽑아낸다. */
export function extractErrorMessage(body: unknown, fallback = "알 수 없는 오류"): string {
  if (!body || typeof body !== "object") return fallback;
  const b = body as Record<string, unknown>;

  const direct = (b.error as Record<string, unknown> | undefined)?.message;
  if (typeof direct === "string") return direct;

  const detail = b.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const nested = (detail as Record<string, unknown>).error as
      | Record<string, unknown>
      | undefined;
    if (typeof nested?.message === "string") return nested.message;
  }
  return fallback;
}

/**
 * JSON 컬럼 값을 객체로 되돌린다.
 * (백엔드가 디코드해서 보내주지만, 예전 데이터나 다른 경로로 문자열이 와도 화면이 깨지지 않게 한다.)
 */
export function parseJsonValue<T = Record<string, unknown>>(value: unknown): T | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return value as T;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
    try {
      return JSON.parse(trimmed) as T;
    } catch {
      return null;
    }
  }
  return null;
}

export interface ApiResult<T> {
  ok: boolean;
  data?: T;
  errorMessage?: string;
}

/** fetch + 공통 에러 처리. 네트워크 오류도 예외 대신 결과 객체로 돌려준다. */
export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      headers:
        init?.body && !(init?.headers as Record<string, string>)?.["Content-Type"]
          ? { "Content-Type": "application/json", ...(init?.headers || {}) }
          : init?.headers,
      ...init,
    });

    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }

    if (!res.ok) {
      return {
        ok: false,
        errorMessage: extractErrorMessage(body, `요청 실패 (HTTP ${res.status})`),
      };
    }
    return { ok: true, data: (body as { data?: T })?.data as T };
  } catch (err) {
    console.error(`[API] ${path} 통신 실패:`, err);
    return { ok: false, errorMessage: "백엔드 서버와 통신할 수 없습니다." };
  }
}
