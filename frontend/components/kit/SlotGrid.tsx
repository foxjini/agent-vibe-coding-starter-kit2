/**
 * 슬롯 그리드 (키트 제공) — 켜져 있는 슬롯을 자동으로 배치합니다.
 * 부품을 추가하면 카드가 생기고, 빼면 사라집니다. 코드는 그대로입니다.
 */
"use client";

import { Cpu } from "lucide-react";
import React from "react";

import ActuatorSlotCard from "@/components/kit/ActuatorSlotCard";
import SensorSlotCard from "@/components/kit/SensorSlotCard";
import { Slot, sortSlots } from "@/lib/slots";

export interface SlotGridProps {
  slots: Slot[];
  onControl: (
    slotId: string,
    state: string,
    value?: Record<string, unknown> | null
  ) => Promise<boolean> | void;
  /** 비어 있을 때 보여 줄 안내 */
  emptyHint?: React.ReactNode;
  disabled?: boolean;
}

export default function SlotGrid({
  slots,
  onControl,
  emptyHint,
  disabled = false,
}: SlotGridProps) {
  const ordered = sortSlots(slots);
  const sensors = ordered.filter((s) => s.role !== "actuator");
  const actuators = ordered.filter((s) => s.role === "actuator");

  if (ordered.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
        <Cpu className="mx-auto mb-3 h-8 w-8 text-slate-300" />
        <p className="font-medium text-slate-600">사용 중인 슬롯이 없습니다.</p>
        <div className="mt-2 text-sm text-slate-500">
          {emptyHint ?? (
            <>
              라즈베리파이에서 <code className="rounded bg-white px-1 py-0.5">daemon.py</code>를
              실행하거나, 아래 &apos;하드웨어 구성&apos;에서 슬롯을 켜 주세요.
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {actuators.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
            액추에이터 ({actuators.length})
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {actuators.map((slot) => (
              <ActuatorSlotCard
                key={slot.slot_id}
                slot={slot}
                onControl={onControl}
                disabled={disabled}
              />
            ))}
          </div>
        </section>
      )}

      {sensors.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
            센서 ({sensors.length})
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {sensors.map((slot) => (
              <SensorSlotCard key={slot.slot_id} slot={slot} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
