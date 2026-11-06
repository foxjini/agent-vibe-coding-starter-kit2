/**
 * 7인치 화면의 타일·버튼 (wakeup 팀 화면 전용)
 * 손가락으로 누르기 쉽도록 버튼은 최소 48px 높이입니다.
 */
"use client";

import React from "react";

export function Tile({
  icon,
  title,
  badge,
  children,
  muted = false,
}: {
  icon: React.ReactNode;
  title: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  /** 배치표에 없는 부품처럼 흐리게 보여 줄 때 */
  muted?: boolean;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-2xl border bg-white p-3 shadow-sm ${
        muted ? "border-dashed border-slate-300 opacity-70" : "border-slate-200"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-slate-700">
          <span className="shrink-0 text-slate-500">{icon}</span>
          <span className="truncate">{title}</span>
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

const TONES = {
  plain: "border border-slate-200 bg-white text-slate-700 active:bg-slate-100",
  primary: "bg-sky-600 text-white active:bg-sky-700",
  danger: "bg-rose-600 text-white active:bg-rose-700",
  soft: "border border-sky-200 bg-sky-50 text-sky-800 active:bg-sky-100",
} as const;

export function TouchButton({
  children,
  onClick,
  disabled,
  tone = "plain",
  className = "",
  ariaLabel,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: keyof typeof TONES;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={`flex min-h-12 items-center justify-center gap-1.5 rounded-xl px-3 text-base font-medium disabled:opacity-40 ${TONES[tone]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Pill({ on, children }: { on: boolean; children: React.ReactNode }) {
  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        on ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"
      }`}
    >
      {children}
    </span>
  );
}

/** 배치표에 그 부품이 없을 때 타일 안에 보여 줄 안내 */
export function MissingSlot({ slotId }: { slotId: string }) {
  return (
    <p className="text-sm text-slate-500">
      배치표에 <code className="rounded bg-slate-100 px-1">{slotId}</code>가 없습니다. 파이 담당에게
      확인하세요.
    </p>
  );
}
