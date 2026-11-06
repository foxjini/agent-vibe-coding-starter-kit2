/**
 * 현재 시각 (wakeup 7인치 화면) — 1초마다 갱신합니다.
 * 서버에서 미리 그릴 때와 브라우저 시각이 달라 화면이 어긋나지 않도록, 첫 값은 브라우저에서 정합니다.
 */
"use client";

import { useEffect, useState } from "react";

export function useClock(): Date | null {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const first = setTimeout(() => setNow(new Date()), 0);
    const ticker = setInterval(() => setNow(new Date()), 1000);
    return () => {
      clearTimeout(first);
      clearInterval(ticker);
    };
  }, []);
  return now;
}

export function hhmm(date: Date | null): string {
  if (!date) return "--:--";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

export function dateText(date: Date | null): string {
  if (!date) return "";
  return `${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAYS[date.getDay()]})`;
}
