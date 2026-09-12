/**
 * 기상 미션 판정 엔진 자가 점검 (scenarios/wakeupEngine.test.ts)
 * =============================================================================
 * 백엔드에 있던 backend/test_mission.py 18항목을 그대로 옮겨 온 것입니다.
 * 브라우저도 백엔드도 없이 판정 규칙만 검사합니다.
 *
 * 실행 방법 (frontend 폴더에서):
 *     node --experimental-strip-types scenarios/wakeupEngine.test.ts
 */
import {
  DEFAULT_MISSION_CONFIG,
  WINNING_HAND,
  beginRound,
  configFromEnv,
  judgeVision,
  startMission,
  timeoutRound,
} from "./wakeupEngine.ts";
// 타입은 실행 시 지워지므로 따로 가져옵니다 (node --experimental-strip-types 요구사항)
import type { Hand, MissionConfig, MissionState } from "./wakeupEngine.ts";

let passed = 0;
let failed = 0;

function check(label: string, condition: boolean, detail = ""): boolean {
  if (condition) {
    passed++;
    console.log(`  [PASS] ${label}`);
  } else {
    failed++;
    console.log(`  [FAIL] ${label}${detail ? ` — ${detail}` : ""}`);
  }
  return condition;
}

function section(title: string): void {
  console.log(`\n${title}\n${"-".repeat(68)}`);
}

const CONFIG: MissionConfig = { ...DEFAULT_MISSION_CONFIG, roundGraceSeconds: 2 };
/** 판정을 예측 가능하게 하려고 AI 손을 고정합니다. */
const always = (hand: Hand) => () => hand;
/** 유예 시간을 넘긴 시각 */
const afterGrace = (state: MissionState) =>
  state.roundStartedAt + CONFIG.roundGraceSeconds * 1000 + 100;

console.log("=".repeat(68));
console.log(" 기상 미션 판정 엔진 — 자가 점검");
console.log("=".repeat(68));

// ---------------------------------------------------------------------------
section("1. 가위바위보 승패 판정");

