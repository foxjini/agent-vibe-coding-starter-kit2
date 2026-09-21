"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  CalendarClock,
  CircleDot,
  PlayCircle,
  AlertTriangle,
  Bell,
  PowerOff,
  UserX,
  Loader2,
} from "lucide-react";
import { apiUrl } from "@/utils/apiConfig";
import { adminFetch } from "@/utils/adminSession";

interface SchedulerAction {
  action: "warn_10min" | "session_end" | "no_show" | string;
  reservation_id?: number;
  student_name?: string;
  time_slot?: string;
  message?: string;
  at?: string;
}

interface UpcomingItem {
  reservation_id: number;
  student_name: string;
  time_slot: string;
  status: string;
  starts_at: string;
  warns_at: string;
  ends_at: string;
}

interface SchedulerStatus {
  enabled: boolean;
  interval_sec?: number;
  warn_before_min?: number;
  no_show_grace_min?: number;
  timezone?: string;
  now?: string;
  last_tick?: string | null;
  last_error?: string | null;
  actions: SchedulerAction[];
  upcoming: UpcomingItem[];
}

const ACTION_META: Record<string, { icon: React.ElementType; label: string; cls: string }> = {
  warn_10min: { icon: Bell, label: "종료 10분 전", cls: "text-brass bg-brass-soft border-brass/30" },
  session_end: { icon: PowerOff, label: "이용 종료", cls: "text-live bg-live-soft border-live/30" },
  no_show: { icon: UserX, label: "노쇼 취소", cls: "text-ink-3 bg-raised border-line" },
};

/** "2026-09-21T12:21+09:00" → "12:21" */
function hhmm(iso?: string): string {
  if (!iso) return "--:--";
  const m = iso.match(/T(\d{2}:\d{2})/);
  return m ? m[1] : "--:--";
}

/**
 * 예약 시간 자동 운영 엔진 상태 (부록G §2-① · ⑧)
 *
 * 엔진은 백엔드에서 조용히 돌기 때문에, 살아 있는지 확인할 창이 없으면
 * "왜 종료가 안 됐지?"를 추측으로 알아내야 한다. 그래서 마지막으로 돈 시각과
 * 최근에 무엇을 했는지, 오늘 남은 일정이 언제인지를 함께 보여 준다.
 *
 * [지금 한 바퀴] 는 시연·점검용이다. 1분을 기다리지 않고 즉시 돌려 볼 수 있다.
 */
