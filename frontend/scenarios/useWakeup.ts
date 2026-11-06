/**
 * wakeup 팀 시나리오 (scenarios/useWakeup.ts)
 * =============================================================================
 * 1차 완성본의 "알람 → 기상 미션 → 2차 수면 방지"를 **프론트엔드에서** 돌립니다.
 * 백엔드는 슬롯을 중계할 뿐 미션 규칙을 모릅니다 (docs/부록F 9-2절).
 *
 * 다른 팀은 이 파일을 복사해서 자기 시나리오로 고쳐 쓰면 됩니다.
 * 판정 규칙은 scenarios/wakeupEngine.ts에 따로 있어 그대로 테스트할 수 있습니다.
 *
 * ⚠️ 브라우저 탭을 닫으면 미션이 멈춥니다. 화면 없이도 일어나야 하는 것
 *    (정해진 시각에 알람, 미션 성공 60초 뒤 확인)은 규칙과 serverTimer로 백엔드에 맡깁니다.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ScenarioApi, useScenario } from "@/lib/scenario";
import { isOnState, numberFrom, sensorNumber } from "@/lib/slots";
import {
  IDLE_MISSION,
  bedShouldShake,
  configFromEnv,
  deviceConfigFromEnv,
  judgePattern,
  judgeVision,
  nextBedAngle,
  roundDurationSeconds,
  startMission,
  timeoutRound,
} from "@/scenarios/wakeupEngine";
import type {
  DeviceConfig,
  MissionConfig,
  MissionOutcome,
  MissionState,
  PatternFeedback,
} from "@/scenarios/wakeupEngine";

/** wakeup 팀 하드웨어 배치 — pi/slot_map.py와 같은 슬롯을 가리킵니다. */
export const WAKEUP_SLOTS = {
  buzzer: "actuator_01",
  curtain: "actuator_02",   // 커튼 서보
  bed: "actuator_03",       // 모션 베드 서보
  light: "actuator_04",     // 조명 (네오픽셀)
  button: "sensor_01",
  pressure: "sensor_02",    // 침대 압력 센서
} as const;

export interface WakeupPopup {
  message: string;
  timeLeft: number;
}

export interface WakeupApi {
  scenario: ScenarioApi;
  mission: MissionState;
  /** 이번 라운드에 남은 시간(초) */
  remainingSeconds: number;
  popup: WakeupPopup | null;
  ringing: boolean;
  startAlarm: () => Promise<void>;
  stopAlarm: () => Promise<void>;
  confirmWakeup: () => void;
  /**
   * 패턴 미션 — 화면에 그린 패턴을 판정에 넘깁니다 (그리기 판이 손을 뗄 때 부릅니다).
   * 맞음·틀림을 돌려주므로 판이 잠깐 색으로 보여 줄 수 있습니다.
   */
  submitPattern: (drawn: number[]) => PatternFeedback;
  config: MissionConfig;
  /** 조명·커튼·모션 베드 설정 (.env의 NEXT_PUBLIC_WAKEUP_*) */
  device: DeviceConfig;
  /** 침대 압력 (센서 값 그대로, 없으면 null) */
  pressure: number | null;
  /** 지금 모션 베드를 흔드는 중인지 */
  bedShaking: boolean;
  /** 조명이 켜져 있는지 */
  lightOn: boolean;
  /** 커튼 서보의 지금 각도 (보고 전이면 null) */
  curtainAngle: number | null;
  /** 이 배치표에 그 부품이 등록돼 있는지 — 없으면 명령을 보내지 않습니다 */
  hasSlot: (slotId: string) => boolean;
  /** 알람 끄기 + 조명 끄기 + 모션 베드 0° (제어 화면의 "모두 끄기") */
  stopAll: () => Promise<void>;
}

