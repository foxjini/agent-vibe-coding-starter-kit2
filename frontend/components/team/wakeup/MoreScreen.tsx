/**
 * 기타 화면 (wakeup 7인치 화면) — 영상인식 감지 로그 · 알림 기록 · 지금 설정값
 */
"use client";

import { Bell, Settings2, X } from "lucide-react";
import Link from "next/link";
import React from "react";

import VisionLogCard from "@/components/kit/VisionLogCard";
import { API_BASE_URL } from "@/lib/api";
import type { WakeupApi } from "@/scenarios/useWakeup";

export default function MoreScreen({ wakeup }: { wakeup: WakeupApi }) {
  const { notices, dismissNotice, connected } = wakeup.scenario;
  const { device, config } = wakeup;
  const settings: [string, string][] = [
    ["미션", config.mode === "pattern" ? "패턴 그리기" : "가위바위보·사물"],
    ["모션 베드 기준 압력", String(device.bedPressureThreshold)],
    ["모션 베드 각도 · 간격", `${device.bedAngle}° · ${device.bedShakeSeconds}초`],
    ["커튼 열림 · 닫힘", `${device.curtainOpenAngle}° · ${device.curtainCloseAngle}°`],
    ["기상 조명", `${device.lightColor} · 밝기 ${device.lightBrightness}`],
    ["백엔드", `${API_BASE_URL} · ${connected ? "연결됨" : "연결 대기"}`],
  ];

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-3 p-3">
      <div className="min-h-0 overflow-y-auto">
        <VisionLogCard limit={8} />
      </div>
      <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
        <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
            <Bell className="h-4 w-4 text-slate-500" />
            알림 {notices.length}개
          </div>
          {notices.length === 0 ? (
            <p className="text-sm text-slate-500">새 알림이 없습니다.</p>
          ) : (
            <ul className="space-y-1.5">
              {notices.map((notice) => (
                <li key={notice.id} className="flex items-start gap-2 text-sm text-slate-700">
                  <span className="flex-1">{notice.message}</span>
                  <button
                    type="button"
                    onClick={() => dismissNotice(notice.id)}
                    aria-label="알림 지우기"
                    className="-my-2 flex h-10 w-10 shrink-0 items-center justify-center text-slate-400 active:text-slate-700"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="mb-1 text-sm font-semibold text-slate-700">지금 설정 (.env의 NEXT_PUBLIC_WAKEUP_*)</div>
          <dl className="text-sm">
            {settings.map(([key, value]) => (
              <div key={key} className="flex justify-between gap-2 border-b border-slate-100 py-1.5 last:border-0">
                <dt className="text-slate-500">{key}</dt>
                <dd className="truncate text-right font-medium text-slate-800">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
        <Link
          href="/kit"
          className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white text-base font-medium text-slate-700 active:bg-slate-100"
        >
          <Settings2 className="h-5 w-5" />
          하드웨어·규칙 설정 (/kit)
        </Link>
      </div>
    </div>
  );
}
