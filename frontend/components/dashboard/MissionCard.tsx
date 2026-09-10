"use client";

import React from "react";
import { Hand, Repeat, Swords, Timer, Trophy } from "lucide-react";

export interface MissionState {
  active: boolean;
  mode?: string;
  round?: number;
  wins?: number;
  required_wins?: number;
  ai_hand?: string | null;
  expected_hand?: string | null;
  remaining_seconds?: number;
  lastResult?: string | null;
  lastResultMessage?: string | null;
}

const HAND_EMOJI: Record<string, string> = {
  rock: "✊",
  paper: "✋",
  scissors: "✌️",
};

const HAND_KO: Record<string, string> = {
  rock: "주먹(바위)",
  paper: "보",
  scissors: "가위",
};

const RESULT_STYLE: Record<string, string> = {
  win: "border-emerald-200 bg-emerald-50 text-emerald-800",
  lose: "border-rose-200 bg-rose-50 text-rose-800",
  draw: "border-amber-200 bg-amber-50 text-amber-800",
  timeout: "border-rose-200 bg-rose-50 text-rose-800",
  object: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

interface MissionCardProps {
  mission: MissionState;
}

export const MissionCard: React.FC<MissionCardProps> = ({ mission }) => {
  if (!mission.active) return null;

  const required = mission.required_wins ?? 2;
  const wins = mission.wins ?? 0;
  const aiHand = mission.ai_hand ?? null;
  const expected = mission.expected_hand ?? null;

  return (
    <div className="rounded-xl border-2 border-sky-300 bg-white p-5 shadow-sm ring-2 ring-sky-100">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-sky-50 text-sky-700 border border-sky-200">
            <Swords className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">
              기상 미션 진행 중 · {mission.round ?? 1}라운드
            </h3>
            <p className="text-xs text-slate-500">
              {mission.mode === "object"
                ? "카메라에 지정된 사물을 보여주세요."
                : "AI를 이기는 손동작을 카메라 앞에 내밀면 알람이 꺼집니다."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-700">
            <Trophy className="w-3.5 h-3.5 text-amber-500" />
            {wins} / {required}승
          </span>
          {typeof mission.remaining_seconds === "number" && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-mono font-semibold text-white">
              <Timer className="w-3.5 h-3.5" />
              {mission.remaining_seconds}초
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* AI가 낸 손 */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-center">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            AI가 낸 손
          </div>
          <div className="text-5xl leading-tight" aria-hidden>
            {aiHand ? HAND_EMOJI[aiHand] ?? "❔" : "❔"}
          </div>
          <div className="mt-1 text-sm font-bold text-slate-800">
            {aiHand ? HAND_KO[aiHand] ?? aiHand : "대기 중"}
          </div>
        </div>

        {/* 내가 내야 하는 손 */}
        <div className="rounded-lg border-2 border-sky-300 bg-sky-50/60 p-4 text-center">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-sky-600 mb-1">
            내가 내야 하는 손
          </div>
          <div className="text-5xl leading-tight animate-pulse" aria-hidden>
            {expected ? HAND_EMOJI[expected] ?? "❔" : "❔"}
          </div>
          <div className="mt-1 text-sm font-bold text-sky-900">
            {expected ? HAND_KO[expected] ?? expected : "대기 중"}
          </div>
        </div>
      </div>

      {/* 진행 게이지 */}
      <div className="mt-4 flex items-center gap-1.5">
        {Array.from({ length: required }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
              i < wins ? "bg-emerald-500" : "bg-slate-200"
            }`}
          />
        ))}
      </div>

      {mission.lastResultMessage && (
        <div
          className={`mt-3 rounded-lg border p-2.5 text-xs flex items-center gap-2 ${
            RESULT_STYLE[mission.lastResult ?? ""] ??
            "border-slate-200 bg-slate-50 text-slate-700"
          }`}
        >
          {mission.lastResult === "win" || mission.lastResult === "object" ? (
            <Hand className="w-3.5 h-3.5 shrink-0" />
          ) : (
            <Repeat className="w-3.5 h-3.5 shrink-0" />
          )}
          <span>{mission.lastResultMessage}</span>
        </div>
      )}
    </div>
  );
};

export default MissionCard;
