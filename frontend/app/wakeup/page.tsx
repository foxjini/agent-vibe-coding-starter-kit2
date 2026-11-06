/**
 * 스마트 기상 시스템 (app/wakeup/page.tsx) — **wakeup 팀 화면 · 7인치 터치모니터(800×480)용**
 * =============================================================================
 * 라즈베리파이에 연결한 7인치 터치모니터의 브라우저가 윈도 PC의 이 화면(`/wakeup`)에 접속합니다.
 * 위에 상단 줄, 아래에 탭이 있고 탭마다 화면이 바뀝니다.
 *
 *   홈   시계 · 다음 알람 · 침실 상태      (알람이 울리면 기상 미션 화면으로 바뀝니다)
 *   예약 알람 시각 정하기 (▲▼ 버튼 — 터치 화면에는 키보드가 없으니까요)
 *   센서 침대 압력 · 기상 확인 버튼
 *   제어 알람 · 커튼 · 모션 베드 · 조명  (+ 모두 끄기 버튼)
 *   기타 카메라가 본 것 · 알림 · 설정값
 *
 * 디자인 "새벽빛": 평상시는 어두운 밤 화면(night), 알람이 울리면 화면 전체가 해 뜨는 색(dawn).
 * 색·글꼴·크기 규칙은 app/wakeup/wakeup.css와 components/team/wakeup/DESIGN.md에 있습니다.
 * 시나리오(미션 판정, 조명·커튼·모션 베드 동작)는 `scenarios/useWakeup.ts`에 있습니다.
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

/** 알림 종류 → 앞에 붙는 점 색 */
const NOTICE_DOT: Record<string, string> = {
  info: "bg-(--wk-dim)",
  success: "bg-(--wk-ok)",
  warn: "bg-(--wk-accent)",
  alert: "bg-(--wk-alert)",
};

export default function WakeupPage() {
  const wakeup = useWakeup();
  const schedule = useAlarmSchedule();
  const [tab, setTab] = useState<TabId>("home");
  const { connected, notices, dismissNotice } = wakeup.scenario;

  // 알람·미션 중과 기상 확인 창이 떠 있는 동안은 새벽빛 화면입니다.
  // 알람이 울리는 동안은 어느 탭에 있었든 홈(기상 미션)을 보여 주고 탭을 숨깁니다
  const alarmMode = wakeup.ringing || wakeup.mission.active;
  const shown: TabId = alarmMode ? "home" : tab;
  const latest = notices[0] ?? null; // 최신 알림이 맨 앞 (lib/scenario.ts)

  const menu = [
    { label: "하드웨어와 규칙 설정", icon: <Settings2 className="h-5 w-5" />, href: "/kit" },
    {
      label: "알람 지금 울려 보기",
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
      className="wk relative flex h-dvh select-none flex-col overflow-hidden"
      data-phase={alarmMode || wakeup.popup ? "dawn" : "night"}
      onContextMenu={(event) => event.preventDefault()}
    >
      <div className="wk-sunrise" aria-hidden="true" />

      <AppBar
        title={TEAM_NAME}
        connected={connected}
        alarmMode={alarmMode}
        showClock={shown !== "home"}
        menu={menu}
      />

      {/* 가장 최근 알림 한 줄 (전체 기록은 기타 탭). 미션 중에는 미션 화면이 같은 내용을 보여 주므로 숨깁니다 */}
      {latest && !alarmMode && (
        <div role="status" className="relative z-10 flex h-11 shrink-0 items-center gap-3 pl-5 text-base">
          <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${NOTICE_DOT[latest.level] ?? NOTICE_DOT.info}`} />
          <span className="min-w-0 flex-1 truncate">{latest.message}</span>
          <button
            type="button"
            onClick={() => dismissNotice(latest.id)}
            aria-label="알림 닫기"
            className="wk-press flex h-11 w-12 shrink-0 items-center justify-center text-(--wk-dim) active:bg-(--wk-press)"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <main className="relative z-10 min-h-0 flex-1">
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
