"use client";

import React, { useState } from "react";
import { Music, Award, Plus, Mic, Sparkles, Check } from "lucide-react";

import { Song } from "@/types";
import { apiUrl } from "@/utils/apiConfig";

interface SongHistorySectionProps {
  allSongs: Song[];
  favoriteSongs: Song[];
  onSongRecorded: () => void;
  onOpenKaraoke?: () => void;
}

export function SongHistorySection({
  allSongs,
  favoriteSongs,
  onSongRecorded,
  onOpenKaraoke,
}: SongHistorySectionProps) {
  const [title, setTitle] = useState<string>("");
  const [singer, setSinger] = useState<string>("");
  const [isAdding, setIsAdding] = useState<boolean>(false);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  const handleAddSong = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !singer.trim()) return;

    setIsAdding(true);
    try {
      const res = await fetch(apiUrl("/api/songs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          singer: singer.trim(),
        }),
      });

      if (res.ok) {
        setSuccessNotice(`'${title}' 곡이 기록되었습니다!`);
        setTitle("");
        setSinger("");
        onSongRecorded();
        setTimeout(() => setSuccessNotice(null), 3000);
      }
    } catch {
      // ignore
    } finally {
      setIsAdding(false);
    }
  };

  const handleQuickSing = async (song: Song) => {
    try {
      const res = await fetch(apiUrl("/api/songs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: song.title,
          singer: song.singer,
        }),
      });
      if (res.ok) {
        setSuccessNotice(`'${song.title}' 1회 추가 완료!`);
        onSongRecorded();
        setTimeout(() => setSuccessNotice(null), 2500);
      }
    } catch {
      // ignore
    }
  };

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
          <div className="flex items-center gap-2">
            {onOpenKaraoke && (
              <button
                onClick={onOpenKaraoke}
                className="px-3 py-1 rounded-lg bg-brass text-on-accent text-xs font-bold shadow-md transition-all cursor-pointer flex items-center gap-1.5"
              >
                <Mic className="w-3.5 h-3.5" />
                노래방에서 반주로 부르기 🎤
              </button>
            )}
            <span className="whitespace-nowrap text-xs font-semibold px-2.5 py-1 rounded bg-raised text-brass">
              총 {favoriteSongs.length}곡
            </span>
          </div>
        </div>

        {favoriteSongs.length === 0 ? (
          <div className="text-center py-6 text-ink-3 text-xs">
            아직 3회 이상 불린 나의 18번 곡이 없습니다. 노래를 부르고 기록해 보세요!
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
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono text-brass bg-brass-soft/60 px-2 py-1 rounded border border-brass/30">
                    {song.sing_count}회
                  </span>
                  <button
                    onClick={() => {
                      if (onOpenKaraoke) {
                        onOpenKaraoke();
                      } else {
                        handleQuickSing(song);
                      }
                    }}
                    className="p-1.5 rounded bg-raised hover:bg-brass hover:text-on-accent text-ink-3 transition-colors cursor-pointer"
                    title="노래방 반주로 부르기"
                  >
                    <Mic className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main Grid: Left Add Song Form, Right All Songs List */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Add Song Form (4 Cols) */}
        <div className="lg:col-span-4 bg-surface/90 border border-line rounded-2xl p-6 shadow-xl space-y-4">
          <div className="border-b border-line pb-3">
            <h3 className="text-base font-bold text-ink flex items-center gap-2">
              <Plus className="w-4 h-4 text-brass" />
              부른 노래 기록 추가
            </h3>
            <p className="text-xs text-ink-3 mt-0.5">부른 곡을 등록하면 나의 18번으로 누적 카운트됩니다.</p>
          </div>

          {successNotice && (
            <div className="p-3 rounded-lg bg-free-soft/50 border border-free/50 text-free text-xs flex items-center gap-2">
              <Check className="w-4 h-4 text-free shrink-0" />
              <span>{successNotice}</span>
            </div>
          )}

          <form onSubmit={handleAddSong} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-ink-2 mb-1">곡 제목</label>
              <input
                type="text"
                placeholder="예: 다시 만나"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink-2 mb-1">가수 이름</label>
              <input
                type="text"
                placeholder="예: 더윈드"
                value={singer}
                onChange={(e) => setSinger(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isAdding}
              className="w-full py-2.5 rounded-lg bg-brass hover:bg-brass/90 active:bg-brass/80 text-on-accent text-xs font-bold transition-all shadow-md cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50 mt-2"
            >
              <Mic className="w-3.5 h-3.5" />
              {isAdding ? "등록 중..." : "노래 부르기 기록"}
            </button>
          </form>
        </div>

        {/* All Songs History (8 Cols) */}
        <div className="lg:col-span-8 bg-surface/90 border border-line rounded-2xl p-6 shadow-xl space-y-4">
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
                    <th className="pb-2 font-medium text-right">가창 추가</th>
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
                      <td className="py-2.5 text-right">
                        <button
                          onClick={() => handleQuickSing(song)}
                          className="px-2 py-1 rounded bg-raised hover:bg-brass hover:text-on-accent text-ink-2 text-[11px] border border-line-strong transition-colors cursor-pointer"
                        >
                          +1회
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
