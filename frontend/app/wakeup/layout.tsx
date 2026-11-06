/**
 * wakeup 화면 전용 레이아웃 — 7인치 터치모니터(800×480)
 * 4팀 공통 레이아웃(app/layout.tsx)은 그대로이고, `/wakeup` 주소에만 적용됩니다.
 *   - 확대·축소 막기 (키오스크 화면에서 잘못 눌러 확대되지 않게)
 *   - wakeup 글꼴(IBM Plex Sans KR)과 디자인 토큰(wakeup.css — 모두 `.wk` 안에서만 동작)
 * 글꼴은 build 때 PC가 받아 함께 내보내므로, 파이 브라우저는 인터넷이 없어도 됩니다.
 */
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_KR } from "next/font/google";
import React from "react";

import "./wakeup.css";

const plex = IBM_Plex_Sans_KR({
  weight: ["200", "400", "500", "600"],
  variable: "--font-wakeup",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "스마트 기상 시스템",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#0f1226",
};

export default function WakeupLayout({ children }: { children: React.ReactNode }) {
  return <div className={`${plex.variable} contents`}>{children}</div>;
}
