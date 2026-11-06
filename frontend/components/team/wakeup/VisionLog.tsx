/**
 * 영상인식 감지 기록 (wakeup 7인치 화면 전용 모양)
 * 데이터를 읽는 방법은 키트의 VisionLogCard와 같습니다(같은 API·같은 실시간 구독).
 * 키트 카드는 4팀 공통이라 고치지 않고, 밤 화면에 맞는 모양만 여기서 새로 그립니다.
 */
"use client";

import React, { useCallback, useEffect, useState } from "react";

import type { VisionEventItem } from "@/components/kit/VisionLogCard";
import { apiFetch } from "@/lib/api";
import { useScenario } from "@/lib/scenario";

export default function VisionLog({ limit = 8 }: { limit?: number }) {
  const { onVision } = useScenario();
  const [events, setEvents] = useState<VisionEventItem[]>([]);

  const load = useCallback(async () => {
    const res = await apiFetch<VisionEventItem[]>(`/api/events/vision?limit=${limit}`);
    if (res.ok && Array.isArray(res.data)) setEvents(res.data);
  }, [limit]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(
    () =>
      onVision(null, (event) => {
        setEvents((prev) => [{ ...event, id: `ws-${Date.now()}-${Math.random()}` }, ...prev].slice(0, limit));
      }),
    [onVision, limit]
  );

  return (
    <section>
      <h2 className="mb-2 text-lg font-medium">카메라가 본 것</h2>
      {events.length === 0 ? (
        <p className="text-base text-(--wk-dim)">
          아직 기록이 없어요. PC에서 영상인식 프로그램(vision)을 켜면 여기에 쌓입니다.
        </p>
      ) : (
        <ul>
          {events.map((event, index) => {
            const time = event.created_at
              ? new Date(event.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
              : "방금";
            return (
              <li
                key={event.id ?? `${index}-${event.created_at ?? ""}`}
                className="flex min-h-11 items-center gap-3 border-b border-(--wk-line) text-base last:border-0"
              >
                <span
                  aria-hidden="true"
                  className={`h-2 w-2 shrink-0 rounded-full ${event.detected ? "bg-(--wk-ok)" : "border border-(--wk-dim)"}`}
                />
                <span className="min-w-0 flex-1 truncate">
                  {event.label || event.event_type || "감지"}
                  {event.confidence !== null && event.confidence !== undefined && (
                    <span className="text-(--wk-dim)"> {Math.round(event.confidence * 100)}%</span>
                  )}
                </span>
                <span className="shrink-0 text-(--wk-dim)">{time}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
