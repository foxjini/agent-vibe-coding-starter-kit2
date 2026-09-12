/**
 * 하드웨어 구성 화면 (키트 제공) — 슬롯 20칸의 '의미'를 데이터로 설정합니다.
 * =============================================================================
 * 여기서 바꾸는 것은 **코드가 아니라 데이터**입니다 (docs/부록F 3장).
 * 보통은 라즈베리파이가 `slot_map.py`를 올려서 자동으로 채워지고,
 * 이 화면은 라벨을 다듬거나 파이 없이 화면만 먼저 만들 때 씁니다.
 */
"use client";

import { Loader2, RefreshCw } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import {
  COMMON_ACTUATOR_KINDS,
  COMMON_SENSOR_KINDS,
  CONTROL_TYPES,
  CONTROL_TYPE_LABELS,
  ControlType,
  Slot,
  normalizeSlot,
} from "@/lib/slots";

interface Draft {
  label: string;
  kind: string;
  unit: string;
  control_type: string;
}

function draftOf(slot: Slot): Draft {
  return {
    label: slot.label ?? "",
    kind: slot.kind && slot.kind !== "unassigned" ? slot.kind : "",
    unit: slot.unit ?? "",
    control_type: slot.control_type ?? "",
  };
}

export default function HardwareSetup({ onChanged }: { onChanged?: () => void }) {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [savingSlot, setSavingSlot] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch<Record<string, unknown>[]>("/api/slots");
    if (res.ok && Array.isArray(res.data)) {
      const list = res.data.map(normalizeSlot);
      setSlots(list);
      setDrafts(Object.fromEntries(list.map((s) => [s.slot_id, draftOf(s)])));
    } else {
      setMessage({ text: res.errorMessage ?? "슬롯 목록을 읽지 못했습니다.", ok: false });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  const patch = async (slot: Slot, fields: Record<string, unknown>) => {
    setSavingSlot(slot.slot_id);
    const res = await apiFetch<Record<string, unknown>>(`/api/slots/${slot.slot_id}`, {
      method: "PATCH",
      body: JSON.stringify(fields),
    });
    setSavingSlot(null);

    if (!res.ok) {
      setMessage({ text: res.errorMessage ?? "저장하지 못했습니다.", ok: false });
      return;
    }
    setMessage({ text: `${slot.slot_id} 저장 완료`, ok: true });
    setSlots((prev) =>
      prev.map((s) => (s.slot_id === slot.slot_id ? { ...s, ...fields } : s))
    );
    onChanged?.();
  };

  const sensors = slots.filter((s) => s.role === "sensor");
  const actuators = slots.filter((s) => s.role === "actuator");
  const usedCount = slots.filter((s) => s.enabled).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">하드웨어 구성</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            슬롯 20칸 중 <strong className="text-slate-700">{usedCount}칸</strong>을 쓰고
            있습니다. 부품을 떼면 &apos;사용&apos;을 끄세요 — 슬롯 자체는 사라지지 않습니다.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:border-slate-300"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      {message && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            message.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <SlotTable
        title="액추에이터 (actuator_01 ~ actuator_10)"
        slots={actuators}
        drafts={drafts}
        setDrafts={setDrafts}
        savingSlot={savingSlot}
        onPatch={patch}
      />
      <SlotTable
        title="센서 (sensor_01 ~ sensor_10)"
        slots={sensors}
        drafts={drafts}
        setDrafts={setDrafts}
        savingSlot={savingSlot}
        onPatch={patch}
      />
    </div>
  );
}

function SlotTable({
  title,
  slots,
  drafts,
  setDrafts,
  savingSlot,
  onPatch,
}: {
  title: string;
  slots: Slot[];
  drafts: Record<string, Draft>;
  setDrafts: React.Dispatch<React.SetStateAction<Record<string, Draft>>>;
  savingSlot: string | null;
  onPatch: (slot: Slot, fields: Record<string, unknown>) => Promise<void>;
}) {
  const isActuator = slots[0]?.role === "actuator";
  const kinds = isActuator ? COMMON_ACTUATOR_KINDS : COMMON_SENSOR_KINDS;

  const update = (slotId: string, field: keyof Draft, value: string) =>
    setDrafts((prev) => ({ ...prev, [slotId]: { ...prev[slotId], [field]: value } }));

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <h3 className="border-b border-slate-100 bg-slate-50 px-4 py-2.5 text-sm font-semibold text-slate-600">
        {title}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
              <th className="px-4 py-2 font-medium">슬롯</th>
              <th className="px-3 py-2 font-medium">사용</th>
              <th className="px-3 py-2 font-medium">이름(라벨)</th>
              <th className="px-3 py-2 font-medium">종류</th>
              <th className="px-3 py-2 font-medium">
                {isActuator ? "제어 방식" : "단위"}
              </th>
              <th className="px-3 py-2 font-medium">저장</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((slot) => {
              const draft = drafts[slot.slot_id] ?? draftOf(slot);
              const saving = savingSlot === slot.slot_id;
              return (
                <tr
                  key={slot.slot_id}
                  className={`border-b border-slate-50 last:border-0 ${
                    slot.enabled ? "" : "bg-slate-50/50 text-slate-400"
                  }`}
                >
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                    {slot.slot_id}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={Boolean(slot.enabled)}
                      onChange={(e) => void onPatch(slot, { enabled: e.target.checked })}
                      className="h-4 w-4 cursor-pointer accent-sky-600"
                      aria-label={`${slot.slot_id} 사용 여부`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={draft.label}
                      placeholder={isActuator ? "예: 알람 부저" : "예: 실내 온도"}
                      onChange={(e) => update(slot.slot_id, "label", e.target.value)}
                      className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-slate-800 focus:border-sky-400 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      list={`kinds-${isActuator ? "actuator" : "sensor"}`}
                      value={draft.kind}
                      placeholder={isActuator ? "예: buzzer" : "예: temperature"}
                      onChange={(e) => update(slot.slot_id, "kind", e.target.value)}
                      className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-slate-800 focus:border-sky-400 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    {isActuator ? (
                      <select
                        value={draft.control_type}
                        onChange={(e) =>
                          update(slot.slot_id, "control_type", e.target.value)
                        }
                        className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-slate-800 focus:border-sky-400 focus:outline-none"
                      >
                        <option value="">(자동)</option>
                        {CONTROL_TYPES.map((type: ControlType) => (
                          <option key={type} value={type}>
                            {CONTROL_TYPE_LABELS[type]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={draft.unit}
                        placeholder="예: °C"
                        onChange={(e) => update(slot.slot_id, "unit", e.target.value)}
                        className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-slate-800 focus:border-sky-400 focus:outline-none"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() =>
                        void onPatch(slot, {
                          label: draft.label || null,
                          kind: draft.kind || null,
                          ...(isActuator
                            ? { control_type: draft.control_type || null }
                            : { unit: draft.unit || null }),
                        })
                      }
                      className="flex h-8 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-600 hover:border-slate-300 disabled:opacity-50"
                    >
                      {saving && <Loader2 className="h-3 w-3 animate-spin" />}
                      저장
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <datalist id={`kinds-${isActuator ? "actuator" : "sensor"}`}>
        {kinds.map((kind) => (
          <option key={kind} value={kind} />
        ))}
      </datalist>
    </section>
  );
}