export function useWakeup(): WakeupApi {
  const scenario = useScenario();
  const { slots, slotOf, setActuator, notify, onVision, onSensor, onSlotChange, serverTimer } =
    scenario;

  // Next.js는 `process.env.NEXT_PUBLIC_X`처럼 **직접 쓴 것만** 브라우저 코드에 넣어 줍니다.
  // process.env를 통째로 넘기면 브라우저에서는 빈 객체가 되어 설정이 조용히 무시됩니다.
  const [config] = useState<MissionConfig>(() =>
    configFromEnv({
      NEXT_PUBLIC_MISSION_MODE: process.env.NEXT_PUBLIC_MISSION_MODE,
      NEXT_PUBLIC_MISSION_REQUIRED_WINS: process.env.NEXT_PUBLIC_MISSION_REQUIRED_WINS,
      NEXT_PUBLIC_MISSION_ROUND_TIMEOUT_SECONDS:
        process.env.NEXT_PUBLIC_MISSION_ROUND_TIMEOUT_SECONDS,
      NEXT_PUBLIC_MISSION_ROUND_GRACE_SECONDS:
        process.env.NEXT_PUBLIC_MISSION_ROUND_GRACE_SECONDS,
      NEXT_PUBLIC_MISSION_MIN_CONFIDENCE: process.env.NEXT_PUBLIC_MISSION_MIN_CONFIDENCE,
      NEXT_PUBLIC_MISSION_OBJECT_TARGETS: process.env.NEXT_PUBLIC_MISSION_OBJECT_TARGETS,
      NEXT_PUBLIC_MISSION_OBJECT_REQUIRED_HITS:
        process.env.NEXT_PUBLIC_MISSION_OBJECT_REQUIRED_HITS,
      NEXT_PUBLIC_WAKEUP_POPUP_DELAY_SECONDS:
        process.env.NEXT_PUBLIC_WAKEUP_POPUP_DELAY_SECONDS,
      NEXT_PUBLIC_WAKEUP_CONFIRM_TIMEOUT_SECONDS:
        process.env.NEXT_PUBLIC_WAKEUP_CONFIRM_TIMEOUT_SECONDS,
      NEXT_PUBLIC_PATTERN_LENGTH: process.env.NEXT_PUBLIC_PATTERN_LENGTH,
      NEXT_PUBLIC_PATTERN_STEP_SECONDS: process.env.NEXT_PUBLIC_PATTERN_STEP_SECONDS,
      NEXT_PUBLIC_PATTERN_KEEP_VISIBLE: process.env.NEXT_PUBLIC_PATTERN_KEEP_VISIBLE,
    })
  );
  const [device] = useState<DeviceConfig>(() =>
    deviceConfigFromEnv({
      NEXT_PUBLIC_WAKEUP_BED_PRESSURE: process.env.NEXT_PUBLIC_WAKEUP_BED_PRESSURE,
      NEXT_PUBLIC_WAKEUP_BED_ANGLE: process.env.NEXT_PUBLIC_WAKEUP_BED_ANGLE,
      NEXT_PUBLIC_WAKEUP_BED_SHAKE_SECONDS: process.env.NEXT_PUBLIC_WAKEUP_BED_SHAKE_SECONDS,
      NEXT_PUBLIC_WAKEUP_CURTAIN_OPEN_ANGLE: process.env.NEXT_PUBLIC_WAKEUP_CURTAIN_OPEN_ANGLE,
      NEXT_PUBLIC_WAKEUP_CURTAIN_CLOSE_ANGLE: process.env.NEXT_PUBLIC_WAKEUP_CURTAIN_CLOSE_ANGLE,
      NEXT_PUBLIC_WAKEUP_LIGHT_COLOR: process.env.NEXT_PUBLIC_WAKEUP_LIGHT_COLOR,
      NEXT_PUBLIC_WAKEUP_LIGHT_BRIGHTNESS: process.env.NEXT_PUBLIC_WAKEUP_LIGHT_BRIGHTNESS,
    })
  );
  const [mission, setMission] = useState<MissionState>(IDLE_MISSION);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [popup, setPopup] = useState<WakeupPopup | null>(null);

  // 콜백 안에서 최신 상태를 읽어야 하므로 ref로도 들고 있습니다.
  const missionRef = useRef<MissionState>(IDLE_MISSION);
  const roundTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const guardTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const confirmedRef = useRef(false);

  const buzzer = slots.find((s) => s.slot_id === WAKEUP_SLOTS.buzzer);
  const ringing = isOnState(buzzer?.current_state ?? buzzer?.desired_state);

  // 침실 장치 — 배치표에 없는 부품에는 명령을 보내지 않습니다 (오류 알림이 쏟아지지 않게)
  const hasSlot = useCallback((slotId: string) => slotOf(slotId) !== undefined, [slotOf]);
  const lightSlot = slotOf(WAKEUP_SLOTS.light);
  const curtainSlot = slotOf(WAKEUP_SLOTS.curtain);
  const pressure = sensorNumber(slotOf(WAKEUP_SLOTS.pressure)?.current_value);
  const lightOn = isOnState(lightSlot?.current_state ?? lightSlot?.desired_state);
  const curtainAngle = numberFrom(
    curtainSlot?.current_value ?? curtainSlot?.desired_value, ["angle"], Number.NaN
  );
  const bedShaking =
    hasSlot(WAKEUP_SLOTS.bed) &&
    bedShouldShake(mission.active, pressure, device.bedPressureThreshold);

  // 콜백 안에서 최신 슬롯을 읽기 위한 ref
  const hasSlotRef = useRef(hasSlot);
  useEffect(() => {
    hasSlotRef.current = hasSlot;
  }, [hasSlot]);

  const applyMission = useCallback((next: MissionState) => {
    missionRef.current = next;
    setMission(next);
  }, []);

  const clearGuards = useCallback(() => {
    guardTimers.current.forEach((id) => clearTimeout(id));
    guardTimers.current = [];
  }, []);

  // --------------------------------------------------------------------
  // 라운드 제한 시간
  // --------------------------------------------------------------------

  // 제한 시간이 지나면 다음 라운드를 열고 타이머를 다시 겁니다.
  // 자기 자신을 부르는 구조라, 타이머가 터질 때 최신 함수를 읽도록 ref를 거칩니다.
  const armRoundTimerRef = useRef<(state: MissionState) => void>(() => {});
  const armRoundTimer = useCallback(
    (state: MissionState) => armRoundTimerRef.current(state),
    []
  );

  useEffect(() => {
    armRoundTimerRef.current = (state: MissionState) => {
      if (roundTimer.current) clearTimeout(roundTimer.current);
      if (!state.active) {
        setRemainingSeconds(0);
        return;
      }
      const seconds = roundDurationSeconds(state, config);
      setRemainingSeconds(seconds);
      roundTimer.current = setTimeout(() => {
        const outcome = timeoutRound(missionRef.current, config, Date.now());
        if (outcome.kind === "result") {
          applyMission(outcome.state);
          notify(outcome.message, "warn");
          armRoundTimerRef.current(outcome.state);
        }
      }, seconds * 1000);
    };
  }, [applyMission, config, notify]);

  // 남은 시간 표시용 카운트다운
  useEffect(() => {
    if (!mission.active) return;
    const ticker = setInterval(
      () => setRemainingSeconds((prev) => Math.max(0, prev - 1)),
      1000
    );
    return () => clearInterval(ticker);
  }, [mission.active, mission.round]);

  // --------------------------------------------------------------------
  // 2차 수면 방지 — 미션 성공 후 일정 시간 뒤 기상 확인
  // --------------------------------------------------------------------

  const startSecondSleepGuard = useCallback(() => {
    clearGuards();
    confirmedRef.current = false;

    // 화면이 열려 있으면 팝업으로 확인을 받습니다.
    const popupTimer = setTimeout(() => {
      setPopup({
        message: "기상 확인: 2차 수면 방지를 위해 화면의 버튼이나 기상 확인 버튼을 눌러 주세요!",
        timeLeft: config.confirmTimeoutSeconds,
      });

      const expireTimer = setTimeout(() => {
        if (confirmedRef.current) return;
        setPopup(null);
        notify("기상 확인 시간 초과로 알람이 다시 동작합니다!", "alert");
        void setActuator(WAKEUP_SLOTS.buzzer, "on", { volume: 90, frequency: 1200 });
      }, config.confirmTimeoutSeconds * 1000);
      guardTimers.current.push(expireTimer);
    }, config.popupDelaySeconds * 1000);
    guardTimers.current.push(popupTimer);

    // 탭을 닫아도 확인 알림이 뜨도록 백엔드에도 같은 시각을 예약해 둡니다.
    void serverTimer(
      config.popupDelaySeconds + config.confirmTimeoutSeconds,
      { message: "기상 확인: 아직 일어나지 않았다면 알람이 다시 울립니다!", level: "warn" },
      "2차 수면 방지 확인"
    );
  }, [clearGuards, config, notify, serverTimer, setActuator]);

  const confirmWakeup = useCallback(() => {
    confirmedRef.current = true;
    clearGuards();
    setPopup(null);
    notify("기상 확인 완료! 활기찬 하루를 시작하세요.", "success");
  }, [clearGuards, notify]);

  // 팝업 카운트다운
  useEffect(() => {
    if (!popup) return;
    const ticker = setInterval(() => {
      setPopup((prev) =>
        prev && prev.timeLeft > 1 ? { ...prev, timeLeft: prev.timeLeft - 1 } : null
      );
    }, 1000);
    return () => clearInterval(ticker);
  }, [popup?.message]);   // eslint-disable-line react-hooks/exhaustive-deps

  // --------------------------------------------------------------------
  // 미션 시작 / 중단
  // --------------------------------------------------------------------

  const beginMission = useCallback(
    (reason: string) => {
      if (missionRef.current.active) return;
      const { state, message } = startMission(config, Date.now(), reason);
      applyMission(state);
      armRoundTimer(state);
      notify(`기상 미션을 시작합니다! ${message}`, "info");

      // 조명을 켜고 커튼을 엽니다 (모션 베드는 아래 효과가 압력을 보고 판단합니다)
      if (hasSlotRef.current(WAKEUP_SLOTS.light)) {
        void setActuator(WAKEUP_SLOTS.light, "on", {
          color: device.lightColor,
          brightness: device.lightBrightness,
        });
      }
      if (hasSlotRef.current(WAKEUP_SLOTS.curtain)) {
        void setActuator(WAKEUP_SLOTS.curtain, "move", { angle: device.curtainOpenAngle });
      }
    },
    [applyMission, armRoundTimer, config, device, notify, setActuator]
  );

  const cancelMission = useCallback(() => {
    if (roundTimer.current) clearTimeout(roundTimer.current);
    applyMission(IDLE_MISSION);
    setRemainingSeconds(0);
  }, [applyMission]);

  const startAlarm = useCallback(async () => {
    await setActuator(WAKEUP_SLOTS.buzzer, "on", { volume: 80, frequency: 1000 });
  }, [setActuator]);

  const stopAlarm = useCallback(async () => {
    cancelMission();
    clearGuards();
    setPopup(null);
    await setActuator(WAKEUP_SLOTS.buzzer, "off");
  }, [cancelMission, clearGuards, setActuator]);

  const stopAll = useCallback(async () => {
    await stopAlarm();
    if (hasSlotRef.current(WAKEUP_SLOTS.light)) await setActuator(WAKEUP_SLOTS.light, "off");
    if (hasSlotRef.current(WAKEUP_SLOTS.bed)) {
      await setActuator(WAKEUP_SLOTS.bed, "move", { angle: 0 });
    }
  }, [stopAlarm, setActuator]);

  // --------------------------------------------------------------------
  // 모션 베드 — 미션 중 아직 누워 있으면(압력 ≥ 기준) 0° ↔ 설정 각도로 흔들기
  // 압력이 기준 아래로 내려가거나 미션이 끝나면 멈추고 0°로 돌아갑니다.
  // --------------------------------------------------------------------

  useEffect(() => {
    if (!bedShaking) return;
    let angle = 0;
    const step = () => {
      angle = nextBedAngle(angle, device.bedAngle);
      void setActuator(WAKEUP_SLOTS.bed, "move", { angle });
    };
    step();
    const ticker = setInterval(step, device.bedShakeSeconds * 1000);
    return () => {
      clearInterval(ticker);
      void setActuator(WAKEUP_SLOTS.bed, "move", { angle: 0 });
    };
  }, [bedShaking, device, setActuator]);

  // --------------------------------------------------------------------
  // 판정 결과 처리 — 카메라(비전)와 그리기 판(패턴)이 같은 길을 씁니다
  // --------------------------------------------------------------------

  const handleOutcome = useCallback(
    (outcome: Exclude<MissionOutcome, { kind: "ignored" }>) => {
      applyMission(outcome.state);

      if (outcome.kind === "success") {
        if (roundTimer.current) clearTimeout(roundTimer.current);
        setRemainingSeconds(0);
        notify(outcome.message, "success");
        void setActuator(WAKEUP_SLOTS.buzzer, "off");
        startSecondSleepGuard();
        return;
      }

      notify(outcome.message, outcome.result === "win" ? "success" : "info");
      armRoundTimer(outcome.state);
    },
    [applyMission, armRoundTimer, notify, setActuator, startSecondSleepGuard]
  );

  const submitPattern = useCallback(
    (drawn: number[]): PatternFeedback => {
      const outcome = judgePattern(missionRef.current, config, drawn, Date.now());
      if (outcome.kind === "ignored") {
        return outcome.reason === "TOO_SHORT" ? "too-short" : "not-ready";
      }
      handleOutcome(outcome);
      if (outcome.kind === "success") return "success";
      return outcome.result === "win" ? "correct" : "wrong";
    },
    [config, handleOutcome]
  );

  // --------------------------------------------------------------------
  // 구독 — 부저가 울리면 미션 시작, 비전 이벤트로 판정, 버튼으로 기상 확인
  // --------------------------------------------------------------------

  useEffect(
    () =>
      onSlotChange(WAKEUP_SLOTS.buzzer, (slot) => {
        const on = isOnState(slot.current_state ?? slot.desired_state);
        if (on) beginMission("alarm");
        else if (missionRef.current.active) cancelMission();
      }),
    [onSlotChange, beginMission, cancelMission]
  );

  useEffect(
    () =>
      onVision(null, (event) => {
        const outcome = judgeVision(
          missionRef.current,
          config,
          { label: event.label, detected: Boolean(event.detected), confidence: event.confidence },
          Date.now()
        );

        if (outcome.kind === "ignored") {
          // 사물 연속 감지 횟수처럼 무시된 이벤트도 상태는 이어져야 합니다.
          if (outcome.state !== missionRef.current) applyMission(outcome.state);
          return;
        }
        handleOutcome(outcome);
      }),
    [onVision, applyMission, config, handleOutcome]
  );

  useEffect(
    () =>
      onSensor(WAKEUP_SLOTS.button, (event) => {
        // 물리 버튼도 화면의 확인 버튼과 같은 역할을 합니다.
        if (event.pressed) confirmWakeup();
      }),
    [onSensor, confirmWakeup]
  );

  // 화면이 사라질 때 타이머 정리
  useEffect(() => {
    const timers = guardTimers;
    return () => {
      if (roundTimer.current) clearTimeout(roundTimer.current);
      timers.current.forEach((id) => clearTimeout(id));
    };
  }, []);

  return {
    scenario,
    mission,
    remainingSeconds,
    popup,
    ringing,
    startAlarm,
    stopAlarm,
    confirmWakeup,
    submitPattern,
    config,
    device,
    pressure,
    bedShaking,
    lightOn,
    curtainAngle: Number.isFinite(curtainAngle) ? curtainAngle : null,
    hasSlot,
    stopAll,
  };
}
