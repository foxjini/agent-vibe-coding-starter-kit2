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
 *
 * 미션 종류 (NEXT_PUBLIC_MISSION_MODE)
 *   rps      카메라 앞에서 가위바위보를 이깁니다
 *   object   카메라에 지정한 사물을 보여 줍니다
 *   auto     위 둘 다 받습니다 (기본)
 *   pattern  화면에 나온 3×3 점 패턴을 따라 그립니다 — 카메라가 필요 없습니다
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

// =============================================================================
// 패턴 미션 — 스마트폰 잠금화면처럼 3×3 점을 이어 그립니다
// =============================================================================
//
//      0   1   2
//      3   4   5        점 번호는 위 왼쪽부터 0~8입니다.
//      6   7   8
//
// 매 라운드 **새 패턴**을 보여 주고 따라 그리게 합니다. 외운 패턴은 잠결에도
// 그릴 수 있어서 깨우는 효과가 없기 때문입니다. 저장할 것도 없습니다.

export const PATTERN_GRID = 3;
export const PATTERN_DOTS = PATTERN_GRID * PATTERN_GRID;

/** 패턴을 보여 주기 전 비워 두는 시간(초) — 그동안 직전 결과(맞음·틀림)를 보여 줍니다 */
export const PATTERN_LEAD_SECONDS = 0.8;
/** 마지막 점까지 보여 준 뒤, 그리기를 받기 전에 잠깐 멈추는 시간(초) */
export const PATTERN_TAIL_SECONDS = 0.5;
/** 이보다 적게 이은 것은 실수로 건드린 것으로 보고 세지 않습니다 (휴대폰과 같습니다) */
export const PATTERN_MIN_INPUT = 2;

/** 화면에서 점을 부르는 이름 (화면 읽기 프로그램·키보드 사용자용) */
export const DOT_NAMES = [
  "위 왼쪽", "위 가운데", "위 오른쪽",
  "가운데 왼쪽", "한가운데", "가운데 오른쪽",
  "아래 왼쪽", "아래 가운데", "아래 오른쪽",
] as const;

/** 그리기 판이 받은 결과 — 맞음·틀림을 잠깐 색으로 보여 줄 때 씁니다 */
export type PatternFeedback = "success" | "correct" | "wrong" | "too-short" | "not-ready";

/**
 * 두 점 사이에 **정확히 한가운데 있는 점**. 없으면 null.
 *
 * 휴대폰 잠금화면은 0에서 2로 그으면 사이의 1을 지나간 것으로 칩니다
 * (1을 아직 안 지났다면). 이 규칙이 없으면 "0 → 2"처럼 손으로는 그릴 수 없는
 * 패턴이 나옵니다.
 */
export function middleDot(a: number, b: number): number | null {
  const ra = Math.floor(a / PATTERN_GRID);
  const ca = a % PATTERN_GRID;
  const rb = Math.floor(b / PATTERN_GRID);
  const cb = b % PATTERN_GRID;
  if ((ra + rb) % 2 !== 0 || (ca + cb) % 2 !== 0) return null;
  const mid = ((ra + rb) / 2) * PATTERN_GRID + (ca + cb) / 2;
  return mid === a || mid === b ? null : mid;
}

/**
 * 그리고 있는 경로에 점 하나를 이어 붙입니다 — **휴대폰과 같은 규칙**입니다.
 *
 *   · 이미 지난 점은 다시 넣지 않습니다
 *   · 사이에 아직 안 지난 점이 있으면 그 점이 먼저 들어갑니다 (0 → 2 는 0, 1, 2)
 *   · 사이의 점을 이미 지났다면 건너뛸 수 있습니다
 *
 * 바뀐 것이 없으면 **같은 배열을 그대로** 돌려줍니다 (화면이 쓸데없이 다시 그리지 않게).
 */
export function addDot(path: number[], dot: number): number[] {
  if (!Number.isInteger(dot) || dot < 0 || dot >= PATTERN_DOTS || path.includes(dot)) {
    return path;
  }
  if (path.length === 0) return [dot];
  const mid = middleDot(path[path.length - 1], dot);
  return mid !== null && !path.includes(mid) ? [...path, mid, dot] : [...path, dot];
}

export function samePattern(a: readonly number[], b: readonly number[]): boolean {
  return a.length === b.length && a.every((dot, i) => dot === b[i]);
}

