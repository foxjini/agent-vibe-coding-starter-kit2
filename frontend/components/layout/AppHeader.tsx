"use client";

import React from "react";
import Link from "next/link";
import { Mic2, Clock } from "lucide-react";
import { ConnectionBadge } from "@/components/dashboard/ConnectionBadge";
import { useClock } from "@/hooks/useBoothData";
import { Device } from "@/types";

interface AppHeaderProps {
  title: string;
  subtitle: string;
  devices: Device[];
  isConnected: boolean;
  /** 오른쪽 끝에 붙일 라우트별 버튼 (예: 관리자 링크) */
  actions?: React.ReactNode;
  /** 제목을 눌렀을 때 갈 곳 (기본: /) */
  homeHref?: string;
}

/**
 * `/` 와 `/admin` 이 함께 쓰는 상단 바.
 *
 * `/booth` 는 부스 대형 화면에 계속 띄워 두는 키오스크 화면이라 이 헤더를 쓰지
 * 않는다. 그래서 app/layout.tsx 가 아니라 별도 컴포넌트로 뒀다 — layout 에 넣으면
 * 세 화면 모두에 따라붙는다.
 */
export function AppHeader({
  title,
  subtitle,
  devices,
  isConnected,
  actions,
  homeHref = "/",
}: AppHeaderProps) {
  const timeStr = useClock();

  const relay = devices.find((d) => d.id === "relay_1");
  const doorLock = devices.find((d) => d.id === "door_lock_1");
  const isPowerOn = relay?.current_state === "on";
  const isUnlocked =
    doorLock?.current_state === "unlocked" || doorLock?.current_state === "open";

  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-line px-4 lg:px-8 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <Link href={homeHref} className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-xl bg-brass text-on-accent shadow-lg shrink-0">
            <Mic2 className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-extrabold tracking-tight text-ink truncate">
              {title}
            </h1>
            <p className="text-[11px] text-ink-3 truncate">{subtitle}</p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 text-xs font-mono tnum">
            <span
              className={`px-2.5 py-1 rounded-full border ${
                isPowerOn
                  ? "bg-free-soft text-free border-free/40"
                  : "bg-raised text-ink-3 border-line-strong"
              }`}
            >
              전원: {isPowerOn ? "ON" : "OFF"}
            </span>
            <span
              className={`px-2.5 py-1 rounded-full border ${
                isUnlocked
                  ? "bg-free-soft text-free border-free/40"
                  : "bg-raised text-ink-3 border-line-strong"
              }`}
            >
              도어락: {isUnlocked ? "열림" : "잠김"}
            </span>
          </div>

          <ConnectionBadge connected={isConnected} />

          <div
            suppressHydrationWarning
            className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-lg bg-raised/80 border border-line font-mono tnum text-xs text-ink-2"
          >
            <Clock className="w-3.5 h-3.5 text-ink-3" />
            <span>{timeStr || "--:--:--"}</span>
          </div>

          {actions}
        </div>
      </div>
    </header>
  );
}
