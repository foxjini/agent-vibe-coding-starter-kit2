"use client";

import React, { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { Mic2, Users, Clock, PartyPopper, Trash2, RotateCcw, Loader2, KeyRound } from "lucide-react";
import { apiUrl } from "@/utils/apiConfig";
import {
  subscribeTicket,
  getTicketSnapshot,
  getTicketServerSnapshot,
  parseTicket,
  saveTicket,
  clearTicket,
} from "@/utils/ticketStore";
import { QueueSnapshot, QueueTicket } from "@/types";

const POLL_MS = 4000;

/**
 * `/try` — 전시장 관람객의 폰 화면 (부록G §2-③)
 *
 * 부스 화면의 QR을 찍으면 여기로 온다. 전시장에 온 사람에게는 예약 PIN이 없고,
 * 줄을 서서 기다리는 동안 "내가 몇 번째인지"를 알 방법도 없었다.
 *
 * 화면은 한 가지만 크게 말한다 — 지금 당신 차례가 맞는가 아닌가.
 * 그래서 대기 번호와 상태 문구를 화면에서 가장 큰 요소로 두고, 나머지는 뺀다.
 */
export default function TryPage() {
  const storedId = useSyncExternalStore(
    subscribeTicket,
    getTicketSnapshot,
    getTicketServerSnapshot
  );
  const stored = useMemo(() => parseTicket(storedId), [storedId]);
  const ticketId = stored?.id ?? null;
  const storedPin = stored?.pin ?? null;

  const [ticket, setTicket] = useState<QueueTicket | null>(null);
  const [queue, setQueue] = useState<QueueSnapshot | null>(null);
  const [nickname, setNickname] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const qRes = await fetch(apiUrl("/api/experience/queue"));
      if (qRes.ok) setQueue((await qRes.json()).data ?? null);
    } catch {
      /* 잠깐 끊겨도 화면은 그대로 둔다 */
    }
    if (!ticketId) {
      setTicket(null);
      return;
    }
    try {
      // 비밀번호를 같이 보내면 "내 체험권"임이 확인되어 서버가 비밀번호를 돌려준다
      const query = storedPin ? `?pin=${encodeURIComponent(storedPin)}` : "";
      const tRes = await fetch(apiUrl(`/api/experience/tickets/${ticketId}${query}`));
      if (tRes.ok) setTicket((await tRes.json()).data ?? null);
      else if (tRes.status === 404) clearTicket();
    } catch {
      /* 위와 같다 */
    }
  }, [ticketId, storedPin]);

  useEffect(() => {
    // effect 본문에서 곧바로 상태를 바꾸지 않도록 첫 조회를 한 틱 미룬다
    const first = setTimeout(load, 0);
    const timer = setInterval(load, POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  const issue = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/experience/tickets"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: nickname.trim() || "관람객" }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json?.error?.message ?? "체험권을 받지 못했습니다.");
        return;
      }
      saveTicket(json.data.id, json.data.pin_code);
      setTicket(json.data);
    } catch {
      setError("부스 시스템에 연결할 수 없습니다. 잠시 뒤 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  };

  /**
   * [체험권 버리기] — 줄에서 실제로 빠진다.
   * 예전에는 이 폰에서만 지워져서, 떠난 사람이 줄에 남아 있다가 호출되고 다음
   * 사람이 호출 유예 시간만큼 괜히 기다렸다. 체험 중에는 버릴 수 없다(서버가 막는다).
   */
  const leave = async () => {
    if (!ticketId) return;
    if (!window.confirm("체험권을 버리면 줄에서 빠집니다. 다시 받으면 맨 뒤로 갑니다.")) return;
    if (storedPin) {
      try {
        const res = await fetch(apiUrl(`/api/experience/tickets/${ticketId}/leave`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin: storedPin }),
        });
        if (res.status === 409) {
          const json = await res.json().catch(() => null);
          setError(json?.error?.message ?? "지금은 체험권을 버릴 수 없습니다.");
          return;
        }
      } catch {
        /* 서버에 닿지 않으면 이 폰에서만 지운다 — 줄은 호출 유예 시간 뒤 저절로 넘어간다 */
      }
    }
    setError(null);
    clearTicket();
  };

  const finished = ticket && (ticket.status === "done" || ticket.status === "expired");
  const myTurn = ticket?.status === "called";
  const playing = ticket?.status === "active";

  return (
    <div className="theme-day min-h-screen bg-canvas text-ink">
      <header className="px-5 py-4 border-b border-line bg-surface">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-brass text-on-accent flex items-center justify-center shrink-0">
            <Mic2 className="w-4 h-4" aria-hidden />
          </span>
          <span>
            <span className="block text-sm font-extrabold">학교 노래방 부스</span>
            <span className="block text-[11px] text-ink-3">전시 체험</span>
          </span>
        </Link>
      </header>

      <main className="max-w-md mx-auto px-5 py-6 space-y-5">
        {/* ── 체험권이 없을 때 ─────────────────────────────── */}
        {!ticket || finished ? (
          <>
            {finished && (
              <div className="rounded-2xl bg-surface border border-line p-5 text-center">
                <PartyPopper className="w-7 h-7 text-brass mx-auto" aria-hidden />
                <p className="mt-2 text-base font-bold">
                  {ticket?.status === "done" ? "체험이 끝났습니다!" : "차례를 놓쳤습니다"}
                </p>
                <p className="mt-1 text-sm text-ink-2">
                  {ticket?.status === "done"
                    ? "즐거우셨다면 한 번 더 줄을 서 보세요."
                    : "호출된 뒤 시간 안에 오지 않아 다음 분에게 넘어갔습니다."}
                </p>
              </div>
            )}

            <section className="rounded-2xl bg-surface border border-line p-6 space-y-4">
              <div>
                <h1 className="text-xl font-extrabold">노래방 부스 체험하기</h1>
                <p className="mt-1.5 text-sm text-ink-2 leading-relaxed">
                  체험권을 받으면 <strong className="text-ink">대기 번호</strong>가 나옵니다.
                  차례가 되면 이 화면에 <strong className="text-ink">입장 비밀번호</strong>가
                  뜨고, 부스 앞 키패드에 누르면 문이 열립니다.
                </p>
              </div>

              <div className="flex items-center gap-4 px-4 py-3 rounded-xl bg-raised border border-line text-sm">
                <span className="flex items-center gap-1.5 text-ink-2">
                  <Users className="w-4 h-4 text-ink-3" aria-hidden />
                  대기 <strong className="text-ink tnum">{queue?.waiting_count ?? 0}</strong>명
                </span>
                <span className="flex items-center gap-1.5 text-ink-2">
                  <Clock className="w-4 h-4 text-ink-3" aria-hidden />약{" "}
                  <strong className="text-ink tnum">{queue?.estimated_wait_min ?? 0}</strong>분
                </span>
              </div>

              <div className="space-y-2.5">
                <label htmlFor="try-nickname" className="block text-sm font-bold">
                  이름 <span className="font-normal text-ink-3">(선택 · 호출할 때 부릅니다)</span>
                </label>
                <input
                  id="try-nickname"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value.slice(0, 10))}
                  placeholder="예: 민제"
                  maxLength={10}
                  className="w-full px-4 py-3 rounded-xl bg-raised border border-line-strong placeholder-ink-3 outline-none"
                />
                <button
                  onClick={issue}
                  disabled={busy || queue?.enabled === false}
                  className="w-full py-3.5 rounded-xl bg-ink hover:bg-ink/90 disabled:opacity-50 text-surface font-extrabold transition-colors cursor-pointer inline-flex items-center justify-center gap-2"
                >
                  {busy ? <Loader2 className="w-5 h-5 animate-spin" aria-hidden /> : null}
                  {finished ? "다시 줄 서기" : "체험권 받기"}
                </button>
                {queue?.enabled === false && (
                  <p className="text-sm text-ink-3 text-center">지금은 체험 모드를 운영하지 않습니다.</p>
                )}
                {error && <p className="text-sm text-live">{error}</p>}
              </div>
            </section>
          </>
        ) : (
          /* ── 체험권이 있을 때 ───────────────────────────── */
          <section
            className={`rounded-2xl border overflow-hidden ${
              myTurn ? "bg-surface border-free/50" : "bg-surface border-line"
            }`}
          >
            <div
              className={`px-5 py-2.5 border-b text-xs font-bold ${
                myTurn
                  ? "bg-free-soft border-free/25 text-free"
                  : playing
                  ? "bg-brass-soft border-brass/25 text-brass"
                  : "bg-raised border-line text-ink-3"
              }`}
            >
              {myTurn ? "지금 입장하세요" : playing ? "체험 중입니다" : "대기 중"}
            </div>

            <div className="p-6 text-center space-y-1">
              <span className="block text-[11px] font-semibold tracking-wider uppercase text-ink-3">
                대기 번호
              </span>
              <span className="block font-mono tnum text-7xl font-extrabold leading-none">
                {ticket.ticket_no}
              </span>
              <span className="block text-sm text-ink-2 pt-1">{ticket.nickname}님</span>
            </div>

            {myTurn ? (
              <div className="px-6 pb-6 space-y-4">
                <div className="rounded-xl bg-free-soft border border-free/30 p-4 text-center">
                  <span className="flex items-center justify-center gap-1.5 text-[11px] font-semibold tracking-wider uppercase text-free">
                    <KeyRound className="w-3.5 h-3.5" aria-hidden />
                    입장 비밀번호
                  </span>
                  <span className="block font-mono tnum text-5xl font-extrabold tracking-[0.18em] text-ink mt-1.5">
                    {ticket.pin_code ?? storedPin ?? "----"}
                  </span>
                </div>
                <p className="text-sm text-ink-2 text-center leading-relaxed">
                  부스 앞 키패드에 이 네 자리를 누르면 문이 열립니다.
                  <br />
                  <strong className="text-ink">{queue?.call_grace_minutes ?? 2}분</strong> 안에
                  오지 않으면 다음 분에게 넘어갑니다.
                </p>
              </div>
            ) : playing ? (
              <div className="px-6 pb-6">
                <p className="text-sm text-ink-2 text-center leading-relaxed">
                  마음껏 부르세요! <strong className="text-ink">{queue?.experience_minutes ?? 3}분</strong>{" "}
                  뒤에 자동으로 정리되고 다음 분이 들어옵니다.
                </p>
              </div>
            ) : (
              <div className="px-6 pb-6 space-y-3">
                <div className="flex items-center justify-center gap-5 py-3 rounded-xl bg-raised border border-line">
                  <span className="text-center">
                    <span className="block text-[11px] text-ink-3">앞에</span>
                    <span className="block font-mono tnum text-2xl font-bold">
                      {ticket.position ?? 0}명
                    </span>
                  </span>
                  <span className="w-px h-8 bg-line" aria-hidden />
                  <span className="text-center">
                    <span className="block text-[11px] text-ink-3">예상 대기</span>
                    <span className="block font-mono tnum text-2xl font-bold">
                      약 {ticket.estimated_wait_min ?? 0}분
                    </span>
                  </span>
                </div>
                {queue?.paused_reason && (
                  <p className="text-sm font-semibold text-brass text-center">
                    {queue.paused_reason}
                  </p>
                )}
                <p className="text-sm text-ink-2 text-center leading-relaxed">
                  차례가 되면 이 화면에 비밀번호가 뜹니다.
                  <br />이 페이지를 닫아도 괜찮습니다 — 다시 열면 그대로 남아 있습니다.
                </p>
              </div>
            )}

            {error && <p className="px-6 pb-3 text-sm text-live">{error}</p>}

            <div className="px-6 pb-5 flex items-center justify-between gap-2 border-t border-line pt-4">
              <button
                onClick={() => void load()}
                className="text-xs font-semibold text-ink-3 hover:text-ink transition-colors cursor-pointer inline-flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" aria-hidden />
                새로고침
              </button>
              {!playing && (
                <button
                  onClick={() => void leave()}
                  className="text-xs font-semibold text-ink-3 hover:text-live transition-colors cursor-pointer inline-flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden />
                  체험권 버리기
                </button>
              )}
            </div>
          </section>
        )}

        <p className="text-center text-xs text-ink-3">
          <Link href="/" className="underline underline-offset-4 hover:text-ink">
            학교 학생이신가요? 예약 화면으로
          </Link>
        </p>
      </main>
    </div>
  );
}
