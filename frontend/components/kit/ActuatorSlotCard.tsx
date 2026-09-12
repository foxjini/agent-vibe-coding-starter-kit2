/**
 * 액추에이터 슬롯 카드 (키트 제공) — `control_type`만 보고 위젯을 자동으로 고릅니다.
 * =============================================================================
 * 팀이 부저를 서보로 바꿔도 이 파일은 고치지 않습니다 (docs/부록F 3-1절, 9-1절).
 *
 *   onoff  토글            pulse  토글 + 점멸 주기
 *   tonal  토글 + 주파수·볼륨   pwm    세기 슬라이더
 *   servo  각도 슬라이더        rgb    색상 선택
 *   level  단계 버튼
 *
 * 상태는 desired(내린 명령)와 current(하드웨어가 보고한 결과)를 **따로** 보여 줍니다.
 * 합쳐서 보여 주면 "껐는데 계속 울리는" 상황을 화면에서 알 수 없습니다 (부록A 계약).
 */
"use client";

import { Loader2 } from "lucide-react";
import React, { useState } from "react";

import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import SlotIcon from "@/components/kit/SlotIcon";
import {
  ControlType,
  Slot,
  controlTypeOf,
  isOnState,
  numberFrom,
  onStateFor,
  slotLabel,
  slotStatus,
  valueRange,
} from "@/lib/slots";

export interface ActuatorSlotCardProps {
  slot: Slot;
  onControl: (
    slotId: string,
    state: string,
    value?: Record<string, unknown> | null
  ) => Promise<boolean> | void;
  disabled?: boolean;
}

const RANGE_DEFAULTS: Record<ControlType, { min: number; max: number; step: number }> = {
  onoff: { min: 0, max: 1, step: 1 },
  pulse: { min: 0, max: 1, step: 1 },
  tonal: { min: 50, max: 4000, step: 10 },
  pwm: { min: 0, max: 100, step: 5 },
  servo: { min: 0, max: 180, step: 5 },
  rgb: { min: 0, max: 255, step: 1 },
  level: { min: 0, max: 3, step: 1 },
};

/** 현재 화면에 표시할 값 — 사용자가 조작 중이면 그 값, 아니면 서버 값. */
function useControlValue(slot: Slot, key: string[], fallback: number) {
  const [local, setLocal] = useState<number | null>(null);
  const server = numberFrom(slot.desired_value ?? slot.current_value, key, fallback);
  return [local ?? server, setLocal] as const;
}

