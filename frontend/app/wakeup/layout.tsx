/**
 * wakeup 화면 전용 레이아웃 — 7인치 터치모니터(800×480)에서 확대·축소되지 않게 합니다.
 * 4팀 공통 레이아웃(app/layout.tsx)은 그대로이고, `/wakeup` 주소에만 적용됩니다.
 */
import type { Metadata, Viewport } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "스마트 기상 시스템",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function WakeupLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
