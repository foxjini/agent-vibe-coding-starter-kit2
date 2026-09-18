/**
 * study 팀 판정 엔진 (scenarios/studyEngine.ts) — ★ study 팀이 고치는 파일
 * ============================================================================
 * 카메라(`vision/detectors/study_focus.py`)는 **재기만** 합니다.
 * "집중하고 있다 / 졸고 있다"를 정하는 것은 **여기**입니다.
 *
 * 이 파일에는 React가 없습니다. 순수 함수뿐이라 브라우저 없이 시험할 수 있습니다.
 *
 *     cd frontend && node --experimental-strip-types scenarios/studyEngine.test.ts
 *
 * 임계값을 고쳤으면 **반드시 위 명령을 한 번 돌리세요.**
 */

// ============================================================================
// ★ 여기를 고쳐서 맞춥니다
// ============================================================================

/** 눈을 이만큼(초) 이어서 감고 있으면 졸고 있다고 봅니다. */
export const DROWSY_SECONDS = 1.5;

/** 창에서 눈을 감고 있던 비율이 이보다 크면 졸고 있다고 봅니다. */
export const DROWSY_CLOSED_RATIO = 0.5;

/** 시선·고개가 이 비율 넘게 벗어나 있으면 딴짓으로 봅니다. */
export const DISTRACTED_RATIO = 0.5;

/** 얼굴이 안 보인 비율이 이보다 크면 자리를 비운 것으로 봅니다. */
export const AWAY_RATIO = 0.5;

/** 표본이 이보다 적으면 **판정을 보류**합니다 (찍어서 맞히지 않습니다). */
export const MIN_SAMPLES = 5;

/** 집중도 점수에서 깎는 정도. 셋을 더해 100이 되게 두면 이해하기 쉽습니다. */
export const PENALTY = {
  /** 눈을 감고 있던 비율 */
  eyesClosed: 45,
  /** 고개를 숙이고 있던 비율 */
  headDown: 25,
  /** 시선이 벗어나 있던 비율 */
  lookAway: 30,
};

/** 얼굴이 이 픽셀보다 작으면 "카메라가 멀다"고 화면에 알려 줍니다. */
export const GOOD_FACE_PX = 192;

/**
 * 이벤트 사이 간격이 이보다 길면 그만큼을 시간에 더하지 않습니다.
 * 탭을 한참 덮어 뒀다가 돌아왔을 때 몇 시간이 한꺼번에 쌓이는 것을 막습니다.
 */
export const MAX_GAP_SECONDS = 10;

/** 타임라인 막대 하나가 담는 시간(초). 기본 1분. */
export const BUCKET_SECONDS = 60;

/** 타임라인에 남겨 둘 막대 개수 (기본 90분치). */
export const MAX_BUCKETS = 90;

// ============================================================================
// 카메라가 보내온 값
// ============================================================================

/** `face_visible` 이벤트의 `extra`를 읽기 좋은 형태로 바꾼 것. */
export interface FocusMeasure {
  /** 이 창에서 본 프레임 수 */
  samples: number;
  /** 얼굴이 보였는가 */
  face: boolean;
  /** 눈이 얼마나 떠 있었나 (0 감음 ~ 1 뜸) */
  eyesOpen: number;
  /** 눈을 감고 있던 프레임 비율 */
  closedRatio: number;
  /** 가장 길게 이어서 눈을 감고 있던 시간(초) */
  closedRun: number;
  /** 고개를 숙이고 있던 프레임 비율 */
  headDown: number;
  /** 시선·고개가 벗어나 있던 프레임 비율 */
  lookAway: number;
  /** 얼굴이 안 보인 프레임 비율 */
  noFace: number;
  /** 얼굴 폭(픽셀) — 설치 품질 */
  facePx: number;
  /** 이 사람의 '정면'을 다 배웠는가 */
  calibrated: boolean;
}

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/**
 * 비전 이벤트의 `extra`를 읽습니다.
 *
 * 카메라 쪽은 파이썬이라 `closed_run`처럼 밑줄로 옵니다. 여기서 한 번만 바꿔 두면
 * 화면 코드에서는 `closedRun`으로 씁니다.
 */
export function parseMeasure(extra: Record<string, unknown> | null | undefined): FocusMeasure {
  const e = extra ?? {};
  return {
    samples: num(e.samples),
    face: e.face === true,
    eyesOpen: num(e.eyes_open),
    closedRatio: num(e.closed_ratio),
    closedRun: num(e.closed_run),
    headDown: num(e.head_down),
    lookAway: num(e.look_away),
    noFace: num(e.no_face),
    facePx: num(e.face_px),
    calibrated: e.calibrated === true,
  };
}

