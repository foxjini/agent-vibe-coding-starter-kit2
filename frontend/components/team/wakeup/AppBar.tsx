/**
 * 상단 바 (wakeup 7인치 화면) — 팀 이름 · 지금 시각 · 연결 상태 · ⋮ 메뉴
 */
"use client";

import { AlarmClock } from "lucide-react";
import React from "react";

import OverflowMenu from "@/components/team/wakeup/OverflowMenu";
import type { MenuItem } from "@/components/team/wakeup/OverflowMenu";
import { hhmm, useClock } from "@/components/team/wakeup/useClock";

export default function AppBar({
  title,
  connected,
  alarmMode,
  menu,
}: {
  title: string;
  connected: boolean;
  /** 알람이 울리는 중이면 바 색을 바꿔 한눈에 알 수 있게 합니다 */
  alarmMode: boolean;
  menu: MenuItem[];
}) {
  const now = useClock();
  return (
    <header
      className={`flex h-12 shrink-0 items-center gap-3 border-b pl-4 pr-1 ${
        alarmMode ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"
      }`}
    >
      <h1 className="flex min-w-0 flex-1 items-center gap-2 text-lg font-semibold text-slate-900">
        {alarmMode && <AlarmClock className="h-5 w-5 shrink-0 text-rose-600" aria-hidden="true" />}
        <span className="truncate">{alarmMode ? "기상 미션 중" : title}</span>
      </h1>
      <span className="text-lg font-semibold tabular-nums text-slate-700">{hhmm(now)}</span>
      <span
        className="flex items-center gap-1.5 text-sm text-slate-600"
        aria-label={connected ? "실시간 연결됨" : "연결 대기 중"}
      >
        <span
          className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-400"}`}
        />
        {connected ? "연결됨" : "연결 대기"}
      </span>
      <OverflowMenu items={menu} />
    </header>
  );
}
