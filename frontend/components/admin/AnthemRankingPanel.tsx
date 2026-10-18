"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Download, Gift, Loader2, RotateCcw, School } from "lucide-react";
import { apiUrl } from "@/utils/apiConfig";
import { adminFetch } from "@/utils/adminSession";
import { SCHOOL_ANTHEM_TITLE } from "@/data/karaokeSongs";
import { ScoreRecord } from "@/types";

/** 상품을 준 기록 id — 이 노트북에만 적어 두는 메모다 (서버에는 남기지 않는다) */
const GIVEN_KEY = "karaoke.anthemPrizeGiven.v1";

function readGiven(): number[] {
  try {
    return JSON.parse(window.localStorage.getItem(GIVEN_KEY) || "[]");
  } catch {
    return [];
  }
}

/** "2026-10-18T03:21:09Z" → 이 노트북 시간대로 "12:21:09" (오늘 기록이 아니면 날짜도) */
function formatWhen(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  const today = new Date();
  return d.toDateString() === today.toDateString() ? time : `${d.getMonth() + 1}/${d.getDate()} ${time}`;
}

/**
 * 교가 순위 · 상품 배부 (관리자 화면)
 *
 * 축제 교가 부르기 대회의 순위표다. 같은 이름으로 여러 번 부르면 가장 높은 점수
 * 하나만 남기고, 같은 점수면 먼저 낸 사람이 앞선다. 동명이인은 기록 시각으로 구분한다.
 * [CSV 내려받기]로 엑셀에서 열어 상품 명단을 만든다.
 */
export function AnthemRankingPanel() {
  const [period, setPeriod] = useState<"today" | "all">("today");
  const [rows, setRows] = useState<ScoreRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [given, setGiven] = useState<number[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = `period=${period}&limit=50&best=true&title=${encodeURIComponent(SCHOOL_ANTHEM_TITLE)}`;
      const res = await fetch(apiUrl(`/api/scores/top?${q}`));
      if (res.ok) setRows((await res.json()).data || []);
    } catch {
      /* 백엔드가 꺼져 있어도 관리자 화면은 떠 있어야 한다 */
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    const first = setTimeout(() => {
      setGiven(readGiven());
      void load();
    }, 0);
    const timer = setInterval(load, 15_000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  const toggleGiven = (id: number) => {
    const next = given.includes(id) ? given.filter((g) => g !== id) : [...given, id];
    setGiven(next);
    try {
      window.localStorage.setItem(GIVEN_KEY, JSON.stringify(next));
    } catch {
      /* 저장이 막혀도 이번 화면에서는 유지된다 */
    }
  };

  const download = async () => {
    setNotice(null);
    try {
      const q = `period=${period}&best=true&title=${encodeURIComponent(SCHOOL_ANTHEM_TITLE)}`;
      const res = await adminFetch(`/api/scores/export?${q}`);
      if (res.status === 401) {
        setNotice("관리자 인증이 만료되었습니다. 다시 인증해 주세요.");
        return;
      }
      if (!res.ok) {
        setNotice("기록을 내려받지 못했습니다.");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `교가순위-${period === "today" ? "오늘" : "전체"}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setNotice("백엔드에 연결할 수 없습니다.");
    }
  };

  return (
    <section className="bg-surface border border-line rounded-2xl p-5 sm:p-6 space-y-4" data-testid="anthem-ranking">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-start gap-3 min-w-0">
          <School className="w-5 h-5 text-brass shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <h3 className="text-base font-bold text-ink">교가 순위 · 상품 배부</h3>
            <p className="text-xs text-ink-3 mt-0.5">
              교가 점수만 모은 순위입니다. 같은 이름은 최고 점수 하나만, 같은 점수면 먼저 부른 사람이
              앞섭니다. 동명이인은 기록 시각으로 구분하세요.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-line-strong overflow-hidden text-xs font-bold">
            {(["today", "all"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 cursor-pointer ${
                  period === p ? "bg-ink text-surface" : "bg-raised text-ink-2 hover:text-ink"
                }`}
              >
                {p === "today" ? "오늘" : "전체"}
              </button>
            ))}
          </div>
          <button
            onClick={() => void load()}
            className="px-3 py-1.5 rounded-lg bg-raised border border-line-strong text-xs font-bold text-ink-2 inline-flex items-center gap-1.5 cursor-pointer"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
            새로고침
          </button>
          <button
            onClick={() => void download()}
            className="px-3 py-1.5 rounded-lg bg-ink hover:bg-ink/90 text-surface text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            CSV 내려받기
          </button>
        </div>
      </div>

      {notice && <p className="text-xs text-live">{notice}</p>}

      {rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-ink-3">
          아직 교가 기록이 없습니다. 부스에서 교가를 부르고 채점하면 여기에 쌓입니다.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-line text-ink-3 text-[11px]">
                <th className="pb-2 font-medium w-12">순위</th>
                <th className="pb-2 font-medium">이름</th>
                <th className="pb-2 font-medium">점수</th>
                <th className="pb-2 font-medium">등급</th>
                <th className="pb-2 font-medium">기록 시각</th>
                <th className="pb-2 font-medium text-right">상품</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {rows.map((r, i) => {
                const done = given.includes(r.id);
                return (
                  <tr key={r.id} className={i < 3 ? "bg-brass-soft/40" : undefined}>
                    <td className="py-2 font-mono tnum font-bold text-ink">{i + 1}</td>
                    <td className="py-2 font-semibold text-ink">{r.nickname}</td>
                    <td className="py-2 font-mono tnum font-bold text-brass">{r.score}</td>
                    <td className="py-2 text-ink-2">{r.rank_label ?? "-"}</td>
                    <td className="py-2 font-mono tnum text-xs text-ink-3">{formatWhen(r.created_at)}</td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => toggleGiven(r.id)}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold border inline-flex items-center gap-1 cursor-pointer ${
                          done
                            ? "bg-free-soft border-free/50 text-free"
                            : "bg-raised border-line-strong text-ink-2 hover:text-ink"
                        }`}
                        title="이 노트북에만 기록됩니다"
                      >
                        <Gift className="w-3 h-3" />
                        {done ? "배부함" : "배부 표시"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
