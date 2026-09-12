/**
 * 기상 미션 판정 엔진 (scenarios/wakeupEngine.ts) — wakeup 팀 시나리오
 * =============================================================================
 * 1차 완성본에서 백엔드(services/trigger_service.py)가 하던 판정을 그대로 옮겨 온 것입니다.
 * 플랫폼 키트는 "시나리오 로직은 프론트엔드가 맡는다"이므로(docs/부록F 9-2절),
 * 이 파일에는 **React도 화면도 없습니다** — 순수 판정 규칙만 있어서 그대로 테스트할 수 있습니다.
 *
 *   node --experimental-strip-types scenarios/wakeupEngine.test.ts
 *
 * 다른 팀이 자기 시나리오를 만들 때 이 파일을 본보기로 삼으면 됩니다.
 */

export const RPS_HANDS = ["rock", "paper", "scissors"] as const;
export type Hand = (typeof RPS_HANDS)[number];

/** key가 value를 이깁니다. */
const BEATS: Record<Hand, Hand> = {
  rock: "scissors",
  scissors: "paper",
  paper: "rock",
};

/** AI가 낸 손을 이기려면 사용자가 내야 하는 손. */
export const WINNING_HAND: Record<Hand, Hand> = {
  scissors: "rock",
  paper: "scissors",
  rock: "paper",
};

export const HAND_KO: Record<Hand, string> = {
  rock: "주먹(바위)",
  paper: "보",
  scissors: "가위",
};

export type RoundResult = "win" | "lose" | "draw" | "timeout" | "object";
export type MissionMode = "auto" | "rps" | "object";

export interface MissionConfig {
  mode: MissionMode;
  requiredWins: number;
  roundTimeoutSeconds: number;
  /** 새 라운드 직후 유예 시간 — 직전 손이 다시 들어와 억울하게 지는 것을 막습니다. */
  roundGraceSeconds: number;
  minConfidence: number;
  objectTargets: string[];
  objectRequiredHits: number;
  /** 미션 성공 후 기상 확인 팝업까지의 시간 */
  popupDelaySeconds: number;
  /** 팝업이 뜬 뒤 확인을 기다리는 시간 */
  confirmTimeoutSeconds: number;
}

export const DEFAULT_MISSION_CONFIG: MissionConfig = {
  mode: "auto",
  requiredWins: 2,
  roundTimeoutSeconds: 15,
  roundGraceSeconds: 2,
  minConfidence: 0.6,
  objectTargets: ["person", "bottle", "cup", "book", "cell phone"],
  objectRequiredHits: 2,
  popupDelaySeconds: 25,
  confirmTimeoutSeconds: 15,
};

export interface MissionState {
  active: boolean;
  round: number;
  wins: number;
  requiredWins: number;
  mode: MissionMode;
  aiHand: Hand | null;
  expectedHand: Hand | null;
  objectHits: number;
  /** 이번 라운드가 시작된 시각(ms) — 유예 시간 판정에 씁니다 */
  roundStartedAt: number;
  lastResult: RoundResult | null;
  lastResultMessage: string | null;
  reason: string | null;
}

export const IDLE_MISSION: MissionState = {
  active: false,
  round: 0,
  wins: 0,
  requiredWins: DEFAULT_MISSION_CONFIG.requiredWins,
  mode: DEFAULT_MISSION_CONFIG.mode,
  aiHand: null,
  expectedHand: null,
  objectHits: 0,
  roundStartedAt: 0,
  lastResult: null,
  lastResultMessage: null,
  reason: null,
};

/** 비전 클라이언트가 보낸 이벤트 하나. */
export interface VisionInput {
  label: string | null | undefined;
  detected: boolean;
  confidence?: number | null;
}

/** 판정 결과 — 화면이 무엇을 해야 하는지까지 알려 줍니다. */
export type MissionOutcome =
  | { kind: "ignored"; reason: string; state: MissionState }
  | { kind: "result"; state: MissionState; result: RoundResult; message: string }
  | { kind: "success"; state: MissionState; evidence: string; message: string };

function isHand(label: string): label is Hand {
  return (RPS_HANDS as readonly string[]).includes(label);
}

/**
 * 새 라운드를 엽니다. 직전과 같은 손은 내지 않습니다
 * (같은 손이 반복되면 사용자가 판정 결과를 헷갈립니다).
 */
