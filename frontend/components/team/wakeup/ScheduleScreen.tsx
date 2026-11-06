/**
 * 예약 화면 (wakeup 7인치 화면)
 * 터치 화면에는 키보드가 없으므로 시각은 ± 버튼과 자주 쓰는 시각으로 고릅니다.
 * 예약은 자동화 규칙으로 저장돼, 화면을 꺼도 백엔드가 정해진 시각에 알람을 울립니다.
 */
"use client";

import { Loader2, Minus, Plus, Trash2 } from "lucide-react";
import React from "react";

import type { AlarmSchedule } from "@/components/team/AlarmScheduleCard";
import { TouchButton } from "@/components/team/wakeup/Tile";

const PRESETS = ["06:00", "06:30", "07:00", "07:30", "08:00"];

/** "HH:MM"을 분으로 → 더하고 → 다시 "HH:MM" (하루를 넘으면 돌아갑니다) */
export function shiftTime(time: string, minutes: number): string {
  const [h, m] = time.split(":").map((part) => Number(part) || 0);
  const total = (((h * 60 + m + minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function Stepper({
  label,
  value,
  onMinus,
  onPlus,
}: {
  label: string;
  value: string;
  onMinus: () => void;
  onPlus: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <TouchButton onClick={onPlus} ariaLabel={`${label} 올리기`} className="w-24">
        <Plus className="h-6 w-6" />
      </TouchButton>
      <div className="text-[72px] font-semibold leading-none tabular-nums text-slate-900">{value}</div>
      <TouchButton onClick={onMinus} ariaLabel={`${label} 내리기`} className="w-24">
        <Minus className="h-6 w-6" />
      </TouchButton>
    </div>
  );
}

export default function ScheduleScreen({ schedule }: { schedule: AlarmSchedule }) {
  const { time, setTime, saved, busy, error, save, remove } = schedule;
  const [hh, mm] = time.split(":");

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-3 p-3">
      <div className="flex items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white shadow-sm">
        <Stepper
          label="시"
          value={hh}
          onPlus={() => setTime(shiftTime(time, 60))}
          onMinus={() => setTime(shiftTime(time, -60))}
        />
        <div className="pb-2 text-[64px] font-semibold text-slate-300">:</div>
        <Stepper
          label="분"
          value={mm}
          onPlus={() => setTime(shiftTime(time, 5))}
          onMinus={() => setTime(shiftTime(time, -5))}
        />
      </div>

      <div className="flex min-h-0 flex-col gap-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="text-sm font-medium text-slate-500">지금 예약</div>
          {saved ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-4xl font-semibold tabular-nums text-slate-900">{saved.at}</span>
              <TouchButton onClick={() => void remove()} disabled={busy} ariaLabel="알람 예약 취소">
                <Trash2 className="h-5 w-5" />
                취소
              </TouchButton>
            </div>
          ) : (
            <div className="py-2 text-lg text-slate-600">예약된 알람이 없습니다</div>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2">
          {PRESETS.map((preset) => (
            <TouchButton
              key={preset}
              onClick={() => setTime(preset)}
              tone={preset === time ? "soft" : "plain"}
            >
              <span className="tabular-nums">{preset}</span>
            </TouchButton>
          ))}
        </div>

        <TouchButton
          onClick={() => void save()}
          disabled={busy}
          tone="primary"
          className="mt-auto min-h-14 text-lg"
        >
          {busy && <Loader2 className="h-5 w-5 animate-spin" />}
          {saved ? `${time}로 변경` : `${time}에 예약`}
        </TouchButton>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </div>
    </div>
  );
}
