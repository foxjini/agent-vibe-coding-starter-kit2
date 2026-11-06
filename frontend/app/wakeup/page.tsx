/**
 * 스마트 기상 시스템 (app/wakeup/page.tsx) — **wakeup 팀 화면 · 7인치 터치모니터(800×480)용**
 * =============================================================================
 * 라즈베리파이에 연결한 7인치 터치모니터의 브라우저가 윈도 PC의 이 화면(`/wakeup`)에 접속합니다.
 * 모바일 앱처럼 위에 상단 바, 아래에 탭 바가 있고 탭마다 화면이 바뀝니다.
 *
 *   홈   현재 시각 · 다음 알람 · 침실 상태      (알람이 울리면 기상 미션 화면으로 바뀝니다)
 *   예약 알람 시각 정하기 (± 버튼 — 터치 화면에는 키보드가 없으니까요)
 *   센서 침대 압력 · 기상 확인 버튼
 *   제어 알람 · 커튼 · 모션 베드 · 조명  (+ 모두 끄기 버튼)
 *   기타 영상인식 감지 로그 · 알림 · 설정값
 *
 * 시나리오(미션 판정, 조명·커튼·모션 베드 동작)는 `scenarios/useWakeup.ts`,
 * 판정 규칙은 `scenarios/wakeupEngine.ts`(React 없는 순수 함수)에 있습니다.
 * 화면 조각은 `components/team/wakeup/`에 있습니다. 하드웨어·규칙 설정은 `/kit`.
 */
"use client";

import { Bell, Maximize, RefreshCw, Settings2, X } from "lucide-react";
import React, { useState } from "react";

import { useAlarmSchedule } from "@/components/team/AlarmScheduleCard";
import WakeupConfirmModal from "@/components/team/WakeupConfirmModal";
import AppBar from "@/components/team/wakeup/AppBar";
import ControlScreen from "@/components/team/wakeup/ControlScreen";
import HomeScreen from "@/components/team/wakeup/HomeScreen";
import MoreScreen from "@/components/team/wakeup/MoreScreen";
import ScheduleScreen from "@/components/team/wakeup/ScheduleScreen";
import SensorScreen from "@/components/team/wakeup/SensorScreen";
import TabBar from "@/components/team/wakeup/TabBar";
import type { TabId } from "@/components/team/wakeup/TabBar";
import { useWakeup } from "@/scenarios/useWakeup";

/** 팀 이름은 `frontend/.env.local`의 NEXT_PUBLIC_TEAM_NAME에서 옵니다 (study 화면과 같음). */
const TEAM_NAME = process.env.NEXT_PUBLIC_TEAM_NAME || "스마트 기상 시스템";

const NOTICE_STYLES: Record<string, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  alert: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function WakeupPage() {
  const wakeup = useWakeup();
  const schedule = useAlarmSchedule();
  const [tab, setTab] = useState<TabId>("home");
  const { connected, notices, dismissNotice } = wakeup.scenario;

  // 알람이 울리는 동안은 어느 탭에 있었든 홈(기상 미션)을 보여 주고 탭 바를 숨깁니다
  const alarmMode = wakeup.ringing || wakeup.mission.active;
  const shown: TabId = alarmMode ? "home" : tab;
  const latest = notices[0] ?? null; // 최신 알림이 맨 앞 (lib/scenario.ts)

  const menu = [
    { label: "하드웨어·규칙 설정", icon: <Settings2 className="h-5 w-5" />, href: "/kit" },
    {
      label: "알람 테스트 (지금 울리기)",
      icon: <Bell className="h-5 w-5" />,
      onSelect: () => void wakeup.startAlarm(),
    },
    {
      label: "전체 화면",
      icon: <Maximize className="h-5 w-5" />,
      onSelect: () => void document.documentElement.requestFullscreen?.().catch(() => {}),
    },
    {
      label: "새로 고침",
      icon: <RefreshCw className="h-5 w-5" />,
      onSelect: () => window.location.reload(),
    },
  ];

  return (
    <div
      className="flex h-dvh select-none flex-col overflow-hidden bg-slate-50"
      onContextMenu={(event) => event.preventDefault()}
    >
      <AppBar title={TEAM_NAME} connected={connected} alarmMode={alarmMode} menu={menu} />

      {/* 가장 최근 알림 한 줄 (전체 기록은 기타 탭) */}
      {latest && (
        <div
          className={`flex h-10 shrink-0 items-center gap-2 border-b pl-4 text-sm ${
            NOTICE_STYLES[latest.level] ?? NOTICE_STYLES.info
          }`}
        >
          <Bell className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1 truncate">{latest.message}</span>
          <button
            type="button"
            onClick={() => dismissNotice(latest.id)}
            aria-label="알림 닫기"
            className="flex h-10 w-12 shrink-0 items-center justify-center opacity-70 active:opacity-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <main className="min-h-0 flex-1">
        {shown === "home" && (
          <HomeScreen
            wakeup={wakeup}
            schedule={schedule}
            alarmMode={alarmMode}
            onOpenSchedule={() => setTab("schedule")}
          />
        )}
        {shown === "schedule" && <ScheduleScreen schedule={schedule} />}
        {shown === "sensors" && <SensorScreen wakeup={wakeup} />}
        {shown === "control" && <ControlScreen wakeup={wakeup} />}
        {shown === "more" && <MoreScreen wakeup={wakeup} />}
      </main>

      {!alarmMode && <TabBar active={tab} onChange={setTab} badges={{ more: notices.length }} />}

      {wakeup.popup && (
        <WakeupConfirmModal
          message={wakeup.popup.message}
          timeLeft={wakeup.popup.timeLeft}
          onConfirm={wakeup.confirmWakeup}
        />
      )}
    </div>
  );
}
