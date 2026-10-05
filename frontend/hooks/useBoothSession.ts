"use client";

import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "@/utils/apiConfig";
import { BoothSession } from "@/types";

/** 받은 시각을 함께 들고 다닌다 — 남은 시간을 화면에서 줄여 나갈 때 쓴다 */
export type BoothSessionState = BoothSession & { fetchedAt: number };

const REFRESH_MS = 30_000;

/**
 * 지금 부스를 쓰는 사람과 남은 시간 (부스 화면 전용, GET /api/booth/session)
 *
 * 부스 전원이 켜져 있는 동안만 묻는다 — 꺼져 있으면 쓰는 사람이 없다.
 * 남은 시간은 서버가 잰 값(remaining_sec)과 받은 시각(fetchedAt)을 같이 보관하고,
 * 화면에서는 "받은 뒤로 흐른 시간"만 뺀다. 부스 PC의 시계가 틀려도 맞게 나온다.
 */
export function useBoothSession(isPowerOn: boolean): BoothSessionState | null {
  const [session, setSession] = useState<BoothSessionState | null>(null);

  const fetchSession = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/booth/session"));
      if (res.ok) {
        const data = (await res.json()).data as BoothSession;
        setSession({ ...data, fetchedAt: Date.now() });
      }
    } catch {
      /* 표시용이라 못 받아도 노래방은 그대로 돈다 */
    }
  }, []);

  useEffect(() => {
    if (!isPowerOn) {
      // 전원이 꺼지면 지난 사람의 이름이 다음 사람 화면에 잠깐이라도 비치지 않게 비운다
      const clear = setTimeout(() => setSession(null), 0);
      return () => clearTimeout(clear);
    }
    const first = setTimeout(fetchSession, 0);
    const timer = setInterval(fetchSession, REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [isPowerOn, fetchSession]);

  return isPowerOn ? session : null;
}

/** 지금 남은 시간(초). 알 수 없으면 null */
export function remainingSeconds(session: BoothSessionState | null, nowMs: number): number | null {
  if (!session?.kind || typeof session.remaining_sec !== "number") return null;
  return Math.max(0, session.remaining_sec - Math.floor((nowMs - session.fetchedAt) / 1000));
}

/** "13:20" — 서버가 부스 시간대로 보내 준 값에서 시:분만 꺼낸다 (브라우저 시간대와 무관) */
export function endsAtLabel(session: BoothSessionState | null): string | null {
  const text = session?.ends_at;
  return text && text.length >= 16 ? text.slice(11, 16) : null;
}
