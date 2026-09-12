/**
 * 스마트 기상 시스템 대시보드 (app/page.tsx) — wakeup 팀 화면
 * =============================================================================
 * 플랫폼 키트 위에 팀 시나리오를 얹은 화면입니다.
 *
 *   키트가 주는 것   슬롯 카드 자동 생성(SlotGrid), 실시간 상태, 알림
 *   팀이 만드는 것   기상 미션 판정(scenarios/), 미션 카드, 알람 예약 카드
 *
 * 부품을 바꿔도 이 파일은 거의 손대지 않습니다 — 카드가 알아서 바뀝니다.
 * 하드웨어 구성과 자동화 규칙 화면은 /kit 에 있습니다 (docs/부록F 9장).
 */
"use client";

import { AlarmClock, Bell, BellOff, Settings2, Wifi, WifiOff, X } from "lucide-react";
import Link from "next/link";
import React from "react";

import SlotGrid from "@/components/kit/SlotGrid";
import VisionLogCard from "@/components/kit/VisionLogCard";
import AlarmScheduleCard from "@/components/team/AlarmScheduleCard";
import WakeupConfirmModal from "@/components/team/WakeupConfirmModal";
import WakeupMissionCard from "@/components/team/WakeupMissionCard";
import { useWakeup } from "@/scenarios/useWakeup";

const NOTICE_STYLES: Record<string, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  alert: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function WakeupDashboardPage() {
  const {
    scenario,
    mission,
    remainingSeconds,
    popup,
    ringing,
    startAlarm,
    stopAlarm,
    confirmWakeup,
  } = useWakeup();
  const { slots, connected, notices, dismissNotice, setActuator } = scenario;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* 머리말 */}
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">스마트 기상 시스템</h1>
            <p className="mt-1 text-sm text-slate-500">
              알람이 울리면 카메라 앞에서 가위바위보를 이겨야 꺼집니다
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`flex h-9 items-center gap-1.5 rounded-full border px-3 text-sm font-medium ${
                connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
              {connected ? "실시간 연결됨" : "연결 대기 중"}
            </span>
            <Link
              href="/kit"
              className="flex h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 hover:border-slate-300"
            >
              <Settings2 className="h-4 w-4" />
              하드웨어·규칙 설정
            </Link>
          </div>
        </header>

        {/* 알림 */}
        {notices.length > 0 && (
          <div className="mb-5 space-y-2">
            {notices.map((notice) => (
              <div
                key={notice.id}
                className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${
                  NOTICE_STYLES[notice.level] ?? NOTICE_STYLES.info
                }`}
              >
                <span className="flex items-start gap-2">
                  <Bell className="mt-0.5 h-4 w-4 shrink-0" />
                  {notice.message}
                </span>
                <button
                  type="button"
                  onClick={() => dismissNotice(notice.id)}
                  aria-label="알림 닫기"
                  className="shrink-0 opacity-60 hover:opacity-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 알람 제어 + 미션 */}
        <section className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="space-y-4">
            <AlarmScheduleCard />
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <AlarmClock className="h-3.5 w-3.5 text-slate-500" />
                지금 바로
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void startAlarm()}
                  disabled={ringing}
                  className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:border-slate-300 disabled:opacity-50"
                >
                  <Bell className="h-4 w-4" />
                  알람 울리기
                </button>
                <button
                  type="button"
                  onClick={() => void stopAlarm()}
                  disabled={!ringing}
                  className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 text-sm font-medium text-rose-700 hover:border-rose-300 disabled:opacity-50"
                >
                  <BellOff className="h-4 w-4" />
                  알람 끄기
                </button>
              </div>
              <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
                미션을 건너뛰고 끄는 버튼입니다. 정상 기상은 미션을 완수해서 꺼 주세요.
              </p>
            </div>
          </div>

          <div className="lg:col-span-2">
            <WakeupMissionCard mission={mission} remainingSeconds={remainingSeconds} />
          </div>
        </section>

        {/* 하드웨어 — 슬롯이 바뀌면 카드도 알아서 바뀝니다 */}
        <SlotGrid
          slots={slots}
          onControl={setActuator}
          emptyHint={
            <>
              라즈베리파이에서 <code className="rounded bg-white px-1 py-0.5">daemon.py</code>를
              실행하면 부저와 버튼이 여기에 나타납니다.
            </>
          }
        />

        <section className="mt-8">
          <VisionLogCard />
        </section>
      </div>

      {popup && (
        <WakeupConfirmModal
          message={popup.message}
          timeLeft={popup.timeLeft}
          onConfirm={confirmWakeup}
        />
      )}
    </main>
  );
}
