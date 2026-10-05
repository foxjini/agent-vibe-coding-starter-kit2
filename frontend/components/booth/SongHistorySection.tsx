"use client";

import React from "react";
import { Music, Award, Sparkles } from "lucide-react";

import { Song } from "@/types";

interface SongHistorySectionProps {
  allSongs: Song[];
  favoriteSongs: Song[];
}

/**
 * 애창곡 기록 (보기 전용) — `/` 와 `/admin`
 *
 * 기록은 부스에서 노래를 부르고 채점하면 저절로 쌓인다 (부스 전원이 켜져 있을 때만).
 * 예전에는 이 화면에 [노래 부르기 기록] 폼과 [+1회] 버튼이 있어서, 부르지 않은
 * 곡도 아무 폰에서나 횟수를 올릴 수 있었다. 그러면 "3회 이상 불린 18번"이라는
 * 기준이 의미가 없어진다.
 */
export function SongHistorySection({ allSongs, favoriteSongs }: SongHistorySectionProps) {
  return (
    <div className="space-y-8">
      {/* Top Banner: 나의 18번 (3회 이상 곡) */}
      <div className="bg-surface border border-brass/40 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
          <div className="flex items-start gap-2.5 min-w-0">
            <Award className="w-5 h-5 text-brass shrink-0 mt-0.5" />
            <div className="min-w-0">
              <h3 className="text-base font-bold text-ink">
                나의 18번 애창곡
                <span className="ml-2 align-middle text-[11px] font-semibold px-2 py-0.5 rounded-full bg-brass-soft text-brass border border-brass/25 whitespace-nowrap">
                  3회 이상 가창
                </span>
              </h3>
              <p className="text-xs text-ink-3">우리 학교 노래방에서 3회 이상 불린 인기 애창곡입니다.</p>
            </div>
          </div>
          <span className="whitespace-nowrap text-xs font-semibold px-2.5 py-1 rounded bg-raised text-brass">
            총 {favoriteSongs.length}곡
          </span>
        </div>

        {favoriteSongs.length === 0 ? (
          <div className="text-center py-6 text-ink-3 text-xs">
            아직 3회 이상 불린 곡이 없습니다. 부스에서 노래를 부르고 채점하면 기록됩니다!
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {favoriteSongs.map((song, idx) => (
              <div
                key={song.id}
                className="p-3.5 rounded-xl bg-surface/80 border border-brass/30 flex items-center justify-between hover:border-brass/60 transition-all shadow-md group"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-brass/20 text-brass flex items-center justify-center text-xs font-bold font-mono">
                    {idx + 1}
                  </span>
                  <div>
                    <h4 className="text-xs font-bold text-ink group-hover:text-ink transition-colors">
                      {song.title}
                    </h4>
                    <span className="text-[10px] text-ink-3">{song.singer}</span>
                  </div>
                </div>
                <span className="text-xs font-bold font-mono text-brass bg-brass-soft/60 px-2 py-1 rounded border border-brass/30">
                  {song.sing_count}회
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 전체 가창 기록 */}
      <div className="bg-surface/90 border border-line rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <h3 className="text-base font-bold text-ink flex items-center gap-2">
            <Music className="w-4 h-4 text-free" />
            전체 노래 가창 기록 목록
          </h3>
          <span className="text-xs text-ink-3">총 {allSongs.length}곡 등록됨</span>
        </div>

        <div className="overflow-x-auto">
          {allSongs.length === 0 ? (
            <div className="py-8 text-center text-ink-3 text-xs">등록된 노래 기록이 없습니다.</div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-line text-ink-3 text-[11px]">
                  <th className="pb-2 font-medium">곡 제목</th>
                  <th className="pb-2 font-medium">가수</th>
                  <th className="pb-2 font-medium">가창 횟수</th>
                  <th className="pb-2 font-medium">최근 부른 시간</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {allSongs.map((song) => (
                  <tr key={song.id} className="hover:bg-raised/30 transition-colors">
                    <td className="py-2.5 font-semibold text-ink flex items-center gap-2">
                      {song.sing_count >= 3 && <Sparkles className="w-3 h-3 text-brass" />}
                      {song.title}
                    </td>
                    <td className="py-2.5 text-ink-2">{song.singer}</td>
                    <td className="py-2.5">
                      <span
                        className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] ${
                          song.sing_count >= 3
                            ? "bg-brass-soft text-brass border border-brass/40"
                            : "bg-raised text-ink-2"
                        }`}
                      >
                        {song.sing_count}회
                      </span>
                    </td>
                    <td className="py-2.5 text-ink-3 text-[11px] font-mono">
                      {song.last_sung_at ? song.last_sung_at.replace("T", " ").slice(0, 16) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
