/**
 * study 팀 시나리오 훅 (scenarios/useStudy.ts) — ★ study 팀이 고치는 파일
 * ============================================================================
 * 카메라가 보낸 것을 받아 `studyEngine.ts`에 넣고, 화면이 쓸 값을 돌려줍니다.
 *
 *   vision/detectors/study_focus.py  →  백엔드  →  useScenario().onVision
 *        →  studyEngine.classify()   →  이 훅  →  app/study/page.tsx
 *
 * 판정 규칙은 여기가 아니라 `studyEngine.ts`에 있습니다 (브라우저 없이 시험하려고).
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useScenario } from "@/lib/scenario";
import type { ScenarioApi } from "@/lib/scenario";
import {
  STORAGE_KEY,
  applyMeasure,
  classify,
  focusScore,
  isCameraTooFar,
  newSession,
  parseMeasure,
  restoreSession,
  serializeSession,
  summarize,
} from "./studyEngine";
import type { FocusMeasure, SessionState, StudyState } from "./studyEngine";

/** 카메라 소식이 이 시간(초) 동안 없으면 "신호 없음"으로 봅니다. */
export const SIGNAL_TIMEOUT_SECONDS = 12;

/** 졸음 알림을 이 시간(초) 안에는 다시 띄우지 않습니다. */
export const ALERT_COOLDOWN_SECONDS = 30;

/** 화면이 뜨기 전에 쓰는 빈 기록. 서버와 브라우저가 같은 것을 그리게 하려고 둡니다. */
const EMPTY_SESSION: SessionState = newSession(0);

function loadSession(now: number): SessionState {
  if (typeof window === "undefined") return newSession(now);
  try {
    return restoreSession(window.localStorage.getItem(STORAGE_KEY), now) ?? newSession(now);
  } catch {
    // 사생활 보호 모드 등에서 localStorage를 못 쓸 수 있습니다 — 그래도 동작해야 합니다
    return newSession(now);
  }
}

function saveSession(session: SessionState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, serializeSession(session));
  } catch {
    /* 저장이 안 돼도 화면은 그대로 동작합니다 */
  }
}

export interface StudyApi {
  /**
   * 키트 SDK 그대로. **화면에서는 이것을 쓰세요.**
   *
   * ⚠️ `useScenario()`는 부를 때마다 **새 인스턴스**(WebSocket·구독·알림이 따로)를
   *    만듭니다. 화면에서 또 부르면 여기서 띄운 알림이 화면에 나타나지 않습니다.
   *    한 화면에서는 `useStudy()` 하나만 부르고, 슬롯·알림은 이 `scenario`에서 꺼내 쓰세요.
   */
  scenario: ScenarioApi;
  /** 카메라가 마지막으로 보낸 측정값 (아직 없으면 null) */
  measure: FocusMeasure | null;
  /** 지금 상태 */
  state: StudyState;
  /** 집중도 점수 0~100 (판정할 수 없으면 null) */
  score: number | null;
  session: SessionState;
  summary: ReturnType<typeof summarize>;
  /** 백엔드 WebSocket 연결 여부 */
  connected: boolean;
  /** 카메라에서 소식이 끊겼는가 */
  signalLost: boolean;
  /** 이 사람의 '정면'을 아직 배우는 중인가 */
  calibrating: boolean;
  /** 얼굴이 작게 잡혀 눈을 제대로 못 재는가 */
  cameraTooFar: boolean;
  /** 지금까지 졸았다고 본 횟수 */
  drowsyEpisodes: number;
  /** 세션을 처음부터 다시 */
  resetSession: () => void;
}