export function SchedulerPanel() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/scheduler/status"));
      if (res.ok) setStatus((await res.json()).data ?? null);
    } catch {
      /* 백엔드가 꺼져 있어도 관리자 화면은 떠 있어야 한다 */
    }
  }, []);

  useEffect(() => {
    // 첫 조회를 setTimeout 으로 미루는 이유: effect 본문에서 곧바로 상태를 바꾸면
    // 렌더가 연쇄로 일어난다. 30초마다 갱신은 전시장에서 충분한 주기다.
    const first = setTimeout(load, 0);
    const timer = setInterval(load, 30_000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  const runNow = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const res = await adminFetch("/api/scheduler/run", { method: "POST" });
      if (res.status === 401) {
        setNotice("관리자 인증이 만료되었습니다. 다시 인증해 주세요.");
      } else if (res.ok) {
        const json = await res.json();
        const n = json?.data?.actions?.length ?? 0;
        setNotice(n ? `${n}건을 처리했습니다.` : "지금 처리할 일이 없습니다.");
        await load();
      } else {
        setNotice("실행에 실패했습니다.");
      }
    } catch {
      setNotice("백엔드에 연결할 수 없습니다.");
    } finally {
      setBusy(false);
    }
  };

  const live = status?.enabled && !status?.last_error;

  return (
    <section className="bg-surface border border-line rounded-2xl p-5 sm:p-6 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-start gap-3 min-w-0">
          <CalendarClock className="w-5 h-5 text-brass shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <h3 className="text-base font-bold text-ink">예약 시간 자동 운영</h3>
            <p className="text-xs text-ink-3 mt-0.5">
              사람이 버튼을 누르지 않아도 종료 알림 · 퇴실 처리 · 노쇼 취소가 시각에 맞춰
              진행됩니다.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-bold ${
              live
                ? "bg-free-soft text-free border-free/30"
                : status?.enabled === false
                ? "bg-raised text-ink-3 border-line"
                : "bg-live-soft text-live border-live/30"
            }`}
          >
            {live ? (
              <CircleDot className="w-3.5 h-3.5" aria-hidden />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5" aria-hidden />
            )}
            {status === null ? "확인 중" : live ? "동작 중" : status.enabled ? "오류" : "꺼짐"}
          </span>
          <button
            onClick={runNow}
            disabled={busy}
            className="px-3 py-1.5 rounded-lg bg-ink hover:bg-ink/90 disabled:opacity-50 text-surface text-xs font-bold transition-colors cursor-pointer inline-flex items-center gap-1.5"
          >
            {busy ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
            ) : (
              <PlayCircle className="w-3.5 h-3.5" aria-hidden />
            )}
            지금 한 바퀴
          </button>
        </div>
      </div>

      {status?.last_error && (
        <p className="text-xs text-live flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden />
          {status.last_error}
        </p>
      )}
      {notice && <p className="text-xs text-ink-2">{notice}</p>}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* 오늘 남은 일정 */}
        <div>
          <h4 className="text-[11px] font-bold tracking-wider uppercase text-ink-3 mb-2.5">
            오늘 남은 일정
          </h4>
          {!status?.upcoming?.length ? (
            <p className="text-xs text-ink-3">오늘 처리할 예약이 없습니다.</p>
          ) : (
            <ul className="space-y-2">
              {status.upcoming.map((u) => (
                <li key={u.reservation_id} className="p-3 rounded-xl bg-raised border border-line">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-ink truncate">
                      {u.student_name}
                      <span className="ml-2 font-normal text-ink-3">
                        {u.time_slot === "lunch" ? "점심" : "저녁"}
                      </span>
                    </span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${
                        u.status === "active"
                          ? "bg-brass-soft text-brass border-brass/30"
                          : "bg-surface text-ink-3 border-line"
                      }`}
                    >
                      {u.status === "active" ? "이용 중" : "입장 대기"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-2 font-mono tnum text-[11px] text-ink-3">
                    <span>시작 {hhmm(u.starts_at)}</span>
                    <span className="text-brass">알림 {hhmm(u.warns_at)}</span>
                    <span className="text-live">종료 {hhmm(u.ends_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 최근 처리 내역 */}
        <div>
          <h4 className="text-[11px] font-bold tracking-wider uppercase text-ink-3 mb-2.5">
            최근 처리 내역
          </h4>
          {!status?.actions?.length ? (
            <p className="text-xs text-ink-3">아직 자동으로 처리한 일이 없습니다.</p>
          ) : (
            <ul className="space-y-2">
              {status.actions.slice(0, 5).map((a, i) => {
                const meta = ACTION_META[a.action] ?? {
                  icon: CircleDot,
                  label: a.action,
                  cls: "text-ink-3 bg-raised border-line",
                };
                const Icon = meta.icon;
                return (
                  <li key={`${a.reservation_id}-${a.at}-${i}`} className="flex items-start gap-2.5">
                    <span
                      className={`shrink-0 mt-0.5 inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-bold whitespace-nowrap ${meta.cls}`}
                    >
                      <Icon className="w-3 h-3" aria-hidden />
                      {meta.label}
                    </span>
                    <span className="min-w-0 text-xs text-ink-2">
                      <span className="font-mono tnum text-ink-3 mr-1.5">{hhmm(a.at)}</span>
                      {a.message}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <p className="pt-1 text-[11px] text-ink-3 font-mono tnum">
        주기 {status?.interval_sec ?? "--"}초 · 종료 {status?.warn_before_min ?? "--"}분 전 알림 ·
        노쇼 유예 {status?.no_show_grace_min ?? "--"}분 · {status?.timezone ?? "--"} · 마지막 실행{" "}
        {hhmm(status?.last_tick ?? undefined)}
      </p>
    </section>
  );
}
