/**
 * 점 세 개(⋮) 메뉴 (wakeup 7인치 화면) — 자주 쓰지 않는 기능을 모아 둡니다.
 */
"use client";

import { EllipsisVertical } from "lucide-react";
import Link from "next/link";
import React, { useEffect, useRef, useState } from "react";

export interface MenuItem {
  label: string;
  icon: React.ReactNode;
  /** 다른 화면으로 가는 항목 */
  href?: string;
  onSelect?: () => void;
}

export default function OverflowMenu({ items }: { items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // 메뉴 밖을 누르면 닫습니다
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  const itemClass =
    "wk-press flex min-h-12 w-full items-center gap-3 px-4 text-left text-base text-(--wk-text) active:bg-(--wk-press)";

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="메뉴 열기"
        aria-expanded={open}
        className="wk-press flex h-12 w-12 items-center justify-center rounded-full text-(--wk-dim) active:bg-(--wk-press)"
      >
        <EllipsisVertical className="h-6 w-6" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-1 top-12 z-40 w-64 overflow-hidden rounded-[var(--wk-radius-control)] border border-(--wk-line-strong) bg-(--wk-bg) py-1 shadow-2xl"
        >
          {items.map((item) =>
            item.href ? (
              <Link key={item.label} href={item.href} role="menuitem" className={itemClass}>
                <span className="text-(--wk-dim)">{item.icon}</span>
                {item.label}
              </Link>
            ) : (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                className={itemClass}
                onClick={() => {
                  setOpen(false);
                  item.onSelect?.();
                }}
              >
                <span className="text-(--wk-dim)">{item.icon}</span>
                {item.label}
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}
