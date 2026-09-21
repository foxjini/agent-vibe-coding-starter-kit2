"use client";

import React, { useCallback, useMemo, useState } from "react";
import { CheckCircle2, Loader2, ScanSearch, XCircle, ExternalLink, AlertTriangle } from "lucide-react";
import { KARAOKE_SONGS, KaraokeSong } from "@/data/karaokeSongs";
import { videoAttempts, registerVideoId } from "@/utils/karaokeMedia";
import {
  probeVideoIds,
  parseYouTubeId,
  youtubeWatchUrl,
  ProbeResult,
  ProbeStatus,
} from "@/utils/youtubePlayer";

/**
 * 노래방 영상 점검 패널
 *
 * 유튜브 영상이 "우리 화면에서 재생되는가"는 영상을 열어 봐서는 알 수 없다.
 * 영상 주인이 [다른 사이트에서 재생 금지]를 걸어 두면 유튜브에서는 잘 보이는데
 * 우리 화면에서만 코드 150으로 막힌다. 후보를 하나씩 손으로 확인하려면
 * 10곡 × 후보 3개 = 서른 번 가까이 눌러 봐야 한다.
 *
 * 이 패널은 화면 밖에 작은 플레이어를 잠깐씩 띄워 보는 방식으로 그 일을 대신한다.
 * 소리는 나지 않으며, 되는 영상은 그 자리에서 바로 등록할 수 있다.
 */

const STATUS_STYLE: Record<ProbeStatus, { label: string; cls: string }> = {
  ok: { label: "재생 가능", cls: "text-free bg-free/15 border-free/40" },
  blocked: { label: "퍼가기 금지", cls: "text-live bg-live/15 border-live/40" },
  missing: { label: "삭제·비공개", cls: "text-live bg-live/15 border-live/40" },
  invalid: { label: "잘못된 ID", cls: "text-brass bg-brass/15 border-brass/40" },
  unplayable: { label: "재생 불가", cls: "text-brass bg-brass/15 border-brass/40" },
  timeout: { label: "응답 없음", cls: "text-ink-3 bg-raised border-line-strong" },
  error: { label: "실패", cls: "text-ink-3 bg-raised border-line-strong" },
};

interface VideoCheckPanelProps {
  /** 등록이 성공했을 때 부모(노래방 화면)가 재생 소스를 다시 잡도록 알려 준다 */
  onRegistered?: (songId: string, videoId: string) => void;
}

