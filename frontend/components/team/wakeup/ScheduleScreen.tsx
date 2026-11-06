/**
 * 예약 (wakeup 7인치 화면)
 * 터치 화면에는 키보드가 없으므로 시각은 ▲▼ 버튼과 자주 쓰는 시각으로 고릅니다.
 * 예약은 자동화 규칙으로 저장돼, 화면을 꺼도 백엔드가 정해진 시각에 알람을 울립니다.
 */
"use client";

import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
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

function Wheel({
  label,
  value,
  onUp,
  onDown,
}: {
  label: string;
  value: string;
  onUp: () => void;
  onDown: () => void;
}) {
  return (
    <div className="flex flex-col items-center">
      <TouchButton onClick={onUp} tone="quiet" ariaLabel={`${label} 올리기`} className="h-14 w-28">
        <ChevronUp className="h-8 w-8" />
      </TouchButton>
      <span className="wk-clock text-[88px] leading-none tracking-[-0.03em]">{value}</span>
      <TouchButton onClick={onDown} tone="quiet" ariaLabel={`${label} 내리기`} className="h-14 w-28">
        <ChevronDown className="h-8 w-8" />
      </TouchButton>
    </div>
  );
}

export default function ScheduleScreen({ schedule }: { schedule: AlarmSchedule }) {
  const { time, setTime, saved, busy, error, save, remove } = schedule;
  const [hh, mm] = time.split(":");
  const unchanged = saved?.at === time;

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6 px-6 pb-4">
      <div className="flex items-center justify-center gap-2">
        <Wheel
          label="시"
          value={hh}
          onUp={() => setTime(shiftTime(time, 60))}
          onDown={() => setTime(shiftTime(time, -60))}
        />
        <span className="wk-clock pb-3 text-[72px] leading-none text-(--wk-dim)" aria-hidden="true">
          :
        </span>
        <Wheel
          label="분"
          value={mm}
          onUp={() => setTime(shiftTime(time, 5))}
          onDown={() => setTime(shiftTime(time, -5))}
        />
      </div>

      <div className="flex min-h-0 flex-col justify-center gap-4">
        <p className="text-lg text-(--wk-dim)">
          {saved ? (
            <>
              지금은 <span className="text-(--wk-text)">{saved.at}</span>에 울려요
            </>
          ) : (
            "아직 정한 알람이 없어요"
          )}
        </p>

        <div className="grid grid-cols-3 gap-2" role="group" aria-label="자주 쓰는 시각">
          {PRESETS.map((preset) => (
            <TouchButton
              key={preset}
              onClick={() => setTime(preset)}
              tone={preset === time ? "selected" : "plain"}
              ariaPressed={preset === time}
              className="px-2"
            >
              {preset}
            </TouchButton>
          ))}
        </div>

        <div className="flex gap-2">
          <TouchButton
            onClick={() => void save()}
            disabled={busy || unchanged}
            tone="accent"
            className="min-h-14 flex-1 text-lg"
          >
            {busy && <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" />}
            {unchanged ? `${time}에 맞춰 둠` : saved ? `${time}로 바꾸기` : `${time}에 맞추기`}
          </TouchButton>
          {saved && (
            <TouchButton onClick={() => void remove()} disabled={busy} className="min-h-14">
              예약 지우기
            </TouchButton>
          )}
        </div>
        {error && (
          <p role="alert" className="text-base text-(--wk-alert)">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
