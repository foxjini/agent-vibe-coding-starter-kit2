"use client";

import { Reservation } from "@/types";

/**
 * 발급받은 예약 PIN 보관소
 *
 * 왜 필요한가:
 *   예약을 마치면 4자리 PIN이 화면에 뜨는데, 지금까지는 그게 컴포넌트 상태에만
 *   있었다. 관람객이 페이지를 닫거나 새로고침하면 PIN이 사라진다. 부스 앞에
 *   가서야 "번호가 뭐였지?" 하게 되는 구조였다.
 *
 * 왜 useState + useEffect 가 아니라 이 방식인가:
 *   서버에서 렌더링할 때는 localStorage 가 없어서 화면이 한 번 어긋난다(하이드레이션
 *   불일치). useSyncExternalStore 는 "서버 값"과 "브라우저 값"을 따로 받으므로
 *   그 문제가 없다. 프로젝트의 adminSession.ts 도 같은 방식을 쓴다.
 *
 * 저장은 이 브라우저 안에서만 일어난다 — 서버로 보내지 않는다.
 */

const KEY = "karaoke:voucher";

let cache: string | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function read(): string | null {
  if (!loaded) {
    try {
      cache = window.localStorage.getItem(KEY);
    } catch {
      cache = null; // 시크릿 모드 등 저장소가 막힌 경우
    }
    loaded = true;
  }
  return cache;
}

function emit() {
  listeners.forEach((fn) => fn());
}

export function subscribeVoucher(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** 스냅샷은 문자열이어야 한다 — 매번 새 객체를 돌려주면 무한 렌더링이 된다 */
export function getVoucherSnapshot(): string | null {
  return read();
}

export function getVoucherServerSnapshot(): string | null {
  return null;
}

export function saveVoucher(reservation: Reservation): void {
  const json = JSON.stringify(reservation);
  cache = json;
  loaded = true;
  try {
    window.localStorage.setItem(KEY, json);
  } catch {
    /* 저장이 막혀 있어도 이번 방문 동안은 화면에 남는다 */
  }
  emit();
}

export function clearVoucher(): void {
  cache = null;
  loaded = true;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* 무시 */
  }
  emit();
}

/** 저장해 둔 예약이 이미 지난 날짜면 더 보여 줄 이유가 없다 */
export function isExpired(reservation: Reservation): boolean {
  const day = String(reservation.reservation_date ?? "").slice(0, 10);
  if (!day) return false;
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
    today.getDate()
  ).padStart(2, "0")}`;
  return day < todayStr;
}
