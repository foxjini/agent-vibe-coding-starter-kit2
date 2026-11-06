/**
 * 기상 미션 (wakeup 팀 화면) — 키트 컴포넌트가 아니라 **팀 화면**입니다.
 * 새벽빛 디자인(app/wakeup/wakeup.css)의 의미 변수를 씁니다. 해야 할 일을 가장 크게 보여 줍니다.
 * 판정은 scenarios/wakeupEngine.ts가 하고, 이 파일은 보여 주기만 합니다.
 */
"use client";

import React from "react";

import PatternPad from "@/components/team/PatternPad";
import { patternTiming } from "@/scenarios/wakeupEngine";
import type { Hand, MissionConfig, MissionState, PatternFeedback } from "@/scenarios/wakeupEngine";

/** 손 이름 + 받침에 맞는 조사 (주먹을 · 보를 · 가위를) */
const HAND_OBJ: Record<Hand, string> = { rock: "주먹을", paper: "보를", scissors: "가위를" };

const OBJECT_KO: Record<string, string> = {
  person: "사람",
  bottle: "물병",
  cup: "컵",
  book: "책",
  "cell phone": "휴대폰",
};

const RESULT_TONE: Record<string, string> = {
  win: "text-(--wk-ok)",
  object: "text-(--wk-ok)",
  lose: "text-(--wk-alert)",
  draw: "text-(--wk-dim)",
  timeout: "text-(--wk-alert)",
};

export default function WakeupMissionCard({
  mission,
  remainingSeconds,
  config,
  onSubmitPattern,
}: {
  mission: MissionState;
  remainingSeconds: number;
  /** 패턴 미션의 속도·정답 남기기, 사물 목록을 읽습니다 */
  config?: MissionConfig;
  /** 패턴 미션 — 그린 패턴을 판정에 넘깁니다 (useWakeup().submitPattern) */
  onSubmitPattern?: (drawn: number[]) => PatternFeedback;
  /** 예전 화면과 호환용 (지금은 7인치 크기 하나뿐) */
  compact?: boolean;
}) {
  if (!mission.active) {
    return <p className="text-base text-(--wk-dim)">알람이 울리면 기상 미션이 시작됩니다.</p>;
  }

  const patternView =
    mission.mode === "pattern" && mission.pattern && config && onSubmitPattern
      ? {
          pattern: mission.pattern,
          keepVisible: config.patternKeepVisible,
          onSubmit: onSubmitPattern,
          ...patternTiming(mission, config),
        }
      : null;

  // 예로 들 물건 두 개 (사람은 빼고)
  const objects = (config?.objectTargets ?? [])
    .filter((name) => name !== "person")
    .slice(0, 2)
    .map((name) => OBJECT_KO[name] ?? name);
  const acceptsObjects = mission.mode === "auto" || mission.mode === "object";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline justify-between gap-3 text-base text-(--wk-dim)">
        <span>
          {patternView ? "패턴 그리기" : mission.aiHand ? "가위바위보" : "물건 보여 주기"} {mission.round}라운드
        </span>
        <span aria-label={`남은 시간 ${remainingSeconds}초`} className="font-medium">
          {remainingSeconds}초
        </span>
      </div>

      {patternView ? (
        <div className="mx-auto my-2 w-full max-w-[210px]">
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
        <div className="flex flex-1 flex-col justify-center py-2">
          {mission.aiHand && mission.expectedHand ? (
            <>
              <p className="text-xl text-(--wk-dim)">AI는 {HAND_OBJ[mission.aiHand]} 냈어요</p>
              <p className="mt-1 text-[56px] font-semibold leading-tight tracking-tight">
                {HAND_OBJ[mission.expectedHand]} 내세요
              </p>
            </>
          ) : (
            <p className="text-[44px] font-semibold leading-tight">물건을 카메라에 보여 주세요</p>
          )}
          {acceptsObjects && objects.length > 0 && (
            <p className="mt-3 text-base text-(--wk-dim)">
              {mission.aiHand ? "또는 " : ""}
              {objects.join(", ")} 같은 물건을 보여 줘도 돼요
            </p>
          )}
        </div>
      )}

      <div className="flex items-center gap-3">
        <div className="flex gap-1.5" aria-hidden="true">
          {Array.from({ length: mission.requiredWins }, (_, i) => (
            <span
              key={i}
              className={`h-3 w-10 rounded-full ${i < mission.wins ? "bg-(--wk-ok)" : "bg-(--wk-line-strong)"}`}
            />
          ))}
        </div>
        <span className="text-base text-(--wk-dim)">
          {mission.requiredWins}번 중 {mission.wins}번 성공
        </span>
      </div>

      {mission.lastResult && mission.lastResultMessage && (
        <p
          role="status"
          className={`mt-2 truncate text-base font-medium ${RESULT_TONE[mission.lastResult] ?? "text-(--wk-dim)"}`}
        >
          {mission.lastResultMessage}
        </p>
      )}
    </div>
  );
}
