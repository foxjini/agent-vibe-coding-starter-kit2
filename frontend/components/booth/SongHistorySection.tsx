"use client";

import React, { useState } from "react";
import { Music, Award, Plus, Mic, Sparkles, Check } from "lucide-react";

import { Song } from "@/types";

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
      const res = await fetch("http://localhost:8000/api/songs", {
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
      const res = await fetch("http://localhost:8000/api/songs", {
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
      <div className="bg-gradient-to-r from-amber-950/40 via-slate-900 to-indigo-950/40 border border-amber-500/40 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-amber-500/20 pb-3">
          <div className="flex items-center gap-2">
            <Award className="w-6 h-6 text-amber-400" />
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                나의 18번 애창곡 리스트
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  3회 이상 가창
                </span>
              </h3>
              <p className="text-xs text-slate-400">우리 학교 노래방에서 3회 이상 불린 인기 애창곡입니다.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onOpenKaraoke && (
              <button
                onClick={onOpenKaraoke}
                className="px-3 py-1 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 text-xs font-bold shadow-md shadow-amber-500/20 transition-all cursor-pointer flex items-center gap-1.5"
              >
                <Mic className="w-3.5 h-3.5" />
                노래방에서 반주로 부르기 🎤
              </button>
            )}
            <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-800 text-amber-300">
              총 {favoriteSongs.length}곡
            </span>
          </div>
        </div>

        {favoriteSongs.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs">
            아직 3회 이상 불린 나의 18번 곡이 없습니다. 노래를 부르고 기록해 보세요!
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {favoriteSongs.map((song, idx) => (
              <div
                key={song.id}
                className="p-3.5 rounded-xl bg-slate-900/80 border border-amber-500/30 flex items-center justify-between hover:border-amber-400/60 transition-all shadow-md group"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-xs font-bold font-mono">
                    {idx + 1}
                  </span>
                  <div>
                    <h4 className="text-xs font-bold text-white group-hover:text-amber-300 transition-colors">
                      {song.title}
                    </h4>
                    <span className="text-[10px] text-slate-400">{song.singer}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono text-amber-400 bg-amber-950/60 px-2 py-1 rounded border border-amber-500/30">
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
                    className="p-1.5 rounded bg-slate-800 hover:bg-amber-600 hover:text-white text-slate-400 transition-colors cursor-pointer"
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
        <div className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Plus className="w-4 h-4 text-indigo-400" />
              부른 노래 기록 추가
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">부른 곡을 등록하면 나의 18번으로 누적 카운트됩니다.</p>
          </div>

          {successNotice && (
            <div className="p-3 rounded-lg bg-emerald-950/50 border border-emerald-500/50 text-emerald-300 text-xs flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successNotice}</span>
            </div>
          )}

          <form onSubmit={handleAddSong} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">곡 제목</label>
              <input
                type="text"
                placeholder="예: 다시 만나"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">가수 이름</label>
              <input
                type="text"
                placeholder="예: 더윈드"
                value={singer}
                onChange={(e) => setSinger(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isAdding}
              className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50 mt-2"
            >
              <Mic className="w-3.5 h-3.5" />
              {isAdding ? "등록 중..." : "노래 부르기 기록"}
            </button>
          </form>
        </div>

        {/* All Songs History (8 Cols) */}
        <div className="lg:col-span-8 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Music className="w-4 h-4 text-cyan-400" />
              전체 노래 가창 기록 목록
            </h3>
            <span className="text-xs text-slate-400">총 {allSongs.length}곡 등록됨</span>
          </div>

          <div className="overflow-x-auto">
            {allSongs.length === 0 ? (
              <div className="py-8 text-center text-slate-500 text-xs">등록된 노래 기록이 없습니다.</div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                    <th className="pb-2 font-medium">곡 제목</th>
                    <th className="pb-2 font-medium">가수</th>
                    <th className="pb-2 font-medium">가창 횟수</th>
                    <th className="pb-2 font-medium">최근 부른 시간</th>
                    <th className="pb-2 font-medium text-right">가창 추가</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {allSongs.map((song) => (
                    <tr key={song.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-2.5 font-semibold text-white flex items-center gap-2">
                        {song.sing_count >= 3 && <Sparkles className="w-3 h-3 text-amber-400" />}
                        {song.title}
                      </td>
                      <td className="py-2.5 text-slate-300">{song.singer}</td>
                      <td className="py-2.5">
                        <span
                          className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] ${
                            song.sing_count >= 3
                              ? "bg-amber-950 text-amber-300 border border-amber-500/40"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {song.sing_count}회
                        </span>
                      </td>
                      <td className="py-2.5 text-slate-400 text-[11px] font-mono">
                        {song.last_sung_at ? song.last_sung_at.replace("T", " ").slice(0, 16) : "-"}
                      </td>
                      <td className="py-2.5 text-right">
                        <button
                          onClick={() => handleQuickSing(song)}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-indigo-600 hover:text-white text-slate-300 text-[11px] border border-slate-700 transition-colors cursor-pointer"
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