export function useStudy(): StudyApi {
  const scenario = useScenario();
  const { connected, onVision, notify } = scenario;

  const [measure, setMeasure] = useState<FocusMeasure | null>(null);
  const [lastEventAt, setLastEventAt] = useState<number>(0);

  // ⚠️ 서버에서 미리 그린 HTML과 브라우저가 그린 것이 다르면 React가 화면을 버립니다.
  //    localStorage와 현재 시각은 서버에 없으므로, **처음에는 빈 값으로 그리고**
  //    화면이 뜬 뒤에 불러옵니다. (안 그러면 "Text content did not match" 오류)
  const [session, setSession] = useState<SessionState | null>(null);
  // 렌더 중에 Date.now()를 부르면 그릴 때마다 값이 달라집니다(React 19가 막습니다).
  // 그래서 '지금'을 상태로 들고, 아래 타이머가 2초마다 갱신합니다. 0이면 아직 화면이 뜨기 전.
  const [now, setNow] = useState<number>(0);

  const lastAlertRef = useRef(0);

  // ---- 카메라가 보낸 측정값 받기 ------------------------------------------
  useEffect(() => {
    const stop = onVision(["face_visible", "no_face"], (event) => {
      const now = Date.now();
      // 어느 라벨이든 "카메라가 살아 있다"는 신호입니다
      setLastEventAt(now);
      // 측정값은 **face_visible에만** 실려 옵니다. 다른 라벨의 extra를 읽으면
      // 빈 값으로 덮어써서 화면이 "확인 중"으로 되돌아갑니다.
      if (event.label !== "face_visible") return;

      const next = parseMeasure(event.extra);
      setMeasure(next);
      setSession((prev) => {
        const updated = applyMeasure(prev ?? loadSession(now), next, now);
        saveSession(updated);
        return updated;
      });
    });
    return stop;
  }, [onVision]);

  // ---- 졸음은 face_visible을 기다리지 않고 바로 알립니다 --------------------
  useEffect(() => {
    const stop = onVision("eyes_closed", (event) => {
      if (!event.detected) return;
      const now = Date.now();
      if (now - lastAlertRef.current < ALERT_COOLDOWN_SECONDS * 1000) return;
      lastAlertRef.current = now;
      notify("졸고 있는 것 같아요. 잠깐 일어나서 스트레칭해 보세요.", "warn");
    });
    return stop;
  }, [onVision, notify]);

  // ---- 화면이 뜬 뒤에 저장된 기록을 불러오고, 2초마다 '지금'을 갱신합니다 ----
  //
  //   localStorage와 현재 시각은 **브라우저에만** 있습니다. 서버가 미리 그릴 때는 없으므로,
  //   그릴 때 바로 읽으면 두 결과가 달라져 React가 화면을 버립니다.
  //   그래서 화면이 뜬 **직후**(타이머 콜백 안에서) 읽습니다.
  useEffect(() => {
    const tick = () => {
      const at = Date.now();
      setNow(at);
      setSession((prev) => prev ?? loadSession(at));
    };
    const first = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, 2000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, []);

  const resetSession = useCallback(() => {
    const fresh = newSession(Date.now());
    setNow(fresh.startedAt);
    setSession(fresh);
    setMeasure(null);
    lastAlertRef.current = 0;
    saveSession(fresh);
  }, []);

  const signalLost =
    now > 0 && lastEventAt > 0 && (now - lastEventAt) / 1000 > SIGNAL_TIMEOUT_SECONDS;

  // 화면이 뜨기 전에는 빈 기록으로 그립니다 (서버가 그린 것과 같아야 하므로)
  const shown = session ?? EMPTY_SESSION;

  const state: StudyState = useMemo(() => {
    if (!measure || signalLost) return "unknown";
    return classify(measure);
  }, [measure, signalLost]);

  return {
    scenario,
    measure,
    state,
    score: measure && !signalLost ? focusScore(measure) : null,
    session: shown,
    summary: summarize(shown, now > 0 ? now : shown.startedAt),
    connected,
    signalLost,
    calibrating: !!measure && measure.face && !measure.calibrated,
    cameraTooFar: !!measure && isCameraTooFar(measure),
    drowsyEpisodes: shown.drowsyEpisodes,
    resetSession,
  };
}

/**
 * 졸면 장치를 움직이고 싶을 때 쓰는 훅 — **기본은 꺼져 있습니다.**
 *
 * ⚠️ 같은 일을 `/kit` 규칙 편집기로도 할 수 있습니다 (코드 없이).
 *    **둘 중 하나만 쓰세요.** 둘 다 켜면 서로 껐다 켰다 하며 싸웁니다.
 *
 *    규칙 편집기로 하려면:  트리거 `eyes_closed` → 액션 `actuator_03` 켜기
 */
export function useStudyActuators(
  /** `useStudy().scenario.setActuator`를 그대로 넘기세요 (여기서 useScenario를 또 부르면 안 됩니다) */
  setActuator: ScenarioApi["setActuator"],
  state: StudyState,
  enabled: boolean,
  slots: { drowsy?: string; away?: string } = {}
): void {
  const lastRef = useRef<StudyState | null>(null);

  useEffect(() => {
    if (!enabled || state === lastRef.current) return;
    const previous = lastRef.current;
    lastRef.current = state;

    const drowsySlot = slots.drowsy;
    let stopBuzz = 0;
    if (state === "drowsy" && drowsySlot) {
      void setActuator(drowsySlot, "on", { intensity: 70 });
      // 3초만 울리고 끕니다 (계속 울리면 신경만 쓰입니다)
      stopBuzz = window.setTimeout(() => void setActuator(drowsySlot, "off"), 3000);
    }

    const awaySlot = slots.away;
    if (awaySlot && state === "away") {
      void setActuator(awaySlot, "off");
    }
    if (awaySlot && previous === "away" && state !== "away") {
      void setActuator(awaySlot, "on");
    }

    // 화면을 떠나면 예약해 둔 '끄기'도 취소합니다
    return () => {
      if (stopBuzz) window.clearTimeout(stopBuzz);
    };
  }, [state, enabled, slots.drowsy, slots.away, setActuator]);
}
