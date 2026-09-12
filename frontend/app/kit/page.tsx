/**
 * 플랫폼 키트 대시보드 (app/kit/page.tsx)
 * =============================================================================
 * 팀이 **자유롭게 고쳐 쓰는 화면**입니다. 아래 3개 탭이 키트가 제공하는 전부입니다.
 *
 *   대시보드     SlotGrid — 켜져 있는 슬롯이 자동으로 카드가 됩니다
 *   하드웨어 구성 HardwareSetup — 슬롯 20칸에 의미를 붙입니다 (데이터 수정)
 *   자동화 규칙   RuleEditor — 코드 없이 자동화를 만듭니다
 *
 * 부품을 추가·제거해도 이 파일은 고치지 않습니다 (docs/부록F 9장).
 */
"use client";

import { Bell, Cpu, Settings2, Wifi, WifiOff, Workflow, X } from "lucide-react";
import React, { useState } from "react";

import HardwareSetup from "@/components/kit/HardwareSetup";
import RuleEditor from "@/components/kit/RuleEditor";
import SlotGrid from "@/components/kit/SlotGrid";
import { useScenario } from "@/lib/scenario";

type Tab = "dashboard" | "hardware" | "rules";

const TABS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "dashboard", label: "대시보드", icon: Cpu },
  { id: "hardware", label: "하드웨어 구성", icon: Settings2 },
  { id: "rules", label: "자동화 규칙", icon: Workflow },
];

const NOTICE_STYLES: Record<string, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  alert: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function KitDashboardPage() {
  const scenario = useScenario();
  const [tab, setTab] = useState<Tab>("dashboard");

  const { slots, connected, notices, dismissNotice, setActuator, refresh } = scenario;
  const activeCount = slots.length;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* 머리말 */}
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">IoT 플랫폼 키트</h1>
            <p className="mt-1 text-sm text-slate-500">
              사용 중인 슬롯 {activeCount}개 · 부품을 바꿔도 화면 코드는 그대로입니다
            </p>
          </div>
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
        </header>

        {/* 알림 (규칙의 notify 액션도 여기로 들어옵니다) */}
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

        {/* 탭 */}
        <nav className="mb-6 flex gap-1 border-b border-slate-200">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                tab === id
                  ? "border-sky-600 text-sky-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>

        {tab === "dashboard" && <SlotGrid slots={slots} onControl={setActuator} />}
        {tab === "hardware" && <HardwareSetup onChanged={() => void refresh()} />}
        {tab === "rules" && <RuleEditor slots={slots} />}
      </div>
    </main>
  );
}
