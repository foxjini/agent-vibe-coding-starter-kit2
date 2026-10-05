/**
 * 패턴 그리기 판 (components/team/PatternPad.tsx) — ★ wakeup 팀 화면
 * =============================================================================
 * 스마트폰 잠금화면처럼 3×3 점을 이어 그립니다. 한 라운드는 이렇게 흘러갑니다.
 *
 *   잠깐 비움  →  점이 하나씩 켜지며 패턴을 보여 줌  →  사용자가 똑같이 이어 그림
 *   (직전 결과)     (이때 그린 것은 무시합니다)          (손을 떼면 판정)
 *
 * 판정은 여기서 하지 않습니다 — `onSubmit`으로 넘기면 scenarios/wakeupEngine.ts가 합니다.
 *
 * 입력 방법
 *   · 마우스·터치·펜 — Pointer Events 하나로 모두 받습니다 (PC에서 마우스로 시험 가능)
 *   · 키보드 — Tab으로 점을 옮겨 다니며 Enter/Space로 고르고 [확인]
 */
"use client";

import React from "react";

import {
  DOT_NAMES,
  PATTERN_DOTS,
  PATTERN_GRID,
  PATTERN_MIN_INPUT,
  addDot,
} from "@/scenarios/wakeupEngine";
import type { PatternFeedback } from "@/scenarios/wakeupEngine";

/** 손가락이 점 가운데에서 이 거리(칸 단위) 안에 들어오면 그 점을 지난 것으로 봅니다 */
const HIT_RADIUS = 0.32;
/** 빠르게 그어도 점을 놓치지 않도록, 이 간격(칸 단위)마다 지나간 자리를 확인합니다 */
const SAMPLE_STEP = 0.1;
/** 맞음·틀림을 색으로 보여 주는 시간 */
const FEEDBACK_MS = 800;
const HINT_MS = 1600;

type Phase = "waiting" | "showing" | "input";
type Point = { x: number; y: number };

const ALL_DOTS = Array.from({ length: PATTERN_DOTS }, (_, i) => i);

function center(dot: number): Point {
  return { x: (dot % PATTERN_GRID) + 0.5, y: Math.floor(dot / PATTERN_GRID) + 0.5 };
}

function hitDot(p: Point): number | null {
  for (const dot of ALL_DOTS) {
    const c = center(dot);
    if (Math.hypot(p.x - c.x, p.y - c.y) <= HIT_RADIUS) return dot;
  }
  return null;
}

function polyline(path: readonly number[]): string {
  return path.map((dot) => `${center(dot).x},${center(dot).y}`).join(" ");
}

/** 선 색 — 화면 전체에서 같은 뜻에는 같은 색을 씁니다 */
const STROKE = {
  shown: "#f59e0b",    // 보여 주는 패턴 (amber-500)
  drawn: "#0ea5e9",    // 내가 그리는 선 (sky-500)
  correct: "#10b981",  // 맞음 (emerald-500)
  wrong: "#f43f5e",    // 틀림 (rose-500)
} as const;