export function beginRound(
  state: MissionState,
  config: MissionConfig,
  now: number,
  pick: (choices: Hand[]) => Hand = (choices) =>
    choices[Math.floor(Math.random() * choices.length)]
): { state: MissionState; message: string } {
  const choices = RPS_HANDS.filter((hand) => hand !== state.aiHand);
  const aiHand = pick(choices.length ? [...choices] : [...RPS_HANDS]);

  const next: MissionState = {
    ...state,
    active: true,
    round: state.round + 1,
    aiHand,
    expectedHand: WINNING_HAND[aiHand],
    objectHits: 0,
    roundStartedAt: now,
  };
  return {
    state: next,
    message:
      `AI가 '${HAND_KO[aiHand]}'을(를) 냈습니다! ` +
      `'${HAND_KO[WINNING_HAND[aiHand]]}'을(를) 내서 이기세요.`,
  };
}

/** 미션을 시작합니다 (알람이 울리기 시작할 때). */
export function startMission(
  config: MissionConfig,
  now: number,
  reason: string,
  pick?: (choices: Hand[]) => Hand
): { state: MissionState; message: string } {
  const base: MissionState = {
    ...IDLE_MISSION,
    active: true,
    mode: config.mode,
    requiredWins: config.requiredWins,
    reason,
  };
  return beginRound(base, config, now, pick);
}

/**
 * 비전 이벤트 하나를 판정합니다.
 * 백엔드 trigger_service.handle_vision_event와 같은 규칙입니다.
 */
export function judgeVision(
  state: MissionState,
  config: MissionConfig,
  input: VisionInput,
  now: number,
  pick?: (choices: Hand[]) => Hand
): MissionOutcome {
  if (!state.active) {
    return { kind: "ignored", reason: "MISSION_INACTIVE", state };
  }

  const label = String(input.label ?? "").trim().toLowerCase();

  if (!input.detected || !label) {
    // 사물이 사라지면 연속 감지를 처음부터 다시 셉니다.
    if (label && !isHand(label)) {
      return { kind: "ignored", reason: "NOT_DETECTED", state: { ...state, objectHits: 0 } };
    }
    return { kind: "ignored", reason: "NOT_DETECTED", state };
  }

  // 새 라운드 직후 유예: 직전 손이 다시 들어와 억울하게 지는 것을 막습니다.
  if (now - state.roundStartedAt < config.roundGraceSeconds * 1000) {
    return { kind: "ignored", reason: "GRACE_PERIOD", state };
  }

  if (input.confidence !== null && input.confidence !== undefined &&
      input.confidence < config.minConfidence) {
    return { kind: "ignored", reason: "LOW_CONFIDENCE", state };
  }

  if (isHand(label)) {
    if (state.mode === "object") {
      return { kind: "ignored", reason: "MODE_OBJECT_ONLY", state };
    }
    return judgeHand(state, config, label, now, pick);
  }

  if (state.mode === "rps") {
    return { kind: "ignored", reason: "MODE_RPS_ONLY", state };
  }
  return judgeObject(state, config, label, now, pick);
}

function judgeHand(
  state: MissionState,
  config: MissionConfig,
  userHand: Hand,
  now: number,
  pick?: (choices: Hand[]) => Hand
): MissionOutcome {
  if (!state.aiHand) return { kind: "ignored", reason: "NO_ROUND", state };

  const result: RoundResult =
    userHand === state.aiHand ? "draw" : BEATS[userHand] === state.aiHand ? "win" : "lose";

  if (result !== "win") {
    // 지거나 비기면 승수는 그대로 두고 라운드를 다시 엽니다.
    const retried = beginRound({ ...state, lastResult: result }, config, now, pick);
    return {
      kind: "result",
      result,
      state: { ...retried.state, lastResult: result, lastResultMessage: retried.message },
      message:
        result === "draw"
          ? `비겼습니다! 다시 한 번 — ${retried.message}`
          : `아쉽습니다! 다시 한 번 — ${retried.message}`,
    };
  }

  const wins = state.wins + 1;
  if (wins >= state.requiredWins) {
    return {
      kind: "success",
      evidence: `rps:${userHand}`,
      state: { ...IDLE_MISSION, wins, requiredWins: state.requiredWins },
      message: "기상 미션을 완수했습니다! 알람이 해제되었습니다.",
    };
  }

  const next = beginRound({ ...state, wins, lastResult: "win" }, config, now, pick);
  return {
    kind: "result",
    result: "win",
    state: { ...next.state, wins, lastResult: "win", lastResultMessage: next.message },
    message: `이겼습니다! (${wins}/${state.requiredWins}) ${next.message}`,
  };
}

