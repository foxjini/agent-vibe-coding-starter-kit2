/**
 * 기상 미션 카드 (wakeup 팀 화면) — 키트 컴포넌트가 아니라 **팀 화면**입니다.
 * 다른 팀은 이 파일 대신 자기 시나리오 화면을 만들면 됩니다.
 */
"use client";

import { Grid3x3, Hand, Sparkles, Timer } from "lucide-react";
import React from "react";

import PatternPad from "@/components/team/PatternPad";
import { HAND_KO, patternTiming } from "@/scenarios/wakeupEngine";
import type { MissionConfig, MissionState, PatternFeedback } from "@/scenarios/wakeupEngine";

const RESULT_STYLES: Record<string, string> = {
  win: "border-emerald-200 bg-emerald-50 text-emerald-800",
  object: "border-emerald-200 bg-emerald-50 text-emerald-800",
  lose: "border-rose-200 bg-rose-50 text-rose-800",
  draw: "border-amber-200 bg-amber-50 text-amber-800",
  timeout: "border-amber-200 bg-amber-50 text-amber-800",
};

export default function WakeupMissionCard({
  mission,
  remainingSeconds,
  config,
  onSubmitPattern,
}: {
  mission: MissionState;
  remainingSeconds: number;
  /** 패턴 미션에서 보여 주는 속도·정답 남기기를 읽습니다 */
  config?: MissionConfig;
  /** 패턴 미션 — 그린 패턴을 판정에 넘깁니다 (useWakeup().submitPattern) */
  onSubmitPattern?: (drawn: number[]) => PatternFeedback;
}) {
  if (!mission.active) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
        <Sparkles className="mx-auto mb-2 h-6 w-6 text-slate-300" />
        <p className="text-sm text-slate-500">
          알람이 울리면 기상 미션이 시작됩니다.
        </p>
      </div>
    );
  }

  const aiHand = mission.aiHand;
  const expected = mission.expectedHand;
  // 패턴 미션이면 그리기 판에 넘길 것을 한데 모읍니다 (아니면 null → 가위바위보 화면)
  const patternView =
    mission.mode === "pattern" && mission.pattern && config && onSubmitPattern
      ? {
          pattern: mission.pattern,
          keepVisible: config.patternKeepVisible,
          onSubmit: onSubmitPattern,
          ...patternTiming(mission, config),
        }
      : null;

  return (
    <div className="rounded-xl border border-sky-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-sky-500">
            {patternView ? <Grid3x3 className="h-3.5 w-3.5" /> : <Hand className="h-3.5 w-3.5" />}
            기상 미션 · {mission.round}라운드
          </div>
          <h3 className="text-base font-medium text-slate-800">
            {patternView
              ? "보여 준 패턴을 똑같이 이어 그려야 알람이 꺼집니다"
              : "카메라 앞에서 이겨야 알람이 꺼집니다"}
          </h3>
        </div>
        <span className="flex shrink-0 items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
          <Timer className="h-3.5 w-3.5" />
          {remainingSeconds}초
        </span>
      </div>

      {patternView ? (
        <div className="mb-4">
          <PatternPad
            pattern={patternView.pattern}
            round={mission.round}
            showStartsAt={patternView.showStartsAt}
            inputOpensAt={patternView.inputOpensAt}
            stepMs={patternView.stepMs}
            keepVisible={patternView.keepVisible}
            onSubmit={patternView.onSubmit}
          />
        </div>
      ) : (
        <div className="mb-4 flex items-center justify-center gap-6 rounded-lg bg-slate-50 py-5">
          <div className="text-center">
            <div className="text-xs text-slate-400">AI가 낸 손</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">
              {aiHand ? HAND_KO[aiHand] : "—"}
            </div>
          </div>
          <div className="text-2xl text-slate-300">vs</div>
          <div className="text-center">
            <div className="text-xs text-slate-400">내야 하는 손</div>
            <div className="mt-1 text-2xl font-semibold text-sky-700">
              {expected ? HAND_KO[expected] : "—"}
            </div>
          </div>
        </div>
      )}

      <div className="mb-3 flex items-center gap-2">
        <span className="text-sm text-slate-600">{patternView ? "성공" : "승리"}</span>
        <div className="flex gap-1">
          {Array.from({ length: mission.requiredWins }, (_, i) => (
            <span
              key={i}
              className={`h-2.5 w-8 rounded-full ${
                i < mission.wins ? "bg-emerald-500" : "bg-slate-200"
              }`}
            />
          ))}
        </div>
        <span className="text-sm tabular-nums text-slate-500">
          {mission.wins} / {mission.requiredWins}
        </span>
      </div>

      {mission.lastResult && mission.lastResultMessage && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            RESULT_STYLES[mission.lastResult] ?? "border-slate-200 bg-slate-50 text-slate-700"
          }`}
        >
          {mission.lastResultMessage}
        </div>
      )}
    </div>
  );
}
