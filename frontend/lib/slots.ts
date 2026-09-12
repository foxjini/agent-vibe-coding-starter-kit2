/**
 * 슬롯 해석기 (lib/slots.ts) — 키트 제공, 수정하지 마세요.
 * =============================================================================
 * 슬롯 메타데이터(label·kind·control_type·unit·value_schema)를 화면이 쓸 수 있는
 * 형태로 바꿔 줍니다. **위젯 종류를 여기서만 결정**하므로, 팀이 부품을 바꿔도
 * 카드 컴포넌트는 고치지 않습니다 (docs/부록F 3-1절, 9-1절).
 */

/** 백엔드 `GET /api/slots` · `GET /api/devices` 한 줄. */
export interface Slot {
  slot_id: string;
  id?: string;
  role?: "sensor" | "actuator" | null;
  slot_index?: number | null;
  enabled?: boolean | null;
  label?: string | null;
  name?: string | null;
  kind?: string | null;
  unit?: string | null;
  control_type?: string | null;
  value_schema?: Record<string, unknown> | string | null;
  meta?: Record<string, unknown> | string | null;
  display_order?: number | null;
  desired_state?: string | null;
  current_state?: string | null;
  desired_value?: unknown;
  current_value?: unknown;
  updated_at?: string | null;
}

/** 액추에이터 제어 방식 (부록F 3-1절). */
export type ControlType =
  | "onoff"
  | "pulse"
  | "tonal"
  | "pwm"
  | "servo"
  | "rgb"
  | "level";

export const CONTROL_TYPES: ControlType[] = [
  "onoff",
  "pulse",
  "tonal",
  "pwm",
  "servo",
  "rgb",
  "level",
];

/** 설정 화면 드롭다운용 설명. */
export const CONTROL_TYPE_LABELS: Record<ControlType, string> = {
  onoff: "켜기/끄기 (LED·릴레이)",
  pulse: "점멸 (경보등)",
  tonal: "소리 (부저 — 주파수·볼륨)",
  pwm: "세기 조절 (진동모터·밝기)",
  servo: "각도 (서보모터)",
  rgb: "색상 (네오픽셀)",
  level: "단계 (혼잡도 표시등)",
};

/** 자주 쓰는 부품 종류 — 설정 화면에서 고를 수 있게 미리 넣어 둡니다. */
export const COMMON_SENSOR_KINDS = [
  "button",
  "touch",
  "presence",
  "motion",
  "temperature",
  "humidity",
  "distance",
  "pressure",
  "light",
  "camera",
];

export const COMMON_ACTUATOR_KINDS = [
  "buzzer",
  "led",
  "relay",
  "servo",
  "neopixel",
  "vibration_motor",
  "motor",
  "level_led",
];

// ============================================================================
// 값 해석
// ============================================================================

/** JSON 컬럼이 문자열로 와도 객체로 되돌립니다. */
export function asObject(value: unknown): Record<string, unknown> | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed.startsWith("{")) return null;
    try {
      const parsed = JSON.parse(trimmed);
      return typeof parsed === "object" && parsed !== null
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  }
  return null;
}

/** 값 객체에서 숫자 하나를 꺼냅니다 (별칭을 순서대로 찾습니다). */
export function numberFrom(
  value: unknown,
  keys: string[],
  fallback: number
): number {
  const obj = asObject(value);
  if (obj) {
    for (const key of [...keys, "value"]) {
      const raw = obj[key];
      if (typeof raw === "number" && Number.isFinite(raw)) return raw;
      if (typeof raw === "string" && raw.trim() !== "" && !Number.isNaN(Number(raw))) {
        return Number(raw);
      }
    }
  }
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return fallback;
}

/**
 * 센서 보고값에서 차트·큰 숫자로 보여 줄 값을 꺼냅니다.
 * 숫자 센서는 `{"value": 24.5}` 규약을 지켜야 여기서 잡힙니다 (부록F 3-2절).
 */
export function sensorNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const obj = asObject(value);
  if (!obj) return null;
  const raw = obj.value;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  for (const key of ["pressed", "detected", "connected"]) {
    if (key in obj) return obj[key] ? 1 : 0;
  }
  return null;
}

/** 센서 보고값을 사람이 읽을 한 줄로 만듭니다. */
export function sensorText(slot: Slot): { value: string; unit: string; hint: string } {
  const obj = asObject(slot.current_value);
  const unit = slot.unit ?? "";

  if (obj) {
    if ("pressed" in obj) {
      return { value: obj.pressed ? "눌림" : "대기", unit: "", hint: "" };
    }
    if ("detected" in obj) {
      return { value: obj.detected ? "감지됨" : "없음", unit: "", hint: "" };
    }
    if ("connected" in obj) {
      const fps = typeof obj.fps === "number" ? `${obj.fps} fps` : "";
      return { value: obj.connected ? "연결됨" : "끊김", unit: "", hint: fps };
    }
  }

  const numeric = sensorNumber(slot.current_value);
  if (numeric !== null) {
    const rounded = Math.abs(numeric) >= 100 ? Math.round(numeric) : Math.round(numeric * 10) / 10;
    return { value: String(rounded), unit, hint: "" };
  }

  if (slot.current_state) return { value: slot.current_state, unit: "", hint: "" };
  return { value: "—", unit: "", hint: "아직 보고 없음" };
}

// ============================================================================
// 상태 판정
// ============================================================================

