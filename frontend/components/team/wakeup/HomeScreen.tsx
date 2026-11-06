/**
 * 홈 화면 (wakeup 7인치 화면)
 *   평상시 — 큰 시계 · 다음 예약 알람 · 침실 상태(침대 · 조명 · 커튼)
 *   알람 중 — 기상 미션 · 수행 상태 · 알람 끄기
 */
"use client";

import {
  AlarmClock,
  BedDouble,
  BellOff,
  Blinds,
  ChevronRight,
  CircleCheck,
  Circle,
  Lightbulb,
} from "lucide-react";
import React from "react";

import type { AlarmSchedule } from "@/components/team/AlarmScheduleCard";
import WakeupMissionCard from "@/components/team/WakeupMissionCard";
import { dateText, hhmm, useClock } from "@/components/team/wakeup/useClock";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

/** 침대에 누워 있는지 — 압력 센서가 없으면 null */
function bedText(w: WakeupApi): { lying: boolean | null; text: string } {
  if (!w.hasSlot(WAKEUP_SLOTS.pressure) || w.pressure === null) {
    return { lying: null, text: "압력 센서 없음" };
  }
  const lying = w.pressure >= w.device.bedPressureThreshold;
  return { lying, text: `${lying ? "누워 있음" : "비어 있음"} · ${Math.round(w.pressure)}` };
}

function curtainText(w: WakeupApi): string {
  if (!w.hasSlot(WAKEUP_SLOTS.curtain)) return "커튼 없음";
  if (w.curtainAngle === null) return "확인 중";
  return w.curtainAngle >= w.device.curtainOpenAngle - 5 ? `열림 · ${w.curtainAngle}°` : `닫힘 · ${w.curtainAngle}°`;
}

function StatusRow({
  icon,
  label,
  value,
  done,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  /** true면 초록 체크 */
  done?: boolean;
}) {
  return (
    <div className="flex min-h-12 items-center gap-3 border-b border-slate-100 last:border-0">
      <span className="text-slate-500">{icon}</span>
      <span className="flex-1 text-base text-slate-700">{label}</span>
      <span className={`text-base font-semibold ${done ? "text-emerald-700" : "text-slate-600"}`}>
        {value}
      </span>
      {done === undefined ? null : done ? (
        <CircleCheck className="h-5 w-5 text-emerald-600" />
      ) : (
        <Circle className="h-5 w-5 text-slate-300" />
      )}
    </div>
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
  const bed = bedText(wakeup);

  if (alarmMode) {
    const lyingNow = bed.lying === true;
    return (
      <div className="grid h-full grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-3 p-3">
        <div className="min-h-0 overflow-y-auto">
          <WakeupMissionCard
            mission={wakeup.mission}
            remainingSeconds={wakeup.remainingSeconds}
            config={wakeup.config}
            onSubmitPattern={wakeup.submitPattern}
            compact
          />
        </div>
        <div className="flex min-h-0 flex-col gap-3">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-1 shadow-sm">
            <StatusRow
              icon={<Lightbulb className="h-5 w-5" />}
              label="조명"
              value={wakeup.hasSlot(WAKEUP_SLOTS.light) ? (wakeup.lightOn ? "켜짐" : "꺼짐") : "없음"}
              done={wakeup.lightOn}
            />
            <StatusRow
              icon={<Blinds className="h-5 w-5" />}
              label="커튼"
              value={curtainText(wakeup)}
              done={
                wakeup.curtainAngle !== null &&
                wakeup.curtainAngle >= wakeup.device.curtainOpenAngle - 5
              }
            />
            <StatusRow
              icon={<BedDouble className="h-5 w-5" />}
              label="모션 베드"
              value={
                wakeup.bedShaking ? "흔드는 중" : lyingNow ? "대기" : bed.lying === false ? "멈춤" : "—"
              }
            />
            <StatusRow
              icon={<BedDouble className="h-5 w-5" />}
              label="침대"
              value={bed.text}
              done={bed.lying === false}
            />
          </div>
          <button
            type="button"
            onClick={() => void wakeup.stopAlarm()}
            className="mt-auto flex min-h-14 items-center justify-center gap-2 rounded-2xl bg-rose-600 text-lg font-semibold text-white active:bg-rose-700"
          >
            <BellOff className="h-6 w-6" />
            알람 끄기
          </button>
          <p className="text-center text-xs text-slate-500">
            미션을 건너뛰고 끄는 버튼입니다. 정상 기상은 미션을 완수해서 꺼 주세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-3 p-3">
      <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="text-[96px] font-semibold leading-none tabular-nums text-slate-900">
          {hhmm(now)}
        </div>
        <div className="mt-3 text-xl text-slate-500">{dateText(now)}</div>
      </div>
      <div className="flex min-h-0 flex-col gap-3">
        <button
          type="button"
          onClick={onOpenSchedule}
          className="flex min-h-[96px] items-center gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-4 text-left active:bg-sky-100"
        >
          <AlarmClock className="h-8 w-8 shrink-0 text-sky-600" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-sky-700">다음 알람</span>
            {schedule.saved ? (
              <span className="block text-4xl font-semibold tabular-nums text-slate-900">
                {schedule.saved.at}
              </span>
            ) : (
              <span className="block text-lg text-slate-600">예약 없음 · 눌러서 예약</span>
            )}
          </span>
          <ChevronRight className="h-6 w-6 text-sky-500" />
        </button>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-1 shadow-sm">
          <StatusRow icon={<BedDouble className="h-5 w-5" />} label="침대" value={bed.text} />
          <StatusRow
            icon={<Lightbulb className="h-5 w-5" />}
            label="조명"
            value={wakeup.hasSlot(WAKEUP_SLOTS.light) ? (wakeup.lightOn ? "켜짐" : "꺼짐") : "없음"}
          />
          <StatusRow icon={<Blinds className="h-5 w-5" />} label="커튼" value={curtainText(wakeup)} />
        </div>
      </div>
    </div>
  );
}