export default function ActuatorSlotCard({
  slot,
  onControl,
  disabled = false,
}: ActuatorSlotCardProps) {
  const controlType = controlTypeOf(slot);
  const status = slotStatus(slot);
  const onState = onStateFor(controlType);
  const commanded = isOnState(slot.desired_state);
  const [busy, setBusy] = useState(false);

  const range = valueRange(slot, RANGE_DEFAULTS[controlType]);
  const [frequency, setFrequency] = useControlValue(slot, ["frequency"], 1000);
  const [volume, setVolume] = useControlValue(slot, ["volume"], 80);
  const [duty, setDuty] = useControlValue(slot, ["duty", "level"], 100);
  const [angle, setAngle] = useControlValue(slot, ["angle"], range.max);
  const [onTime, setOnTime] = useControlValue(slot, ["on_time"], 0.4);
  const [level, setLevel] = useControlValue(slot, ["level"], range.max);
  const [color, setColor] = useState<string | null>(null);

  const currentColor =
    color ??
    (() => {
      const r = numberFrom(slot.desired_value, ["r"], 255);
      const g = numberFrom(slot.desired_value, ["g"], 255);
      const b = numberFrom(slot.desired_value, ["b"], 255);
      const hex = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
      return `#${hex(r)}${hex(g)}${hex(b)}`;
    })();

  /** control_type에 맞는 value 객체를 만듭니다 (부록F 3-1절 표). */
  const buildValue = (): Record<string, unknown> | null => {
    switch (controlType) {
      case "tonal":
        return { frequency: Math.round(frequency), volume: Math.round(volume) };
      case "pwm":
        return { duty: Math.round(duty) };
      case "servo":
        return { angle: Math.round(angle) };
      case "pulse":
        return { on_time: onTime, off_time: onTime };
      case "level":
        return { level: Math.round(level) };
      case "rgb": {
        const hex = currentColor.replace("#", "");
        return {
          r: parseInt(hex.slice(0, 2), 16) || 0,
          g: parseInt(hex.slice(2, 4), 16) || 0,
          b: parseInt(hex.slice(4, 6), 16) || 0,
        };
      }
      default:
        return null;
    }
  };

  const send = async (state: string) => {
    setBusy(true);
    try {
      await onControl(slot.slot_id, state, state === "off" ? null : buildValue());
    } finally {
      setBusy(false);
    }
  };

  const controlsDisabled = disabled || busy;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:border-slate-300">
      {/* 머리말 */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <SlotIcon slot={slot} className="h-3.5 w-3.5 text-slate-500" />
            액추에이터 · {controlType}
          </div>
          <h3 className="truncate text-base font-medium text-slate-800">
            {slotLabel(slot)}
          </h3>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(
            status.tone
          )}`}
        >
          {status.label}
        </span>
      </div>

      {/* 상태 계약: 명령과 실제 반영을 따로 */}
      <div className="mb-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <div className="text-xs text-slate-400">내린 명령</div>
          <div className="font-medium text-slate-700">{slot.desired_state ?? "—"}</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <div className="text-xs text-slate-400">하드웨어 보고</div>
          <div className="font-medium text-slate-700">
            {status.reported ? slot.current_state : "보고 없음"}
          </div>
        </div>
      </div>

      {/* control_type별 조절 위젯 */}
      <div className="space-y-3">
        {controlType === "tonal" && (
          <>
            <SliderRow
              label="주파수"
              unit="Hz"
              value={frequency}
              min={range.min}
              max={range.max}
              step={range.step}
              disabled={controlsDisabled}
              onChange={setFrequency}
            />
            <SliderRow
              label="볼륨"
              unit="%"
              value={volume}
              min={0}
              max={100}
              step={5}
              disabled={controlsDisabled}
              onChange={setVolume}
            />
          </>
        )}

        {controlType === "pwm" && (
          <SliderRow
            label="세기"
            unit="%"
            value={duty}
            min={range.min}
            max={range.max}
            step={range.step}
            disabled={controlsDisabled}
            onChange={setDuty}
          />
        )}

        {controlType === "servo" && (
          <SliderRow
            label="각도"
            unit="도"
            value={angle}
            min={range.min}
            max={range.max}
            step={range.step}
            disabled={controlsDisabled}
            onChange={setAngle}
          />
        )}

        {controlType === "pulse" && (
          <SliderRow
            label="점멸 주기"
            unit="초"
            value={onTime}
            min={0.1}
            max={2}
            step={0.1}
            disabled={controlsDisabled}
            onChange={setOnTime}
          />
        )}

        {controlType === "level" && (
          <div>
            <div className="mb-1.5 text-sm text-slate-600">단계</div>
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: range.max - range.min + 1 }, (_, i) => range.min + i).map(
                (step) => (
                  <button
                    key={step}
                    type="button"
                    disabled={controlsDisabled}
                    onClick={() => setLevel(step)}
                    className={`h-10 min-w-10 rounded-lg border px-3 text-sm font-medium transition-colors disabled:opacity-50 ${
                      Math.round(level) === step
                        ? "border-sky-300 bg-sky-50 text-sky-700"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                    }`}
                  >
                    {step}
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {controlType === "rgb" && (
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-600" htmlFor={`${slot.slot_id}-color`}>
              색상
            </label>
            <input
              id={`${slot.slot_id}-color`}
              type="color"
              value={currentColor}
              disabled={controlsDisabled}
              onChange={(e) => setColor(e.target.value)}
              className="h-10 w-16 cursor-pointer rounded-lg border border-slate-200 disabled:opacity-50"
            />
            <span className="font-mono text-sm text-slate-500">{currentColor}</span>
          </div>
        )}
      </div>

      {/* 켜기 / 끄기 */}
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          disabled={controlsDisabled}
          onClick={() => void send(onState)}
          className={`flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50 ${
            commanded
              ? "border-emerald-300 bg-emerald-50 text-emerald-700"
              : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
          }`}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {controlType === "servo" ? "이동" : "켜기"}
        </button>
        <button
          type="button"
          disabled={controlsDisabled}
          onClick={() => void send("off")}
          className={`h-11 flex-1 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50 ${
            !commanded
              ? "border-slate-300 bg-slate-100 text-slate-700"
              : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
          }`}
        >
          끄기
        </button>
      </div>

      <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
        <span className="font-mono">{slot.slot_id}</span>
        {status.pending && (
          <span className="ml-2 text-amber-600">
            하드웨어가 아직 반영하지 않았습니다
          </span>
        )}
      </div>
    </div>
  );
}

function SliderRow({
  label,
  unit,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  unit: string;
  value: number;
  min: number;
  max: number;
  step: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium tabular-nums text-slate-800">
          {step < 1 ? value.toFixed(1) : Math.round(value)}
          <span className="ml-0.5 text-slate-400">{unit}</span>
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-sky-600 disabled:opacity-50"
      />
    </div>
  );
}
