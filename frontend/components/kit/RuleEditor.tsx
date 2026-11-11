/**
 * 규칙 편집기 (키트 제공) — 자동화를 **코드가 아니라 데이터**로 만듭니다.
 * =============================================================================
 * 트리거 3종 · 액션 2종 (docs/부록F 7장)
 *   센서 임계값 / 비전 감지 / 정해진 시각  →  액추에이터 제어 / 알림
 *
 * 라운드·승수가 있는 게임 로직은 규칙으로 만들지 말고 시나리오 SDK로 쓰세요 (부록F 7-4절).
 *
 * 비전 감지에는 "사람 수 범위"(이상·미만)를, RGB/네오픽셀 켜기에는 "색"을 함께 줄 수 있습니다
 * — 예: car_1 사람 2~3명 → 1번 칸 LED 노랑 (subway). 비워 두면 예전과 같은 규칙이 만들어집니다.
 *
 * 만든 규칙은 [수정]으로 고칠 수 있습니다. 화면에 없는 설정(otherwise·cooldown_seconds·두 번째 액션 등
 * 코드/API로 넣은 것)은 수정해도 지워지지 않고 그대로 남습니다.
 */
"use client";

import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { Slot, onStateFor, controlTypeOf, slotLabel } from "@/lib/slots";

type TriggerType = "sensor_threshold" | "vision_label" | "schedule";

interface RuleRow {
  id: number;
  name: string;
  enabled: boolean;
  definition: Record<string, unknown> | string | null;
  priority?: number;
  last_fired_at?: string | null;
}

const OPERATORS = [">", ">=", "<", "<=", "==", "!="];

const TRIGGER_LABELS: Record<TriggerType, string> = {
  sensor_threshold: "센서 값이 기준을 넘으면",
  vision_label: "카메라가 무언가를 감지하면",
  schedule: "정해진 시각이 되면",
};

/** 입력 칸 공통 모양 — 글자색을 직접 정해, PC가 다크 모드여도 흰 바탕에 옅은 글자가 되지 않게 합니다. */
const INPUT =
  "rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 " +
  "placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100";

type Json = Record<string, unknown>;

/** 저장된 definition(문자열 또는 객체)을 객체로 읽습니다. 못 읽으면 null. */
function parseDefinition(definition: RuleRow["definition"]): Json | null {
  if (definition && typeof definition === "object") return definition;
  if (typeof definition !== "string") return null;
  try {
    const parsed = JSON.parse(definition);
    return parsed && typeof parsed === "object" ? (parsed as Json) : null;
  } catch {
    return null;
  }
}

