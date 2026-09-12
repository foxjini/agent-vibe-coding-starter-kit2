/**
 * 규칙 편집기 (키트 제공) — 자동화를 **코드가 아니라 데이터**로 만듭니다.
 * =============================================================================
 * 트리거 3종 · 액션 2종 (docs/부록F 7장)
 *   센서 임계값 / 비전 감지 / 정해진 시각  →  액추에이터 제어 / 알림
 *
 * 라운드·승수가 있는 게임 로직은 규칙으로 만들지 말고 시나리오 SDK로 쓰세요 (부록F 7-4절).
 */
"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { Slot, onStateFor, controlTypeOf, slotLabel } from "@/lib/slots";

type TriggerType = "sensor_threshold" | "vision_label" | "schedule";

interface RuleRow {
  id: number;
  name: string;
  enabled: boolean;
  definition: Record<string, unknown> | string | null;
  last_fired_at?: string | null;
}

const OPERATORS = [">", ">=", "<", "<=", "==", "!="];

const TRIGGER_LABELS: Record<TriggerType, string> = {
  sensor_threshold: "센서 값이 기준을 넘으면",
  vision_label: "카메라가 무언가를 감지하면",
  schedule: "정해진 시각이 되면",
};

/** 규칙 하나를 사람이 읽는 한 문장으로 바꿉니다. */
export function describeRule(
  definition: Record<string, unknown> | string | null,
  slots: Slot[]
): string {
  const def =
    typeof definition === "string"
      ? (() => {
          try {
            return JSON.parse(definition) as Record<string, unknown>;
          } catch {
            return null;
          }
        })()
      : definition;
  if (!def) return "(읽을 수 없는 규칙)";

  const when = (def.when ?? {}) as Record<string, unknown>;
  const nameOf = (slotId: unknown) => {
    const slot = slots.find((s) => s.slot_id === slotId);
    return slot ? slotLabel(slot) : String(slotId ?? "?");
  };

  let trigger = "언제?";
  if (when.type === "sensor_threshold") {
    trigger = `${nameOf(when.slot_id)} 값이 ${when.op} ${when.value}이면`;
  } else if (when.type === "vision_label") {
    const labels = (when.labels as string[]) ?? [when.label];
    trigger = `카메라가 '${labels.filter(Boolean).join(", ")}'을(를) 감지하면`;
  } else if (when.type === "schedule") {
    trigger = `매일 ${when.at}이 되면`;
  }

  const actions = ((def.then as Record<string, unknown>[]) ?? []).map((action) => {
    const delay = action.after_seconds ? `${action.after_seconds}초 뒤 ` : "";
    if (action.action === "set_actuator") {
      return `${delay}${nameOf(action.slot_id)}을(를) ${action.state}`;
    }
    return `${delay}"${action.message}" 알림`;
  });

  return `${trigger} → ${actions.join(", ") || "(동작 없음)"}`;
}