export function VideoCheckPanel({ onRegistered }: VideoCheckPanelProps) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<Record<string, ProbeResult>>({});
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [notice, setNotice] = useState<string | null>(null);

  const [pasteText, setPasteText] = useState("");
  const [pasteTarget, setPasteTarget] = useState(KARAOKE_SONGS[0].id);

  /** 곡별 후보 목록 (관리자 등록본이 있으면 맨 앞에 온다) */
  const plan = useMemo(
    () => KARAOKE_SONGS.map((song) => ({ song, ids: videoAttempts(song) })),
    []
  );

  const runProbe = useCallback(async (ids: string[]) => {
    const unique = ids.filter((id, i) => ids.indexOf(id) === i);
    if (unique.length === 0) return;

    setRunning(true);
    setNotice(null);
    setProgress({ done: 0, total: unique.length });

    await probeVideoIds(unique, (result) => {
      setResults((prev) => ({ ...prev, [result.videoId]: result }));
      setProgress((prev) => ({ ...prev, done: prev.done + 1 }));
    });

    setRunning(false);
  }, []);

  const checkAll = useCallback(() => {
    void runProbe(plan.flatMap((p) => p.ids));
  }, [plan, runProbe]);

  const checkPasted = useCallback(() => {
    const ids = pasteText
      .split(/[\s,]+/)
      .map((line) => parseYouTubeId(line))
      .filter((id): id is string => Boolean(id));

    if (ids.length === 0) {
      setNotice("유튜브 링크를 한 줄에 하나씩 붙여넣어 주세요.");
      return;
    }
    void runProbe(ids);
  }, [pasteText, runProbe]);

  const register = useCallback(
    async (songId: string, videoId: string) => {
      const res = await registerVideoId(songId, videoId);
      if (res.ok) {
        setNotice(`${videoId} 등록 완료 — 모든 기기에 적용됩니다.`);
        onRegistered?.(songId, videoId);
      } else {
        setNotice(res.message);
      }
    },
    [onRegistered]
  );

  /** 이 곡에서 확인이 끝난 후보 중 재생 가능한 첫 번째 */
  const firstOk = (ids: string[]) => ids.find((id) => results[id]?.status === "ok");

  const okCount = Object.values(results).filter((r) => r.status === "ok").length;
  const checkedCount = Object.keys(results).length;

  return (
    <div className="bg-surface/90 border border-line rounded-2xl shadow-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-raised/40 transition-colors cursor-pointer text-left"
      >
        <span className="flex items-center gap-2.5">
          <ScanSearch className="w-5 h-5 text-brass" />
          <span>
            <span className="block text-sm font-black text-ink">노래방 영상 점검</span>
            <span className="block text-[11px] text-ink-3">
              후보 영상이 우리 화면에서 재생되는지 실제로 확인하고, 되는 영상을 바로 등록합니다
            </span>
          </span>
        </span>
        <span className="text-xs text-ink-3 shrink-0">
          {checkedCount > 0 && `확인 ${checkedCount}개 · 가능 ${okCount}개 · `}
          {open ? "접기" : "펼치기"}
        </span>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-line">
          <div className="flex flex-wrap items-center gap-2 pt-4">
            <button
              onClick={checkAll}
              disabled={running}
              className="px-4 py-2 rounded-xl bg-brass hover:bg-brass/90 disabled:bg-line-strong disabled:cursor-not-allowed text-on-accent font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {running ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <ScanSearch className="w-3.5 h-3.5" />
              )}
              {running
                ? `점검 중 ${progress.done}/${progress.total}`
                : `${KARAOKE_SONGS.length}곡 후보 전체 점검`}
            </button>
            <span className="text-[11px] text-ink-3">
              화면 밖에서 조용히 확인하므로 소리는 나지 않습니다. 30초쯤 걸립니다.
            </span>
          </div>

          {notice && (
            <p className="text-[11px] text-brass flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {notice}
            </p>
          )}

          {/* ── 곡별 결과 ─────────────────────────────────── */}
          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {plan.map(({ song, ids }) => {
              const best = firstOk(ids);
              return (
                <div
                  key={song.id}
                  className="p-3 rounded-xl bg-canvas/60 border border-line space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-ink truncate">
                      {song.title}
                      <span className="text-ink-3 font-normal"> · {song.singer}</span>
                    </span>
                    {best && (
                      <button
                        onClick={() => register(song.id, best)}
                        className="px-2.5 py-1 rounded-lg bg-free hover:bg-free/90 text-on-accent font-bold text-[11px] shrink-0 transition-colors cursor-pointer"
                      >
                        이 영상 등록
                      </button>
                    )}
                  </div>

                  <ul className="space-y-1">
                    {ids.map((id) => {
                      const r = results[id];
                      const style = r ? STATUS_STYLE[r.status] : null;
                      return (
                        <li key={id} className="flex items-center gap-2 text-[11px]">
                          {r?.status === "ok" ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-free shrink-0" />
                          ) : r ? (
                            <XCircle className="w-3.5 h-3.5 text-live/70 shrink-0" />
                          ) : (
                            <span className="w-3.5 h-3.5 rounded-full border border-line-strong shrink-0" />
                          )}
                          <a
                            href={youtubeWatchUrl(id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono text-ink-3 hover:text-ink underline underline-offset-2"
                          >
                            {id}
                          </a>
                          {style && (
                            <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${style.cls}`}>
                              {style.label}
                              {r?.code ? ` (${r.code})` : ""}
                            </span>
                          )}
                        </li>
                      );
                    })}
                    {ids.length === 0 && (
                      <li className="text-[11px] text-ink-3">후보 영상이 없습니다</li>
                    )}
                  </ul>
                </div>
              );
            })}
          </div>

          {/* ── 직접 찾은 영상 점검 ───────────────────────── */}
          <div className="pt-3 border-t border-line space-y-2">
            <p className="text-[11px] text-ink-3 leading-relaxed">
              직접 찾은 노래방 영상이 있으면 링크를 한 줄에 하나씩 붙여넣고 점검해 보세요.
              <span className="text-free"> 재생 가능</span>으로 나온 영상만 등록하면 됩니다.
            </p>
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              rows={3}
              placeholder={"https://www.youtube.com/watch?v=...\nhttps://youtu.be/..."}
              className="w-full px-3 py-2 rounded-xl bg-canvas border border-line-strong text-[11px] font-mono text-ink placeholder-ink-3 focus:outline-none focus:border-brass"
            />
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={checkPasted}
                disabled={running}
                className="px-3 py-1.5 rounded-lg bg-line-strong hover:bg-line-strong/90 disabled:opacity-50 disabled:cursor-not-allowed text-ink font-bold text-xs transition-colors cursor-pointer"
              >
                붙여넣은 링크 점검
              </button>
              <select
                value={pasteTarget}
                onChange={(e) => setPasteTarget(e.target.value)}
                className="px-2 py-1.5 rounded-lg bg-canvas border border-line-strong text-xs text-ink focus:outline-none focus:border-brass"
              >
                {KARAOKE_SONGS.map((s: KaraokeSong) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-ink-3">곡에 등록</span>
            </div>

            <ul className="space-y-1">
              {Object.values(results)
                .filter((r) => !plan.some((p) => p.ids.includes(r.videoId)))
                .map((r) => {
                  const style = STATUS_STYLE[r.status];
                  return (
                    <li key={r.videoId} className="flex items-center gap-2 text-[11px]">
                      <a
                        href={youtubeWatchUrl(r.videoId)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-ink-3 hover:text-ink underline underline-offset-2 flex items-center gap-1"
                      >
                        {r.videoId}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                      <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${style.cls}`}>
                        {style.label}
                        {r.code ? ` (${r.code})` : ""}
                      </span>
                      {r.status === "ok" && (
                        <button
                          onClick={() => register(pasteTarget, r.videoId)}
                          className="px-2 py-0.5 rounded bg-free hover:bg-free/90 text-on-accent font-bold text-[10px] transition-colors cursor-pointer"
                        >
                          등록
                        </button>
                      )}
                    </li>
                  );
                })}
            </ul>
          </div>

          <p className="text-[10px] text-ink-3 leading-relaxed">
            퍼가기 금지(코드 101·150)는 영상 주인이 외부 사이트 재생을 막아 둔 것으로, 우리 코드로는
            풀 수 없습니다. 공식 노래방 채널과 대형 기획사 뮤직비디오에 많습니다. 전시회처럼 확실해야
            하는 자리에서는 <code className="text-brass">public/media/karaoke/</code>에 정식
            확보한 반주 파일을 넣어 두는 편이 안전합니다 (자세한 내용은 부록F).
          </p>
        </div>
      )}
    </div>
  );
}
