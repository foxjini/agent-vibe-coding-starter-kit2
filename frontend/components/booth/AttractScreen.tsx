"use client";

import React, { useEffect, useState } from "react";
import { Mic2, Loader2, Trophy, Crown, Flame, Clock, CalendarCheck } from "lucide-react";
import { QueueSnapshot, ScoreRecord } from "@/types";
import { QrCode } from "@/components/booth/QrCode";
import { RemainingClock } from "@/components/booth/SessionStrip";
import { BoothSessionState, endsAtLabel } from "@/hooks/useBoothSession";

interface PopularSong {
  id: string;
  title: string;
  singer: string;
}

interface AttractScreenProps {
  /**
   * standby — 부스 전원이 꺼져 있다(비어 있음). 키패드로 인증해야 한다.
   *           노래방을 여는 버튼은 아예 그리지 않는다.
   * ready   — 비밀번호 인증으로 전원이 들어왔다. 이제 노래방을 시작할 수 있다.
   */
  mode: "standby" | "ready";
  /** standby 때 왼쪽에 놓을 화면 키패드 */
  keypad?: React.ReactNode;
  /** ready 때 보여 줄 이용자·남은 시간 */
  session?: BoothSessionState | null;
  topToday: ScoreRecord[];
  topAll: ScoreRecord[];
  popularSongs: PopularSong[];
  nickname: string;
  onNicknameChange: (value: string) => void;
  onEnter: () => void;
  onEnterWithoutMic: () => void;
  isEntering: boolean;
  enterNotice: string | null;
  /** 전시 체험 대기열 (부록G §2-③). 체험 모드를 안 쓰면 null 이다 */
  queue?: QueueSnapshot | null;
}

/** 순환 패널 정의 — 순서가 곧 화면에 도는 순서다 */
const PANELS = [
  { key: "today", label: "오늘의 순위", icon: Flame },
  { key: "all", label: "명예의 전당", icon: Crown },
  { key: "songs", label: "인기 애창곡", icon: Trophy },
] as const;

const ROTATE_MS = 8000;

/**
 * 무인 어트랙트 화면 (부록G §2-⑥)
 *
 * 부스 대형 화면에서 노래방이 아직 시작되지 않았을 때 떠 있는 화면이다.
 * 목적은 셋이다.
 *   1. 처음 온 사람에게 "여기서 뭘 하면 되는지" 한 문장으로 알려 준다
 *   2. 비밀번호를 누를 키패드를 준다 — 인증 전에는 노래방을 열 방법이 없다
 *      (예전에는 [노래방 시작하기]를 누르면 예약 없이도 노래방이 열렸다)
 *   3. 순위를 돌려 보여 줘서 "나도 해 볼까" 하게 만든다
 *
 * 2~3m 떨어져서 보므로 글자를 크게 쓴다. 순위 숫자는 tabular-nums 로 자리를
 * 고정해 패널이 바뀔 때 숫자가 흔들리지 않게 한다.
 */
