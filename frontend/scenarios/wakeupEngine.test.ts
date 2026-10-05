/**
 * 기상 미션 판정 엔진 자가 점검 (scenarios/wakeupEngine.test.ts)
 * =============================================================================
 * 백엔드에 있던 backend/test_mission.py 18항목을 그대로 옮겨 온 것에
 * 패턴 미션(3×3 점 이어 그리기) 검사를 더했습니다.
 * 브라우저도 백엔드도 없이 판정 규칙만 검사합니다.
 *
 * 실행 방법 (frontend 폴더에서):
 *     node --experimental-strip-types scenarios/wakeupEngine.test.ts
 */
import {
  DEFAULT_MISSION_CONFIG,
  PATTERN_DOTS,
  WINNING_HAND,
  addDot,
  beginRound,
  configFromEnv,
  generatePattern,
  judgePattern,
  judgeVision,
  middleDot,
  patternTiming,
  roundDurationSeconds,
  samePattern,
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

// ===========================================================================
// 패턴 미션 — 3×3 점 이어 그리기
// ===========================================================================

/** 같은 씨앗이면 늘 같은 수를 내는 난수 (시험을 다시 돌려도 결과가 같게) */
function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 손으로 점을 차례로 짚었을 때 실제로 남는 경로 (휴대폰 규칙 그대로) */
function trace(dots: number[]): number[] {
  return dots.reduce<number[]>((path, dot) => addDot(path, dot), []);
}

const PATTERN: MissionConfig = { ...DEFAULT_MISSION_CONFIG, mode: "pattern", requiredWins: 2 };

section("P1. 사이에 낀 점 — 휴대폰 잠금화면 규칙");
{
  check("가로로 건너뛰면 가운데 점 (0→2 사이 1)", middleDot(0, 2) === 1);
  check("반대 방향도 같음 (2→0 사이 1)", middleDot(2, 0) === 1);
  check("세로 (1→7 사이 4)", middleDot(1, 7) === 4);
  check("대각선 (0→8 · 2→6 사이 4)", middleDot(0, 8) === 4 && middleDot(2, 6) === 4);
  check("바로 옆은 낀 점 없음 (0→1)", middleDot(0, 1) === null);
  check("말 이동처럼 비스듬하면 낀 점 없음 (0→5)", middleDot(0, 5) === null);
  check("같은 점끼리는 낀 점 없음", middleDot(4, 4) === null);

  check("0 → 2 로 그으면 1이 저절로 들어감", samePattern(trace([0, 2]), [0, 1, 2]));
  check("1을 이미 지났으면 건너뛸 수 있음 (1 → 0 → 2)", samePattern(trace([1, 0, 2]), [1, 0, 2]));
  check("이미 지난 점은 다시 안 들어감", samePattern(trace([0, 1, 0, 4]), [0, 1, 4]));
  check("판 밖의 번호는 무시", samePattern(trace([0, 9, -1, 1]), [0, 1]));

  const path = [0, 1];
  check("바뀐 것이 없으면 같은 배열을 그대로 돌려줌 (화면이 다시 안 그림)",
        addDot(path, 1) === path);
}

section("P2. 새 패턴 만들기 — 보인 그대로 그릴 수 있는가");
{
  let checked = 0;
  let allDrawable = true;
  let allUnique = true;
  let allInRange = true;
  let allLength = true;
  let example = "";
  for (let length = 3; length <= 9; length++) {
    for (let seed = 1; seed <= 300; seed++) {
      const pattern = generatePattern(length, seeded(seed * 31 + length));
      checked++;
      if (pattern.length !== length) allLength = false;
      if (new Set(pattern).size !== pattern.length) allUnique = false;
      if (!pattern.every((d) => Number.isInteger(d) && d >= 0 && d < PATTERN_DOTS)) allInRange = false;
      // 핵심: 보여 준 점을 차례로 짚으면 정확히 같은 패턴이 되어야 합니다.
      // (사이의 점을 건너뛰는 패턴이 나오면 손으로는 절대 똑같이 그릴 수 없습니다)
      if (!samePattern(trace(pattern), pattern)) {
        allDrawable = false;
        example = example || pattern.join("→");
      }
    }
  }
  check(`요청한 개수만큼 만듦 (길이 3~9 × 300번 = ${checked}개)`, allLength);
  check("같은 점이 두 번 나오지 않음", allUnique);
  check("점 번호가 0~8 안에 있음", allInRange);
  check("만든 패턴은 모두 화면에 보인 그대로 그릴 수 있음", allDrawable, example);

  check("같은 씨앗이면 같은 패턴 (시험 재현용)",
        samePattern(generatePattern(5, seeded(7)), generatePattern(5, seeded(7))));
  check("너무 짧게 요청해도 3개는 만듦", generatePattern(1, seeded(3)).length === 3);
  check("너무 길게 요청해도 9개까지만", generatePattern(20, seeded(3)).length === 9);

  const distinct = new Set<string>();
  for (let seed = 1; seed <= 200; seed++) distinct.add(generatePattern(4, seeded(seed)).join(","));
  check("매번 다른 패턴이 나옴 (200번 중 서로 다른 것 150개 이상)", distinct.size >= 150,
        `${distinct.size}개`);
}

section("P3. 패턴 미션 시작과 시간표");
{
  const { state, message } = startMission(PATTERN, 1000, "alarm", undefined, seeded(11));
  check("패턴 미션이 시작됨", state.active && state.mode === "pattern" && state.round === 1);
  check("패턴이 만들어짐 (점 4개)", (state.pattern?.length ?? 0) === 4);
  check("가위바위보 손은 쓰지 않음", state.aiHand === null && state.expectedHand === null);
  check("안내 문구에 점 개수가 들어감", message.includes("점 4개"));

  const timing = patternTiming(state, PATTERN);
  check("보여 주기는 잠깐 비운 뒤 시작", timing.showStartsAt === 1000 + 800);
  check("그리기는 다 보여 준 뒤에 열림 (0.8 + 4×0.7 + 0.5초)",
        timing.inputOpensAt === 1000 + 800 + 4 * 700 + 500, String(timing.inputOpensAt));
  check("라운드 제한 시간에 보여 주는 시간이 더해짐 (그리는 시간이 줄지 않게)",
        roundDurationSeconds(state, PATTERN) === Math.ceil(4.1) + PATTERN.roundTimeoutSeconds,
        String(roundDurationSeconds(state, PATTERN)));

  const rps = startMission({ ...DEFAULT_MISSION_CONFIG, mode: "rps" }, 1000, "alarm", () => "rock");
  check("다른 미션의 제한 시간은 그대로",
        roundDurationSeconds(rps.state, DEFAULT_MISSION_CONFIG) === DEFAULT_MISSION_CONFIG.roundTimeoutSeconds);
  check("다른 미션에는 패턴이 없음", rps.state.pattern === null);
}

section("P4. 그린 패턴 판정");
{
  const start = startMission(PATTERN, 0, "alarm", undefined, seeded(5)).state;
  const answer = start.pattern ?? [];
  const opens = patternTiming(start, PATTERN).inputOpensAt;

  const early = judgePattern(start, PATTERN, answer, opens - 1);
  check("보여 주는 중에 그린 것은 무시 (오답으로 치지 않음)",
        early.kind === "ignored" && early.reason === "STILL_SHOWING");

  const tap = judgePattern(start, PATTERN, [answer[0]], opens + 10);
  check("점 하나만 건드린 것은 세지 않음 (휴대폰과 같음)",
        tap.kind === "ignored" && tap.reason === "TOO_SHORT" && tap.state === start);

  const reversed = [...answer].reverse();
  const wrong = judgePattern(start, PATTERN, reversed, opens + 10, seeded(6));
  check("거꾸로 그리면 틀림 (순서까지 맞아야 함)", wrong.kind === "result" && wrong.result === "lose");
  if (wrong.kind === "result") {
    check("틀리면 승수는 그대로", wrong.state.wins === 0);
    check("틀리면 새 패턴으로 라운드를 다시 엶",
          wrong.state.round === 2 && !samePattern(wrong.state.pattern ?? [], answer));
    check("틀렸다는 안내가 남음", (wrong.state.lastResultMessage ?? "").includes("패턴이 달라요"));
  }

  const right = judgePattern(start, PATTERN, answer, opens + 10, seeded(8));
  check("맞게 그리면 이김", right.kind === "result" && right.result === "win");
  if (right.kind === "result") {
    check("이기면 승수가 오름", right.state.wins === 1);
    check("이겨도 다음 라운드는 새 패턴",
          right.state.round === 2 && !samePattern(right.state.pattern ?? [], answer));

    const second = right.state;
    const final = judgePattern(second, PATTERN, second.pattern ?? [],
                               patternTiming(second, PATTERN).inputOpensAt + 10);
    check("필요한 만큼 이기면 미션 성공", final.kind === "success");
    if (final.kind === "success") {
      check("성공하면 미션이 끝남", final.state.active === false);
      check("성공 근거에 패턴 길이가 남음", final.evidence === "pattern:4");
    }
  }

  const inactive = judgePattern({ ...start, active: false }, PATTERN, answer, opens + 10);
  check("미션이 꺼져 있으면 무시", inactive.kind === "ignored");
  const rpsState = startMission({ ...DEFAULT_MISSION_CONFIG, mode: "rps" }, 0, "a", () => "rock").state;
  check("가위바위보 미션 중에 그린 것은 무시",
        judgePattern(rpsState, DEFAULT_MISSION_CONFIG, [0, 1, 2], 99999).kind === "ignored");
}

section("P5. 패턴 미션 중에는 카메라를 받지 않음");
{
  const start = startMission(PATTERN, 0, "alarm", undefined, seeded(9)).state;
  const vision = judgeVision(start, PATTERN, { label: "rock", detected: true, confidence: 0.99 }, 99999);
  check("손동작이 들어와도 무시", vision.kind === "ignored" && vision.reason === "MODE_PATTERN_ONLY");
  const object = judgeVision(start, PATTERN, { label: "cup", detected: true, confidence: 0.99 }, 99999);
  check("사물이 들어와도 무시", object.kind === "ignored");

  const timedOut = timeoutRound(start, PATTERN, 50000, undefined, seeded(10));
  check("시간이 지나면 새 패턴으로 다시", timedOut.kind === "result" &&
        timedOut.result === "timeout" && timedOut.state.round === 2 &&
        !samePattern(timedOut.state.pattern ?? [], start.pattern ?? []));
}

section("P6. 환경변수로 난이도 바꾸기");
{
  const easy = configFromEnv({
    NEXT_PUBLIC_MISSION_MODE: "pattern",
    NEXT_PUBLIC_PATTERN_LENGTH: "6",
    NEXT_PUBLIC_PATTERN_STEP_SECONDS: "1.2",
    NEXT_PUBLIC_PATTERN_KEEP_VISIBLE: "true",
  });
  check("pattern 모드를 고를 수 있음", easy.mode === "pattern");
  check("점 개수·보여 주는 속도·정답 남기기를 바꿀 수 있음",
        easy.patternLength === 6 && easy.patternStepSeconds === 1.2 && easy.patternKeepVisible);

  const clamped = configFromEnv({ NEXT_PUBLIC_PATTERN_LENGTH: "15", NEXT_PUBLIC_PATTERN_STEP_SECONDS: "0.01" });
  check("점 개수는 9개까지, 속도는 0.2초보다 빠르지 않게",
        clamped.patternLength === 9 && clamped.patternStepSeconds === 0.2);

  const odd = configFromEnv({ NEXT_PUBLIC_PATTERN_LENGTH: "많이", NEXT_PUBLIC_PATTERN_KEEP_VISIBLE: "nope" });
  check("이상한 값은 기본값으로", odd.patternLength === 4 && odd.patternKeepVisible === false);
  check("모드를 안 적으면 기존처럼 auto", configFromEnv({}).mode === "auto");
}

console.log("\n" + "=".repeat(68));
console.log(` 결과: 성공 ${passed}건 / 실패 ${failed}건`);
console.log("=".repeat(68));
process.exit(failed ? 1 : 0);
