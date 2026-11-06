/**
 * 떠 있는 동작 버튼 (FAB, wakeup 7인치 화면) — 화면 오른쪽 아래의 둥근 큰 버튼
 */
"use client";

import React from "react";

export default function Fab({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute bottom-3 right-3 z-30 flex h-14 items-center gap-2 rounded-full bg-slate-900 px-5 text-base font-semibold text-white shadow-lg active:bg-slate-700"
    >
      {icon}
      {label}
    </button>
  );
}
