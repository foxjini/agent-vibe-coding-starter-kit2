/**
 * 비전 감지 로그 (키트 제공) — 카메라가 무엇을 봤는지 최근 순으로 보여 줍니다.
 * 팀이 감지 대상을 바꿔도 이 파일은 고치지 않습니다 (라벨을 그대로 표시합니다).
 */
"use client";

import { Activity, CheckCircle2, XCircle } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useScenario } from "@/lib/scenario";

export interface VisionEventItem {
  id?: number | string;
  event_type?: string;
  label?: string | null;
  detected?: boolean;
  count?: number | null;
  confidence?: number | null;
  created_at?: string | null;
}

export default function VisionLogCard({ limit = 12 }: { limit?: number }) {
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

  // 새 이벤트가 들어오면 목록 맨 위에 끼워 넣습니다 (새로고침 없이 갱신).
  useEffect(
    () =>
      onVision(null, (event) => {
        setEvents((prev) =>
          [{ ...event, id: `ws-${Date.now()}-${Math.random()}` }, ...prev].slice(0, limit)
        );
      }),
    [onVision, limit]
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-800">영상인식 감지 로그</h3>
        </div>
        <span className="text-xs text-slate-400">최근 {events.length}개</span>
      </div>

      {events.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 py-8 text-center text-xs text-slate-400">
          수신된 영상인식 이벤트가 없습니다. (비전 클라이언트를 실행하세요)
        </div>
      ) : (
        <div className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-100">
          {events.map((event, index) => {
            const detected = Boolean(event.detected);
            const time = event.created_at
              ? new Date(event.created_at).toLocaleTimeString("ko-KR")
              : "방금";
            return (
              <div
                key={event.id ?? `${index}-${event.created_at ?? ""}`}
                className="flex items-center justify-between p-3 text-xs transition-colors hover:bg-slate-50/80"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  {detected ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-slate-400" />
                  )}
                  <div className="min-w-0">
                    <span className="font-semibold text-slate-800">
                      {event.label || event.event_type || "감지"}
                    </span>
                    {typeof event.count === "number" && event.count > 0 && (
                      <span className="ml-2 text-slate-400">
                        개수 <strong className="text-slate-600">{event.count}</strong>
                      </span>
                    )}
                    {event.confidence !== null && event.confidence !== undefined && (
                      <span className="ml-2 text-slate-400">
                        신뢰도{" "}
                        <strong className="text-slate-600">
                          {Math.round(event.confidence * 100)}%
                        </strong>
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span
                    className={`rounded border px-2 py-0.5 text-[10px] font-medium ${
                      detected
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-slate-200 bg-slate-100 text-slate-600"
                    }`}
                  >
                    {detected ? "감지됨" : "미감지"}
                  </span>
                  <span suppressHydrationWarning className="font-mono text-[11px] text-slate-400">
                    {time}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
