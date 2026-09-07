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
      <div className="p-3.5 rounded-2xl bg-emerald-950/40 border border-emerald-500/40 flex items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-2.5 min-w-0">
          <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-bold text-emerald-200">관리자 모드로 인증되었습니다.</p>
            <p className="text-[11px] text-emerald-300/70 mt-0.5">
              기기 직접 제어와 시나리오 강제 실행을 사용할 수 있습니다. 자리를 비울 때는 인증을 해제하세요.
            </p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
        >
          <LogOut className="w-3.5 h-3.5" />
          인증 해제
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-2xl bg-slate-900/80 border border-indigo-500/40 shadow-lg space-y-3">
      <div className="flex items-start gap-2.5">
        <ShieldAlert className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-bold text-white">관리자 인증이 필요한 화면입니다.</p>
          <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
            도어락·전원 직접 제어와 시나리오 강제 실행은 관리자만 사용할 수 있습니다.
            <br />
            관람객·학생은 <strong className="text-slate-300">키패드 인증</strong>과{" "}
            <strong className="text-slate-300">예약 신청</strong>만 이용하세요.
          </p>
        </div>
      </div>

      <form onSubmit={handleLogin} className="flex gap-2">
        <div className="relative flex-1">
          <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="관리자 PIN 입력"
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 tracking-widest"
          />
        </div>
        <button
          type="submit"
          disabled={busy || !pin.trim()}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold text-xs transition-colors shrink-0 cursor-pointer"
        >
          {busy ? "확인 중..." : "인증"}
        </button>
      </form>

      {error && (
        <p className="text-[11px] text-rose-300 flex items-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}
