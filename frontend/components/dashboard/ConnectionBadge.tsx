"use client";

import React, { useEffect, useState } from "react";

interface ConnectionBadgeProps {
  connected: boolean;
  className?: string;
}

export const ConnectionBadge: React.FC<ConnectionBadgeProps> = ({
  connected,
  className = "",
}) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // SSR Hydration Mismatch 방지: 마운트 전에는 로딩/대기 기본 상태 표시
  if (!mounted) {
    return (
      <span
        suppressHydrationWarning
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 ${className}`}
      >
        <span className="w-2 h-2 rounded-full bg-slate-400" />
        동기화 준비 중...
      </span>
    );
  }

  return (
    <span
      suppressHydrationWarning
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors duration-200 ${
        connected
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
          : "bg-rose-50 text-rose-700 border border-rose-200"
      } ${className}`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          connected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
        }`}
      />
      {connected ? "실시간 연결됨" : "연결 대기 중 (백엔드 확인)"}
    </span>
  );
};

export default ConnectionBadge;
