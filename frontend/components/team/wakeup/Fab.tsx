/**
 * 떠 있는 동작 버튼 (FAB, wakeup 7인치 화면) — 화면 오른쪽 아래
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
      className="wk-press absolute bottom-4 right-4 z-30 flex h-14 items-center gap-2 rounded-full bg-(--wk-accent) px-6 text-base font-semibold text-(--wk-on-accent) shadow-xl"
    >
      {icon}
      {label}
    </button>
  );
}