for (const aiHand of ["rock", "paper", "scissors"] as Hand[]) {
  const { state } = startMission(CONFIG, 0, "test", always(aiHand));
  const winning = WINNING_HAND[aiHand];
  const outcome = judgeVision(
    state, CONFIG, { label: winning, detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check(
    `AI가 ${aiHand}일 때 ${winning}을(를) 내면 승리`,
    outcome.kind === "result" && outcome.result === "win",
    JSON.stringify(outcome).slice(0, 120)
  );
}

{
  const { state } = startMission(CONFIG, 0, "test", always("rock"));
  const outcome = judgeVision(
    state, CONFIG, { label: "rock", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("같은 손이면 무승부", outcome.kind === "result" && outcome.result === "draw");
  check("무승부면 승수가 늘지 않음", outcome.kind === "result" && outcome.state.wins === 0);
  check("무승부면 다음 라운드가 열림", outcome.kind === "result" && outcome.state.round === 2);
}

{
  const { state } = startMission(CONFIG, 0, "test", always("rock"));
  const outcome = judgeVision(
    state, CONFIG, { label: "scissors", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("지는 손이면 패배", outcome.kind === "result" && outcome.result === "lose");
  check("패배해도 승수는 유지(초기화되지 않음)",
        outcome.kind === "result" && outcome.state.wins === 0);
  check("패배 후 재시도 라운드가 열림", outcome.kind === "result" && outcome.state.round === 2);
}

// ---------------------------------------------------------------------------
section("2. 미션 완주");

{
  let { state } = startMission(CONFIG, 0, "test", always("rock"));
  const first = judgeVision(
    state, CONFIG, { label: "paper", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("1승 후에는 아직 성공이 아님", first.kind === "result" && first.state.wins === 1);
  state = first.state;

  const second = judgeVision(
    state, CONFIG,
    { label: WINNING_HAND[state.aiHand!], detected: true, confidence: 0.9 },
    afterGrace(state)
  );
  check("필요 승수를 채우면 미션 성공", second.kind === "success",
        JSON.stringify(second).slice(0, 120));
  check("성공하면 미션이 끝난 상태가 됨",
        second.kind === "success" && second.state.active === false);
  check("성공 근거에 낸 손이 기록됨",
        second.kind === "success" && second.evidence.startsWith("rps:"));
}

// ---------------------------------------------------------------------------
section("3. 오판정 방지");

{
  const { state } = startMission(CONFIG, 0, "test", always("rock"));
  const tooEarly = judgeVision(
    state, CONFIG, { label: "paper", detected: true, confidence: 0.9 },
    state.roundStartedAt + 500      // 유예 시간 안
  );
  check("유예 시간 안의 이벤트는 무시됨(직전 손 재전송 보호)",
        tooEarly.kind === "ignored" && tooEarly.reason === "GRACE_PERIOD");

  const lowConf = judgeVision(
    state, CONFIG, { label: "paper", detected: true, confidence: 0.3 }, afterGrace(state)
  );
  check("신뢰도 미달 이벤트는 판정하지 않음",
        lowConf.kind === "ignored" && lowConf.reason === "LOW_CONFIDENCE");

  const notDetected = judgeVision(
    state, CONFIG, { label: "paper", detected: false, confidence: 0.9 }, afterGrace(state)
  );
  check("감지되지 않은 이벤트는 판정하지 않음", notDetected.kind === "ignored");

  const idle = judgeVision(
    { ...state, active: false }, CONFIG,
    { label: "paper", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("미션이 없으면 판정하지 않음",
        idle.kind === "ignored" && idle.reason === "MISSION_INACTIVE");
}

// ---------------------------------------------------------------------------
section("4. 시간 초과");

{
  const { state } = startMission(CONFIG, 0, "test", always("rock"));
  const outcome = timeoutRound(state, CONFIG, 20000);
  check("시간 초과 시 자동 재시도", outcome.kind === "result" && outcome.result === "timeout");
  check("시간 초과해도 승수는 유지", outcome.kind === "result" && outcome.state.wins === 0);
  check("시간 초과 후 새 라운드가 열림", outcome.kind === "result" && outcome.state.round === 2);
}

// ---------------------------------------------------------------------------
section("5. 사물 감지 미션");

{
  const objectConfig: MissionConfig = { ...CONFIG, mode: "object" };
  let { state } = startMission(objectConfig, 0, "test", always("rock"));

  const once = judgeVision(
    state, objectConfig, { label: "person", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("사물 1회 감지로는 통과하지 않음",
        once.kind === "ignored" && once.reason === "NEED_MORE_HITS");
  state = once.state;

  const twice = judgeVision(
    state, objectConfig, { label: "person", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("사물 2회 연속 감지로 라운드 통과",
        twice.kind === "result" && twice.result === "object", JSON.stringify(twice).slice(0, 120));

  const notTarget = judgeVision(
    state, objectConfig, { label: "airplane", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("미지정 사물은 통과시키지 않음",
        notTarget.kind === "ignored" && notTarget.reason === "NOT_A_TARGET");

  const handInObjectMode = judgeVision(
    state, objectConfig, { label: "rock", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("object 모드에서는 손동작을 판정하지 않음",
        handInObjectMode.kind === "ignored" && handInObjectMode.reason === "MODE_OBJECT_ONLY");

  const rpsConfig: MissionConfig = { ...CONFIG, mode: "rps" };
  const objectInRpsMode = judgeVision(
    { ...state, mode: "rps" }, rpsConfig,
    { label: "person", detected: true, confidence: 0.9 }, afterGrace(state)
  );
  check("rps 모드에서는 사물을 판정하지 않음",
        objectInRpsMode.kind === "ignored" && objectInRpsMode.reason === "MODE_RPS_ONLY");

  const disappeared = judgeVision(
    { ...state, objectHits: 1 }, objectConfig,
    { label: "person", detected: false }, afterGrace(state)
  );
  check("사물이 사라지면 연속 감지가 초기화됨",
        disappeared.kind === "ignored" && disappeared.state.objectHits === 0);
}

// ---------------------------------------------------------------------------
section("6. 라운드 진행 규칙");

{
  const { state } = startMission(CONFIG, 0, "test", always("rock"));
  check("라운드가 열리면 이겨야 하는 손이 함께 제시됨",
        state.expectedHand === WINNING_HAND[state.aiHand!]);

  // 같은 손을 연달아 내면 사용자가 판정을 헷갈립니다.
  const next = beginRound(state, CONFIG, 1000);
  check("다음 라운드는 직전과 다른 손을 냄", next.state.aiHand !== state.aiHand,
        `${state.aiHand} → ${next.state.aiHand}`);
}

// ---------------------------------------------------------------------------
section("7. 설정 읽기");

{
  const config = configFromEnv({
    NEXT_PUBLIC_MISSION_MODE: "rps",
    NEXT_PUBLIC_MISSION_REQUIRED_WINS: "3",
    NEXT_PUBLIC_MISSION_OBJECT_TARGETS: "person, cup",
  });
  check("환경설정으로 모드·승수·대상을 바꿀 수 있음",
        config.mode === "rps" && config.requiredWins === 3 &&
        config.objectTargets.join(",") === "person,cup",
        JSON.stringify(config).slice(0, 140));

  const fallback = configFromEnv({ NEXT_PUBLIC_MISSION_REQUIRED_WINS: "이상한값" });
  check("잘못된 설정값은 기본값으로 되돌림",
        fallback.requiredWins === DEFAULT_MISSION_CONFIG.requiredWins);
}

console.log("\n" + "=".repeat(68));
console.log(` 결과: 성공 ${passed}건 / 실패 ${failed}건`);
console.log("=".repeat(68));
process.exit(failed ? 1 : 0);