export default function RuleEditor({ slots }: { slots: Slot[] }) {
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const sensors = slots.filter((s) => s.role === "sensor");
  const actuators = slots.filter((s) => s.role === "actuator");

  // 새 규칙 입력값
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<TriggerType>("sensor_threshold");
  const [pickedSensorId, setSensorId] = useState("");
  const [operator, setOperator] = useState(">");
  const [threshold, setThreshold] = useState("28");
  const [label, setLabel] = useState("person");
  const [at, setAt] = useState("07:30");
  const [actionKind, setActionKind] = useState<"set_actuator" | "notify">("set_actuator");
  const [pickedActuatorId, setActuatorId] = useState("");
  const [pickedActuatorState, setActuatorState] = useState<string | null>(null);
  const [notifyMessage, setNotifyMessage] = useState("확인해 주세요!");
  const [afterSeconds, setAfterSeconds] = useState("0");

  const load = useCallback(async () => {
    const res = await apiFetch<RuleRow[]>("/api/rules");
    if (res.ok && Array.isArray(res.data)) setRules(res.data);
    else setError(res.errorMessage ?? null);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  // 고를 수 있는 감지 라벨 — 코드에 적어 두지 않고, 비전 클라이언트가 신고한 것을 씁니다.
  // (`vision/detectors/`에 팀이 검출기를 추가하면 여기 후보에도 자동으로 나타납니다.)
  const [visionLabels, setVisionLabels] = useState<string[]>([]);
  useEffect(() => {
    const timer = setTimeout(() => {
      void (async () => {
        const res = await apiFetch<{
          object_labels?: string[];
          known_detectors?: { labels?: string[] }[];
        }>("/api/vision/config");
        if (!res.ok || !res.data) return;
        const fromDetectors = (res.data.known_detectors ?? []).flatMap((d) => d.labels ?? []);
        const merged = [...(res.data.object_labels ?? []), ...fromDetectors];
        setVisionLabels([...new Set(merged.filter(Boolean))]);
      })();
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  // 고르지 않았으면 첫 슬롯을 기본값으로 씁니다.
  // (이펙트로 state를 맞추면 렌더가 연쇄되므로 파생해서 계산합니다)
  const sensorId = pickedSensorId || sensors[0]?.slot_id || "";
  const actuatorId = pickedActuatorId || actuators[0]?.slot_id || "";
  const selectedActuator = actuators.find((s) => s.slot_id === actuatorId);
  const actuatorState =
    pickedActuatorState ??
    (selectedActuator ? onStateFor(controlTypeOf(selectedActuator)) : "on");

  const buildDefinition = () => {
    const when =
      trigger === "sensor_threshold"
        ? {
            type: "sensor_threshold",
            slot_id: sensorId,
            op: operator,
            value: Number(threshold),
          }
        : trigger === "vision_label"
          ? { type: "vision_label", label: label.trim().toLowerCase(), min_confidence: 0.6 }
          : { type: "schedule", at };

    const delay = Number(afterSeconds) || 0;
    const action =
      actionKind === "set_actuator"
        ? {
            action: "set_actuator",
            slot_id: actuatorId,
            state: actuatorState,
            ...(delay > 0 ? { after_seconds: delay } : {}),
          }
        : {
            action: "notify",
            message: notifyMessage,
            level: "info",
            ...(delay > 0 ? { after_seconds: delay } : {}),
          };

    return { when, then: [action] };
  };

  const create = async () => {
    setError(null);
    if (trigger === "sensor_threshold" && !sensorId) {
      setError("센서 슬롯이 없습니다. 먼저 하드웨어 구성에서 센서를 켜 주세요.");
      return;
    }
    if (actionKind === "set_actuator" && !actuatorId) {
      setError("액추에이터 슬롯이 없습니다. 먼저 하드웨어 구성에서 액추에이터를 켜 주세요.");
      return;
    }

    setBusy(true);
    const res = await apiFetch("/api/rules", {
      method: "POST",
      body: JSON.stringify({
        name: name.trim() || "이름 없는 규칙",
        definition: buildDefinition(),
        enabled: true,
      }),
    });
    setBusy(false);

    if (!res.ok) {
      setError(res.errorMessage ?? "규칙을 만들지 못했습니다.");
      return;
    }
    setName("");
    setOpen(false);
    await load();
  };

  const remove = async (ruleId: number) => {
    const res = await apiFetch(`/api/rules/${ruleId}`, { method: "DELETE" });
    if (!res.ok) setError(res.errorMessage ?? "삭제하지 못했습니다.");
    await load();
  };

  const toggle = async (rule: RuleRow) => {
    const res = await apiFetch(`/api/rules/${rule.id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: rule.name,
        definition:
          typeof rule.definition === "string"
            ? JSON.parse(rule.definition)
            : rule.definition,
        enabled: !rule.enabled,
      }),
    });
    if (!res.ok) setError(res.errorMessage ?? "수정하지 못했습니다.");
    await load();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">자동화 규칙</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            브라우저를 닫아도 백엔드가 실행합니다. 라운드·승수가 있는 게임은 규칙이 아니라
            시나리오로 만드세요.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex h-9 items-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50 px-3 text-sm font-medium text-sky-700 hover:border-sky-300"
        >
          <Plus className="h-4 w-4" />
          {open ? "닫기" : "규칙 추가"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {open && (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <Field label="규칙 이름">
            <input
              type="text"
              value={name}
              placeholder="예: 더우면 선풍기 켜기"
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
            />
          </Field>

          <Field label="언제 (트리거)">
            <select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as TriggerType)}
              className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
            >
              {(Object.keys(TRIGGER_LABELS) as TriggerType[]).map((type) => (
                <option key={type} value={type}>
                  {TRIGGER_LABELS[type]}
                </option>
              ))}
            </select>
          </Field>

          {trigger === "sensor_threshold" && (
            <div className="grid grid-cols-3 gap-2">
              <select
                value={sensorId}
                onChange={(e) => setSensorId(e.target.value)}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              >
                {sensors.length === 0 && <option value="">(센서 없음)</option>}
                {sensors.map((slot) => (
                  <option key={slot.slot_id} value={slot.slot_id}>
                    {slotLabel(slot)}
                  </option>
                ))}
              </select>
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              >
                {OPERATORS.map((op) => (
                  <option key={op} value={op}>
                    {op}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              />
            </div>
          )}

          {trigger === "vision_label" && (
            <Field label="감지할 대상 (영문 라벨)">
              <input
                type="text"
                value={label}
                placeholder="person, cup, bottle …"
                onChange={(e) => setLabel(e.target.value)}
                className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              />
              {visionLabels.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {visionLabels.map((candidate) => (
                    <button
                      key={candidate}
                      type="button"
                      onClick={() => setLabel(candidate)}
                      className={`rounded-full border px-2 py-0.5 text-xs ${
                        label === candidate
                          ? "border-sky-300 bg-sky-50 text-sky-800"
                          : "border-slate-200 text-slate-500 hover:border-slate-300"
                      }`}
                    >
                      {candidate}
                    </button>
                  ))}
                </div>
              )}
            </Field>
          )}

          {trigger === "schedule" && (
            <Field label="시각">
              <input
                type="time"
                value={at}
                onChange={(e) => setAt(e.target.value)}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              />
            </Field>
          )}

          <Field label="무엇을 (액션)">
            <select
              value={actionKind}
              onChange={(e) => setActionKind(e.target.value as "set_actuator" | "notify")}
              className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
            >
              <option value="set_actuator">액추에이터 제어</option>
              <option value="notify">화면에 알림</option>
            </select>
          </Field>

          {actionKind === "set_actuator" ? (
            <div className="grid grid-cols-2 gap-2">
              <select
                value={actuatorId}
                onChange={(e) => {
                  setActuatorId(e.target.value);
                  setActuatorState(null);   // 새 부품에 맞는 기본 동작으로 되돌림
                }}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              >
                {actuators.length === 0 && <option value="">(액추에이터 없음)</option>}
                {actuators.map((slot) => (
                  <option key={slot.slot_id} value={slot.slot_id}>
                    {slotLabel(slot)}
                  </option>
                ))}
              </select>
              <select
                value={actuatorState}
                onChange={(e) => setActuatorState(e.target.value)}
                className="rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
              >
                <option value="on">켜기</option>
                <option value="move">이동 (서보)</option>
                <option value="off">끄기</option>
              </select>
            </div>
          ) : (
            <input
              type="text"
              value={notifyMessage}
              onChange={(e) => setNotifyMessage(e.target.value)}
              className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
            />
          )}

          <Field label="몇 초 뒤에 실행할까요 (0이면 바로)">
            <input
              type="number"
              min="0"
              value={afterSeconds}
              onChange={(e) => setAfterSeconds(e.target.value)}
              className="w-32 rounded-md border border-slate-200 px-2.5 py-2 text-sm focus:border-sky-400 focus:outline-none"
            />
          </Field>

          <button
            type="button"
            disabled={busy}
            onClick={() => void create()}
            className="flex h-10 items-center gap-2 rounded-lg bg-sky-600 px-4 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            규칙 만들기
          </button>
        </div>
      )}

      {rules.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
          아직 규칙이 없습니다.
        </p>
      ) : (
        <ul className="space-y-2">
          {rules.map((rule) => (
            <li
              key={rule.id}
              className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-800">{rule.name}</span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      rule.enabled
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-slate-200 bg-slate-50 text-slate-500"
                    }`}
                  >
                    {rule.enabled ? "켜짐" : "꺼짐"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {describeRule(rule.definition, slots)}
                </p>
                {rule.last_fired_at && (
                  <p className="mt-1 text-xs text-slate-400">
                    마지막 발동: {new Date(rule.last_fired_at).toLocaleString("ko-KR")}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-1.5">
                <button
                  type="button"
                  onClick={() => void toggle(rule)}
                  className="h-8 rounded-md border border-slate-200 px-2.5 text-xs text-slate-600 hover:border-slate-300"
                >
                  {rule.enabled ? "끄기" : "켜기"}
                </button>
                <button
                  type="button"
                  onClick={() => void remove(rule.id)}
                  aria-label={`${rule.name} 삭제`}
                  className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-400 hover:border-rose-200 hover:text-rose-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-sm font-medium text-slate-600">{label}</div>
      {children}
    </div>
  );
}
