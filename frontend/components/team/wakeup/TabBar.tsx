/**
 * 하단 탭 바 (wakeup 7인치 화면) — 홈 · 예약 · 센서 · 제어 · 기타
 */
"use client";

import { Activity, AlarmClock, Ellipsis, House, SlidersHorizontal } from "lucide-react";
import React from "react";

export type TabId = "home" | "schedule" | "sensors" | "control" | "more";

const TABS: { id: TabId; label: string; Icon: typeof House }[] = [
  { id: "home", label: "홈", Icon: House },
  { id: "schedule", label: "예약", Icon: AlarmClock },
  { id: "sensors", label: "센서", Icon: Activity },
  { id: "control", label: "제어", Icon: SlidersHorizontal },
  { id: "more", label: "기타", Icon: Ellipsis },
];

export default function TabBar({
  active,
  onChange,
  badges = {},
}: {
  active: TabId;
  onChange: (tab: TabId) => void;
  /** 탭 위에 띄울 숫자 (예: 기타 탭의 알림 개수) */
  badges?: Partial<Record<TabId, number>>;
}) {
  return (
    <nav
      aria-label="화면 이동"
      className="grid h-[60px] shrink-0 grid-cols-5 border-t border-slate-200 bg-white"
    >
      {TABS.map(({ id, label, Icon }) => {
        const on = id === active;
        const badge = badges[id] ?? 0;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-current={on ? "page" : undefined}
            className={`relative flex flex-col items-center justify-center gap-0.5 text-sm font-medium ${
              on ? "text-sky-700" : "text-slate-500 active:bg-slate-50"
            }`}
          >
            {on && <span className="absolute inset-x-6 top-0 h-1 rounded-b-full bg-sky-600" />}
            <span className="relative">
              <Icon className="h-6 w-6" />
              {badge > 0 && (
                <span className="absolute -right-3 -top-1.5 min-w-5 rounded-full bg-rose-500 px-1 text-center text-[11px] font-bold leading-5 text-white">
                  {badge > 9 ? "9+" : badge}
                </span>
              )}
            </span>
            {label}
          </button>
        );
      })}
    </nav>
  );
}