/** 규칙 하나를 사람이 읽는 한 문장으로 바꿉니다. */
export function describeRule(
  definition: Record<string, unknown> | string | null,
  slots: Slot[]
): string {
  const def = parseDefinition(definition);
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
    const lo = typeof when.count_at_least === "number" ? when.count_at_least : null;
    const hi = typeof when.count_below === "number" ? when.count_below : null;
    const range =
      lo !== null && hi !== null
        ? hi - 1 === lo
          ? ` (${lo}명)`
          : ` (${lo}~${hi - 1}명)`
        : lo !== null
          ? ` (${lo}명 이상)`
          : hi !== null
            ? ` (${hi}명 미만)`
            : "";
    trigger = `카메라가 '${labels.filter(Boolean).join(", ")}'을(를) 감지하면${range}`;
  } else if (when.type === "schedule") {
    trigger = `매일 ${when.at}이 되면`;
  }

  const actions = ((def.then as Record<string, unknown>[]) ?? []).map((action) => {
    const delay = action.after_seconds ? `${action.after_seconds}초 뒤 ` : "";
    if (action.action === "set_actuator") {
      const color = (action.value as Record<string, unknown> | undefined)?.color;
      return `${delay}${nameOf(action.slot_id)}을(를) ${action.state}${color ? ` ${color}` : ""}`;
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
  // 수정 중인 규칙 (null이면 새 규칙 만들기)
  const [editing, setEditing] = useState<RuleRow | null>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const sensors = slots.filter((s) => s.role === "sensor");
  const actuators = slots.filter((s) => s.role === "actuator");

  // 입력값
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<TriggerType>("sensor_threshold");
  const [pickedSensorId, setSensorId] = useState("");
  const [operator, setOperator] = useState(">");
  const [threshold, setThreshold] = useState("28");
  const [label, setLabel] = useState("person");
  // 사람 수 범위 (비우면 조건 없음) — 예: 2 이상 4 미만 = 2~3명
  const [countMin, setCountMin] = useState("");
  const [countBelow, setCountBelow] = useState("");
  // RGB·네오픽셀을 켤 때 줄 색
  const [color, setColor] = useState("#00c853");
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
  const colorable =
    !!selectedActuator && controlTypeOf(selectedActuator) === "rgb" && actuatorState === "on";

  /** 빈칸이면 null, 아니면 0 이상의 정수 (잘못 쓰면 NaN) */
  const countValue = (text: string): number | null => {
    if (text.trim() === "") return null;
    const n = Number(text);
    return Number.isInteger(n) && n >= 0 ? n : Number.NaN;
  };

  /** 입력 칸을 처음 상태로 되돌립니다 (새 규칙용). */
  const resetForm = () => {
    setName("");
    setTrigger("sensor_threshold");
    setSensorId("");
    setOperator(">");
    setThreshold("28");
    setLabel("person");
    setCountMin("");
    setCountBelow("");
    setColor("#00c853");
    setAt("07:30");
    setActionKind("set_actuator");
    setActuatorId("");
    setActuatorState(null);
    setNotifyMessage("확인해 주세요!");
    setAfterSeconds("0");
  };

  /** 저장된 규칙을 입력 칸에 채웁니다. */
  const fillForm = (rule: RuleRow, def: Json) => {
    resetForm();
    setName(rule.name);
    const when = (def.when ?? {}) as Json;
    if (when.type === "sensor_threshold") {
      setTrigger("sensor_threshold");
      setSensorId(String(when.slot_id ?? ""));
      setOperator(String(when.op ?? ">"));
      setThreshold(String(when.value ?? ""));
    } else if (when.type === "vision_label") {
      setTrigger("vision_label");
      const labels = Array.isArray(when.labels) ? (when.labels as string[]) : [];
      setLabel(String(when.label ?? labels[0] ?? ""));
      setCountMin(typeof when.count_at_least === "number" ? String(when.count_at_least) : "");
      setCountBelow(typeof when.count_below === "number" ? String(when.count_below) : "");
    } else if (when.type === "schedule") {
      setTrigger("schedule");
      setAt(String(when.at ?? "07:30"));
    }
    const first = (Array.isArray(def.then) ? (def.then[0] as Json | undefined) : undefined) ?? {};
    if (first.action === "notify") {
      setActionKind("notify");
      setNotifyMessage(String(first.message ?? ""));
    } else if (first.action === "set_actuator") {
      setActionKind("set_actuator");
      setActuatorId(String(first.slot_id ?? ""));
      setActuatorState(typeof first.state === "string" ? first.state : null);
      const value = first.value as Json | undefined;
      if (value && typeof value.color === "string") setColor(value.color);
    }
    setAfterSeconds(String(first.after_seconds ?? 0));
  };

  /** 화면 칸으로 다 보여 줄 수 없는 설정이 있는지 (있으면 '그대로 유지' 안내) */
  const hiddenSettings = (def: Json | null): boolean => {
    if (!def) return false;
    const when = (def.when ?? {}) as Json;
    return (
      !(String(when.type) in TRIGGER_LABELS) ||
      (Array.isArray(when.labels) && when.labels.length > 1) ||
      (Array.isArray(def.then) && def.then.length > 1) ||
      def.otherwise !== undefined ||
      def.cooldown_seconds !== undefined
    );
  };

  const editingDef = editing ? parseDefinition(editing.definition) : null;

  const buildDefinition = (base: Json | null) => {
    const baseWhen = (base?.when ?? {}) as Json;
    let when: Json;
    if (trigger === "sensor_threshold") {
      when = {
        ...(baseWhen.type === "sensor_threshold" ? baseWhen : {}),
        type: "sensor_threshold",
        slot_id: sensorId,
        op: operator,
        value: Number(threshold),
      };
    } else if (trigger === "vision_label") {
      const picked = label.trim().toLowerCase();
      const kept: Json = baseWhen.type === "vision_label" ? { ...baseWhen } : {};
      delete kept.count_at_least;
      delete kept.count_below;
      // 라벨을 바꿨으면 예전 라벨 목록(labels)이 새 라벨을 가리지 않게 지웁니다
      const oldLabels = Array.isArray(kept.labels) ? (kept.labels as string[]) : null;
      if (oldLabels && oldLabels[0] !== picked) delete kept.labels;
      when = {
        min_confidence: 0.6,
        ...kept,
        type: "vision_label",
        label: picked,
        ...(countValue(countMin) !== null ? { count_at_least: countValue(countMin) } : {}),
        ...(countValue(countBelow) !== null ? { count_below: countValue(countBelow) } : {}),
      };
    } else {
      when = { ...(baseWhen.type === "schedule" ? baseWhen : {}), type: "schedule", at };
    }

    const baseThen = Array.isArray(base?.then) ? (base.then as Json[]) : [];
    const baseFirst: Json = { ...(baseThen[0] ?? {}) };
    delete baseFirst.after_seconds;
    const delay = Number(afterSeconds) || 0;
    let action: Json;
    if (actionKind === "set_actuator") {
      // 같은 부품이면 화면에 없는 값(서보 각도 등)은 남기고, 색만 화면 값으로 바꿉니다
      const sameSlot = baseFirst.action === "set_actuator" && baseFirst.slot_id === actuatorId;
      const keptValue: Json = sameSlot && baseFirst.value && typeof baseFirst.value === "object"
        ? { ...(baseFirst.value as Json) }
        : {};
      delete keptValue.color;
      const value: Json = { ...keptValue, ...(colorable ? { color } : {}) };
      const rest: Json = sameSlot ? { ...baseFirst } : {};
      delete rest.value;
      action = {
        ...rest,
        action: "set_actuator",
        slot_id: actuatorId,
        state: actuatorState,
        ...(Object.keys(value).length > 0 ? { value } : {}),
      };
    } else {
      action = {
        level: "info",
        ...(baseFirst.action === "notify" ? baseFirst : {}),
        action: "notify",
        message: notifyMessage,
      };
    }
    if (delay > 0) action.after_seconds = delay;

    return { ...(base ?? {}), when, then: [action, ...baseThen.slice(1)] };
  };

  const save = async () => {
    setError(null);
    if (trigger === "sensor_threshold" && !sensorId) {
      setError("센서 슬롯이 없습니다. 먼저 하드웨어 구성에서 센서를 켜 주세요.");
      return;
    }
    if (trigger === "vision_label") {
      const lo = countValue(countMin);
      const hi = countValue(countBelow);
      if (Number.isNaN(lo) || Number.isNaN(hi)) {
        setError("사람 수는 0 이상의 정수로 적거나 비워 두세요.");
        return;
      }
      if (lo !== null && hi !== null && hi <= lo) {
        setError("'미만' 칸은 '이상' 칸보다 커야 합니다 (예: 2 이상 4 미만 = 2~3명).");
        return;
      }
    }
    if (actionKind === "set_actuator" && !actuatorId) {
      setError("액추에이터 슬롯이 없습니다. 먼저 하드웨어 구성에서 액추에이터를 켜 주세요.");
      return;
    }

    setBusy(true);
    const res = editing
      ? await apiFetch(`/api/rules/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: name.trim() || editing.name,
            definition: buildDefinition(editingDef),
            enabled: editing.enabled,
            priority: editing.priority ?? 0,
          }),
        })
      : await apiFetch("/api/rules", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim() || "이름 없는 규칙",
            definition: buildDefinition(null),
            enabled: true,
          }),
        });
    setBusy(false);

    if (!res.ok) {
      setError(res.errorMessage ?? (editing ? "규칙을 수정하지 못했습니다." : "규칙을 만들지 못했습니다."));
      return;
    }
    closeForm();
    await load();
  };

  const closeForm = () => {
    setOpen(false);
    setEditing(null);
    resetForm();
  };

  const startAdd = () => {
    if (open && !editing) {
      closeForm();
      return;
    }
    setError(null);
    setEditing(null);
    resetForm();
    setOpen(true);
  };

  const startEdit = (rule: RuleRow) => {
    const def = parseDefinition(rule.definition);
    if (!def) return;
    setError(null);
    fillForm(rule, def);
    setEditing(rule);
    setOpen(true);
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  };

  const remove = async (ruleId: number) => {
    const res = await apiFetch(`/api/rules/${ruleId}`, { method: "DELETE" });
    if (!res.ok) setError(res.errorMessage ?? "삭제하지 못했습니다.");
    if (editing?.id === ruleId) closeForm();
    await load();
  };

  const toggle = async (rule: RuleRow) => {
    const def = parseDefinition(rule.definition);
    if (!def) {
      setError("규칙 내용을 읽을 수 없어 켜기/끄기를 바꾸지 못했습니다.");
      return;
    }
    const res = await apiFetch(`/api/rules/${rule.id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: rule.name,
        definition: def,
        enabled: !rule.enabled,
        priority: rule.priority ?? 0,
      }),
    });
    if (!res.ok) setError(res.errorMessage ?? "수정하지 못했습니다.");
    if (editing?.id === rule.id) setEditing({ ...editing, enabled: !rule.enabled });
    await load();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">자동화 규칙</h2>
          <p className="mt-0.5 text-sm text-slate-600">
            브라우저를 닫아도 백엔드가 실행합니다. 라운드·승수가 있는 게임은 규칙이 아니라
            시나리오로 만드세요.
          </p>
        </div>
        <button
          type="button"
          onClick={startAdd}
          className="flex h-9 items-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50 px-3 text-sm font-medium text-sky-700 hover:border-sky-300"
        >
          <Plus className="h-4 w-4" />
          {open && !editing ? "닫기" : "규칙 추가"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {open && (
        <div
          ref={formRef}
          className={`scroll-mt-4 space-y-4 rounded-xl border bg-white p-4 text-slate-900 [color-scheme:light] ${
            editing ? "border-amber-300 ring-2 ring-amber-100" : "border-slate-300"
          }`}
        >
          <div className="text-base font-semibold text-slate-900">
            {editing ? `규칙 수정 — #${editing.id} ${editing.name}` : "새 규칙"}
          </div>
          {editing && hiddenSettings(editingDef) && (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              이 규칙에는 화면에 없는 설정(두 번째 액션, otherwise, cooldown_seconds, 여러 라벨 등)이 있습니다.
              화면에 보이는 칸만 바뀌고, 나머지 설정은 그대로 유지됩니다.
            </p>
          )}

          <Field label="규칙 이름">
            <input
              type="text"
              value={name}
              placeholder="예: 더우면 선풍기 켜기"
              onChange={(e) => setName(e.target.value)}
              className={`w-full ${INPUT}`}
            />
          </Field>

          <Field label="언제 (트리거)">
            <select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as TriggerType)}
              className={`w-full ${INPUT}`}
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
                aria-label="센서"
                className={INPUT}
              >
                {sensors.length === 0 && <option value="">(센서 없음)</option>}
                {sensorId && !sensors.some((s) => s.slot_id === sensorId) && (
                  <option value={sensorId}>{sensorId} (꺼진 슬롯)</option>
                )}
                {sensors.map((slot) => (
                  <option key={slot.slot_id} value={slot.slot_id}>
                    {slotLabel(slot)}
                  </option>
                ))}
              </select>
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                aria-label="비교"
                className={INPUT}
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
                aria-label="기준 값"
                onChange={(e) => setThreshold(e.target.value)}
                className={INPUT}
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
                className={`w-full ${INPUT}`}
              />
              {visionLabels.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {visionLabels.map((candidate) => (
                    <button
                      key={candidate}
                      type="button"
                      onClick={() => setLabel(candidate)}
                      className={`rounded-full border px-2.5 py-1 text-xs ${
                        label === candidate
                          ? "border-sky-400 bg-sky-50 font-medium text-sky-800"
                          : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
                      }`}
                    >
                      {candidate}
                    </button>
                  ))}
                </div>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-sm text-slate-800">
                <span>사람 수</span>
                <input
                  type="number"
                  min="0"
                  value={countMin}
                  placeholder="0"
                  aria-label="사람 수 이상"
                  onChange={(e) => setCountMin(e.target.value)}
                  className={`w-16 ${INPUT} px-2 py-1.5`}
                />
                <span>명 이상</span>
                <input
                  type="number"
                  min="1"
                  value={countBelow}
                  placeholder="∞"
                  aria-label="사람 수 미만"
                  onChange={(e) => setCountBelow(e.target.value)}
                  className={`w-16 ${INPUT} px-2 py-1.5`}
                />
                <span>명 미만</span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                선택 — 비우면 감지될 때마다 실행. 적으면 그 범위에 <strong>들어올 때 한 번</strong> 실행합니다
                (예: 2 이상 4 미만 = 2~3명).
              </p>
            </Field>
          )}

          {trigger === "schedule" && (
            <Field label="시각">
              <input
                type="time"
                value={at}
                onChange={(e) => setAt(e.target.value)}
                className={INPUT}
              />
            </Field>
          )}

          <Field label="무엇을 (액션)">
            <select
              value={actionKind}
              onChange={(e) => setActionKind(e.target.value as "set_actuator" | "notify")}
              className={`w-full ${INPUT}`}
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
                aria-label="액추에이터"
                className={INPUT}
              >
                {actuators.length === 0 && <option value="">(액추에이터 없음)</option>}
                {actuatorId && !actuators.some((s) => s.slot_id === actuatorId) && (
                  <option value={actuatorId}>{actuatorId} (꺼진 슬롯)</option>
                )}
                {actuators.map((slot) => (
                  <option key={slot.slot_id} value={slot.slot_id}>
                    {slotLabel(slot)}
                  </option>
                ))}
              </select>
              <select
                value={actuatorState}
                onChange={(e) => setActuatorState(e.target.value)}
                aria-label="동작"
                className={INPUT}
              >
                <option value="on">켜기</option>
                <option value="move">이동 (서보)</option>
                <option value="off">끄기</option>
              </select>
              {colorable && (
                <label className="col-span-2 flex items-center gap-2 text-sm text-slate-800">
                  색
                  <input
                    type="color"
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    aria-label="켤 색"
                    className="h-9 w-14 cursor-pointer rounded border border-slate-300 bg-white p-0.5"
                  />
                  <code className="text-xs text-slate-700">{color}</code>
                </label>
              )}
            </div>
          ) : (
            <input
              type="text"
              value={notifyMessage}
              aria-label="알림 문구"
              onChange={(e) => setNotifyMessage(e.target.value)}
              className={`w-full ${INPUT}`}
            />
          )}

          <Field label="몇 초 뒤에 실행할까요 (0이면 바로)">
            <input
              type="number"
              min="0"
              value={afterSeconds}
              onChange={(e) => setAfterSeconds(e.target.value)}
              className={`w-32 ${INPUT}`}
            />
          </Field>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void save()}
              className="flex h-10 items-center gap-2 rounded-lg bg-sky-600 px-4 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing ? "수정 저장" : "규칙 만들기"}
            </button>
            {editing && (
              <button
                type="button"
                disabled={busy}
                onClick={closeForm}
                className="h-10 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:border-slate-400"
              >
                취소
              </button>
            )}
          </div>
        </div>
      )}

      {rules.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600">
          아직 규칙이 없습니다.
        </p>
      ) : (
        <ul className="space-y-2">
          {rules.map((rule) => {
            const readable = parseDefinition(rule.definition) !== null;
            const isEditing = editing?.id === rule.id;
            return (
              <li
                key={rule.id}
                className={`flex items-start justify-between gap-3 rounded-xl border bg-white p-4 ${
                  isEditing ? "border-amber-300 ring-2 ring-amber-100" : "border-slate-200"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-800">{rule.name}</span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs ${
                        rule.enabled
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 bg-slate-50 text-slate-600"
                      }`}
                    >
                      {rule.enabled ? "켜짐" : "꺼짐"}
                    </span>
                    {isEditing && <span className="text-xs font-medium text-amber-700">수정 중</span>}
                  </div>
                  <p className="mt-1 text-sm text-slate-700">
                    {describeRule(rule.definition, slots)}
                  </p>
                  {rule.last_fired_at && (
                    <p className="mt-1 text-xs text-slate-500">
                      마지막 발동: {new Date(rule.last_fired_at).toLocaleString("ko-KR")}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <button
                    type="button"
                    onClick={() => startEdit(rule)}
                    disabled={!readable}
                    title={readable ? undefined : "규칙 내용을 읽을 수 없어 수정할 수 없습니다"}
                    className="flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 hover:border-sky-300 hover:text-sky-700 disabled:opacity-40"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    수정
                  </button>
                  <button
                    type="button"
                    onClick={() => void toggle(rule)}
                    className="h-8 rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 hover:border-slate-400"
                  >
                    {rule.enabled ? "끄기" : "켜기"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void remove(rule.id)}
                    aria-label={`${rule.name} 삭제`}
                    className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-500 hover:border-rose-200 hover:text-rose-600"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-sm font-medium text-slate-800">{label}</div>
      {children}
    </div>
  );
}
