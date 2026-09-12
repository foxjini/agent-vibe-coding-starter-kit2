/**
 * 2차 수면 방지 확인 팝업 (wakeup 팀 화면).
 * 제한 시간 안에 확인하지 않으면 시나리오가 알람을 다시 울립니다.
 */
"use client";

import { AlarmClock } from "lucide-react";
import React from "react";

export default function WakeupConfirmModal({
  message,
  timeLeft,
  onConfirm,
}: {
  message: string;
  timeLeft: number;
  onConfirm: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="기상 확인"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-3 flex items-center gap-2 text-rose-600">
          <AlarmClock className="h-5 w-5" />
          <span className="text-sm font-semibold uppercase tracking-wider">2차 수면 방지</span>
        </div>
        <p className="text-lg font-medium text-slate-800">{message}</p>
        <p className="mt-2 text-sm text-slate-500">
          <strong className="tabular-nums text-rose-600">{timeLeft}초</strong> 안에 확인하지
          않으면 알람이 다시 울립니다.
        </p>
        <button
          type="button"
          onClick={onConfirm}
          className="mt-5 h-12 w-full rounded-lg bg-sky-600 text-base font-medium text-white hover:bg-sky-700"
        >
          일어났어요!
        </button>
      </div>
    </div>
  );
}
