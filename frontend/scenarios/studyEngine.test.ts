/**
 * 집중도 판정 자가 점검 (scenarios/studyEngine.test.ts) — ★ study 팀
 * =============================================================================
 * 브라우저도 백엔드도 카메라도 없이 **판정 규칙만** 검사합니다.
 *
 * 실행 방법 (frontend 폴더에서):
 *     node --experimental-strip-types scenarios/studyEngine.test.ts
 *
 * studyEngine.ts의 임계값을 고쳤으면 반드시 이것을 돌려 보세요.
 */
import {
  AWAY_RATIO,
  DROWSY_SECONDS,
  MAX_GAP_SECONDS,
  MIN_SAMPLES,
  STATE_LABEL,
  STORAGE_KEY,
  applyMeasure,
  classify,
  focusScore,
  formatDuration,
  isCameraTooFar,
  newSession,
  parseMeasure,
  restoreSession,
  serializeSession,
  summarize,
} from "./studyEngine.ts";
import type { FocusMeasure, StudyState } from "./studyEngine.ts";

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

/** 집중하고 있는 사람의 측정값. 바꾸고 싶은 것만 넘기면 됩니다. */
function measure(over: Partial<FocusMeasure> = {}): FocusMeasure {
  return {
    samples: 20,
    face: true,
    eyesOpen: 0.9,
    closedRatio: 0.05,
    closedRun: 0.2,
    headDown: 0.0,
    lookAway: 0.05,
    noFace: 0,
    facePx: 260,
    calibrated: true,
    ...over,
  };
}

console.log("=".repeat(68));
console.log(" 집중도 판정 자가 점검 (카메라 없이)");
console.log("=".repeat(68));

// ---------------------------------------------------------------------------
section("1. 카메라가 보낸 값을 제대로 읽는가");
{
  const m = parseMeasure({
    samples: 24, face: true, eyes_open: 0.82, closed_ratio: 0.1,
    closed_run: 1.8, head_down: 0.2, look_away: 0.3, no_face: 0,
    face_px: 268, calibrated: true,
  });
  check("밑줄 이름을 낙타 이름으로 바꿔 읽음",
        m.closedRun === 1.8 && m.lookAway === 0.3 && m.facePx === 268);
  check("얼굴 여부를 불린으로 읽음", m.face === true);

  const empty = parseMeasure(null);
  check("extra가 없어도 터지지 않음", empty.samples === 0 && empty.face === false);

  const weird = parseMeasure({ samples: "여덟", closed_run: null, calibrated: "네" });
  check("이상한 값이 와도 숫자 자리는 0으로 채움",
        weird.samples === 0 && weird.closedRun === 0);
  check("불린이 아닌 값은 false로 읽음", weird.calibrated === false);
}

// ---------------------------------------------------------------------------
section("2. 상태 판정");
{
  check("평소에는 집중", classify(measure()) === "focused");

  check("눈을 오래 감고 있으면 졸음",
        classify(measure({ closedRun: DROWSY_SECONDS })) === "drowsy");
  check("깜빡임 정도로는 졸음이 아님",
        classify(measure({ closedRun: 0.3 })) === "focused");
  check("창의 절반 넘게 감고 있어도 졸음",
        classify(measure({ closedRatio: 0.6, closedRun: 0.4 })) === "drowsy");

  check("시선이 많이 벗어나면 딴 데 봄",
        classify(measure({ lookAway: 0.7 })) === "distracted");
  check("고개를 많이 숙이고 있어도 딴 데 봄",
        classify(measure({ headDown: 0.7 })) === "distracted");

  check("얼굴이 없으면 자리 비움",
        classify(measure({ face: false })) === "away");
  check("얼굴이 안 보인 비율이 높아도 자리 비움",
        classify(measure({ noFace: AWAY_RATIO })) === "away");
}