export function AttractScreen({
  mode,
  keypad,
  session = null,
  topToday,
  topAll,
  popularSongs,
  nickname,
  onNicknameChange,
  onEnter,
  onEnterWithoutMic,
  isEntering,
  enterNotice,
  queue = null,
}: AttractScreenProps) {
  const [panelIndex, setPanelIndex] = useState(0);
  /*
    QR 이 가리킬 주소.

    기본은 이 화면을 띄운 주소를 그대로 쓴다 — 전시장 주소가 바뀌어도 따라간다.
    다만 부스 PC에서 `localhost` 로 띄워 두면 그 QR 은 **그 PC에서만** 열린다.
    관람객 폰은 열 수 없으므로, 그럴 때는 `NEXT_PUBLIC_SITE_URL` 에 PC의
    IPv4 주소(예: http://192.168.0.25:3000)를 넣어 덮어쓴다.
  */
  const [tryUrl, setTryUrl] = useState("");
  const [localOnly, setLocalOnly] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => {
      const base =
        process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/+$/, "") ||
        window.location.origin;
      setTryUrl(`${base}/try`);
      setLocalOnly(/^https?:\/\/(localhost|127\.0\.0\.1)(:|$|\/)/i.test(base));
    }, 0);
    return () => clearTimeout(id);
  }, []);

  // 패널 자동 순환. 사용자가 점을 누르면 그 패널부터 다시 센다.
  useEffect(() => {
    const id = setInterval(() => {
      setPanelIndex((i) => (i + 1) % PANELS.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, [panelIndex]);

  const panel = PANELS[panelIndex];
  const rows: ScoreRecord[] = panel.key === "today" ? topToday : panel.key === "all" ? topAll : [];

  return (
    <section
      aria-label="노래방 부스 안내"
      className="rounded-2xl bg-surface border border-line overflow-hidden"
    >
      <div className="grid lg:grid-cols-5 lg:min-h-[68vh]">
        {/* ── 왼쪽: 무엇을 하면 되는가 ───────────────────────────── */}
        <div className="lg:col-span-3 p-7 sm:p-10 flex flex-col justify-center gap-6">
          {mode === "standby" ? (
            <>
              <div>
                <p className="text-xs font-semibold tracking-[0.2em] uppercase text-brass">
                  스마트 학교 노래방 부스
                </p>
                <h2 className="mt-2 text-4xl sm:text-5xl font-extrabold tracking-tight text-ink leading-[1.1]">
                  지금 비어 있습니다
                </h2>
                <p className="mt-4 text-base text-ink-2 leading-relaxed max-w-xl">
                  예약한 <strong className="text-ink">4자리 비밀번호</strong>를 키패드에 누르면
                  문이 열리고 노래방 전원이 켜집니다. 예약 시간 10분 전부터 들어갈 수 있습니다.
                </p>
              </div>

              <div className="flex flex-wrap items-start gap-5">
                {keypad}

                {/*
                  전시 체험 모드 — 관람객에게는 예약 PIN 이 없다. QR 을 찍어 그 자리에서
                  체험권을 받고 대기 번호를 받는다 (부록G §2-③).
                */}
                {queue?.enabled ? (
                  <div className="flex flex-col gap-3 p-4 rounded-2xl bg-raised border border-line w-fit max-w-xs">
                    {tryUrl && <QrCode value={tryUrl} size={132} />}
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-ink">
                        예약이 없으신가요? <span className="text-brass">QR을 찍으세요</span>
                      </p>
                      <p className="text-xs text-ink-2 mt-1 leading-relaxed">
                        폰으로 체험권을 받으면 대기 번호가 나오고, 차례가 되면 폰에 비밀번호가 뜹니다.
                      </p>
                      {/* 전시 당일에 가장 자주 나는 사고 — 띄운 사람에게만 보이게 적어 둔다 */}
                      {localOnly && (
                        <p className="text-[11px] text-live mt-1.5 leading-relaxed">
                          이 QR은 <strong>이 PC에서만</strong> 열립니다. 관람객 폰으로 찍게 하려면
                          <code className="mx-1">frontend/.env</code> 의
                          <code className="mx-1">NEXT_PUBLIC_SITE_URL</code> 에 이 PC의 IP 주소를
                          넣고 다시 띄우세요.
                        </p>
                      )}
                      {queue.paused_reason && (
                        <p className="text-[11px] text-brass mt-1.5 leading-relaxed">
                          {queue.paused_reason}
                        </p>
                      )}
                      <div className="flex items-start gap-4 mt-3">
                        <span>
                          <span className="block text-[11px] text-ink-3">지금 호출</span>
                          <span className="block font-mono tnum text-2xl font-extrabold text-brass leading-none">
                            {queue.now_serving ? `${queue.now_serving.ticket_no}번` : "—"}
                          </span>
                          {/* 멀리서도 자기가 불린 줄 알아야 한다 — /try 에서 "호출할 때 부릅니다"로
                              받아 둔 이름을 번호 아래에 같이 띄운다 */}
                          {queue.now_serving?.nickname && (
                            <span className="block text-[11px] text-ink-2 mt-0.5 max-w-[7rem] truncate">
                              {queue.now_serving.nickname}님
                            </span>
                          )}
                        </span>
                        <span className="w-px h-8 bg-line" aria-hidden />
                        <span>
                          <span className="block text-[11px] text-ink-3">대기</span>
                          <span className="block font-mono tnum text-2xl font-extrabold text-ink leading-none">
                            {queue.waiting_count}명
                          </span>
                        </span>
                        <span className="w-px h-8 bg-line" aria-hidden />
                        <span>
                          <span className="block text-[11px] text-ink-3">예상</span>
                          <span className="block font-mono tnum text-2xl font-extrabold text-ink leading-none">
                            {queue.estimated_wait_min}분
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-3 p-4 rounded-2xl bg-raised border border-line max-w-xs">
                    <CalendarCheck className="w-5 h-5 text-brass shrink-0 mt-0.5" aria-hidden />
                    <p className="text-sm text-ink-2 leading-relaxed">
                      예약은 폰으로 <strong className="text-ink">예약 화면</strong>에서 신청합니다.
                      당일 예약은 안 되니 하루 전까지 신청하세요.
                    </p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <div>
                <p className="text-xs font-semibold tracking-[0.2em] uppercase text-free">
                  인증 완료 · 문이 열렸습니다
                </p>
                <h2 className="mt-2 text-4xl sm:text-5xl font-extrabold tracking-tight text-ink leading-[1.1]">
                  {session?.user_name ? `${session.user_name}님, 환영합니다!` : "환영합니다!"}
                </h2>
                <p className="mt-4 text-base text-ink-2 leading-relaxed max-w-xl">
                  노래방 전원이 켜졌습니다. 아래 버튼을 누르면 마이크를 준비하고 노래방을 엽니다.
                </p>
                {endsAtLabel(session) && (
                  <p className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-raised border border-line text-sm text-ink-2">
                    <Clock className="w-4 h-4 text-ink-3" aria-hidden />
                    <strong className="text-ink">{endsAtLabel(session)}</strong>까지 · 남은 시간{" "}
                    <strong className="text-ink">
                      <RemainingClock session={session} />
                    </strong>
                  </p>
                )}
              </div>

              {/* 이름을 미리 받아 두면 채점할 때마다 묻지 않아도 순위에 올릴 수 있다 */}
              <div className="space-y-3 max-w-md">
                <label htmlFor="attract-nickname" className="block text-sm font-bold text-ink">
                  순위에 올릴 이름
                  <span className="ml-2 font-normal text-ink-3">(바꿔도 됩니다)</span>
                </label>
                <input
                  id="attract-nickname"
                  value={nickname}
                  onChange={(e) => onNicknameChange(e.target.value.slice(0, 10))}
                  placeholder="별명 (최대 10자)"
                  maxLength={10}
                  className="w-full px-4 py-3 rounded-xl bg-raised border border-line-strong text-ink placeholder-ink-3 outline-none"
                />

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <button
                    onClick={onEnter}
                    disabled={isEntering}
                    className="px-6 py-3.5 rounded-xl bg-brass hover:bg-brass/90 disabled:opacity-60 disabled:cursor-not-allowed text-on-accent font-extrabold text-base transition-colors cursor-pointer inline-flex items-center gap-2"
                  >
                    {isEntering ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" aria-hidden />
                        준비 중…
                      </>
                    ) : (
                      <>
                        <Mic2 className="w-5 h-5" aria-hidden />
                        노래방 시작하기
                      </>
                    )}
                  </button>
                  <button
                    onClick={onEnterWithoutMic}
                    disabled={isEntering}
                    className="text-sm text-ink-3 hover:text-ink underline underline-offset-4 cursor-pointer disabled:opacity-60"
                  >
                    마이크 없이 시작
                  </button>
                </div>

                {enterNotice && <p className="text-sm text-brass">{enterNotice}</p>}
              </div>
            </>
          )}
        </div>

        {/* ── 오른쪽: 순환 패널 ─────────────────────────────────── */}
        <div className="lg:col-span-2 bg-raised border-t lg:border-t-0 lg:border-l border-line p-6 sm:p-8 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <panel.icon className="w-5 h-5 text-brass shrink-0" aria-hidden />
            <h3 className="text-lg font-bold text-ink">{panel.label}</h3>
          </div>

          <div className="flex-1 min-h-[16rem]">
            {panel.key === "songs" ? (
              <ol className="space-y-2.5">
                {popularSongs.slice(0, 5).map((song, i) => (
                  <li key={song.id} className="flex items-center gap-3">
                    <span className="w-7 h-7 shrink-0 rounded-lg bg-surface border border-line flex items-center justify-center font-mono tnum text-sm font-bold text-ink-3">
                      {i + 1}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-base font-bold text-ink truncate">
                        {song.title}
                      </span>
                      <span className="block text-xs text-ink-3 truncate">{song.singer}</span>
                    </span>
                  </li>
                ))}
              </ol>
            ) : rows.length === 0 ? (
              <p className="text-sm text-ink-3 leading-relaxed pt-2">
                {panel.key === "today"
                  ? "오늘은 아직 기록이 없습니다. 첫 번째 주인공이 되어 보세요."
                  : "아직 등록된 기록이 없습니다."}
              </p>
            ) : (
              <ol className="space-y-2.5">
                {rows.map((row, i) => (
                  <li
                    key={row.id}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border ${
                      i === 0 ? "bg-brass-soft border-brass/35" : "bg-surface border-line"
                    }`}
                  >
                    <span
                      className={`w-7 h-7 shrink-0 rounded-lg flex items-center justify-center font-mono tnum text-sm font-bold ${
                        i === 0 ? "bg-brass text-on-accent" : "bg-raised text-ink-3"
                      }`}
                    >
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-base font-bold text-ink truncate">
                        {row.nickname}
                      </span>
                      <span className="block text-xs text-ink-3 truncate">{row.title}</span>
                    </span>
                    <span className="font-mono tnum text-2xl font-extrabold text-ink shrink-0">
                      {row.score}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          {/* 지금 몇 번째 패널인지 — 누르면 그 패널로 바로 간다 */}
          <div className="flex items-center justify-center gap-2 pt-5">
            {PANELS.map((p, i) => (
              <button
                key={p.key}
                onClick={() => setPanelIndex(i)}
                aria-label={`${p.label} 보기`}
                aria-current={i === panelIndex}
                className={`h-2 rounded-full transition-all cursor-pointer ${
                  i === panelIndex ? "w-7 bg-brass" : "w-2 bg-line-strong hover:bg-ink-3"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
