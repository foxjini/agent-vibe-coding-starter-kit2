"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, Clock, PowerOff } from "lucide-react";
import { BoothSessionState, endsAtLabel, remainingSeconds } from "@/hooks/useBoothSession";

/** 1초마다 바뀌는 현재 시각. 이 작은 컴포넌트 안에서만 다시 그리게 한다 */
function useNow(active: boolean): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!active) return;
    const first = setTimeout(() => setNow(Date.now()), 0);
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [active]);
  return now;
}

export function formatClock(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** 남은 시간 "12:34" — 서버 기준. 알 수 없으면 아무것도 그리지 않는다 */
export function RemainingClock({ session }: { session: BoothSessionState | null }) {
  const now = useNow(Boolean(session?.kind));
  const left = remainingSeconds(session, now || session?.fetchedAt || 0);
  if (left === null) return null;
  return <span className="font-mono tnum">{formatClock(left)}</span>;
}

/**
 * 노래방 화면 맨 위 한 줄 — 누가, 언제까지 쓰는지 (부스 화면 전용)
 *
 * 종료 10분 전 알림(LED 깜빡임)은 부스 안에서 LED만 보고는 놓치기 쉽다.
 * 화면에도 같은 때 같은 문구를 띄운다.
 */
export function SessionStrip({
  session,
  isPowerOn,
  ledBlink,
}: {
  session: BoothSessionState | null;
  isPowerOn: boolean;
  ledBlink: boolean;
}) {
  const now = useNow(isPowerOn && Boolean(session?.kind));

  if (!isPowerOn) {
    return (
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-live-soft border border-live/40 text-ink"
        role="status"
        data-testid="session-ended"
      >
        <PowerOff className="w-5 h-5 text-live shrink-0" aria-hidden />
        <p className="text-sm font-bold">
          이용 시간이 끝났습니다. 잠시 후 대기 화면으로 돌아갑니다.
        </p>
      </div>
    );
  }

  const left = remainingSeconds(session, now || session?.fetchedAt || 0);
  const until = endsAtLabel(session);
  const endingSoon = left !== null && left <= 60;
  const warn10 = ledBlink || (session?.kind === "reservation" && left !== null && left <= 600);

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 rounded-2xl bg-surface border border-line text-sm"
      data-testid="session-strip"
    >
      <span className="flex items-center gap-2 font-bold text-free">
        <span className="w-2 h-2 rounded-full bg-free animate-pulse" aria-hidden />
        이용 중
      </span>
      {session?.user_name && <strong className="text-ink">{session.user_name}님</strong>}
      {until && (
        <span className="flex items-center gap-1.5 text-ink-2">
          <Clock className="w-4 h-4 text-ink-3" aria-hidden />
          {until}까지
        </span>
      )}
      {left !== null && (
        <span className="text-ink-2">
          남은 시간{" "}
          <strong className="font-mono tnum text-ink text-base">{formatClock(left)}</strong>
        </span>
      )}
      {(endingSoon || warn10) && (
        <span className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full bg-brass-soft border border-brass/40 text-brass font-bold">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden />
          {endingSoon ? "곧 끝납니다 — 마무리해 주세요" : "종료 10분 전 — 정리를 준비해 주세요"}
        </span>
      )}
    </div>
  );
}