function judgeObject(
  state: MissionState,
  config: MissionConfig,
  label: string,
  now: number,
  pick?: (choices: Hand[]) => Hand
): MissionOutcome {
  if (!config.objectTargets.includes(label)) {
    return { kind: "ignored", reason: "NOT_A_TARGET", state };
  }

  const hits = state.objectHits + 1;
  if (hits < config.objectRequiredHits) {
    // 한 번 스쳐 지나간 것으로는 통과시키지 않습니다 (연속 감지 필요).
    return { kind: "ignored", reason: "NEED_MORE_HITS", state: { ...state, objectHits: hits } };
  }

  const wins = state.wins + 1;
  if (wins >= state.requiredWins) {
    return {
      kind: "success",
      evidence: `object:${label}`,
      state: { ...IDLE_MISSION, wins, requiredWins: state.requiredWins },
      message: "기상 미션을 완수했습니다! 알람이 해제되었습니다.",
    };
  }

  const next = beginRound(
    { ...state, wins, objectHits: 0, lastResult: "object" }, config, now, pick
  );
  return {
    kind: "result",
    result: "object",
    state: { ...next.state, wins, lastResult: "object", lastResultMessage: next.message },
    message: `'${label}' 확인! (${wins}/${state.requiredWins}) ${next.message}`,
  };
}

/** 제한 시간이 지났을 때 — 실패가 아니라 재시도 라운드를 엽니다. */
export function timeoutRound(
  state: MissionState,
  config: MissionConfig,
  now: number,
  pick?: (choices: Hand[]) => Hand
): MissionOutcome {
  if (!state.active) return { kind: "ignored", reason: "MISSION_INACTIVE", state };
  const retried = beginRound({ ...state, lastResult: "timeout" }, config, now, pick);
  return {
    kind: "result",
    result: "timeout",
    state: { ...retried.state, lastResult: "timeout", lastResultMessage: retried.message },
    message: `시간이 초과되었습니다. 다시 한 번 — ${retried.message}`,
  };
}

/** 환경변수 형태의 설정을 읽어 옵니다 (.env.local의 NEXT_PUBLIC_* 값). */
export function configFromEnv(
  env: Record<string, string | undefined> = {}
): MissionConfig {
  const num = (key: string, fallback: number) => {
    const raw = Number(env[key]);
    return Number.isFinite(raw) && raw > 0 ? raw : fallback;
  };
  const mode = String(env.NEXT_PUBLIC_MISSION_MODE ?? "").trim().toLowerCase();
  const targets = String(env.NEXT_PUBLIC_MISSION_OBJECT_TARGETS ?? "")
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);

  return {
    ...DEFAULT_MISSION_CONFIG,
    mode: (["auto", "rps", "object"].includes(mode) ? mode : "auto") as MissionMode,
    requiredWins: num("NEXT_PUBLIC_MISSION_REQUIRED_WINS", DEFAULT_MISSION_CONFIG.requiredWins),
    roundTimeoutSeconds: num(
      "NEXT_PUBLIC_MISSION_ROUND_TIMEOUT_SECONDS", DEFAULT_MISSION_CONFIG.roundTimeoutSeconds
    ),
    roundGraceSeconds: num(
      "NEXT_PUBLIC_MISSION_ROUND_GRACE_SECONDS", DEFAULT_MISSION_CONFIG.roundGraceSeconds
    ),
    minConfidence: num("NEXT_PUBLIC_MISSION_MIN_CONFIDENCE", DEFAULT_MISSION_CONFIG.minConfidence),
    objectTargets: targets.length ? targets : DEFAULT_MISSION_CONFIG.objectTargets,
    objectRequiredHits: num(
      "NEXT_PUBLIC_MISSION_OBJECT_REQUIRED_HITS", DEFAULT_MISSION_CONFIG.objectRequiredHits
    ),
    popupDelaySeconds: num(
      "NEXT_PUBLIC_WAKEUP_POPUP_DELAY_SECONDS", DEFAULT_MISSION_CONFIG.popupDelaySeconds
    ),
    confirmTimeoutSeconds: num(
      "NEXT_PUBLIC_WAKEUP_CONFIRM_TIMEOUT_SECONDS", DEFAULT_MISSION_CONFIG.confirmTimeoutSeconds
    ),
  };
}