export default function PatternPad({
  pattern,
  round,
  showStartsAt,
  inputOpensAt,
  stepMs,
  keepVisible,
  onSubmit,
}: {
  /** 이번 라운드의 정답 (보여 주기에만 씁니다) */
  pattern: number[];
  /** 라운드 번호 — 바뀌면 판을 새로 시작합니다 */
  round: number;
  showStartsAt: number;
  inputOpensAt: number;
  stepMs: number;
  keepVisible: boolean;
  onSubmit: (drawn: number[]) => PatternFeedback;
}) {
  const padRef = React.useRef<HTMLDivElement>(null);
  const wrapRef = React.useRef<HTMLDivElement>(null);

  const [phase, setPhase] = React.useState<Phase>("waiting");
  const [lit, setLit] = React.useState(0);
  const [path, setPath] = React.useState<number[]>([]);
  const [pointer, setPointer] = React.useState<Point | null>(null);
  const [viaKeyboard, setViaKeyboard] = React.useState(false);
  const [feedback, setFeedback] = React.useState<{ kind: PatternFeedback; path: number[] } | null>(
    null
  );
  const [hint, setHint] = React.useState<string | null>(null);

  // 포인터 이벤트 안에서는 최신 값을 읽어야 하므로 ref로도 들고 있습니다
  const pathRef = React.useRef<number[]>([]);
  const drawingRef = React.useRef(false);
  const lastPointRef = React.useRef<Point | null>(null);
  const phaseRef = React.useRef<Phase>("waiting");
  const timersRef = React.useRef<number[]>([]);

  const later = React.useCallback((fn: () => void, ms: number) => {
    timersRef.current.push(window.setTimeout(fn, Math.max(0, ms)));
  }, []);

  const resetDrawing = React.useCallback(() => {
    drawingRef.current = false;
    lastPointRef.current = null;
    pathRef.current = [];
    setPath([]);
    setPointer(null);
    setViaKeyboard(false);
  }, []);

  // ---- 라운드 시간표: 비움 → 보여 주기 → 그리기 ----------------------------
  React.useEffect(() => {
    const timers: number[] = [];
    const at = (when: number, fn: () => void) =>
      timers.push(window.setTimeout(fn, Math.max(0, when - Date.now())));

    // 새 라운드가 열리면 그리던 것을 버리고 처음부터 (타이머 안에서 바꿔야 React가 편합니다)
    at(0, () => {
      phaseRef.current = "waiting";
      setPhase("waiting");
      setLit(0);
      resetDrawing();

      // ⚠️ 휴대폰 세로 화면에서는 판이 알림·예약 카드에 밀려 화면 아래에 있습니다.
      //    잠결에 화면을 켜면 패턴이 화면 밖에서 재생되고 끝나 버리므로,
      //    다 보이지 않으면 패턴을 보여 주기 전에(비움 시간 동안) 가운데로 데려옵니다.
      const box = wrapRef.current?.getBoundingClientRect();
      if (box && (box.top < 0 || box.bottom > window.innerHeight)) {
        const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        wrapRef.current?.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
      }
    });
    pattern.forEach((_, i) =>
      at(showStartsAt + i * stepMs, () => {
        phaseRef.current = "showing";
        setPhase("showing");
        setLit(i + 1);
      })
    );
    at(inputOpensAt, () => {
      phaseRef.current = "input";
      setPhase("input");
    });
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [round, pattern, showStartsAt, inputOpensAt, stepMs, resetDrawing]);

  // 화면을 떠나면 남은 표시용 타이머도 정리합니다
  React.useEffect(() => {
    const timers = timersRef.current;
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, []);

  // ---- 판정에 넘기기 --------------------------------------------------------
  const submit = React.useCallback(
    (drawn: number[]) => {
      const result = onSubmit(drawn);
      resetDrawing();
      if (result === "too-short") {
        setHint(`점을 ${PATTERN_MIN_INPUT}개 이상 이어 그리세요`);
        later(() => setHint(null), HINT_MS);
        return;
      }
      if (result === "not-ready") return;
      // 맞음·틀림을 잠깐 보여 줍니다 — 다음 라운드의 '비움' 시간과 겹치게 맞춰 두었습니다
      setFeedback({ kind: result, path: drawn });
      later(() => setFeedback(null), FEEDBACK_MS);
    },
    [onSubmit, resetDrawing, later]
  );

  // ---- 마우스·터치·펜 --------------------------------------------------------
  const toGrid = (event: React.PointerEvent): Point | null => {
    const box = padRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return null;
    return {
      x: ((event.clientX - box.left) / box.width) * PATTERN_GRID,
      y: ((event.clientY - box.top) / box.height) * PATTERN_GRID,
    };
  };

  /** 직전 위치에서 지금 위치까지 지나간 자리를 촘촘히 확인합니다 (빠른 스와이프 대비) */
  const sweep = (from: Point, to: Point, start: number[]): number[] => {
    const steps = Math.max(1, Math.ceil(Math.hypot(to.x - from.x, to.y - from.y) / SAMPLE_STEP));
    let next = start;
    for (let i = 1; i <= steps; i++) {
      const dot = hitDot({
        x: from.x + ((to.x - from.x) * i) / steps,
        y: from.y + ((to.y - from.y) * i) / steps,
      });
      if (dot !== null) next = addDot(next, dot);
    }
    return next;
  };

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (phaseRef.current !== "input" || event.button > 0) return;
    const point = toGrid(event);
    if (!point) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);

    drawingRef.current = true;
    lastPointRef.current = point;
    const dot = hitDot(point);
    const next = dot === null ? [] : addDot([], dot);
    pathRef.current = next;
    setPath(next);
    setPointer(point);
    setViaKeyboard(false);
    setHint(null);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drawingRef.current) return;
    const point = toGrid(event);
    if (!point) return;
    const next = sweep(lastPointRef.current ?? point, point, pathRef.current);
    lastPointRef.current = point;
    if (next !== pathRef.current) {
      pathRef.current = next;
      setPath(next);
    }
    setPointer(point);
  };

  const onPointerUp = () => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    submit(pathRef.current);
  };

  const onPointerCancel = () => {
    // 전화가 오거나 손바닥이 닿는 등으로 끊기면 판정하지 않고 버립니다
    resetDrawing();
  };

  // ---- 키보드 ----------------------------------------------------------------
  const onDotKey = (event: React.MouseEvent<HTMLButtonElement>, dot: number) => {
    // 마우스·터치 클릭은 위의 포인터 처리로 이미 받았습니다. 키보드(Enter/Space)만 여기서.
    if (event.detail !== 0 || phaseRef.current !== "input") return;
    const next = addDot(pathRef.current, dot);
    pathRef.current = next;
    setPath(next);
    setViaKeyboard(true);
    setHint(null);
  };

  // ---- 그리기 ----------------------------------------------------------------
  const shownPath = pattern.slice(0, lit);
  const showGuide = phase === "input" && keepVisible;
  const flash = feedback && feedback.kind !== "success" ? feedback : null;

  let mainPath: number[] = [];
  let mainColor: string = STROKE.drawn;
  if (flash) {
    mainPath = flash.path;
    mainColor = flash.kind === "correct" ? STROKE.correct : STROKE.wrong;
  } else if (phase === "showing") {
    mainPath = shownPath;
    mainColor = STROKE.shown;
  } else if (phase === "input") {
    mainPath = path;
  }

  const last = mainPath.length ? center(mainPath[mainPath.length - 1]) : null;
  // pointer는 손을 대고 있는 동안에만 값이 있습니다 (떼면 resetDrawing이 비웁니다)
  const rubber = phase === "input" && !flash && pointer !== null && last !== null;

  const status = flash
    ? flash.kind === "correct"
      ? "맞았어요! 다음 패턴이 나옵니다"
      : "틀렸어요. 새 패턴이 나옵니다"
    : phase === "waiting"
      ? "잠시 후 패턴이 나옵니다"
      : phase === "showing"
        ? `순서를 잘 보세요 — ${lit} / ${pattern.length}`
        : keepVisible
          ? "흐린 선을 따라 똑같이 이어 그리세요"
          : "보여 준 순서대로 이어 그리세요";

  return (
    <div ref={wrapRef} className="flex flex-col items-center gap-3">
      <p
        className={`text-sm font-medium ${
          flash?.kind === "wrong"
            ? "text-rose-600"
            : flash?.kind === "correct"
              ? "text-emerald-600"
              : phase === "showing"
                ? "text-amber-600"
                : "text-slate-600"
        }`}
        aria-live="polite"
        data-testid="pattern-status"
      >
        {status}
      </p>

      {/* 화면을 볼 수 없는 사람에게는 보여 주는 순서를 말로 알려 줍니다 */}
      <p className="sr-only" aria-live="polite">
        {phase === "showing" && lit === pattern.length
          ? `보여 준 순서: ${pattern.map((d) => DOT_NAMES[d]).join(", ")}`
          : ""}
      </p>

      <div
        ref={padRef}
        data-phase={phase}
        data-testid="pattern-pad"
        role="group"
        aria-label="패턴 그리기 판. 점이 켜지는 순서를 본 뒤 같은 순서로 이어 그리세요. 키보드로는 점을 차례로 고른 뒤 확인을 누르세요."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        className={`relative aspect-square w-full max-w-[300px] touch-none select-none rounded-2xl border bg-slate-50 ${
          phase === "input" ? "cursor-crosshair border-sky-200" : "border-slate-200"
        }`}
      >
        <svg
          viewBox={`0 0 ${PATTERN_GRID} ${PATTERN_GRID}`}
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          {showGuide && (
            <polyline
              points={polyline(pattern)}
              fill="none"
              stroke={STROKE.shown}
              strokeOpacity={0.35}
              strokeWidth={0.07}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          {mainPath.length > 1 && (
            <polyline
              points={polyline(mainPath)}
              fill="none"
              stroke={mainColor}
              strokeWidth={0.08}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          {rubber && last && pointer && (
            <line
              x1={last.x}
              y1={last.y}
              x2={Math.min(PATTERN_GRID, Math.max(0, pointer.x))}
              y2={Math.min(PATTERN_GRID, Math.max(0, pointer.y))}
              stroke={STROKE.drawn}
              strokeOpacity={0.5}
              strokeWidth={0.06}
              strokeLinecap="round"
            />
          )}
        </svg>

        {ALL_DOTS.map((dot) => {
          const c = center(dot);
          const inMain = mainPath.includes(dot);
          const isStart =
            (phase === "showing" && lit > 0 && pattern[0] === dot) ||
            (showGuide && pattern[0] === dot);
          const guide = showGuide && pattern.includes(dot);
          const fill = inMain ? mainColor : guide ? `${STROKE.shown}66` : undefined;

          return (
            <button
              key={dot}
              type="button"
              tabIndex={phase === "input" ? 0 : -1}
              aria-label={`점 ${dot + 1}, ${DOT_NAMES[dot]}${inMain ? " (선택됨)" : ""}`}
              aria-disabled={phase !== "input"}
              data-dot={dot}
              data-lit-order={phase === "showing" && shownPath.includes(dot)
                ? shownPath.indexOf(dot) + 1
                : undefined}
              onClick={(event) => onDotKey(event, dot)}
              className="absolute flex h-[22%] w-[22%] -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              style={{ left: `${(c.x / PATTERN_GRID) * 100}%`, top: `${(c.y / PATTERN_GRID) * 100}%` }}
            >
              {isStart && (
                <span
                  className="absolute inset-[18%] rounded-full border-2"
                  style={{ borderColor: STROKE.shown }}
                  aria-hidden="true"
                />
              )}
              <span
                className={`block rounded-full transition-[width,height] duration-150 ${
                  inMain ? "h-[46%] w-[46%]" : "h-[28%] w-[28%] bg-slate-300"
                }`}
                style={fill ? { backgroundColor: fill } : undefined}
                aria-hidden="true"
              />
            </button>
          );
        })}
      </div>

      {hint && <p className="text-xs text-amber-700">{hint}</p>}

      {viaKeyboard && path.length > 0 && phase === "input" && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => submit(pathRef.current)}
            className="rounded-lg bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-700"
          >
            확인 ({path.length}개)
          </button>
          <button
            type="button"
            onClick={resetDrawing}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:border-slate-300"
          >
            지우기
          </button>
        </div>
      )}
    </div>
  );
}
