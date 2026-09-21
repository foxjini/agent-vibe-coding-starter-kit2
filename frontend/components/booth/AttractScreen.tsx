"use client";

import React, { useEffect, useState } from "react";
import { Mic2, Loader2, KeyRound, Trophy, Crown, Flame } from "lucide-react";
import { ScoreRecord } from "@/types";

interface PopularSong {
  id: string;
  title: string;
  singer: string;
}

interface AttractScreenProps {
  isPowerOn: boolean;
  topToday: ScoreRecord[];
  topAll: ScoreRecord[];
  popularSongs: PopularSong[];
  nickname: string;
  onNicknameChange: (value: string) => void;
  onEnter: () => void;
  onBrowse: () => void;
  isEntering: boolean;
  enterNotice: string | null;
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
 * 전시장에서 부스를 쓰는 사람이 없을 때 부스 대형 화면에 떠 있는 화면이다.
 * 목적은 둘이다.
 *   1. 처음 온 관람객에게 "여기서 뭘 하면 되는지" 한 문장으로 알려 준다
 *   2. 순위를 돌려 보여 줘서 "나도 해 볼까" 하게 만든다 — 학생들이 종일
 *      같은 설명을 입으로 반복하지 않아도 된다
 *
 * 2~3m 떨어져서 보므로 글자를 크게 쓴다. 순위 숫자는 tabular-nums 로 자리를
 * 고정해 패널이 바뀔 때 숫자가 흔들리지 않게 한다.
 */
export function AttractScreen({
  isPowerOn,
  topToday,
  topAll,
  popularSongs,
  nickname,
  onNicknameChange,
  onEnter,
  onBrowse,
  isEntering,
  enterNotice,
}: AttractScreenProps) {
  const [panelIndex, setPanelIndex] = useState(0);

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
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] uppercase text-brass">
              스마트 학교 노래방 부스
            </p>
            <h2 className="mt-2 text-4xl sm:text-5xl font-extrabold tracking-tight text-ink leading-[1.1]">
              {isPowerOn ? "지금 이용 중입니다" : "지금 비어 있습니다"}
            </h2>
            <p className="mt-4 text-base text-ink-2 leading-relaxed max-w-xl">
              예약한 <strong className="text-ink">4자리 비밀번호</strong>를 부스 앞 키패드에
              입력하면 문이 열리고 전원이 켜집니다.
            </p>
          </div>

          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-raised border border-line w-fit">
            <KeyRound className="w-5 h-5 text-brass shrink-0" aria-hidden />
            <span className="font-mono tnum text-2xl tracking-[0.35em] text-ink-3">● ● ● ●</span>
          </div>

          {/* 이름을 미리 받아 두면 채점할 때마다 묻지 않아도 순위에 올릴 수 있다 */}
          <div className="space-y-3 max-w-md">
            <label htmlFor="attract-nickname" className="block text-sm font-bold text-ink">
              이름을 남기면 순위에 오릅니다
              <span className="ml-2 font-normal text-ink-3">(선택)</span>
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
                onClick={onBrowse}
                className="text-sm text-ink-3 hover:text-ink underline underline-offset-4 cursor-pointer"
              >
                마이크 없이 둘러보기
              </button>
            </div>

            {enterNotice && <p className="text-sm text-brass">{enterNotice}</p>}
          </div>
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