/**
 * 새 패턴을 하나 만듭니다. **화면에 보인 그대로 손으로 그릴 수 있는 것**만 만듭니다 —
 * 아직 안 지난 점을 건너뛰는 이동은 고르지 않습니다.
 *
 * 이 규칙으로는 막다른 길이 생기지 않습니다: 건너뛰려던 점이 막히면 그 사이의 점이
 * 바로 옆이라 언제나 고를 수 있기 때문입니다.
 */
export function generatePattern(length: number, rand: () => number = Math.random): number[] {
  const target = Math.max(3, Math.min(PATTERN_DOTS, Math.round(length) || 0));
  const pickIndex = (n: number) => Math.min(n - 1, Math.floor(rand() * n));

  const path = [pickIndex(PATTERN_DOTS)];
  while (path.length < target) {
    const last = path[path.length - 1];
    const choices: number[] = [];
    for (let dot = 0; dot < PATTERN_DOTS; dot++) {
      if (path.includes(dot)) continue;
      const mid = middleDot(last, dot);
      if (mid !== null && !path.includes(mid)) continue;
      choices.push(dot);
    }
    if (choices.length === 0) break;            // 일어나지 않지만 무한 반복은 막습니다
    path.push(choices[pickIndex(choices.length)]);
  }
  return path;
}