// ---------------------------------------------------------------------------
section("3. 판정을 보류하는가 — 찍어서 맞히지 않기");
{
  check("보정이 안 끝났으면 '확인 중'",
        classify(measure({ calibrated: false })) === "unknown");
  check("표본이 모자라면 '확인 중'",
        classify(measure({ samples: MIN_SAMPLES - 1 })) === "unknown");
  check("확인 중에는 점수를 내지 않음 (0점이 아니라 null)",
        focusScore(measure({ calibrated: false })) === null);
  check("자리에 없을 때도 점수를 내지 않음",
        focusScore(measure({ face: false })) === null);

  check("자리 비움은 보정보다 먼저 판단 (없는 사람을 보정할 수 없음)",
        classify(measure({ face: false, calibrated: false })) === "away");
  check("졸음은 딴짓보다 먼저 판단 (엎드리면 둘 다 참이 됨)",
        classify(measure({ closedRun: 2.0, headDown: 0.9 })) === "drowsy");
}

// ---------------------------------------------------------------------------
section("4. 집중도 점수");
{
  check("완벽하면 100점", focusScore(measure({
    closedRatio: 0, headDown: 0, lookAway: 0 })) === 100);

  const perfect = focusScore(measure({ closedRatio: 0, headDown: 0, lookAway: 0 }))!;
  const sleepy = focusScore(measure({ closedRatio: 0.4, closedRun: 0.5 }))!;
  check("눈을 감고 있을수록 점수가 내려감", sleepy < perfect, `${sleepy} < ${perfect}`);

  const away = focusScore(measure({ lookAway: 0.4 }))!;
  check("시선이 벗어날수록 점수가 내려감", away < perfect, `${away} < ${perfect}`);

  check("점수는 0 아래로 내려가지 않음",
        focusScore(measure({ closedRatio: 0.49, headDown: 1, lookAway: 1,
                             closedRun: 0.1 }))! >= 0);
  check("점수는 0~100 안에 있음", [0, 0.2, 0.45].every((v) => {
    const s = focusScore(measure({ closedRatio: v, headDown: v, lookAway: v,
                                   closedRun: 0.1 }));
    return s !== null && s >= 0 && s <= 100;
  }));
}

// ---------------------------------------------------------------------------
section("5. 카메라가 너무 먼지 알려 주는가");
{
  check("얼굴이 작으면 알려 줌", isCameraTooFar(measure({ facePx: 90 })));
  check("얼굴이 충분히 크면 조용함", !isCameraTooFar(measure({ facePx: 260 })));
  check("자리에 없으면 카메라 탓을 하지 않음",
        !isCameraTooFar(measure({ face: false, facePx: 0 })));
}

// ---------------------------------------------------------------------------
section("6. 세션 누적");
{
  let s = newSession(0);
  check("처음에는 아무것도 쌓여 있지 않음",
        s.seconds.focused === 0 && s.drowsyEpisodes === 0);

  // 3초 간격으로 집중 이벤트 4번
  for (let i = 1; i <= 4; i++) s = applyMeasure(s, measure(), i * 3000);
  check("집중한 시간이 쌓임", Math.round(s.seconds.focused) === 12,
        String(s.seconds.focused));
  check("평균 점수가 기록됨", s.scoreCount === 4);

  const before = s.drowsyEpisodes;
  s = applyMeasure(s, measure({ closedRun: 2.0 }), 15000);
  s = applyMeasure(s, measure({ closedRun: 2.5 }), 18000);
  check("졸음이 이어져도 '횟수'는 한 번만 늘어남",
        s.drowsyEpisodes === before + 1, String(s.drowsyEpisodes));

  s = applyMeasure(s, measure(), 21000);
  s = applyMeasure(s, measure({ closedRun: 2.0 }), 24000);
  check("깼다가 다시 졸면 횟수가 또 늘어남", s.drowsyEpisodes === before + 2);

  check("원래 세션은 그대로 (새 객체를 돌려줌)",
        newSession(0).seconds.focused === 0);
}

// ---------------------------------------------------------------------------
section("7. 탭을 덮어 뒀다 돌아왔을 때");
{
  let s = newSession(0);
  s = applyMeasure(s, measure(), 3000);
  const focusedBefore = s.seconds.focused;
  // 2시간 뒤에 이벤트 하나
  s = applyMeasure(s, measure(), 3000 + 2 * 60 * 60 * 1000);
  const added = s.seconds.focused - focusedBefore;
  check(`오래 비워 둔 시간을 통째로 더하지 않음 (${MAX_GAP_SECONDS}초까지만)`,
        added <= MAX_GAP_SECONDS + 0.01, `${added}초가 더해짐`);
}

