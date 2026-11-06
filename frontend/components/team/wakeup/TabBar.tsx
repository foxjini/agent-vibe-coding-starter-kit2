/**
 * 하단 탭 (wakeup 7인치 화면) — 홈 · 예약 · 센서 · 제어 · 기타
 * 지금 탭은 앰버 글자와 아이콘 위 작은 점으로 표시합니다.
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
  /** 탭에 붙일 숫자 (예: 기타 탭의 알림 개수) */
  badges?: Partial<Record<TabId, number>>;
}) {
  return (
    <nav
      aria-label="화면 이동"
      className="relative z-10 grid h-[60px] shrink-0 grid-cols-5 border-t border-(--wk-line)"
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
            className={`wk-press relative flex flex-col items-center justify-center gap-1 text-sm active:bg-(--wk-press) ${
              on ? "font-semibold text-(--wk-accent)" : "text-(--wk-dim)"
            }`}
          >
            <Icon className="h-6 w-6" strokeWidth={on ? 2.2 : 1.6} aria-hidden="true" />
            <span>
              {label}
              {badge > 0 && <span className="ml-1 text-(--wk-accent)">{badge > 9 ? "9+" : badge}</span>}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
