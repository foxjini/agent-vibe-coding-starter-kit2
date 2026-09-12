/**
 * 시나리오 SDK (lib/scenario.ts) — 키트 제공, 수정하지 마세요.
 * =============================================================================
 * "프론트엔드가 두뇌" 구조에서 팀이 시나리오를 쓰는 곳입니다 (docs/부록F 9-2절).
 * WebSocket 연결·재연결·상태 동기화는 SDK가 처리하므로, 팀은 규칙만 씁니다.
 *
 *   const { slots, setActuator, onSensor, onVision, after, notify } = useScenario();
 *
 *   onSensor("sensor_01", (v) => {
 *     if (v.pressed) setActuator("actuator_01", "off");
 *   });
 *
 * ⚠️ 브라우저 탭을 닫으면 시나리오도 멈춥니다. 화면 없이도 동작해야 하는 것은
 *    자동화 규칙(부록F 7장)이나 serverTimer로 백엔드에 맡기세요.
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { WS_URL, apiFetch } from "@/lib/api";
import { Slot, asObject, normalizeSlot, sortSlots } from "@/lib/slots";

// ============================================================================
// 이벤트 타입
// ============================================================================

export interface SensorEvent {
  slot_id: string;
  value: Record<string, unknown> | null;
  /** 숫자 센서면 여기에 값이 들어옵니다 (`{"value": 24.5}` 규약) */
  number: number | null;
  unit?: string | null;
  current_state?: string | null;
  pressed?: boolean;
  detected?: boolean;
  updated_at?: string | null;
}

export interface VisionEvent {
  event_type?: string;
  label?: string | null;
  detected?: boolean;
  confidence?: number | null;
  count?: number | null;
  created_at?: string | null;
}

export interface NotifyMessage {
  id: number;
  level: "info" | "warn" | "alert" | "success";
  message: string;
  at: number;
}

type SensorHandler = (event: SensorEvent) => void;
type VisionHandler = (event: VisionEvent) => void;
type SlotHandler = (slot: Slot) => void;

/** 구독을 해지하는 함수. 화면이 사라질 때 호출하세요. */
export type Unsubscribe = () => void;

export interface ScenarioApi {
  /** 현재 슬롯 상태 (실시간으로 갱신됩니다) */
  slots: Slot[];
  /** 슬롯 ID로 바로 찾기 */
  slotOf: (slotId: string) => Slot | undefined;
  /** 백엔드 WebSocket 연결 여부 */
  connected: boolean;
  /** 화면에 띄울 알림 목록 (규칙의 notify 액션도 여기로 들어옵니다) */
  notices: NotifyMessage[];
  dismissNotice: (id: number) => void;

  /** 액추에이터 제어 — setActuator("actuator_01", "on", {frequency: 1000}) */
  setActuator: (
    slotId: string,
    state: string,
    value?: Record<string, unknown> | null
  ) => Promise<boolean>;

  /** 센서 보고 구독 */
  onSensor: (slotIds: string | string[], handler: SensorHandler) => Unsubscribe;
  /** 비전 감지 구독 — onVision(["person","cup"], e => ...) · null이면 전부 */
  onVision: (labels: string | string[] | null, handler: VisionHandler) => Unsubscribe;
  /** 슬롯 상태 변화 구독 (액추에이터 반영·센서 상태 모두) */
  onSlotChange: (slotIds: string | string[], handler: SlotHandler) => Unsubscribe;

  /** N초 뒤 실행 (화면이 살아 있는 동안만) */
  after: (seconds: number, callback: () => void) => number;
  /** after로 예약한 것을 취소 */
  cancel: (timerId: number) => void;
  /** 화면 알림 */
  notify: (message: string, level?: NotifyMessage["level"]) => void;
  /**
   * 브라우저를 닫아도 살아있는 타이머 (`POST /api/timers`).
   * 화면이 꺼져도 일어나야 하는 동작을 백엔드에 맡깁니다.
   *   serverTimer(60, { message: "기상 확인!" })
   *   serverTimer(10, { slot_id: "actuator_01", state: "off" })
   * 반복되는 자동화는 타이머가 아니라 규칙(RuleEditor)으로 만드세요.
   */
  serverTimer: (
    seconds: number,
    action: { slot_id: string; state: string; value?: Record<string, unknown> | null }
      | { message: string; level?: string },
    label?: string
  ) => Promise<boolean>;

  /** 슬롯 목록을 다시 읽어옵니다 */
  refresh: () => Promise<void>;
}

// ============================================================================
// 내부 구독 관리
// ============================================================================

function toList(value: string | string[] | null): string[] | null {
  if (value === null) return null;
  return Array.isArray(value) ? value : [value];
}

interface Subscription<H> {
  keys: string[] | null;
  handler: H;
}