/** 켜짐으로 보는 상태 표현 (pi의 drivers/base.py ON_STATES와 같은 목록). */
const ON_STATES = [
  "on",
  "move",
  "start",
  "open",
  "run",
  "active",
  "detected",
  "true",
  "1",
  "high",
];

export function isOnState(state: string | null | undefined): boolean {
  return ON_STATES.includes(String(state ?? "").trim().toLowerCase());
}

export interface SlotStatus {
  /** 하드웨어가 한 번이라도 보고했는가 */
  reported: boolean;
  /** 내린 명령이 아직 하드웨어에 반영되지 않았는가 (부록A 상태 계약) */
  pending: boolean;
  label: string;
  tone: "on" | "off" | "warning" | "disconnected";
}

/**
 * desired(명령)와 current(하드웨어 보고)를 비교해 표시 상태를 만듭니다.
 * 둘을 합쳐서 보여 주면 "껐는데 계속 울리는" 상황을 화면에서 알 수 없습니다.
 */
export function slotStatus(slot: Slot): SlotStatus {
  const reported = slot.current_state !== null && slot.current_state !== undefined;
  if (!reported) {
    return {
      reported: false,
      pending: Boolean(slot.desired_state),
      label: "보고 없음",
      tone: "disconnected",
    };
  }

  const pending =
    Boolean(slot.desired_state) && slot.desired_state !== slot.current_state;
  if (pending) {
    return { reported, pending, label: "반영 대기", tone: "warning" };
  }

  const on = isOnState(slot.current_state);
  return {
    reported,
    pending: false,
    label: on ? "동작 중" : "정지",
    tone: on ? "on" : "off",
  };
}

// ============================================================================
// 위젯 결정 (여기가 "코드를 고치지 않는다"의 핵심입니다)
// ============================================================================

export interface ValueRange {
  min: number;
  max: number;
  step: number;
}

/** value_schema에서 슬라이더 범위를 꺼냅니다. */
export function valueRange(slot: Slot, fallback: ValueRange): ValueRange {
  const schema = asObject(slot.value_schema) ?? {};
  const pick = (key: string, defaultValue: number) => {
    const raw = schema[key];
    return typeof raw === "number" && Number.isFinite(raw) ? raw : defaultValue;
  };
  const min = pick("min", fallback.min);
  const max = pick("max", fallback.max);
  return {
    min,
    max: max > min ? max : fallback.max,
    step: pick("step", fallback.step),
  };
}

/** control_type이 비어 있으면 kind로 짐작합니다 (설정을 덜 채운 팀을 위해). */
export function controlTypeOf(slot: Slot): ControlType {
  const declared = String(slot.control_type ?? "").trim().toLowerCase();
  if (CONTROL_TYPES.includes(declared as ControlType)) return declared as ControlType;

  const kind = String(slot.kind ?? "").trim().toLowerCase();
  if (kind === "buzzer") return "tonal";
  if (kind === "servo") return "servo";
  if (kind === "neopixel" || kind === "rgb_led") return "rgb";
  if (kind === "vibration_motor" || kind === "motor") return "pwm";
  if (kind === "level_led") return "level";
  return "onoff";
}

/** 이 control_type이 켤 때 쓰는 desired_state 문자열 (servo만 "move"). */
export function onStateFor(controlType: ControlType): string {
  return controlType === "servo" ? "move" : "on";
}

/** 아이콘 이름 — 카드가 lucide 아이콘을 고를 때 씁니다. */
export function iconNameFor(slot: Slot): string {
  const kind = String(slot.kind ?? "").trim().toLowerCase();
  const byKind: Record<string, string> = {
    buzzer: "volume",
    led: "lightbulb",
    relay: "power",
    servo: "rotate",
    neopixel: "palette",
    vibration_motor: "vibrate",
    motor: "cog",
    level_led: "bars",
    button: "hand",
    touch: "hand",
    presence: "user",
    motion: "activity",
    temperature: "thermometer",
    humidity: "droplet",
    distance: "ruler",
    pressure: "gauge",
    light: "sun",
    camera: "camera",
  };
  if (byKind[kind]) return byKind[kind];
  return slot.role === "actuator" ? "power" : "activity";
}

// ============================================================================
// 목록 정리
// ============================================================================

/** 대시보드에 보여 줄 이름 (label이 없으면 name, 그것도 없으면 슬롯 ID). */
export function slotLabel(slot: Slot): string {
  return slot.label || slot.name || slot.slot_id || slot.id || "이름 없는 슬롯";
}

/** 슬롯 목록을 화면 순서대로 정렬합니다 (display_order → 슬롯 번호). */
export function sortSlots(slots: Slot[]): Slot[] {
  return [...slots].sort((a, b) => {
    const orderDiff = (a.display_order ?? 0) - (b.display_order ?? 0);
    if (orderDiff !== 0) return orderDiff;
    if (a.role !== b.role) return a.role === "sensor" ? -1 : 1;
    return (a.slot_index ?? 0) - (b.slot_index ?? 0);
  });
}

/** 백엔드 응답을 Slot 형태로 다듬습니다 (구버전 `id`만 오는 경우 포함). */
export function normalizeSlot(raw: Record<string, unknown>): Slot {
  const slot = { ...raw } as unknown as Slot;
  slot.slot_id = (raw.slot_id as string) || (raw.id as string) || "";
  slot.value_schema = asObject(raw.value_schema);
  slot.meta = asObject(raw.meta);
  if (!slot.role) {
    slot.role = slot.slot_id.startsWith("actuator") ? "actuator" : "sensor";
  }
  return slot;
}
