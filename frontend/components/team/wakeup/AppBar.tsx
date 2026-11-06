/**
 * 상단 줄 (wakeup 7인치 화면) — 팀 이름 · 시각 · 연결 상태 · ⋮ 메뉴
 * 밤에는 바탕과 하나로 이어져 눈에 띄지 않고, 알람 중에는 "일어날 시간"을 알립니다.
 */
"use client";

import { Sunrise } from "lucide-react";
import React from "react";

import OverflowMenu from "@/components/team/wakeup/OverflowMenu";
import type { MenuItem } from "@/components/team/wakeup/OverflowMenu";
import { hhmm, useClock } from "@/components/team/wakeup/useClock";

export default function AppBar({
  title,
  connected,
  alarmMode,
  showClock,
  menu,
}: {
  title: string;
  connected: boolean;
  alarmMode: boolean;
  /** 홈에는 큰 시계가 있으므로 위 시각은 다른 탭에서만 */
  showClock: boolean;
  menu: MenuItem[];
}) {
  const now = useClock();
  return (
    <header className="relative z-20 flex h-12 shrink-0 items-center gap-4 pl-5 pr-1">
      <h1 className="flex min-w-0 flex-1 items-center gap-2 text-base">
        {alarmMode ? (
          <>
            <Sunrise className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span className="truncate font-semibold">일어날 시간이에요</span>
          </>
        ) : (
          <span className="truncate text-(--wk-dim)">{title}</span>
        )}
      </h1>
      {showClock && !alarmMode && (
        <span className="text-base font-medium" aria-label="지금 시각">
          {hhmm(now)}
        </span>
      )}
      <span
        className="flex items-center gap-2 text-sm text-(--wk-dim)"
        title={connected ? "실시간 연결됨" : "연결 대기 중"}
      >
        <span
          aria-hidden="true"
          className={`h-2 w-2 rounded-full ${connected ? "bg-(--wk-ok)" : "border border-(--wk-alert)"}`}
        />
        {connected ? "연결됨" : "연결 대기"}
      </span>
      <OverflowMenu items={menu} />
    </header>
  );
}
