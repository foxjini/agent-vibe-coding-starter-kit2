"use client";

import React from "react";

interface ConnectionBadgeProps {
  connected: boolean;
  className?: string;
}

/**
 * 실시간 연결 상태 표시.
 *
 * 예전에는 "마운트 전"을 위한 세 번째 상태(동기화 준비 중)가 따로 있었다.
 * 서버와 클라이언트 모두 처음에는 연결 안 됨(false)으로 시작하므로 하이드레이션
 * 불일치가 날 일이 없고, 상태가 셋이면 읽는 사람만 헷갈린다. 둘로 줄였다.
 *
 * 색만으로 구분하지 않고 점의 모양과 글자를 함께 바꾼다 — 색각 이상인 사람도
 * 구분할 수 있어야 한다.
 */
export const ConnectionBadge: React.FC<ConnectionBadgeProps> = ({
  connected,
  className = "",
}) => (
  <span
    suppressHydrationWarning
    title={connected ? "백엔드와 실시간으로 연결되어 있습니다" : "백엔드에 연결되지 않았습니다"}
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
      border transition-colors ${
        connected
          ? "bg-free-soft text-free border-free/35"
          : "bg-raised text-ink-3 border-line"
      } ${className}`}
  >
    <span
      aria-hidden
      className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-free" : "bg-ink-3"}`}
    />
    {connected ? "실시간 연결됨" : "연결 끊김"}
  </span>
);

export default ConnectionBadge;
