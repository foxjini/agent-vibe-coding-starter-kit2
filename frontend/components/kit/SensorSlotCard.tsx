/**
 * 센서 슬롯 카드 (키트 제공) — kind·unit만 보고 표시 방식을 정합니다.
 * 팀이 센서를 바꿔도 이 파일은 고치지 않습니다 (docs/부록F 9-1절).
 * 디자인은 자유롭게 손보세요.
 */
"use client";

import React from "react";

import SlotIcon from "@/components/kit/SlotIcon";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import { Slot, sensorText, slotLabel, slotStatus } from "@/lib/slots";

function relativeTime(iso?: string | null): string {
  if (!iso) return "";
  const at = new Date(iso).getTime();
  if (Number.isNaN(at)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - at) / 1000));
  if (seconds < 5) return "방금";
  if (seconds < 60) return `${seconds}초 전`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}분 전`;
  return `${Math.round(seconds / 3600)}시간 전`;
}

export default function SensorSlotCard({ slot }: { slot: Slot }) {
  const status = slotStatus(slot);
  const reading = sensorText(slot);

  // 눌림·감지는 빨강(주의), 숫자는 파랑(중립 정보) — ui-ux-rules.md 색상 의미표
  const isEvent = reading.value === "눌림" || reading.value === "감지됨";
  const badgeTone = !status.reported ? "disconnected" : isEvent ? "alert" : "info";
  const badgeLabel = !status.reported ? "보고 없음" : isEvent ? reading.value : "측정 중";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:border-slate-300">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <SlotIcon slot={slot} className="h-3.5 w-3.5 text-slate-500" />
            센서(읽기 전용) · {slot.kind || "미지정"}
          </div>
          <h3 className="truncate text-base font-medium text-slate-800">
            {slotLabel(slot)}
          </h3>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(
            badgeTone
          )}`}
        >
          {badgeLabel}
        </span>
      </div>

      <div className="py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-semibold tabular-nums text-slate-900">
            {reading.value}
          </span>
          {reading.unit && (
            <span className="text-lg font-medium text-slate-500">{reading.unit}</span>
          )}
        </div>
        {reading.hint && (
          <p className="mt-1 text-sm text-slate-500">{reading.hint}</p>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-400">
        <span className="font-mono">{slot.slot_id}</span>
        <span>{relativeTime(slot.updated_at) || "—"}</span>
      </div>
    </div>
  );
}