export type RoundResult = "win" | "lose" | "draw" | "timeout" | "object";
export type MissionMode = "auto" | "rps" | "object" | "pattern";

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
  /** 패턴 미션 — 이어 그릴 점 개수 (3~9). 늘리면 어려워집니다 */
  patternLength: number;
  /** 패턴 미션 — 점 하나를 보여 주는 시간(초). 줄이면 어려워집니다 */
  patternStepSeconds: number;
  /** 패턴 미션 — 그리는 동안에도 정답을 흐리게 남겨 둘지 (쉬운 난이도·시연용) */
  patternKeepVisible: boolean;
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
  patternLength: 4,
  patternStepSeconds: 0.7,
  patternKeepVisible: false,
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
  /** 패턴 미션 — 이번 라운드에 따라 그릴 점 순서 (0~8). 다른 미션에서는 null */
  pattern: number[] | null;
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
  pattern: null,
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
    choices[Math.floor(Math.random() * choices.length)],
  rand: () => number = Math.random
): { state: MissionState; message: string } {
  if (state.mode === "pattern") {
    let pattern = generatePattern(config.patternLength, rand);
    // 직전 라운드와 똑같은 패턴이 나오면 한 번 더 뽑습니다
    if (state.pattern && samePattern(pattern, state.pattern)) {
      pattern = generatePattern(config.patternLength, rand);
    }
    return {
      state: {
        ...state,
        active: true,
        round: state.round + 1,
        aiHand: null,
        expectedHand: null,
        objectHits: 0,
        pattern,
        roundStartedAt: now,
      },
      message: `새 패턴입니다 — 점이 켜지는 순서를 잘 보고 똑같이 이어 그리세요 (점 ${pattern.length}개).`,
    };
  }

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
  pick?: (choices: Hand[]) => Hand,
  rand?: () => number
): { state: MissionState; message: string } {
  const base: MissionState = {
    ...IDLE_MISSION,
    active: true,
    mode: config.mode,
    requiredWins: config.requiredWins,
    reason,
  };
  return beginRound(base, config, now, pick, rand);
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
  if (state.mode === "pattern") {
    // 패턴 미션은 화면에 그려서 풉니다 — 카메라 감지는 받지 않습니다.
    return { kind: "ignored", reason: "MODE_PATTERN_ONLY", state };
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

/**
 * 패턴 라운드의 시간표.
 *
 *   roundStartedAt ── 잠깐 비움(직전 결과 표시) ── 점을 하나씩 보여 줌 ── 잠깐 멈춤 ── 그리기
 *                    PATTERN_LEAD_SECONDS        점 개수 × patternStepSeconds  TAIL
 */
export function patternTiming(
  state: MissionState,
  config: MissionConfig
): { showStartsAt: number; inputOpensAt: number; stepMs: number } {
  const steps = state.pattern?.length ?? config.patternLength;
  const stepMs = config.patternStepSeconds * 1000;
  const showStartsAt = state.roundStartedAt + PATTERN_LEAD_SECONDS * 1000;
  const inputOpensAt = showStartsAt + steps * stepMs + PATTERN_TAIL_SECONDS * 1000;
  return { showStartsAt, inputOpensAt, stepMs };
}

/**
 * 이번 라운드의 제한 시간(초).
 * 패턴 미션은 **보여 주는 시간을 더해** 줍니다 — 그리는 시간이 줄어들지 않게.
 */
export function roundDurationSeconds(state: MissionState, config: MissionConfig): number {
  if (state.mode !== "pattern") return config.roundTimeoutSeconds;
  const { inputOpensAt } = patternTiming(state, config);
  return Math.ceil((inputOpensAt - state.roundStartedAt) / 1000) + config.roundTimeoutSeconds;
}

/**
 * 그린 패턴 하나를 판정합니다. 화면(그리기 판)이 **직접** 부릅니다 —
 * 터치는 비전 이벤트를 만들지 않으므로 judgeVision을 거치지 않습니다.
 *
 * 틀리면 승수는 그대로 두고 **새 패턴**으로 라운드를 다시 엽니다 (가위바위보와 같습니다).
 */
export function judgePattern(
  state: MissionState,
  config: MissionConfig,
  drawn: readonly number[],
  now: number,
  rand?: () => number
): MissionOutcome {
  if (!state.active) {
    return { kind: "ignored", reason: "MISSION_INACTIVE", state };
  }
  if (state.mode !== "pattern" || !state.pattern) {
    return { kind: "ignored", reason: "NOT_PATTERN_ROUND", state };
  }
  if (now < patternTiming(state, config).inputOpensAt) {
    // 아직 보여 주는 중 — 손이 화면에 닿아 있던 것을 오답으로 치지 않습니다
    return { kind: "ignored", reason: "STILL_SHOWING", state };
  }
  if (drawn.length < PATTERN_MIN_INPUT) {
    return { kind: "ignored", reason: "TOO_SHORT", state };
  }

  if (!samePattern(drawn, state.pattern)) {
    const retried = beginRound({ ...state, lastResult: "lose" }, config, now, undefined, rand);
    const message = "패턴이 달라요. 새 패턴을 잘 보고 다시 그려 보세요.";
    return {
      kind: "result",
      result: "lose",
      state: { ...retried.state, lastResult: "lose", lastResultMessage: message },
      message,
    };
  }

  const wins = state.wins + 1;
  if (wins >= state.requiredWins) {
    return {
      kind: "success",
      evidence: `pattern:${state.pattern.length}`,
      state: { ...IDLE_MISSION, wins, requiredWins: state.requiredWins },
      message: "기상 미션을 완수했습니다! 알람이 해제되었습니다.",
    };
  }

  const next = beginRound({ ...state, wins, lastResult: "win" }, config, now, undefined, rand);
  const message = `패턴 성공! (${wins}/${state.requiredWins}) 다음 패턴을 잘 보세요.`;
  return {
    kind: "result",
    result: "win",
    state: { ...next.state, wins, lastResult: "win", lastResultMessage: message },
    message,
  };
}

/** 제한 시간이 지났을 때 — 실패가 아니라 재시도 라운드를 엽니다. */
export function timeoutRound(
  state: MissionState,
  config: MissionConfig,
  now: number,
  pick?: (choices: Hand[]) => Hand,
  rand?: () => number
): MissionOutcome {
  if (!state.active) return { kind: "ignored", reason: "MISSION_INACTIVE", state };
  const retried = beginRound({ ...state, lastResult: "timeout" }, config, now, pick, rand);
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
  const bool = (key: string, fallback: boolean) => {
    const raw = String(env[key] ?? "").trim().toLowerCase();
    if (!raw) return fallback;
    return ["1", "true", "yes", "on"].includes(raw);
  };
  const mode = String(env.NEXT_PUBLIC_MISSION_MODE ?? "").trim().toLowerCase();
  const targets = String(env.NEXT_PUBLIC_MISSION_OBJECT_TARGETS ?? "")
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);

  return {
    ...DEFAULT_MISSION_CONFIG,
    mode: (["auto", "rps", "object", "pattern"].includes(mode) ? mode : "auto") as MissionMode,
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
    patternLength: Math.max(3, Math.min(PATTERN_DOTS, Math.round(
      num("NEXT_PUBLIC_PATTERN_LENGTH", DEFAULT_MISSION_CONFIG.patternLength)
    ))),
    // 너무 빠르면 볼 수가 없고, 너무 느리면 지루합니다
    patternStepSeconds: Math.max(0.2, Math.min(3, num(
      "NEXT_PUBLIC_PATTERN_STEP_SECONDS", DEFAULT_MISSION_CONFIG.patternStepSeconds
    ))),
    patternKeepVisible: bool(
      "NEXT_PUBLIC_PATTERN_KEEP_VISIBLE", DEFAULT_MISSION_CONFIG.patternKeepVisible
    ),
  };
}
