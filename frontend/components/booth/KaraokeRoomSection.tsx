"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Music,
  Mic,
  MicOff,
  Play,
  Pause,
  Award,
  Sparkles,
  Trophy,
  RotateCcw,
  Search,
  Tv,
  PowerOff,
  Volume2,
  ExternalLink,
  SlidersHorizontal,
  AlertTriangle,
  Link2,
  CheckCircle2,
  HardDrive,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { KaraokeAudioScorer, AudioAnalysisResult, FinalScore } from "@/utils/audioScorer";
import { KaraokeAccompanimentEngine } from "@/utils/karaokeAccompaniment";
import {
  createYouTubePlayer,
  parseYouTubeId,
  youtubeWatchUrl,
  YouTubePlayerHandle,
  YT_STATE,
} from "@/utils/youtubePlayer";
import {
  resolveMedia,
  saveVideoId,
  clearVideoId,
  getVideoId,
  ResolvedMedia,
} from "@/utils/karaokeMedia";
import { KARAOKE_SONGS, KaraokeSong, youtubeSearchUrl } from "@/data/karaokeSongs";
import { Device } from "@/types";
import { apiUrl } from "@/utils/apiConfig";

interface KaraokeRoomSectionProps {
  devices: Device[];
  onSongCompleted?: () => void;
}

