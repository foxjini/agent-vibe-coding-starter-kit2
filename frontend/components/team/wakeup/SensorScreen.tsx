/**
 * 센서 (wakeup 7인치 화면)
 * 침대 압력은 기준선이 있는 가로 막대로, 버튼은 상태 글자로 보여 줍니다.
 * 배치표에 다른 센서가 더 있으면 키트가 주는 표시(sensorText) 그대로 덧붙입니다.
 */
"use client";

import React from "react";

import { MissingSlot, Panel, State } from "@/components/team/wakeup/Tile";
import { asObject, sensorText, slotLabel } from "@/lib/slots";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

function Pressure({ wakeup }: { wakeup: WakeupApi }) {
  const slot = wakeup.scenario.slotOf(WAKEUP_SLOTS.pressure);
  const threshold = wakeup.device.bedPressureThreshold;
  if (!slot) {
    return (
      <Panel className="col-span-2 p-5">
        <h2 className="mb-1 text-lg font-medium">침대 압력</h2>
        <MissingSlot slotId={WAKEUP_SLOTS.pressure} />
      </Panel>
    );
  }
  const value = wakeup.pressure;
  const scale = Math.max(100, threshold * 1.5, value ?? 0);
  const lying = value !== null && value >= threshold;
  const pct = (n: number) => `${Math.min(100, (n / scale) * 100)}%`;
  return (
    <Panel className="col-span-2 p-5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-medium">{slotLabel(slot)}</h2>
        <State on={lying}>{value === null ? "측정 전" : lying ? "누워 있어요" : "비어 있어요"}</State>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="wk-clock text-[64px] leading-none">{value === null ? "—" : Math.round(value)}</span>
        <span className="text-xl text-(--wk-dim)">{slot.unit ?? ""}</span>
      </div>
      <div className="relative mt-4 h-3 rounded-full bg-(--wk-sunken)" aria-hidden="true">
        <div className="h-3 rounded-full bg-(--wk-accent)" style={{ width: pct(value ?? 0) }} />
        <div className="absolute -top-2 h-7 w-0.5 bg-(--wk-text)" style={{ left: pct(threshold) }} />
      </div>
      <p className="mt-3 text-base text-(--wk-dim)">
        세로선({threshold})을 넘으면 누워 있는 것으로 봅니다. 미션 중에 넘으면 모션 베드가 흔들려요.
      </p>
    </Panel>
  );
}

function ConfirmButton({ wakeup }: { wakeup: WakeupApi }) {
  const slot = wakeup.scenario.slotOf(WAKEUP_SLOTS.button);
  if (!slot) {
    return (
      <Panel className="p-5">
        <h2 className="mb-1 text-lg font-medium">기상 확인 버튼</h2>
        <MissingSlot slotId={WAKEUP_SLOTS.button} />
      </Panel>
    );
  }
  const pressed = Boolean(asObject(slot.current_value)?.pressed);
  return (
    <Panel className="p-5">
      <h2 className="text-lg font-medium">{slotLabel(slot)}</h2>
      <p className="mt-2">
        <State on={pressed}>{pressed ? "눌렀어요" : "누르지 않음"}</State>
      </p>
      <p className="mt-2 text-base text-(--wk-dim)">기상 확인 창이 떴을 때 누르면 확인돼요</p>
    </Panel>
  );
}

export default function SensorScreen({ wakeup }: { wakeup: WakeupApi }) {
  const known: string[] = [WAKEUP_SLOTS.pressure, WAKEUP_SLOTS.button];
  const others = wakeup.scenario.slots.filter(
    (slot) => slot.role !== "actuator" && !known.includes(slot.slot_id)
  );
  return (
    <div className="grid h-full auto-rows-min grid-cols-2 gap-3 overflow-y-auto px-5 pb-4">
      <Pressure wakeup={wakeup} />
      <ConfirmButton wakeup={wakeup} />
      {others.map((slot) => {
        const reading = sensorText(slot);
        return (
          <Panel key={slot.slot_id} className="p-5">
            <h2 className="text-lg font-medium">{slotLabel(slot)}</h2>
            <p className="mt-1 flex items-baseline gap-1">
              <span className="text-4xl font-medium">{reading.value}</span>
              <span className="text-lg text-(--wk-dim)">{reading.unit}</span>
            </p>
            {reading.hint && <p className="mt-1 text-base text-(--wk-dim)">{reading.hint}</p>}
          </Panel>
        );
      })}
    </div>
  );
}