/** 팀이 쓰는 유일한 훅입니다. */
export function useScenario(): ScenarioApi {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [connected, setConnected] = useState(false);
  const [notices, setNotices] = useState<NotifyMessage[]>([]);

  const sensorSubs = useRef<Set<Subscription<SensorHandler>>>(new Set());
  const visionSubs = useRef<Set<Subscription<VisionHandler>>>(new Set());
  const slotSubs = useRef<Set<Subscription<SlotHandler>>>(new Set());
  const timers = useRef<Set<number>>(new Set());
  const socketRef = useRef<WebSocket | null>(null);
  const noticeSeq = useRef(0);

  // --------------------------------------------------------------------
  // 슬롯 목록
  // --------------------------------------------------------------------

  const refresh = useCallback(async () => {
    const res = await apiFetch<Record<string, unknown>[]>("/api/slots?enabled_only=true");
    if (res.ok && Array.isArray(res.data)) {
      setSlots(sortSlots(res.data.map(normalizeSlot)));
    }
  }, []);

  useEffect(() => {
    // 이펙트 본문에서 곧바로 setState하지 않도록 다음 틱으로 미룬다
    const timer = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(timer);
  }, [refresh]);

  const applySlotPatch = useCallback((slotId: string, patch: Partial<Slot>) => {
    setSlots((prev) => {
      const index = prev.findIndex((s) => s.slot_id === slotId);
      if (index < 0) return prev;
      const next = [...prev];
      const updated = { ...next[index], ...patch };
      next[index] = updated;
      // 구독자에게는 갱신된 슬롯을 그대로 넘깁니다.
      slotSubs.current.forEach((sub) => {
        if (!sub.keys || sub.keys.includes(slotId)) sub.handler(updated);
      });
      return next;
    });
  }, []);

  const pushNotice = useCallback(
    (message: string, level: NotifyMessage["level"] = "info") => {
      noticeSeq.current += 1;
      const notice: NotifyMessage = {
        id: noticeSeq.current,
        level,
        message,
        at: Date.now(),
      };
      setNotices((prev) => [notice, ...prev].slice(0, 5));
    },
    []
  );

  // --------------------------------------------------------------------
  // WebSocket (연결·재연결은 SDK가 처리합니다)
  // --------------------------------------------------------------------

  useEffect(() => {
    let unmounted = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (unmounted) return;
      let socket: WebSocket;
      try {
        socket = new WebSocket(WS_URL);
      } catch {
        retryTimer = setTimeout(connect, 3000);
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (!unmounted) setConnected(true);
      };

      socket.onmessage = (event) => {
        if (unmounted) return;
        let message: Record<string, unknown>;
        try {
          message = JSON.parse(event.data as string);
        } catch {
          return;
        }
        handleMessage(message);
      };

      socket.onclose = () => {
        if (unmounted) return;
        setConnected(false);
        retryTimer = setTimeout(connect, 3000);
      };

      socket.onerror = () => socket.close();
    };

    const handleMessage = (message: Record<string, unknown>) => {
      const type = String(message.type ?? "");
      const slotId = String(message.slot_id ?? message.device_id ?? "");

      if (type === "device_state" && slotId) {
        applySlotPatch(slotId, {
          desired_state: (message.desired_state as string) ?? null,
          current_state: (message.current_state as string) ?? null,
          desired_value: message.desired_value,
          current_value: message.current_value,
          updated_at: (message.updated_at as string) ?? null,
        });
        return;
      }

      if (type === "sensor_reading" && slotId) {
        const value = asObject(message.value);
        applySlotPatch(slotId, {
          current_state: (message.current_state as string) ?? null,
          current_value: message.value,
          updated_at: (message.updated_at as string) ?? null,
        });

        const event: SensorEvent = {
          slot_id: slotId,
          value,
          number:
            value && typeof value.value === "number" ? (value.value as number) : null,
          unit: (message.unit as string) ?? null,
          current_state: (message.current_state as string) ?? null,
          pressed: value ? Boolean(value.pressed) : undefined,
          detected: value ? Boolean(value.detected) : undefined,
          updated_at: (message.updated_at as string) ?? null,
        };
        sensorSubs.current.forEach((sub) => {
          if (!sub.keys || sub.keys.includes(slotId)) sub.handler(event);
        });
        return;
      }

      if (type === "vision_event") {
        const event: VisionEvent = {
          event_type: (message.event_type as string) ?? undefined,
          label: (message.label as string) ?? null,
          detected: Boolean(message.detected),
          confidence: (message.confidence as number) ?? null,
          count: (message.count as number) ?? null,
          created_at: (message.created_at as string) ?? null,
        };
        const label = String(event.label ?? "").toLowerCase();
        visionSubs.current.forEach((sub) => {
          if (!sub.keys || sub.keys.includes(label)) sub.handler(event);
        });
        return;
      }

      if (type === "notify") {
        pushNotice(
          String(message.message ?? ""),
          (message.level as NotifyMessage["level"]) ?? "info"
        );
        return;
      }

      if (type === "slot_config") {
        // 하드웨어 구성이 바뀌었습니다 (pi 등록 또는 설정 화면 수정)
        void refresh();
      }
    };

    connect();
    return () => {
      unmounted = true;
      if (retryTimer) clearTimeout(retryTimer);
      socketRef.current?.close();
    };
  }, [applySlotPatch, pushNotice, refresh]);

  // 화면이 사라질 때 예약해 둔 타이머를 모두 정리합니다.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach((id) => clearTimeout(id));
      pending.clear();
    };
  }, []);

  // --------------------------------------------------------------------
  // 팀이 쓰는 API
  // --------------------------------------------------------------------

  const setActuator = useCallback(
    async (
      slotId: string,
      state: string,
      value: Record<string, unknown> | null = null
    ): Promise<boolean> => {
      const res = await apiFetch(`/api/devices/${slotId}/control`, {
        method: "POST",
        body: JSON.stringify({ desired_state: state, value }),
      });
      if (!res.ok) {
        pushNotice(res.errorMessage ?? `${slotId} 제어에 실패했습니다.`, "alert");
        return false;
      }
      // 낙관적 반영 — 하드웨어 보고가 오면 WebSocket이 다시 덮어씁니다.
      applySlotPatch(slotId, { desired_state: state, desired_value: value });
      return true;
    },
    [applySlotPatch, pushNotice]
  );

  const onSensor = useCallback(
    (slotIds: string | string[], handler: SensorHandler): Unsubscribe => {
      const sub: Subscription<SensorHandler> = { keys: toList(slotIds), handler };
      sensorSubs.current.add(sub);
      return () => {
        sensorSubs.current.delete(sub);
      };
    },
    []
  );

  const onVision = useCallback(
    (labels: string | string[] | null, handler: VisionHandler): Unsubscribe => {
      const keys = toList(labels);
      const sub: Subscription<VisionHandler> = {
        keys: keys ? keys.map((k) => k.toLowerCase()) : null,
        handler,
      };
      visionSubs.current.add(sub);
      return () => {
        visionSubs.current.delete(sub);
      };
    },
    []
  );

  const onSlotChange = useCallback(
    (slotIds: string | string[], handler: SlotHandler): Unsubscribe => {
      const sub: Subscription<SlotHandler> = { keys: toList(slotIds), handler };
      slotSubs.current.add(sub);
      return () => {
        slotSubs.current.delete(sub);
      };
    },
    []
  );

  const after = useCallback((seconds: number, callback: () => void): number => {
    const id = window.setTimeout(() => {
      timers.current.delete(id);
      callback();
    }, Math.max(0, seconds) * 1000);
    timers.current.add(id);
    return id;
  }, []);

  const cancel = useCallback((timerId: number) => {
    window.clearTimeout(timerId);
    timers.current.delete(timerId);
  }, []);

  const serverTimer = useCallback(
    async (
      seconds: number,
      action:
        | { slot_id: string; state: string; value?: Record<string, unknown> | null }
        | { message: string; level?: string },
      label?: string
    ): Promise<boolean> => {
      const body =
        "slot_id" in action
          ? {
              action: "set_actuator",
              slot_id: action.slot_id,
              state: action.state,
              value: action.value ?? null,
            }
          : {
              action: "notify",
              message: action.message,
              level: action.level ?? "info",
            };

      const res = await apiFetch("/api/timers", {
        method: "POST",
        body: JSON.stringify({ seconds, action: body, label: label ?? null }),
      });
      if (!res.ok) {
        pushNotice(res.errorMessage ?? "서버 타이머를 만들지 못했습니다.", "alert");
        return false;
      }
      return true;
    },
    [pushNotice]
  );

  const slotOf = useCallback(
    (slotId: string) => slots.find((s) => s.slot_id === slotId),
    [slots]
  );

  const dismissNotice = useCallback((id: number) => {
    setNotices((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return useMemo(
    () => ({
      slots,
      slotOf,
      connected,
      notices,
      dismissNotice,
      setActuator,
      onSensor,
      onVision,
      onSlotChange,
      after,
      cancel,
      notify: pushNotice,
      serverTimer,
      refresh,
    }),
    [
      slots,
      slotOf,
      connected,
      notices,
      dismissNotice,
      setActuator,
      onSensor,
      onVision,
      onSlotChange,
      after,
      cancel,
      pushNotice,
      serverTimer,
      refresh,
    ]
  );
}