// ---------------------------------------------------------------------------
section("8. 세션 요약");
{
  let s = newSession(0);
  for (let i = 1; i <= 10; i++) s = applyMeasure(s, measure(), i * 3000);      // 집중 30초
  for (let i = 11; i <= 15; i++) s = applyMeasure(s, measure({ lookAway: 0.8 }), i * 3000);
  const now = 15 * 3000;
  const sum = summarize(s, now);

  check("앉아 있던 시간은 집중+딴짓+졸음", Math.round(sum.seated) === 45,
        String(sum.seated));
  check("집중 비율이 계산됨", sum.focusRate === 67, String(sum.focusRate));
  check("평균 점수가 나옴", sum.averageScore !== null);
  check("딴짓 시간이 기록됨", Math.round(sum.distractedSeconds) === 15);

  const fresh = summarize(newSession(now), now);
  check("앉은 적이 없으면 비율은 null (0%가 아님)", fresh.focusRate === null);
  check("잰 적이 없으면 평균도 null", fresh.averageScore === null);
}

// ---------------------------------------------------------------------------
section("9. 타임라인");
{
  let s = newSession(0);
  for (let i = 1; i <= 5; i++) s = applyMeasure(s, measure(), i * 3000);
  check("같은 1분 안의 이벤트는 막대 하나에 모임", s.buckets.length === 1,
        String(s.buckets.length));

  s = applyMeasure(s, measure(), 65000);      // 다음 분
  check("분이 바뀌면 막대가 늘어남", s.buckets.length === 2);
  check("막대마다 평균 점수가 있음", s.buckets[0].score !== null);
  check("막대에 상태별 시간이 담김", s.buckets[0].seconds.focused > 0);
}

// ---------------------------------------------------------------------------
section("10. 저장과 복원 — extra는 DB에 없으므로 브라우저가 기억합니다");
{
  let s = newSession(1_000_000);
  for (let i = 1; i <= 5; i++) s = applyMeasure(s, measure(), 1_000_000 + i * 3000);
  const raw = serializeSession(s);
  const back = restoreSession(raw, 1_000_000 + 20000);

  check("저장했다 되살리면 같은 값", back !== null &&
        Math.round(back.seconds.focused) === Math.round(s.seconds.focused));
  check("시작 시각이 유지됨", back?.startedAt === s.startedAt);
  check("타임라인도 유지됨", (back?.buckets.length ?? 0) === s.buckets.length);

  check("저장된 것이 없으면 null", restoreSession(null, 0) === null);
  check("깨진 문자열이면 null", restoreSession("{이건 JSON이 아님", 0) === null);
  check("모양이 다른 JSON이면 null", restoreSession('{"hello":1}', 0) === null);

  const stale = restoreSession(raw, 1_000_000 + 10 * 60 * 60 * 1000);
  check("너무 오래된 세션은 버리고 새로 시작", stale === null);

  check("저장 키에 버전이 붙어 있음", STORAGE_KEY.includes("v1"));
}

// ---------------------------------------------------------------------------
section("11. 화면에 쓰는 것들");
{
  const states: StudyState[] = ["focused", "distracted", "drowsy", "away", "unknown"];
  check("모든 상태에 한글 이름이 있음",
        states.every((s) => typeof STATE_LABEL[s] === "string" && STATE_LABEL[s].length > 0));
  check("시간을 읽기 좋게 바꿈", formatDuration(125) === "2분 5초", formatDuration(125));
  check("1분 미만은 초만", formatDuration(42) === "42초");
  check("음수도 터지지 않음", formatDuration(-5) === "0초");
}

console.log("\n" + "=".repeat(68));
console.log(` 결과: 성공 ${passed}건 / 실패 ${failed}건`);
console.log("=".repeat(68));
process.exit(failed ? 1 : 0);