// ============================================================================
// 판정 — 여기가 이 파일의 핵심입니다
// ============================================================================

export type StudyState =
  /** 집중해서 보고 있음 */
  | "focused"
  /** 딴 데를 보고 있음 */
  | "distracted"
  /** 졸고 있음 */
  | "drowsy"
  /** 자리에 없음 */
  | "away"
  /** 아직 판단할 수 없음 (보정 중이거나 표본이 모자람) */
  | "unknown";

export const STATE_LABEL: Record<StudyState, string> = {
  focused: "집중",
  distracted: "딴 데 봄",
  drowsy: "졸음",
  away: "자리 비움",
  unknown: "확인 중",
};

/**
 * 측정값 하나를 상태 하나로 바꿉니다.
 *
 * **순서가 중요합니다.** 자리에 없으면 눈을 볼 수 없고,
 * 보정이 안 끝났으면 고개 숙임을 판단할 수 없습니다.
 */
export function classify(m: FocusMeasure): StudyState {
  if (!m.face || m.noFace >= AWAY_RATIO) return "away";
  if (m.samples < MIN_SAMPLES || !m.calibrated) return "unknown";
  if (m.closedRun >= DROWSY_SECONDS || m.closedRatio >= DROWSY_CLOSED_RATIO) return "drowsy";
  if (m.lookAway >= DISTRACTED_RATIO || m.headDown >= DISTRACTED_RATIO) return "distracted";
  return "focused";
}

/**
 * 집중도 점수 0~100.
 *
 * 100에서 시작해 **눈을 감고 있던 만큼 · 고개를 숙이고 있던 만큼 ·
 * 시선이 벗어나 있던 만큼** 깎습니다. 판정할 수 없으면 `null`입니다 —
 * 0점과 "모름"은 다릅니다.
 */
export function focusScore(m: FocusMeasure): number | null {
  const state = classify(m);
  if (state === "away" || state === "unknown") return null;

  const penalty =
    m.closedRatio * PENALTY.eyesClosed +
    m.headDown * PENALTY.headDown +
    m.lookAway * PENALTY.lookAway;

  return Math.max(0, Math.min(100, Math.round(100 - penalty)));
}

/** 카메라가 너무 멀어 눈을 제대로 못 재는 상태인가. */
export function isCameraTooFar(m: FocusMeasure): boolean {
  return m.face && m.facePx > 0 && m.facePx < GOOD_FACE_PX;
}

// ============================================================================
// 세션 누적 — "오늘 50분 중 몇 분을 집중했나"
// ============================================================================

export interface TimelineBucket {
  /** 이 막대가 시작된 시각 (ms) */
  at: number;
  /** 이 막대에서 각 상태로 보낸 시간(초) */
  seconds: Record<StudyState, number>;
  /** 이 막대의 평균 점수 (점수가 없었으면 null) */
  score: number | null;
  scoreSum: number;
  scoreCount: number;
}

export interface SessionState {
  startedAt: number;
  lastAt: number;
  /** 각 상태로 보낸 시간(초) */
  seconds: Record<StudyState, number>;
  /** 졸기 시작한 횟수 (졸음으로 **바뀐** 횟수) */
  drowsyEpisodes: number;
  lastState: StudyState;
  scoreSum: number;
  scoreCount: number;
  buckets: TimelineBucket[];
}

function emptySeconds(): Record<StudyState, number> {
  return { focused: 0, distracted: 0, drowsy: 0, away: 0, unknown: 0 };
}

export function newSession(now: number): SessionState {
  return {
    startedAt: now,
    lastAt: now,
    seconds: emptySeconds(),
    drowsyEpisodes: 0,
    lastState: "unknown",
    scoreSum: 0,
    scoreCount: 0,
    buckets: [],
  };
}

function bucketStart(at: number): number {
  return Math.floor(at / (BUCKET_SECONDS * 1000)) * BUCKET_SECONDS * 1000;
}

/**
 * 측정값 하나를 세션에 더합니다. **새 객체를 돌려줍니다** (원래 것은 그대로).
 *
 * 이벤트는 2~3초에 한 번 오므로, 지난 이벤트로부터 흐른 시간을
 * "그 상태로 보낸 시간"으로 칩니다.
 */
