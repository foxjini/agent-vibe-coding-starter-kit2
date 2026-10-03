"use client";

/**
 * 전시 체험권 보관소 (부록G §2-③)
 *
 * 관람객은 QR을 찍어 체험권을 받고, 차례가 올 때까지 폰을 주머니에 넣는다.
 * 그 사이 화면이 꺼지거나 브라우저가 탭을 정리하면 체험권을 잃어버린다.
 * 그래서 발급받은 체험권을 이 기기에 적어 둔다.
 *
 * 번호(id)와 함께 **입장 비밀번호**도 이 기기에만 적어 둔다. 서버는 발급할 때
 * 한 번만 비밀번호를 알려 주고, 그 뒤에는 비밀번호를 같이 보낸 사람에게만
 * 돌려준다 — 체험권 번호가 1, 2, 3... 으로 이어지기 때문에 그러지 않으면
 * 옆 사람이 남의 비밀번호를 읽어 새치기할 수 있다.
 *
 * voucherStore 와 같은 방식(useSyncExternalStore)을 쓴다 — 서버 렌더링과
 * 어긋나지 않게 하려면 "서버 값"과 "브라우저 값"을 나눠 줘야 한다.
 */

const KEY = "karaoke:ticket";
const LEGACY_KEY = "karaoke:ticketId";

export interface StoredTicket {
  id: number;
  /** 발급 때 받은 입장 비밀번호. 예전 버전으로 받은 체험권에는 없다. */
  pin?: string;
}

let cache: string | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function read(): string | null {
  if (!loaded) {
    try {
      cache = window.localStorage.getItem(KEY);
      if (!cache) {
        // 이전 버전에서는 번호만 적어 두었다 — 그 체험권도 계속 쓸 수 있게 한다
        const legacy = window.localStorage.getItem(LEGACY_KEY);
        cache = legacy ? JSON.stringify({ id: Number(legacy) }) : null;
      }
    } catch {
      cache = null;
    }
    loaded = true;
  }
  return cache;
}

export function subscribeTicket(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getTicketSnapshot(): string | null {
  return read();
}

export function getTicketServerSnapshot(): string | null {
  return null;
}

/** 보관된 문자열을 {id, pin} 으로 푼다. 깨진 값은 없는 것으로 본다. */
export function parseTicket(raw: string | null): StoredTicket | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredTicket;
    return Number.isFinite(parsed?.id) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveTicket(id: number, pin?: string): void {
  cache = JSON.stringify(pin ? { id, pin } : { id });
  loaded = true;
  try {
    window.localStorage.setItem(KEY, cache);
    window.localStorage.removeItem(LEGACY_KEY);
  } catch {
    /* 저장이 막혀 있어도 이번 방문 동안은 유지된다 */
  }
  listeners.forEach((fn) => fn());
}

export function clearTicket(): void {
  cache = null;
  loaded = true;
  try {
    window.localStorage.removeItem(KEY);
    window.localStorage.removeItem(LEGACY_KEY);
  } catch {
    /* 무시 */
  }
  listeners.forEach((fn) => fn());
}
