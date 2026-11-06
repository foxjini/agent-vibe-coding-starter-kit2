/**
 * 2차 수면 방지 확인 창 (wakeup 팀 화면).
 * 제한 시간 안에 확인하지 않으면 시나리오가 알람을 다시 울립니다.
 * 색은 새벽빛 디자인의 의미 변수(--wk-*)를 씁니다 (app/wakeup/wakeup.css).
 */
"use client";

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
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="wk-confirm-title"
      aria-describedby="wk-confirm-desc"
      className="fixed inset-0 z-50 flex items-center justify-center bg-(--wk-scrim) p-6"
    >
      <div className="w-full max-w-lg rounded-[var(--wk-radius-panel)] bg-(--wk-bg) p-7 shadow-2xl">
        <h2 id="wk-confirm-title" className="text-[32px] font-semibold leading-tight">
          정말 일어났나요?
        </h2>
        <p id="wk-confirm-desc" className="mt-2 text-lg text-(--wk-dim)">
          {timeLeft}초 안에 누르지 않으면 알람이 다시 울려요. 침대 옆 확인 버튼을 눌러도 됩니다.
        </p>
        <p className="sr-only">{message}</p>
        <button
          type="button"
          onClick={onConfirm}
          autoFocus
          className="wk-press mt-6 flex min-h-16 w-full items-center justify-center rounded-[var(--wk-radius-control)] bg-(--wk-accent) text-xl font-semibold text-(--wk-on-accent)"
        >
          일어났어요
        </button>
      </div>
    </div>
  );
}
