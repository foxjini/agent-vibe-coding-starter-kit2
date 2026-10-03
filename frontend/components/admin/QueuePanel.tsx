"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Users, SkipForward, XCircle, Loader2, QrCode as QrIcon, KeyRound } from "lucide-react";
import { apiUrl } from "@/utils/apiConfig";
import { adminFetch } from "@/utils/adminSession";
import { QueueSnapshot } from "@/types";

/**
 * 전시 체험 대기열 운영 (부록G §2-③ · ⑧)
 *
 * 대기열은 스케줄러가 1분마다 알아서 굴린다. 이 패널은 그 상태를 보여 주고,
 * 선생님이 필요할 때만 끼어들 수 있게 한다 — 관람객이 자리를 떠났거나,
 * 줄이 꼬였을 때 다음 사람으로 넘기는 정도다.
 */
export function QueuePanel() {
  const [queue, setQueue] = useState<QueueSnapshot | null>(null);
  const [servingPin, setServingPin] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    let snapshot: QueueSnapshot | null = null;
    try {
      const res = await fetch(apiUrl("/api/experience/queue"));
      if (res.ok) {
        snapshot = (await res.json()).data ?? null;
        setQueue(snapshot);
      }
    } catch {
      /* 백엔드가 꺼져 있어도 관리자 화면은 떠 있어야 한다 */
    }

    // 호출만 해 둔 사람의 입장 비밀번호는 관리자만 볼 수 있다.
    // 관람객이 폰에서 번호를 놓쳤을 때 선생님이 읽어 주기 위한 것이다.
    const serving = snapshot?.now_serving;
    if (!serving || serving.status !== "called") {
      setServingPin(null);
      return;
    }
    try {
      const res = await adminFetch(`/api/experience/tickets/${serving.id}`);
      setServingPin(res.ok ? ((await res.json()).data?.pin_code ?? null) : null);
    } catch {
      setServingPin(null);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const timer = setInterval(load, 10_000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  const act = async (path: string, label: string) => {
    setBusy(true);
    setNotice(null);
    try {
      const res = await adminFetch(path, { method: "POST" });
      if (res.status === 401) setNotice("관리자 인증이 만료되었습니다.");
      else if (res.ok) {
        setNotice(`${label} 완료`);
        await load();
      } else setNotice(`${label}에 실패했습니다.`);
    } catch {
      setNotice("백엔드에 연결할 수 없습니다.");
    } finally {
      setBusy(false);
    }
  };

  if (queue && !queue.enabled) {
    return (
      <section className="bg-surface border border-line rounded-2xl p-5 flex items-center gap-3">
        <QrIcon className="w-5 h-5 text-ink-3 shrink-0" aria-hidden />
        <p className="text-sm text-ink-2">
          전시 체험 모드가 꺼져 있습니다.{" "}
          <code className="text-xs">backend/.env</code> 의{" "}
          <code className="text-xs">EXPERIENCE_ENABLED</code> 를 확인하세요.
        </p>
      </section>
    );
  }

  return (
    <section className="bg-surface border border-line rounded-2xl p-5 sm:p-6 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-start gap-3 min-w-0">
          <Users className="w-5 h-5 text-brass shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <h3 className="text-base font-bold text-ink">전시 체험 대기열</h3>
            <p className="text-xs text-ink-3 mt-0.5">
              관람객이 QR로 받은 체험권입니다. 한 명당{" "}
              <strong className="text-ink-2 tnum">{queue?.experience_minutes ?? 3}분</strong>, 호출 후{" "}
              <strong className="text-ink-2 tnum">{queue?.call_grace_minutes ?? 2}분</strong> 안에
              오지 않으면 다음 분에게 넘어갑니다.
            </p>
          </div>
        </div>
        <button
          onClick={() => act("/api/experience/advance", "다음 호출")}
          disabled={busy}
          className="px-3 py-1.5 rounded-lg bg-ink hover:bg-ink/90 disabled:opacity-50 text-surface text-xs font-bold transition-colors cursor-pointer inline-flex items-center gap-1.5"
        >
          {busy ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
          ) : (
            <SkipForward className="w-3.5 h-3.5" aria-hidden />
          )}
          다음 사람 호출
        </button>
      </div>

      {notice && <p className="text-xs text-ink-2">{notice}</p>}
      {queue?.paused_reason && (
        <p className="text-xs font-semibold text-brass bg-brass-soft border border-brass/30 rounded-lg px-3 py-2">
          일시 정지 — {queue.paused_reason}
        </p>
      )}

      <div className="grid gap-5 sm:grid-cols-[auto_1fr] sm:gap-8">
        {/* 지금 호출 중 */}
        <div>
          <h4 className="text-[11px] font-bold tracking-wider uppercase text-ink-3 mb-2">
            지금 호출
          </h4>
          {queue?.now_serving ? (
            <div className="px-4 py-3 rounded-xl bg-brass-soft border border-brass/30 text-center">
              <span className="block font-mono tnum text-4xl font-extrabold text-brass leading-none">
                {queue.now_serving.ticket_no}
              </span>
              <span className="block text-xs text-ink-2 mt-1.5">{queue.now_serving.nickname}</span>
              <span className="block text-[11px] text-ink-3 mt-0.5">
                {queue.now_serving.status === "active" ? "이용 중" : "입장 대기"}
              </span>
              {servingPin && (
                <span
                  className="mt-2 pt-2 border-t border-brass/25 flex items-center justify-center gap-1.5 text-[11px] text-ink-3"
                  title="관람객이 폰에서 비밀번호를 놓쳤을 때만 알려 주세요"
                >
                  <KeyRound className="w-3 h-3" aria-hidden />
                  <span className="font-mono tnum tracking-[0.12em] text-ink-2">{servingPin}</span>
                </span>
              )}
            </div>
          ) : (
            <p className="text-xs text-ink-3">대기 중인 사람이 없습니다.</p>
          )}
        </div>

        {/* 대기 줄 */}
        <div className="min-w-0">
          <h4 className="text-[11px] font-bold tracking-wider uppercase text-ink-3 mb-2">
            대기 {queue?.waiting_count ?? 0}명
            {!!queue?.estimated_wait_min && (
              <span className="ml-2 font-normal normal-case tracking-normal">
                (약 {queue.estimated_wait_min}분)
              </span>
            )}
          </h4>
          {!queue?.waiting?.length ? (
            <p className="text-xs text-ink-3">줄이 비어 있습니다.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {queue.waiting.map((w) => (
                <li
                  key={w.id}
                  className="inline-flex items-center gap-2 pl-2.5 pr-1.5 py-1.5 rounded-lg bg-raised border border-line"
                >
                  <span className="font-mono tnum text-sm font-bold text-ink">{w.ticket_no}</span>
                  <span className="text-xs text-ink-2 max-w-[7rem] truncate">{w.nickname}</span>
                  <button
                    onClick={() => act(`/api/experience/tickets/${w.id}/cancel`, "취소")}
                    disabled={busy}
                    title={`${w.ticket_no}번 취소`}
                    className="text-ink-3 hover:text-live transition-colors cursor-pointer disabled:opacity-40"
                  >
                    <XCircle className="w-4 h-4" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