export function applyMeasure(
  session: SessionState,
  measure: FocusMeasure,
  now: number
): SessionState {
  const state = classify(measure);
  const score = focusScore(measure);

  // 탭을 덮어 뒀다 돌아온 경우 그 시간을 통째로 더하지 않습니다
  const gap = Math.max(0, Math.min((now - session.lastAt) / 1000, MAX_GAP_SECONDS));

  const seconds = { ...session.seconds };
  seconds[state] += gap;

  // 졸음은 "몇 번 졸았나"가 "몇 초 졸았나"보다 더 알아보기 쉽습니다
  const startedDozing = state === "drowsy" && session.lastState !== "drowsy";

  const buckets = session.buckets.slice();
  const slot = bucketStart(now);
  let bucket = buckets[buckets.length - 1];
  if (!bucket || bucket.at !== slot) {
    bucket = { at: slot, seconds: emptySeconds(), score: null, scoreSum: 0, scoreCount: 0 };
    buckets.push(bucket);
    if (buckets.length > MAX_BUCKETS) buckets.shift();
  } else {
    bucket = { ...bucket, seconds: { ...bucket.seconds } };
    buckets[buckets.length - 1] = bucket;
  }
  bucket.seconds[state] += gap;
  if (score !== null) {
    bucket.scoreSum += score;
    bucket.scoreCount += 1;
    bucket.score = Math.round(bucket.scoreSum / bucket.scoreCount);
  }

  return {
    ...session,
    lastAt: now,
    seconds,
    drowsyEpisodes: session.drowsyEpisodes + (startedDozing ? 1 : 0),
    lastState: state,
    scoreSum: session.scoreSum + (score ?? 0),
    scoreCount: session.scoreCount + (score === null ? 0 : 1),
    buckets,
  };
}

export interface SessionSummary {
  /** 세션이 시작된 뒤 흐른 시간(초) */
  elapsed: number;
  /** 자리에 앉아 있던 시간(초) — 자리 비움·확인 중은 뺍니다 */
  seated: number;
  /** 집중한 시간(초) */
  focused: number;
  /** 앉아 있던 시간 중 집중한 비율 0~100 (앉은 적이 없으면 null) */
  focusRate: number | null;
  /** 평균 집중도 점수 (잰 적이 없으면 null) */
  averageScore: number | null;
  drowsyEpisodes: number;
  drowsySeconds: number;
  distractedSeconds: number;
  awaySeconds: number;
}

export function summarize(session: SessionState, now: number): SessionSummary {
  const s = session.seconds;
  const seated = s.focused + s.distracted + s.drowsy;
  return {
    elapsed: Math.max(0, (now - session.startedAt) / 1000),
    seated,
    focused: s.focused,
    focusRate: seated > 0 ? Math.round((s.focused / seated) * 100) : null,
    averageScore:
      session.scoreCount > 0 ? Math.round(session.scoreSum / session.scoreCount) : null,
    drowsyEpisodes: session.drowsyEpisodes,
    drowsySeconds: s.drowsy,
    distractedSeconds: s.distracted,
    awaySeconds: s.away,
  };
}

/** `93분 12초` 처럼 읽기 좋게. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  const sec = total % 60;
  if (m === 0) return `${sec}초`;
  return `${m}분 ${sec}초`;
}

// ============================================================================
// 저장 — extra는 DB에 남지 않으므로 브라우저가 기억합니다
// ============================================================================

/**
 * ⚠️ 비전 `extra`는 **DB에 저장되지 않습니다** (실시간 중계 전용).
 * 그래서 "오늘 얼마나 집중했나"는 이 브라우저가 들고 있어야 합니다.
 * 다른 PC에서 열면 이어지지 않습니다 — 그것이 정상입니다.
 */
export const STORAGE_KEY = "study.session.v1";

/** 저장해 둔 세션이 이 시간(초)보다 오래됐으면 새 세션으로 시작합니다. */
export const SESSION_STALE_SECONDS = 4 * 60 * 60;

export function serializeSession(session: SessionState): string {
  return JSON.stringify(session);
}

/** 저장된 문자열을 세션으로 되살립니다. 이상하면 `null`. */
export function restoreSession(raw: string | null, now: number): SessionState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<SessionState>;
    if (typeof parsed?.startedAt !== "number" || typeof parsed?.lastAt !== "number") {
      return null;
    }
    if ((now - parsed.lastAt) / 1000 > SESSION_STALE_SECONDS) return null;
    return {
      startedAt: parsed.startedAt,
      lastAt: parsed.lastAt,
      seconds: { ...emptySeconds(), ...(parsed.seconds ?? {}) },
      drowsyEpisodes: num(parsed.drowsyEpisodes),
      lastState: (parsed.lastState ?? "unknown") as StudyState,
      scoreSum: num(parsed.scoreSum),
      scoreCount: num(parsed.scoreCount),
      buckets: Array.isArray(parsed.buckets) ? parsed.buckets : [],
    };
  } catch {
    return null;
  }
}