export function KaraokeRoomSection({ devices, onSongCompleted }: KaraokeRoomSectionProps) {
  // 부스 반주기 전원(relay_1) 확인
  const relayDevice = devices.find((d) => d.id === "relay_1");
  const isPowerOn = relayDevice?.current_state === "on";

  // ── 선곡 & 재생 ──────────────────────────────────────────
  const [selectedSong, setSelectedSong] = useState<KaraokeSong>(KARAOKE_SONGS[0]);
  // 재생 소스는 "어느 곡의 결과인지"와 함께 보관한다.
  // 곡을 바꿀 때 effect 안에서 null로 되돌릴 필요가 없어(= 동기 setState 없이)
  // 이전 곡의 소스가 잠깐 보이는 문제도 생기지 않는다.
  const [resolved, setResolved] = useState<{ songId: string; media: ResolvedMedia } | null>(null);
  const media = resolved?.songId === selectedSong.id ? resolved.media : null;
  const [isPlaying, setIsPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playerError, setPlayerError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // ── 영상 등록 ────────────────────────────────────────────
  const [registerInput, setRegisterInput] = useState("");
  const [registerNotice, setRegisterNotice] = useState<string | null>(null);

  // ── 마이크 & 채점 ────────────────────────────────────────
  const [isMicActive, setIsMicActive] = useState(false);
  const [isVirtualMic, setIsVirtualMic] = useState(false);
  const [audioData, setAudioData] = useState<AudioAnalysisResult>({
    volume: 0,
    pitch: 0,
    note: "-",
    cents: 0,
  });
  const [mrVolume, setMrVolume] = useState(0.7);
  const [showScoreModal, setShowScoreModal] = useState(false);
  const [isCalculatingScore, setIsCalculatingScore] = useState(false);
  const [finalScore, setFinalScore] = useState<FinalScore | null>(null);
  const [animatedScore, setAnimatedScore] = useState(0);

  // ── refs ─────────────────────────────────────────────────
  const scorerRef = useRef<KaraokeAudioScorer | null>(null);
  const accompanimentRef = useRef<KaraokeAccompanimentEngine | null>(null);
  const ytHostRef = useRef<HTMLDivElement | null>(null);
  const ytHandleRef = useRef<YouTubePlayerHandle | null>(null);
  const localAudioRef = useRef<HTMLAudioElement | null>(null);
  const virtualTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** 곡이 끝났을 때 채점을 한 번만 실행하기 위한 플래그 */
  const scoredRef = useRef(false);

  /* ─────────────────────────────────────────────────────────
   * 엔진 초기화 / 정리
   * ──────────────────────────────────────────────────────── */
  useEffect(() => {
    scorerRef.current = new KaraokeAudioScorer();
    accompanimentRef.current = new KaraokeAccompanimentEngine();
    return () => {
      scorerRef.current?.stopMicrophone();
      accompanimentRef.current?.dispose();
      ytHandleRef.current?.destroy();
      localAudioRef.current?.pause();
      if (virtualTimerRef.current) clearInterval(virtualTimerRef.current);
      if (tickTimerRef.current) clearInterval(tickTimerRef.current);
    };
  }, []);

  /* ─────────────────────────────────────────────────────────
   * 재생 소스 결정 — 곡이 바뀔 때마다
   * 로컬 파일 → 유튜브 임베드 → 내장 반주 순으로 확인한다
   * ──────────────────────────────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    void resolveMedia(selectedSong).then((m) => {
      if (!cancelled) setResolved({ songId: selectedSong.id, media: m });
    });
    return () => {
      cancelled = true;
    };
  }, [selectedSong]);

  /* ─────────────────────────────────────────────────────────
   * 모든 재생 중지 (곡 전환·정지·언마운트 공통)
   * ──────────────────────────────────────────────────────── */
  const stopAllPlayback = useCallback(() => {
    accompanimentRef.current?.stop();
    if (localAudioRef.current) {
      localAudioRef.current.pause();
      localAudioRef.current.currentTime = 0;
    }
    ytHandleRef.current?.pause();
    if (tickTimerRef.current) {
      clearInterval(tickTimerRef.current);
      tickTimerRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  /* ─────────────────────────────────────────────────────────
   * 채점 실행 (곡 종료 자동 호출 + 버튼 수동 호출 공용)
   * ──────────────────────────────────────────────────────── */
  const recordSongToDB = useCallback(
    async (song: KaraokeSong) => {
      try {
        await fetch(apiUrl("/api/songs"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: song.title, singer: song.singer }),
        });
        onSongCompleted?.();
      } catch {
        /* 백엔드가 꺼져 있어도 노래방 기능 자체는 계속 동작해야 한다 */
      }
    },
    [onSongCompleted]
  );

  const finishAndScore = useCallback(() => {
    if (scoredRef.current) return; // 중복 채점 방지
    scoredRef.current = true;

    stopAllPlayback();
    setIsCalculatingScore(true);
    setShowScoreModal(true);
    setAnimatedScore(0);
    KaraokeAudioScorer.playDrumrollSound();

    const result =
      scorerRef.current?.calculateFinalScore() ?? {
        score: 0,
        comment: "채점 모듈을 초기화하지 못했습니다.",
        rank: "-",
        breakdown: { pitch: 0, timing: 0, volume: 0, expression: 0 },
        sangSomething: false,
      };
    setFinalScore(result);

    // 점수 카운트업 연출
    let current = 0;
    const step = Math.max(1, Math.ceil(result.score / 25));
    const counter = setInterval(() => {
      current = Math.min(result.score, current + step);
      setAnimatedScore(current);

      if (current >= result.score) {
        clearInterval(counter);
        setIsCalculatingScore(false);

        if (result.sangSomething) {
          KaraokeAudioScorer.playFanfareSound();
          if (typeof window !== "undefined" && "speechSynthesis" in window) {
            try {
              window.speechSynthesis.cancel();
              const utt = new SpeechSynthesisUtterance(`${result.score}점입니다! ${result.comment}`);
              utt.lang = "ko-KR";
              utt.rate = 1.05;
              window.speechSynthesis.speak(utt);
            } catch {
              /* TTS 미지원 브라우저는 건너뛴다 */
            }
          }
          void recordSongToDB(selectedSong);
        }
      }
    }, 40);
  }, [recordSongToDB, selectedSong, stopAllPlayback]);

  /* ─────────────────────────────────────────────────────────
   * 유튜브 플레이어 생성 — media가 youtube로 정해졌을 때만
   * ──────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!media || media.source !== "youtube" || !media.youtubeId || !ytHostRef.current) return;

    let disposed = false;
    const host = ytHostRef.current;

    // YT.Player는 넘긴 엘리먼트를 iframe으로 교체하므로 매번 새 자식을 만든다
    host.innerHTML = "";
    const mount = document.createElement("div");
    mount.className = "w-full h-full";
    host.appendChild(mount);

    const songId = selectedSong.id;
    const videoId = media.youtubeId;

    createYouTubePlayer(mount, {
      videoId,
      autoplay: false,
      onReady: (handle) => {
        if (disposed) {
          handle.destroy();
          return;
        }
        ytHandleRef.current = handle;
        handle.setVolume(mrVolume * 100);
        setDuration(handle.getDuration());
        // 실제로 재생되는 것이 확인된 ID만 저장한다
        saveVideoId(songId, videoId);
      },
      onStateChange: (state) => {
        if (disposed) return;
        if (state === YT_STATE.PLAYING) {
          setIsPlaying(true);
          setDuration(ytHandleRef.current?.getDuration() ?? 0);
        } else if (state === YT_STATE.PAUSED) {
          setIsPlaying(false);
        } else if (state === YT_STATE.ENDED) {
          // 노래가 끝나면 자동으로 점수 화면을 띄운다
          finishAndScore();
        }
      },
      onError: (_code, message) => {
        if (disposed) return;
        // 임베드가 막혔거나 삭제된 영상 — 저장된 ID를 지워 다시 등록받는다
        clearVideoId(songId);
        setPlayerError(message);
        setResolved({
          songId,
          media: {
            source: "synth",
            reason: "유튜브 재생에 실패해 내장 자동 반주로 전환했습니다",
          },
        });
      },
    }).catch((err: Error) => {
      if (disposed) return;
      setPlayerError(err.message);
      setResolved({
        songId,
        media: {
          source: "synth",
          reason: "유튜브에 연결하지 못해 내장 자동 반주로 전환했습니다",
        },
      });
    });

    return () => {
      disposed = true;
      ytHandleRef.current?.destroy();
      ytHandleRef.current = null;
      host.innerHTML = "";
    };
    // mrVolume은 아래 별도 effect에서 반영한다 (여기서 재생성되면 영상이 끊긴다)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [media?.source, media?.youtubeId, selectedSong.id, finishAndScore]);

  /** MR 볼륨 변경을 각 재생 소스에 반영 */
  useEffect(() => {
    ytHandleRef.current?.setVolume(mrVolume * 100);
    if (localAudioRef.current) localAudioRef.current.volume = mrVolume;
    accompanimentRef.current?.setVolume(mrVolume);
  }, [mrVolume]);

  /* ─────────────────────────────────────────────────────────
   * 재생 위치 표시 타이머
   * ──────────────────────────────────────────────────────── */
  const startTicker = useCallback(() => {
    if (tickTimerRef.current) clearInterval(tickTimerRef.current);
    tickTimerRef.current = setInterval(() => {
      if (ytHandleRef.current) {
        setElapsed(Math.floor(ytHandleRef.current.getCurrentTime()));
      } else if (localAudioRef.current) {
        setElapsed(Math.floor(localAudioRef.current.currentTime));
      } else {
        setElapsed((prev) => prev + 1);
      }
    }, 1000);
  }, []);

  /* ─────────────────────────────────────────────────────────
   * 마이크
   * ──────────────────────────────────────────────────────── */
  const stopVirtualMic = useCallback(() => {
    setIsVirtualMic(false);
    if (virtualTimerRef.current) {
      clearInterval(virtualTimerRef.current);
      virtualTimerRef.current = null;
    }
    setAudioData({ volume: 0, pitch: 0, note: "-", cents: 0 });
  }, []);

  const startMicrophone = useCallback(async (): Promise<boolean> => {
    if (isVirtualMic) stopVirtualMic();
    const ok = (await scorerRef.current?.startMicrophone(setAudioData)) ?? false;
    setIsMicActive(ok);
    return ok;
  }, [isVirtualMic, stopVirtualMic]);

  const toggleMicrophone = useCallback(async () => {
    if (isMicActive) {
      scorerRef.current?.stopMicrophone();
      setIsMicActive(false);
      setAudioData({ volume: 0, pitch: 0, note: "-", cents: 0 });
      return;
    }
    const ok = await startMicrophone();
    if (!ok) {
      alert(
        "마이크를 사용할 수 없습니다.\n마이크 권한을 허용했는지 확인하거나, '가상보컬' 버튼으로 채점을 체험해 보세요."
      );
    }
  }, [isMicActive, startMicrophone]);

  const toggleVirtualMic = useCallback(() => {
    if (isVirtualMic) {
      stopVirtualMic();
      return;
    }
    if (isMicActive) {
      scorerRef.current?.stopMicrophone();
      setIsMicActive(false);
    }
    scorerRef.current?.resetScore();
    setIsVirtualMic(true);
    const notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"];
    virtualTimerRef.current = setInterval(() => {
      const volume = Math.floor(45 + Math.random() * 45);
      const pitch = Math.floor(220 + Math.random() * 400);
      // 시뮬레이션 값도 채점 통계에 반영해 점수가 실제로 계산되도록 한다
      scorerRef.current?.feedSimulatedFrame(volume, pitch);
      setAudioData({
        volume,
        pitch,
        note: notes[Math.floor(Math.random() * notes.length)],
        cents: Math.floor(Math.random() * 30 - 15),
      });
    }, 150);
  }, [isMicActive, isVirtualMic, stopVirtualMic]);

  /* ─────────────────────────────────────────────────────────
   * 재생 시작 / 정지
   * ──────────────────────────────────────────────────────── */
  const handlePlay = useCallback(async () => {
    if (!media) return;

    scoredRef.current = false;
    setShowScoreModal(false);
    setElapsed(0);
    scorerRef.current?.resetScore();

    // 마이크가 꺼져 있으면 채점을 위해 자동으로 켠다
    if (!isMicActive && !isVirtualMic) {
      await startMicrophone();
    }

    if (media.source === "youtube" && ytHandleRef.current) {
      ytHandleRef.current.seekTo(0);
      ytHandleRef.current.setVolume(mrVolume * 100);
      ytHandleRef.current.play();
      // 유튜브 영상이 반주 역할을 하므로 내장 반주는 확실히 끈다 (소리 겹침 방지)
      accompanimentRef.current?.stop();
    } else if (media.source === "local" && media.localUrl) {
      accompanimentRef.current?.stop();
      if (!localAudioRef.current) {
        localAudioRef.current = new Audio();
      }
      const audio = localAudioRef.current;
      if (audio.src !== new URL(media.localUrl, window.location.href).href) {
        audio.src = media.localUrl;
      }
      audio.volume = mrVolume;
      audio.currentTime = 0;
      audio.onloadedmetadata = () => setDuration(Math.floor(audio.duration || 0));
      audio.onended = () => finishAndScore();
      audio.onerror = () => {
        setPlayerError("반주 파일을 재생할 수 없습니다. 파일 형식을 확인해 주세요.");
        setResolved({
          songId: selectedSong.id,
          media: { source: "synth", reason: "반주 파일 재생 실패 — 내장 자동 반주로 전환" },
        });
      };
      await audio.play().catch(() => {
        setPlayerError("브라우저가 자동 재생을 막았습니다. 다시 한 번 눌러 주세요.");
      });
    } else {
      // 내장 신스 반주 — 곡 길이를 알 수 없으므로 [노래 완료] 버튼으로 끝낸다
      ytHandleRef.current?.pause();
      accompanimentRef.current?.setVolume(mrVolume);
      accompanimentRef.current?.start({
        bpm: selectedSong.mr.bpm,
        style: selectedSong.mr.style,
        progression: selectedSong.mr.progression,
        tonic: selectedSong.mr.tonic,
      });
      setDuration(selectedSong.approxDurationSec);
    }

    setIsPlaying(true);
    startTicker();
  }, [
    media,
    isMicActive,
    isVirtualMic,
    startMicrophone,
    mrVolume,
    selectedSong,
    startTicker,
    finishAndScore,
  ]);

  const handlePause = useCallback(() => {
    stopAllPlayback();
  }, [stopAllPlayback]);

  /** 목록에서 곡을 고르면 재생 중이던 것을 정리하고 새 곡을 준비한다 */
  const handleSelectSong = useCallback(
    (song: KaraokeSong) => {
      stopAllPlayback();
      scoredRef.current = false;
      setSelectedSong(song);
      setPlayerError(null);
      setElapsed(0);
      setDuration(song.approxDurationSec);
      setRegisterInput("");
      setRegisterNotice(null);
      setShowScoreModal(false);
    },
    [stopAllPlayback]
  );

  /** 유튜브 노래방 영상 등록 */
  const handleRegisterVideo = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const id = parseYouTubeId(registerInput);
      if (!id) {
        setRegisterNotice("유튜브 링크 형식이 아닙니다. 주소창의 링크를 그대로 붙여넣어 주세요.");
        return;
      }
      saveVideoId(selectedSong.id, id);
      setPlayerError(null);
      setRegisterInput("");
      setRegisterNotice(`'${selectedSong.title}' 영상이 등록되었습니다.`);
      setResolved({
        songId: selectedSong.id,
        media: {
          source: "youtube",
          youtubeId: id,
          reason: "유튜브 공식 임베드 플레이어로 스트리밍 중 (복제 없음)",
        },
      });
    },
    [registerInput, selectedSong]
  );

  /* ─────────────────────────────────────────────────────────
   * 표시용 파생값
   * ──────────────────────────────────────────────────────── */
  const filteredSongs = KARAOKE_SONGS.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.singer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const currentCue =
    [...selectedSong.guideCues].reverse().find((c) => c.t <= elapsed) ?? selectedSong.guideCues[0];
  const nextCue = selectedSong.guideCues.find((c) => c.t > elapsed);

  const formatSeconds = (sec: number) => {
    const m = Math.floor(Math.max(0, sec) / 60);
    const s = Math.floor(Math.max(0, sec) % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const progressPct = duration > 0 ? Math.min(100, (elapsed / duration) * 100) : 0;

  // Tailwind는 클래스 문자열을 정적으로 훑기 때문에 `bg-${color}-950` 같은 조합은
  // 빌드에서 제거된다. 완성된 클래스 문자열을 그대로 적어 둔다.
  const sourceBadge = {
    local: {
      icon: HardDrive,
      label: "로컬 반주 파일",
      className: "bg-emerald-950/50 border-emerald-500/40 text-emerald-300",
    },
    youtube: {
      icon: Tv,
      label: "유튜브 노래방 영상",
      className: "bg-rose-950/50 border-rose-500/40 text-rose-300",
    },
    synth: {
      icon: Radio,
      label: "내장 자동 반주",
      className: "bg-indigo-950/50 border-indigo-500/40 text-indigo-300",
    },
  }[media?.source ?? "synth"];
  const SourceIcon = sourceBadge.icon;

  return (
    <div className="space-y-6">
      {/* 전원 차단 경고 */}
      {!isPowerOn && (
        <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-200 text-sm flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-3">
            <PowerOff className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="font-bold">현재 부스 반주기 전원(릴레이)이 차단되어 있습니다.</p>
              <p className="text-xs text-amber-300/80 mt-0.5">
                첫 번째 탭의 키패드에 예약 비밀번호를 입력하거나, 부스 반주기 전원을 켜 주세요.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-900/60 text-amber-300 border border-amber-700 shrink-0">
            Relay Power: OFF
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── 왼쪽: 노래방 화면 ─────────────────────────────── */}
        <div className="lg:col-span-8 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col space-y-4">
          {/* 헤더 */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="p-2 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-md shrink-0">
                <Tv className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-bold text-white flex items-center gap-2 flex-wrap">
                  <span className="truncate">{selectedSong.title}</span>
                  <span className="text-xs font-normal text-slate-400">- {selectedSong.singer}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shrink-0">
                    {selectedSong.tag}
                  </span>
                </h3>
                <p className="text-[11px] text-slate-400">
                  {isPlaying
                    ? `가창 중 · ${formatSeconds(elapsed)} / ${formatSeconds(duration)}`
                    : "대기 중 · 곡을 고르고 [반주 시작]을 누르세요"}
                </p>
              </div>
            </div>

            {/* 현재 재생 소스 배지 */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-[11px] font-bold shrink-0 ${sourceBadge.className}`}
            >
              <SourceIcon className="w-3.5 h-3.5" />
              {sourceBadge.label}
            </div>
          </div>

          {/* 화면 */}
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-slate-950 border-2 border-indigo-500/40 shadow-2xl">
            {media?.source === "youtube" ? (
              /* 유튜브 노래방 영상 — 가사는 영상이 직접 표시한다 */
              <div className="relative w-full h-full">
                <div ref={ytHostRef} className="w-full h-full" />
                {/* 구간 안내 오버레이 (영상 위, 클릭은 통과시킨다) */}
                {isPlaying && currentCue && (
                  <div className="absolute bottom-0 inset-x-0 pointer-events-none p-3 bg-gradient-to-t from-slate-950/90 to-transparent">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="px-2 py-0.5 rounded-full bg-amber-400/25 text-amber-200 border border-amber-400/40 font-bold shrink-0">
                        {currentCue.label}
                      </span>
                      {currentCue.hint && (
                        <span className="text-slate-300 truncate">{currentCue.hint}</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : media?.source === "local" ? (
              /* 로컬 반주 파일 재생 화면 */
              <GuideScreen
                song={selectedSong}
                isPlaying={isPlaying}
                elapsed={elapsed}
                cueLabel={currentCue?.label}
                cueHint={currentCue?.hint}
                nextCueLabel={nextCue?.label}
                volume={audioData.volume}
                headline="학교 보유 반주 파일로 재생 중"
                onStart={handlePlay}
              />
            ) : (
              /* 유튜브 영상이 아직 등록되지 않았거나 재생에 실패한 경우 */
              <div className="w-full h-full overflow-y-auto p-5 flex flex-col justify-center">
                {playerError && (
                  <div className="mb-3 flex items-start gap-2 p-2.5 rounded-xl bg-rose-950/50 border border-rose-500/40 text-rose-200 text-xs">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{playerError}</span>
                  </div>
                )}

                <div className="text-center space-y-1 mb-4">
                  <Link2 className="w-8 h-8 text-indigo-400 mx-auto" />
                  <h4 className="text-base font-black text-white">노래방 영상 등록하기</h4>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    <span className="text-indigo-300 font-bold">{selectedSong.title}</span>의 노래방
                    영상을 유튜브에서 찾아 링크를 붙여넣으면, 가사가 나오는 영상이 이 화면에
                    재생됩니다.
                    <br />
                    등록 전에는 내장 자동 반주로도 노래하고 점수를 받을 수 있습니다.
                  </p>
                </div>

                <div className="flex justify-center mb-3">
                  <a
                    href={youtubeSearchUrl(selectedSong)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-1.5 transition-colors shadow"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    유튜브에서 &quot;{selectedSong.youtubeSearchQuery}&quot; 검색
                  </a>
                </div>

                <form onSubmit={handleRegisterVideo} className="flex gap-2 max-w-md mx-auto w-full">
                  <input
                    type="text"
                    value={registerInput}
                    onChange={(e) => setRegisterInput(e.target.value)}
                    placeholder="유튜브 링크를 붙여넣으세요"
                    className="flex-1 px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors shrink-0 cursor-pointer"
                  >
                    등록
                  </button>
                </form>

                {registerNotice && (
                  <p className="text-center text-[11px] text-emerald-300 mt-2 flex items-center justify-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {registerNotice}
                  </p>
                )}

                {isPlaying && currentCue && (
                  <div className="mt-4 text-center">
                    <span className="text-xs px-3 py-1 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold">
                      {currentCue.label}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 진행 바 */}
          <div className="space-y-1">
            <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-pink-400 transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>{formatSeconds(elapsed)}</span>
              <span>{duration > 0 ? formatSeconds(duration) : "--:--"}</span>
            </div>
          </div>

          {/* 재생 근거 안내 — 전시회 관람객에게 보여 줄 문구 */}
          {media && (
            <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500/70 shrink-0" />
              {media.reason}
            </p>
          )}

          {/* 컨트롤 바 */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => (isPlaying ? handlePause() : void handlePlay())}
                disabled={!media}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200 border border-slate-700 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                {isPlaying ? "일시정지" : "반주 시작"}
              </button>

              <button
                onClick={finishAndScore}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 font-black text-xs flex items-center gap-1.5 shadow-lg shadow-amber-500/20 transition-all cursor-pointer"
              >
                <Trophy className="w-4 h-4" />
                노래 완료 &amp; 점수 채점! 💯
              </button>

              {media?.source === "youtube" && media.youtubeId && (
                <a
                  href={youtubeWatchUrl(media.youtubeId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  title="화면이 작으면 유튜브에서 직접 크게 열 수 있습니다"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  유튜브에서 열기
                </a>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* MR 볼륨 */}
              <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
                <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-[11px] text-slate-400">반주 볼륨</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={mrVolume}
                  onChange={(e) => setMrVolume(parseFloat(e.target.value))}
                  className="w-16 sm:w-20 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <span className="font-mono text-[10px] text-indigo-300 w-7 text-right">
                  {Math.round(mrVolume * 100)}%
                </span>
              </div>

              {/* 마이크 미터 */}
              <div className="flex items-center gap-3 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
                <button
                  onClick={() => void toggleMicrophone()}
                  className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                    isMicActive
                      ? "bg-rose-950 text-rose-300 border-rose-500/50"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}
                  title={isMicActive ? "마이크 끄기" : "마이크 켜기"}
                >
                  {isMicActive ? (
                    <Mic className="w-4 h-4 text-rose-400 animate-pulse" />
                  ) : (
                    <MicOff className="w-4 h-4" />
                  )}
                </button>

                <button
                  onClick={toggleVirtualMic}
                  className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
                    isVirtualMic
                      ? "bg-cyan-950 text-cyan-300 border-cyan-500/50"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}
                  title="마이크가 없을 때 채점을 체험하는 시뮬레이션 모드"
                >
                  {isVirtualMic ? "가상보컬 ON" : "가상보컬"}
                </button>

                <div className="flex items-center gap-1.5">
                  <Volume2 className="w-3.5 h-3.5 text-slate-400" />
                  <div className="w-20 sm:w-24 h-2.5 rounded-full bg-slate-800 overflow-hidden p-0.5 flex items-center">
                    <div
                      className={`h-full rounded-full transition-all duration-75 ${
                        audioData.volume > 70
                          ? "bg-rose-500"
                          : audioData.volume > 40
                          ? "bg-amber-400"
                          : "bg-emerald-400"
                      }`}
                      style={{ width: `${Math.max(4, audioData.volume)}%` }}
                    />
                  </div>
                </div>

                {/* 음정 정확도 게이지 — 가운데에 가까울수록 정확 */}
                <div className="hidden sm:flex items-center gap-1.5" title="음정 정확도">
                  <span className="font-mono text-[10px] text-slate-400">{audioData.note}</span>
                  <div className="relative w-14 h-2.5 rounded-full bg-slate-800 overflow-hidden">
                    <div className="absolute left-1/2 top-0 w-px h-full bg-slate-600" />
                    {audioData.pitch > 0 && (
                      <div
                        className={`absolute top-0.5 w-1.5 h-1.5 rounded-full transition-all duration-75 ${
                          Math.abs(audioData.cents) < 15 ? "bg-emerald-400" : "bg-amber-400"
                        }`}
                        style={{
                          left: `calc(${50 + Math.max(-45, Math.min(45, audioData.cents))}% - 3px)`,
                        }}
                      />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── 오른쪽: 선곡 목록 ─────────────────────────────── */}
        <div className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Music className="w-4 h-4 text-amber-400" />
              학생 애창곡 TOP 10
            </h3>
            <span className="text-[11px] text-slate-400">2026.09 기준</span>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="곡명 또는 가수 검색..."
              className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="space-y-2 overflow-y-auto pr-1 flex-1 max-h-[520px]">
            {filteredSongs.map((song) => {
              const isCurrent = selectedSong.id === song.id;
              const hasVideo = Boolean(getVideoId(song));
              return (
                <button
                  key={song.id}
                  onClick={() => handleSelectSong(song)}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isCurrent
                      ? "bg-indigo-950/60 border-indigo-500 text-white shadow-md shadow-indigo-950/40"
                      : "bg-slate-950/50 border-slate-800/80 hover:bg-slate-800/50 text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-5 text-center text-[11px] font-black shrink-0 ${
                        isCurrent ? "text-amber-300" : "text-slate-600"
                      }`}
                    >
                      {KARAOKE_SONGS.indexOf(song) + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold truncate">{song.title}</span>
                        <span className="text-[9px] px-1.5 py-px rounded bg-slate-800 text-amber-300 shrink-0">
                          {song.tag}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">
                        {song.singer} · {song.genre}
                      </p>
                    </div>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded shrink-0 border ${
                        hasVideo
                          ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                          : "bg-slate-800/60 text-slate-500 border-slate-700"
                      }`}
                      title={hasVideo ? "노래방 영상이 등록된 곡" : "영상 미등록 — 내장 반주로 재생"}
                    >
                      {hasVideo ? "영상 ✓" : "미등록"}
                    </span>
                  </div>
                  {isCurrent && (
                    <p className="text-[10px] text-indigo-300/80 mt-1.5 pl-7 leading-relaxed">
                      {song.pickReason}
                    </p>
                  )}
                </button>
              );
            })}
          </div>

          <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-500 leading-relaxed">
            <p className="flex items-start gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500/70 shrink-0 mt-0.5" />
              <span>
                노래방 영상은 <strong className="text-slate-400">내려받지 않고</strong> 유튜브 공식
                플레이어로 재생합니다. 자세한 근거는{" "}
                <code className="text-indigo-400">docs/부록F</code> 문서를 확인하세요.
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* ── 점수 결과 모달 ─────────────────────────────────── */}
      {showScoreModal && (
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md bg-gradient-to-b from-slate-900 to-indigo-950 border-2 border-amber-500/60 rounded-3xl p-6 shadow-2xl text-center relative overflow-hidden space-y-5">
            <div className="absolute inset-0 pointer-events-none opacity-40">
              <div className="absolute w-2 h-2 rounded-full bg-amber-400 top-6 left-12 animate-ping" />
              <div className="absolute w-3 h-3 rounded-full bg-rose-400 top-16 right-10 animate-bounce" />
              <div className="absolute w-2.5 h-2.5 rounded-full bg-cyan-400 bottom-10 left-16 animate-pulse" />
              <div className="absolute w-2 h-2 rounded-full bg-emerald-400 bottom-16 right-12 animate-ping" />
            </div>

            <div className="relative">
              <span className="text-[11px] uppercase tracking-wider px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">
                KARAOKE SCORE
              </span>
              <h3 className="text-xl font-black text-white mt-2">{selectedSong.title}</h3>
              <p className="text-xs text-slate-400">{selectedSong.singer}</p>
            </div>

            <div className="relative py-2">
              <div className="w-36 h-36 mx-auto rounded-full bg-gradient-to-br from-amber-500/20 via-purple-500/20 to-indigo-500/20 border-4 border-amber-400/80 flex flex-col items-center justify-center shadow-xl shadow-amber-500/20">
                <span className="text-[10px] font-bold text-amber-300">FINAL SCORE</span>
                <div className="text-5xl font-black text-amber-400 tracking-tighter my-0.5">
                  {animatedScore}
                  <span className="text-2xl font-bold text-amber-200">점</span>
                </div>
                <div className="px-2.5 py-0.5 rounded-full bg-amber-400 text-slate-950 font-black text-xs">
                  등급 {finalScore?.rank ?? "-"}
                </div>
              </div>
            </div>

            {/* 항목별 점수 — 왜 이 점수인지 학생에게 보여 준다 */}
            {finalScore?.sangSomething && (
              <div className="relative grid grid-cols-4 gap-1.5">
                {[
                  { label: "음정", value: finalScore.breakdown.pitch, max: 35 },
                  { label: "박자", value: finalScore.breakdown.timing, max: 30 },
                  { label: "성량", value: finalScore.breakdown.volume, max: 20 },
                  { label: "표현", value: finalScore.breakdown.expression, max: 15 },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="bg-slate-900/70 border border-slate-800 rounded-xl p-2"
                  >
                    <p className="text-[10px] text-slate-400">{item.label}</p>
                    <p className="text-sm font-black text-indigo-300">
                      {item.value}
                      <span className="text-[10px] font-normal text-slate-500">/{item.max}</span>
                    </p>
                    <div className="h-1 mt-1 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${(item.value / item.max) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="relative bg-slate-900/80 border border-slate-800 rounded-2xl p-3.5 shadow-inner">
              <p className="text-sm font-bold text-slate-100 flex items-center justify-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                {isCalculatingScore ? "점수를 채점하고 있습니다..." : finalScore?.comment}
              </p>
              {finalScore?.sangSomething && !isCalculatingScore && (
                <p className="text-[11px] text-slate-400 mt-1">
                  애창곡 DB에 가창 기록이 등록되었습니다!
                </p>
              )}
            </div>

            <div className="relative flex items-center justify-center gap-3">
              <button
                onClick={() => setShowScoreModal(false)}
                className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold text-xs transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                닫기
              </button>
              <button
                onClick={() => {
                  setShowScoreModal(false);
                  void handlePlay();
                }}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/30 transition-all cursor-pointer flex items-center gap-1.5"
              >
                <Award className="w-4 h-4" />
                한 번 더 부르기!
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
 * 로컬 반주 파일 재생 시의 화면 (영상이 없으므로 구간 안내를 크게 보여 준다)
 * ──────────────────────────────────────────────────────────── */
function GuideScreen({
  song,
  isPlaying,
  elapsed,
  cueLabel,
  cueHint,
  nextCueLabel,
  volume,
  headline,
  onStart,
}: {
  song: KaraokeSong;
  isPlaying: boolean;
  elapsed: number;
  cueLabel?: string;
  cueHint?: string;
  nextCueLabel?: string;
  volume: number;
  headline: string;
  onStart: () => void;
}) {
  return (
    <div className="h-full flex flex-col justify-between p-6">
      <div className="flex items-center justify-between text-xs text-indigo-300/80 font-mono border-b border-indigo-500/20 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="font-bold text-white uppercase tracking-wider">KARAOKE LIVE</span>
        </div>
        <span>{headline}</span>
      </div>

      <div className="flex flex-col items-center justify-center text-center my-auto space-y-4 px-4">
        {isPlaying ? (
          <>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-400/20 text-amber-300 text-xs font-bold border border-amber-400/30">
              🎤 {formatTime(elapsed)}
            </div>
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 via-amber-200 to-pink-300 drop-shadow-[0_0_20px_rgba(234,179,8,0.4)] leading-snug">
              {cueLabel}
            </h2>
            {cueHint && <p className="text-sm text-slate-300">{cueHint}</p>}
            {nextCueLabel && (
              <p className="text-xs text-slate-500">다음 구간: {nextCueLabel}</p>
            )}
          </>
        ) : (
          <div className="space-y-3">
            <div className="w-16 h-16 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shadow-lg mx-auto">
              <Play className="w-8 h-8 fill-current ml-1" />
            </div>
            <h4 className="text-xl font-black text-white">{song.title}</h4>
            <p className="text-xs text-slate-400">{song.singer}</p>
            <button
              onClick={onStart}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
            >
              반주 시작 &amp; 가창하기
            </button>
          </div>
        )}
      </div>

      {/* 그래픽 이퀄라이저 */}
      <div className="flex items-center gap-1.5 h-6 pt-3 border-t border-indigo-500/20">
        {[40, 75, 55, 90, 65, 80, 45, 100, 60, 85, 50, 70].map((h, i) => (
          <div
            key={i}
            className={`w-1.5 rounded-full transition-all duration-150 ${
              isPlaying ? "bg-gradient-to-t from-indigo-500 to-pink-400" : "bg-slate-800"
            }`}
            style={{ height: isPlaying ? `${Math.max(20, (h * (volume + 30)) / 100)}%` : "20%" }}
          />
        ))}
      </div>
    </div>
  );
}

function formatTime(sec: number) {
  const m = Math.floor(Math.max(0, sec) / 60);
  const s = Math.floor(Math.max(0, sec) % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}
