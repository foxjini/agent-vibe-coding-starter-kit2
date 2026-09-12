/**
 * 알람 예약 카드 (wakeup 팀 화면).
 * =============================================================================
 * 예약은 **자동화 규칙**으로 저장됩니다 (부록F 7장). 그래서 브라우저를 닫아도,
 * 컴퓨터를 꺼도 백엔드가 정해진 시각에 부저를 켭니다.
 */
"use client";

import { AlarmClock, Loader2, Trash2 } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

const RULE_NAME = "기상 알람";

interface RuleRow {
  id: number;
  name: string;
  enabled: boolean;
  definition: Record<string, unknown> | string | null;
}

function definitionOf(rule: RuleRow): Record<string, unknown> | null {
  if (typeof rule.definition === "string") {
    try {
      return JSON.parse(rule.definition) as Record<string, unknown>;
    } catch {
      return null;
    }
  }
  return rule.definition;
}

export default function AlarmScheduleCard() {
  const [time, setTime] = useState("07:30");
  const [saved, setSaved] = useState<{ id: number; at: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await apiFetch<RuleRow[]>("/api/rules");
    if (!res.ok || !Array.isArray(res.data)) {
      setError(res.errorMessage ?? null);
      return;
    }
    const alarm = res.data.find((rule) => rule.name === RULE_NAME);
    if (!alarm) {
      setSaved(null);
      return;
    }
    const when = (definitionOf(alarm)?.when ?? {}) as Record<string, unknown>;
    setSaved({ id: alarm.id, at: String(when.at ?? "") });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  const save = async () => {
    setBusy(true);
    setError(null);
    const body = {
      name: RULE_NAME,
      enabled: true,
      definition: {
        when: { type: "schedule", at: time },
        then: [
          {
            action: "set_actuator",
            slot_id: WAKEUP_SLOTS.buzzer,
            state: "on",
            value: { volume: 80, frequency: 1000 },
          },
        ],
      },
    };
    const res = saved
      ? await apiFetch(`/api/rules/${saved.id}`, { method: "PUT", body: JSON.stringify(body) })
      : await apiFetch("/api/rules", { method: "POST", body: JSON.stringify(body) });
    setBusy(false);

    if (!res.ok) {
      setError(res.errorMessage ?? "알람을 저장하지 못했습니다.");
      return;
    }
    await load();
  };

  const remove = async () => {
    if (!saved) return;
    setBusy(true);
    const res = await apiFetch(`/api/rules/${saved.id}`, { method: "DELETE" });
    setBusy(false);
    if (!res.ok) setError(res.errorMessage ?? "알람을 지우지 못했습니다.");
    await load();
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
        <AlarmClock className="h-3.5 w-3.5 text-slate-500" />
        알람 예약
      </div>

      {saved ? (
        <div className="mb-3 flex items-baseline gap-2">
          <span className="text-3xl font-semibold tabular-nums text-slate-900">{saved.at}</span>
          <span className="text-sm text-slate-500">에 부저가 울립니다</span>
        </div>
      ) : (
        <p className="mb-3 text-sm text-slate-500">예약된 알람이 없습니다.</p>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          aria-label="알람 시각"
          className="h-10 rounded-lg border border-slate-200 px-3 text-sm focus:border-sky-400 focus:outline-none"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => void save()}
          className="flex h-10 items-center gap-1.5 rounded-lg bg-sky-600 px-4 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {saved ? "시각 변경" : "예약하기"}
        </button>
        {saved && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void remove()}
            aria-label="알람 예약 취소"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:border-rose-200 hover:text-rose-600 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}

      <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
        예약은 자동화 규칙으로 저장되므로, 브라우저를 닫아도 백엔드가 알람을 울립니다.
      </p>
    </div>
  );
}
