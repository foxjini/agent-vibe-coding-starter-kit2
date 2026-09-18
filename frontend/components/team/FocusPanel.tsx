/**
 * 집중도 화면 조각들 (components/team/FocusPanel.tsx) — ★ study 팀
 * ============================================================================
 * 값을 만들지 않고 **받은 것을 보여 주기만** 합니다.
 * 판정은 `scenarios/studyEngine.ts`, 값 받기는 `scenarios/useStudy.ts`에 있습니다.
 */
"use client";

import { Eye, EyeOff, Moon, UserX, Wand2 } from "lucide-react";
import React from "react";

import { STATE_LABEL, formatDuration } from "@/scenarios/studyEngine";
import type { SessionState, StudyState } from "@/scenarios/studyEngine";

/** 상태마다 쓰는 색과 아이콘. 색을 바꾸려면 여기만 고치면 됩니다. */
const STATE_STYLE: Record<
  StudyState,
  { tone: string; ring: string; bar: string; Icon: React.ElementType }
> = {
  focused: {
    tone: "text-emerald-700",
    ring: "border-emerald-200 bg-emerald-50",
    bar: "bg-emerald-500",
    Icon: Eye,
  },
  distracted: {
    tone: "text-amber-700",
    ring: "border-amber-200 bg-amber-50",
    bar: "bg-amber-500",
    Icon: EyeOff,
  },
  drowsy: {
    tone: "text-rose-700",
    ring: "border-rose-200 bg-rose-50",
    bar: "bg-rose-500",
    Icon: Moon,
  },
  away: {
    tone: "text-slate-500",
    ring: "border-slate-200 bg-slate-50",
    bar: "bg-slate-300",
    Icon: UserX,
  },
  unknown: {
    tone: "text-sky-700",
    ring: "border-sky-200 bg-sky-50",
    bar: "bg-sky-300",
    Icon: Wand2,
  },
};

/** 지금 상태를 크게 보여 주는 카드 — 3초 안에 이것만 보면 됩니다. */
export function NowCard({
  state,
  score,
  calibrating,
}: {
  state: StudyState;
  score: number | null;
  calibrating: boolean;
}) {
  const style = STATE_STYLE[state];
  const Icon = style.Icon;

  return (
    <section className={`rounded-xl border p-6 ${style.ring}`}>
      <div className="flex items-center gap-2">
        {/* 졸고 있을 때만 움직입니다 — 늘 움직이면 아무 뜻이 없습니다 */}
        <Icon
          className={`h-5 w-5 ${style.tone} ${state === "drowsy" ? "animate-pulse" : ""}`}
        />
        <span className={`text-sm font-semibold ${style.tone}`}>
          {calibrating ? "자세를 배우는 중" : STATE_LABEL[state]}
        </span>
      </div>

      <p className={`mt-3 text-6xl font-bold tabular-nums ${style.tone}`}>
        {score === null ? "—" : score}
        {score !== null && <span className="text-2xl font-normal"> 점</span>}
      </p>

      <p className="mt-2 text-sm text-slate-600">
        {calibrating
          ? "화면을 보고 평소처럼 앉아 있어 주세요. 이 사람의 '정면'을 배우는 중입니다."
          : state === "away"
            ? "자리에 없거나 얼굴이 보이지 않습니다."
            : state === "unknown"
              ? "아직 판단할 만큼 보지 못했습니다."
              : "지금 집중도입니다. 눈·고개·시선을 함께 봅니다."}
      </p>
    </section>
  );
}

/** 카메라가 지금 무엇을 보고 있는지 — 임계값을 맞출 때 봅니다. */
export function MeasureRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-1.5 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-800 tabular-nums">
        {value}
        {hint && <span className="ml-1 text-xs font-normal text-slate-400">{hint}</span>}
      </span>
    </div>
  );
}

/** 지난 시간 동안 어떻게 집중했나 — 1분에 막대 하나. */
export function Timeline({ session }: { session: SessionState }) {
  const buckets = session.buckets.slice(-60);

  if (buckets.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-slate-400">
        1분쯤 지나면 여기에 기록이 쌓입니다.
      </p>
    );
  }

  return (
    <div>
      <div className="flex h-24 items-end gap-0.5" role="img" aria-label="분당 집중도 기록">
        {buckets.map((bucket) => {
          // 그 1분 동안 가장 오래 있었던 상태의 색으로 칠합니다
          const top = (Object.keys(bucket.seconds) as StudyState[]).reduce((a, b) =>
            bucket.seconds[a] >= bucket.seconds[b] ? a : b
          );
          const height = bucket.score === null ? 8 : Math.max(8, bucket.score);
          return (
            <div
              key={bucket.at}
              className={`min-w-[4px] max-w-[24px] flex-1 rounded-sm ${STATE_STYLE[top].bar}`}
              style={{ height: `${height}%` }}
              title={`${new Date(bucket.at).toLocaleTimeString("ko-KR", {
                hour: "2-digit",
                minute: "2-digit",
              })} · ${STATE_LABEL[top]}${bucket.score !== null ? ` · ${bucket.score}점` : ""}`}
            />
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {(["focused", "distracted", "drowsy", "away"] as StudyState[]).map((s) => (
          <span key={s} className="flex items-center gap-1 text-xs text-slate-500">
            <span className={`h-2 w-2 rounded-sm ${STATE_STYLE[s].bar}`} />
            {STATE_LABEL[s]}
          </span>
        ))}
      </div>
    </div>
  );
}

/** 세션 요약 — 전시회에서 관람객에게 보여 주는 결과입니다. */
export function SummaryGrid({
  summary,
}: {
  summary: {
    seated: number;
    focused: number;
    focusRate: number | null;
    averageScore: number | null;
    drowsyEpisodes: number;
  };
}) {
  const cells = [
    { label: "앉아 있던 시간", value: formatDuration(summary.seated) },
    { label: "집중한 시간", value: formatDuration(summary.focused) },
    {
      label: "집중 비율",
      value: summary.focusRate === null ? "—" : `${summary.focusRate}%`,
    },
    {
      label: "평균 점수",
      value: summary.averageScore === null ? "—" : `${summary.averageScore}점`,
    },
    { label: "졸음 횟수", value: `${summary.drowsyEpisodes}번` },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {cells.map((cell) => (
        <div key={cell.label} className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs text-slate-500">{cell.label}</p>
          <p className="mt-1 text-lg font-semibold text-slate-900 tabular-nums">
            {cell.value}
          </p>
        </div>
      ))}
    </div>
  );
}
