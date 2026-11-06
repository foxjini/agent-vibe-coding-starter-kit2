/**
 * 홈 (wakeup 7인치 화면)
 *   밤(평상시) — 가는 숫자의 큰 시계 · 다음 알람 · 침실 상태를 문장으로
 *   새벽(알람 중) — 해야 할 미션을 가장 크게, 오른쪽에 깨우는 순서(조명 → 커튼 → 모션 베드)
 */
"use client";

import { BedDouble, BellOff, Blinds, Check, Lightbulb } from "lucide-react";
import React from "react";

import type { AlarmSchedule } from "@/components/team/AlarmScheduleCard";
import WakeupMissionCard from "@/components/team/WakeupMissionCard";
import { Panel, TouchButton } from "@/components/team/wakeup/Tile";
import { dateText, hhmm, useClock } from "@/components/team/wakeup/useClock";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

/** 침대 압력 → 누워 있는지 (센서가 없으면 null) */
function lyingOf(w: WakeupApi): boolean | null {
  if (!w.hasSlot(WAKEUP_SLOTS.pressure) || w.pressure === null) return null;
  return w.pressure >= w.device.bedPressureThreshold;
}

function curtainOpen(w: WakeupApi): boolean | null {
  if (!w.hasSlot(WAKEUP_SLOTS.curtain) || w.curtainAngle === null) return null;
  return w.curtainAngle >= w.device.curtainOpenAngle - 5;
}

/** 저장된 알람이 오늘인지 내일인지 */
function dayOf(at: string, now: Date | null): string {
  if (!now) return "";
  const current = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return at > current ? "오늘" : "내일";
}

function Line({ icon, children, dim }: { icon: React.ReactNode; children: React.ReactNode; dim?: boolean }) {
  return (
    <li className={`flex min-h-11 items-center gap-3 text-lg ${dim ? "text-(--wk-dim)" : ""}`}>
      <span className="text-(--wk-dim)" aria-hidden="true">
        {icon}
      </span>
      {children}
    </li>
  );
}

/** 깨우는 순서 한 단계 — 끝났으면 체크 */
function Step({ done, label, detail }: { done: boolean; label: string; detail: string }) {
  return (
    <li className="flex min-h-14 items-center gap-3 border-b border-(--wk-line) last:border-0">
      <span
        aria-hidden="true"
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          done ? "bg-(--wk-ok) text-(--wk-on-accent)" : "border-2 border-(--wk-line-strong)"
        }`}
      >
        {done && <Check className="h-4 w-4" strokeWidth={3} />}
      </span>
      <span className="flex-1 text-lg font-medium">{label}</span>
      <span className="text-base text-(--wk-dim)">{detail}</span>
    </li>
  );
}

export default function HomeScreen({
  wakeup,
  schedule,
  alarmMode,
  onOpenSchedule,
}: {
  wakeup: WakeupApi;
  schedule: AlarmSchedule;
  alarmMode: boolean;
  onOpenSchedule: () => void;
}) {
  const now = useClock();
  const lying = lyingOf(wakeup);
  const open = curtainOpen(wakeup);
  const has = wakeup.hasSlot;

  if (alarmMode) {
    const bedDetail = !has(WAKEUP_SLOTS.bed)
      ? "부품 없음"
      : wakeup.bedShaking
        ? "흔드는 중"
        : lying === false
          ? "일어났어요"
          : "대기";
    return (
      <div className="grid h-full grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-4 px-5 pb-4 pt-1">
        <div className="min-h-0">
          <WakeupMissionCard
            mission={wakeup.mission}
            remainingSeconds={wakeup.remainingSeconds}
            config={wakeup.config}
            onSubmitPattern={wakeup.submitPattern}
          />
        </div>
        <div className="flex min-h-0 flex-col gap-3">
          <Panel className="px-4 py-1">
            <ol aria-label="깨우는 순서">
              <Step
                done={wakeup.lightOn}
                label="조명"
                detail={has(WAKEUP_SLOTS.light) ? (wakeup.lightOn ? "켜졌어요" : "켜는 중") : "부품 없음"}
              />
              <Step
                done={open === true}
                label="커튼"
                detail={open === null ? "부품 없음" : open ? "열렸어요" : "여는 중"}
              />
              <Step done={lying === false} label="모션 베드" detail={bedDetail} />
            </ol>
          </Panel>
          <TouchButton
            onClick={() => void wakeup.stopAlarm()}
            tone="accent"
            className="mt-auto min-h-16 text-xl"
          >
            <BellOff className="h-6 w-6" aria-hidden="true" />
            미션 없이 알람 끄기
          </TouchButton>
        </div>
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-6 px-8 pb-4">
      <div className="flex flex-col justify-center">
        <p className="wk-clock text-[136px] leading-[0.95] tracking-[-0.04em]">
          {hhmm(now)}
        </p>
        <p className="mt-3 pl-1 text-xl text-(--wk-dim)">{dateText(now)}</p>
      </div>

      <div className="flex flex-col justify-center gap-5">
        <button
          type="button"
          onClick={onOpenSchedule}
          className="wk-press -mx-3 rounded-[var(--wk-radius-control)] px-3 py-2 text-left active:bg-(--wk-press)"
        >
          {schedule.saved ? (
            <>
              <span className="block text-[44px] font-medium leading-tight text-(--wk-accent)">
                {schedule.saved.at}
              </span>
              <span className="block text-lg text-(--wk-dim)">
                {dayOf(schedule.saved.at, now)} 이 시각에 깨워요
              </span>
            </>
          ) : (
            <>
              <span className="block text-2xl font-medium">알람이 없어요</span>
              <span className="block text-lg text-(--wk-accent)">눌러서 시각 정하기</span>
            </>
          )}
        </button>

        <ul className="border-t border-(--wk-line) pt-3">
          <Line icon={<BedDouble className="h-5 w-5" />} dim={lying === null}>
            {lying === null ? "압력 센서 없음" : lying ? "침대에 누워 있어요" : "침대가 비어 있어요"}
          </Line>
          <Line icon={<Lightbulb className="h-5 w-5" />} dim={!has(WAKEUP_SLOTS.light)}>
            {!has(WAKEUP_SLOTS.light) ? "조명 없음" : wakeup.lightOn ? "조명 켜짐" : "조명 꺼짐"}
          </Line>
          <Line icon={<Blinds className="h-5 w-5" />} dim={open === null}>
            {open === null ? "커튼 없음" : open ? "커튼 열림" : "커튼 닫힘"}
          </Line>
        </ul>
      </div>
    </div>
  );
}
