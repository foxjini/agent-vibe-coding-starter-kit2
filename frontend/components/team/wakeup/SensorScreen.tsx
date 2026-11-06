/**
 * 센서 화면 (wakeup 7인치 화면) — 타일 격자
 * 침대 압력은 막대와 기준선으로, 그 밖의 센서는 키트가 주는 표시 그대로 보여 줍니다.
 */
"use client";

import { Activity, BedDouble, Hand } from "lucide-react";
import React from "react";

import { MissingSlot, Pill, Tile } from "@/components/team/wakeup/Tile";
import { asObject, sensorText, slotLabel } from "@/lib/slots";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

function PressureTile({ wakeup }: { wakeup: WakeupApi }) {
  const slot = wakeup.scenario.slotOf(WAKEUP_SLOTS.pressure);
  const threshold = wakeup.device.bedPressureThreshold;
  if (!slot) {
    return (
      <Tile icon={<BedDouble className="h-5 w-5" />} title="침대 압력" muted>
        <MissingSlot slotId={WAKEUP_SLOTS.pressure} />
      </Tile>
    );
  }
  const value = wakeup.pressure;
  const scale = Math.max(100, threshold * 1.5, value ?? 0);
  const lying = value !== null && value >= threshold;
  return (
    <Tile
      icon={<BedDouble className="h-5 w-5" />}
      title={slotLabel(slot)}
      badge={<Pill on={!lying}>{value === null ? "측정 전" : lying ? "누워 있음" : "비어 있음"}</Pill>}
    >
      <div className="flex items-baseline gap-1">
        <span className="text-6xl font-semibold tabular-nums text-slate-900">
          {value === null ? "—" : Math.round(value)}
        </span>
        <span className="text-lg text-slate-500">{slot.unit ?? ""}</span>
      </div>
      <div className="relative mt-3 h-4 rounded-full bg-slate-100">
        <div
          className={`h-4 rounded-full ${lying ? "bg-amber-400" : "bg-emerald-400"}`}
          style={{ width: `${Math.min(100, ((value ?? 0) / scale) * 100)}%` }}
        />
        <div
          className="absolute -top-1 h-6 w-1 rounded bg-rose-500"
          style={{ left: `${Math.min(100, (threshold / scale) * 100)}%` }}
          aria-hidden="true"
        />
      </div>
      <p className="mt-2 text-sm text-slate-500">
        빨간 선(기준 {threshold}) 이상이면 미션 중 모션 베드가 흔들립니다
      </p>
    </Tile>
  );
}

function ButtonTile({ wakeup }: { wakeup: WakeupApi }) {
  const slot = wakeup.scenario.slotOf(WAKEUP_SLOTS.button);
  if (!slot) {
    return (
      <Tile icon={<Hand className="h-5 w-5" />} title="기상 확인 버튼" muted>
        <MissingSlot slotId={WAKEUP_SLOTS.button} />
      </Tile>
    );
  }
  const pressed = Boolean(asObject(slot.current_value)?.pressed);
  return (
    <Tile
      icon={<Hand className="h-5 w-5" />}
      title={slotLabel(slot)}
      badge={<Pill on={pressed}>{pressed ? "눌림" : "대기"}</Pill>}
    >
      <div className="text-5xl font-semibold text-slate-900">{pressed ? "눌림" : "대기"}</div>
      <p className="mt-2 text-sm text-slate-500">기상 확인 팝업이 떴을 때 누르면 확인됩니다</p>
    </Tile>
  );
}

export default function SensorScreen({ wakeup }: { wakeup: WakeupApi }) {
  const known: string[] = [WAKEUP_SLOTS.pressure, WAKEUP_SLOTS.button];
  // 배치표에 다른 센서가 더 있으면 키트 표시 그대로 덧붙입니다
  const others = wakeup.scenario.slots.filter(
    (slot) => slot.role !== "actuator" && !known.includes(slot.slot_id)
  );
  return (
    <div className="grid h-full auto-rows-min grid-cols-2 gap-3 overflow-y-auto p-3">
      <PressureTile wakeup={wakeup} />
      <ButtonTile wakeup={wakeup} />
      {others.map((slot) => {
        const reading = sensorText(slot);
        return (
          <Tile key={slot.slot_id} icon={<Activity className="h-5 w-5" />} title={slotLabel(slot)}>
            <div className="flex items-baseline gap-1">
              <span className="text-5xl font-semibold tabular-nums text-slate-900">{reading.value}</span>
              <span className="text-lg text-slate-500">{reading.unit}</span>
            </div>
            {reading.hint && <p className="mt-1 text-sm text-slate-500">{reading.hint}</p>}
          </Tile>
        );
      })}
    </div>
  );
}
