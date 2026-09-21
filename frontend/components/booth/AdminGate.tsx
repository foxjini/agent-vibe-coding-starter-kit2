"use client";

import React, { useState } from "react";
import { ShieldCheck, ShieldAlert, LogOut, KeyRound } from "lucide-react";
import { adminLogin, adminLogout } from "@/utils/adminSession";

interface AdminGateProps {
  /** 관리자 인증 여부 — adminSession 스토어를 구독한 값이 내려온다 */
  isAuthed: boolean;
}

/**
 * 관리자 인증 게이트 (부록G §3-4)
 *
 * 도어락·전원 제어와 시나리오 강제 실행은 관리자만 할 수 있어야 한다.
 * 관리자 PIN은 이 파일 어디에도 적지 않는다 — 백엔드(.env의 ADMIN_PIN)가 검증한다.
 */
export function AdminGate({ isAuthed }: AdminGateProps) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim() || busy) return;

    setBusy(true);
    setError(null);
    const result = await adminLogin(pin.trim());
    setBusy(false);

    if (result.ok) {
      setPin("");
      // 인증 상태는 adminSession 스토어가 구독자에게 알린다
    } else {
      setPin("");
      setError(result.message);
    }
  };

  const handleLogout = async () => {
    await adminLogout();
  };

  if (isAuthed) {
    return (
      <div className="p-3.5 rounded-2xl bg-free-soft/40 border border-free/40 flex items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-2.5 min-w-0">
          <ShieldCheck className="w-5 h-5 text-free shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-bold text-free">관리자 모드로 인증되었습니다.</p>
            <p className="text-[11px] text-free/70 mt-0.5">
              기기 직접 제어와 시나리오 강제 실행을 사용할 수 있습니다. 자리를 비울 때는 인증을 해제하세요.
            </p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="px-3 py-1.5 rounded-lg bg-raised hover:bg-line-strong/90 text-ink-2 border border-line-strong text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
        >
          <LogOut className="w-3.5 h-3.5" />
          인증 해제
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-2xl bg-surface/80 border border-brass/40 shadow-lg space-y-3">
      <div className="flex items-start gap-2.5">
        <ShieldAlert className="w-5 h-5 text-brass shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-bold text-ink">관리자 인증이 필요한 화면입니다.</p>
          <p className="text-[11px] text-ink-3 mt-0.5 leading-relaxed">
            도어락·전원 직접 제어와 시나리오 강제 실행은 관리자만 사용할 수 있습니다.
            <br />
            관람객·학생은 <strong className="text-ink-2">키패드 인증</strong>과{" "}
            <strong className="text-ink-2">예약 신청</strong>만 이용하세요.
          </p>
        </div>
      </div>

      <form onSubmit={handleLogin} className="flex gap-2">
        <div className="relative flex-1">
          <KeyRound className="w-4 h-4 text-ink-3 absolute left-3 top-2.5" />
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="관리자 PIN 입력"
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-canvas border border-line-strong text-sm text-ink placeholder-ink-3 focus:outline-none focus:border-brass tracking-widest"
          />
        </div>
        <button
          type="submit"
          disabled={busy || !pin.trim()}
          className="px-4 py-2 rounded-xl bg-brass hover:bg-brass/90 disabled:opacity-40 disabled:cursor-not-allowed text-on-accent font-bold text-xs transition-colors shrink-0 cursor-pointer"
        >
          {busy ? "확인 중..." : "인증"}
        </button>
      </form>

      {error && (
        <p className="text-[11px] text-live flex items-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
