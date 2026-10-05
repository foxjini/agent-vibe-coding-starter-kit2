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
  Volume2,
  SlidersHorizontal,
  AlertTriangle,
  CheckCircle2,
  HardDrive,
  Radio,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { KaraokeAudioScorer, AudioAnalysisResult, FinalScore } from "@/utils/audioScorer";
import { KaraokeAccompanimentEngine } from "@/utils/karaokeAccompaniment";
import { createYouTubePlayer, YouTubePlayerHandle, YT_STATE } from "@/utils/youtubePlayer";
import {
  resolveMedia,
  loadVideoOverrides,
  hasNextAttempt,
  ResolvedMedia,
} from "@/utils/karaokeMedia";
import { KARAOKE_SONGS, KaraokeSong } from "@/data/karaokeSongs";
import { AttractScreen } from "@/components/booth/AttractScreen";
import { BoothKeypad } from "@/components/booth/BoothKeypad";
import { SessionStrip } from "@/components/booth/SessionStrip";
import type { BoothAuthNotice } from "@/hooks/useBoothData";
import type { BoothSessionState } from "@/hooks/useBoothSession";
import { Device, QueueSnapshot, ScoreRecord } from "@/types";
import { apiUrl } from "@/utils/apiConfig";

interface KaraokeRoomSectionProps {
  devices: Device[];
  onSongCompleted?: () => void;
  /** 어트랙트 화면에 돌려 보여 줄 순위 (부록G §2-④) */
  topToday?: ScoreRecord[];
  topAll?: ScoreRecord[];
  /** 전시 체험 대기열 — 어트랙트 화면의 QR·대기 현황에 쓴다 */
  queue?: QueueSnapshot | null;
  /** 점수를 남긴 뒤 순위를 다시 받아 오게 한다 */
  onScoreRecorded?: () => void;
  /** 지금 부스를 쓰는 사람과 남은 시간 (GET /api/booth/session) */
  session?: BoothSessionState | null;
  /** 키패드 인증 결과 방송 — 실물 키패드로 누른 결과도 화면 키패드에 띄운다 */
  authNotice?: BoothAuthNotice | null;
  /** 화면 키패드로 인증을 마쳤을 때 (기기 상태를 곧바로 다시 받는다) */
  onKeypadVerified?: () => void;
}

/** 이용 종료 후 대기 화면으로 돌아가기까지 (점수를 볼 시간) */
const RETURN_TO_ATTRACT_MS = 15_000;

export function KaraokeRoomSection({
  devices,
  onSongCompleted,
  topToday = [],
  topAll = [],
  queue = null,
  onScoreRecorded,
  session = null,
  authNotice = null,
  onKeypadVerified,
}: KaraokeRoomSectionProps) {
  /*
   * 부스 반주기 전원(relay_1)이 곧 "인증된 이용 중"이다.
   * 전원은 예약 PIN(예약 시간에만)·호출된 체험권 PIN으로 인증했거나 관리자가
   * 직접 켰을 때만 들어온다. 전원이 꺼져 있으면 노래방을 열 방법을 주지 않는다 —
   * 예전에는 [노래방 시작하기]를 누르면 예약 없이도 노래방이 열리고 반주가 나왔다.
   */
  const relayDevice = devices.find((d) => d.id === "relay_1");
  const isPowerOn = relayDevice?.current_state === "on";
  const ledBlink = devices.find((d) => d.id === "led_1")?.current_state === "blink";

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

  /** 유튜브 시도 목록에서 몇 번째를 쓰는 중인지 — 실패하면 +1 해서 다음 후보로 */
  const [attemptIndex, setAttemptIndex] = useState(0);
  /** 플레이어가 실제로 재생 명령을 받을 준비가 됐는가 */
  const [playerReady, setPlayerReady] = useState(false);
  /**
   * 노래방에 "입장"했는가.
   * 브라우저는 사용자 제스처 없이 소리를 내지 못하고, 마이크 권한 창이 뜨는
   * 동안 제스처가 소실되면 영상 재생까지 막힌다. 그래서 입장 버튼에서
   * 권한과 오디오를 먼저 확보해 두고, 이후 [반주 시작]은 곧바로 재생만 한다.
   */
  const [hasEntered, setHasEntered] = useState(false);
  const [isEntering, setIsEntering] = useState(false);
  /** 순위에 올릴 별명 — 입장할 때 한 번 받아 두고 채점 때마다 묻지 않는다 */
  const [nickname, setNickname] = useState("");
  const [enterNotice, setEnterNotice] = useState<string | null>(null);

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
  /**
   * 이번 점수를 기록에 남겼는가.
   *   excluded — 가상보컬로 부른 점수 (순위·애창곡에 올리지 않는다)
   *   saving / saved / failed — 순위·애창곡 기록 저장 결과
   */
  const [recordStatus, setRecordStatus] = useState<
    "excluded" | "saving" | "saved" | "failed" | null
  >(null);

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
  /**
   * 이번 곡에서 가상보컬(마이크 없이 채점 체험)을 썼는가.
   * 가상보컬은 아무도 안 불러도 그럴듯한 점수가 나온다. 그 점수가 순위에 오르면
   * 실제로 부른 사람의 순위가 밀린다 — 체험용으로만 보여 주고 기록하지 않는다.
   */
  const usedVirtualRef = useRef(false);
  /** ticker가 항상 최신 채점 함수를 부르도록 담아 두는 상자 */
  const finishAndScoreRef = useRef<(() => void) | null>(null);
  /** 유튜브 콜백이 항상 최신 곡·후보 번호를 보도록 담아 두는 상자 */
  const selectedSongRef = useRef(selectedSong);
  const attemptIndexRef = useRef(attemptIndex);

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
    // 관리자 등록본을 먼저 받아 온 뒤 재생 소스를 정한다.
    // 서버가 꺼져 있어도 loadVideoOverrides가 조용히 넘어가고 기본 후보로 재생된다.
    void loadVideoOverrides()
      .then(() => resolveMedia(selectedSong, attemptIndex))
      .then((m) => {
        if (!cancelled) setResolved({ songId: selectedSong.id, media: m });
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSong, attemptIndex]);

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
    async (song: KaraokeSong): Promise<boolean> => {
      try {
        const res = await fetch(apiUrl("/api/songs"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: song.title, singer: song.singer }),
        });
        onSongCompleted?.();
        return res.ok;
      } catch {
        /* 백엔드가 꺼져 있어도 노래방 기능 자체는 계속 동작해야 한다 */
        return false;
      }
    },
    [onSongCompleted]
  );

  /**
   * 채점 결과를 순위에 올린다 (부록G §2-④).
   *
   * 실패해도 조용히 넘어간다 — 점수를 못 남겼다고 해서 노래방 화면이 멈추거나
   * 사용자에게 오류를 띄울 일은 아니다. 부를 때마다 이름을 묻지 않으려고
   * 별명은 입장할 때 한 번만 받는다.
   */
  const recordScoreToDB = useCallback(
    async (song: KaraokeSong, result: FinalScore): Promise<boolean> => {
      try {
        const res = await fetch(apiUrl("/api/scores"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nickname: nickname.trim() || "익명",
            title: song.title,
            singer: song.singer,
            score: result.score,
            rank_label: result.rank,
            pitch: Math.round(result.breakdown.pitch),
            timing: Math.round(result.breakdown.timing),
            volume: Math.round(result.breakdown.volume),
            expression: Math.round(result.breakdown.expression),
          }),
        });
        onScoreRecorded?.();
        return res.ok;
      } catch {
        /* 순위 등록 실패는 노래방 진행을 막지 않는다 */
        return false;
      }
    },
    [nickname, onScoreRecorded]
  );

  const finishAndScore = useCallback(() => {
    if (scoredRef.current) return; // 중복 채점 방지
    scoredRef.current = true;

    stopAllPlayback();
    setIsCalculatingScore(true);
    setShowScoreModal(true);
    setAnimatedScore(0);
    setRecordStatus(null);
    KaraokeAudioScorer.playDrumrollSound();
    const virtual = usedVirtualRef.current;

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
          if (virtual) {
            setRecordStatus("excluded");
          } else {
            setRecordStatus("saving");
            void Promise.all([
              recordSongToDB(selectedSong),
              recordScoreToDB(selectedSong, result),
            ]).then(([song, score]) => setRecordStatus(song && score ? "saved" : "failed"));
          }
        }
      }
    }, 40);
  }, [recordSongToDB, recordScoreToDB, selectedSong, stopAllPlayback]);

  // ticker(setInterval)와 유튜브 콜백은 만들어질 때의 값을 붙잡고 있으므로,
  // 곡이 바뀌어도 최신 값을 보도록 ref에 담아 둔다.
  // 이렇게 해 두면 아래 플레이어 effect가 "영상 ID가 실제로 바뀔 때"만 다시 돌아서
  // 유튜브 위젯이 불필요하게 재생성되지 않는다.
  // (렌더 중에 ref를 쓰면 안 되므로 effect에서 갱신한다)
  useEffect(() => {
    finishAndScoreRef.current = finishAndScore;
    selectedSongRef.current = selectedSong;
    attemptIndexRef.current = attemptIndex;
  }, [finishAndScore, selectedSong, attemptIndex]);

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
        setPlayerReady(true);
        // "다음 영상으로 넘어갑니다" · "불러오는 중입니다" 같은 잠깐짜리 안내를 지운다
        setPlayerError(null);
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
          finishAndScoreRef.current?.();
        }
      },
      onError: (code, message) => {
        if (disposed) return;
        setPlayerReady(false);

        // 어떤 영상이 몇 번 코드로 실패했는지는 콘솔에 남긴다. 영상 점검과 등록은
        // 관리자 화면(/admin)의 [노래방 영상 점검]에서 한다 — 부스 화면은 관람객용이다.
        console.warn(
          `[노래방] 재생 실패 — 곡=${selectedSongRef.current.id} 영상=${videoId} 코드=${code} (${message})`
        );

        // 임베드가 막혔거나 삭제된 영상 — 같은 곡의 다음 후보로 자동 전환한다.
        // 후보를 다 쓴 뒤에야 내장 반주로 떨어진다.
        if (hasNextAttempt(selectedSongRef.current, attemptIndexRef.current)) {
          setPlayerError("이 영상을 재생할 수 없어 다음 노래방 영상으로 넘어갑니다.");
          setAttemptIndex((prev) => prev + 1);
          return;
        }

        // 내장 반주로 바뀐 이유는 화면 아래 재생 안내(media.reason)가 이미 말해 준다
        setPlayerError(null);
        setResolved({
          songId: selectedSongRef.current.id,
          media: {
            source: "synth",
            reason: "유튜브 영상을 모두 재생할 수 없어 내장 자동 반주로 전환했습니다",
          },
        });
      },
    }).catch((err: Error) => {
      if (disposed) return;
      console.warn(`[노래방] 유튜브 플레이어를 만들지 못했습니다: ${err.message}`);
      setPlayerReady(false);
      setPlayerError(null);
      setResolved({
        songId: selectedSongRef.current.id,
        media: {
          source: "synth",
          reason: "유튜브에 연결하지 못해 내장 자동 반주로 전환했습니다",
        },
      });
    });

    return () => {
      disposed = true;
      setPlayerReady(false);
      ytHandleRef.current?.destroy();
      ytHandleRef.current = null;
      host.innerHTML = "";
    };
    // 의존성은 "재생할 영상 자체"로만 좁혔다.
    // 곡/후보/채점 함수는 위에서 ref에 담아 두고 콜백에서 최신 값을 읽는다.
    // 여기에 이것들을 넣으면 곡 정보가 조금만 바뀌어도 플레이어가 통째로 다시
    // 만들어지고, 그때마다 유튜브 위젯이 새 iframe에 postMessage를 쏘면서
    // 콘솔에 target origin 경고가 쌓인다.
    // mrVolume도 아래 별도 effect에서 반영한다 (여기서 재생성되면 영상이 끊긴다)
    //
    // hasEntered 는 반드시 넣어야 한다. 입장 전에는 대기 화면만 그려져 플레이어를
    // 붙일 자리(ytHostRef)가 없다. 그때 한 번 돌고 끝나면, 입장한 뒤 기본 선택곡을
    // 그대로 고른 사람은 "영상 불러오는 중"에서 영원히 멈춘다 (실제로 그랬다).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [media?.source, media?.youtubeId, hasEntered]);

  const stopVirtualMic = useCallback(() => {
    setIsVirtualMic(false);
    if (virtualTimerRef.current) {
      clearInterval(virtualTimerRef.current);
      virtualTimerRef.current = null;
    }
    setAudioData({ volume: 0, pitch: 0, note: "-", cents: 0 });
  }, []);

  /*
   * 이용이 끝나 부스 전원이 꺼지면 대기(어트랙트) 화면으로 돌아간다.
   *
   * 팀 트리거 규칙이 "이용 종료 시 … 전원과 마이크를 차단한다"이므로 반주와
   * 마이크는 그 자리에서 끊는다. 방금 부른 사람이 점수를 볼 수 있게 화면만 조금
   * 기다렸다가 돌아간다. 대기 화면에는 키패드·QR·"지금 호출 N번"이 있어서 다음
   * 사람이 그것을 봐야 한다.
   */
  const prevPowerRef = useRef(isPowerOn);
  useEffect(() => {
    const wasOn = prevPowerRef.current;
    prevPowerRef.current = isPowerOn;
    if (wasOn === isPowerOn) return;

    if (isPowerOn) {
      // 새 사람이 인증했다. 앞사람의 종료 화면(15초)이 아직 떠 있으면 곧바로 걷어 내고
      // 환영 화면부터 시작한다 — 그대로 두면 앞사람 이름으로 점수가 올라간다.
      if (!hasEntered) return;
      const reset = setTimeout(() => {
        setShowScoreModal(false);
        setEnterNotice(null);
        setNickname("");
        setHasEntered(false);
      }, 0);
      return () => clearTimeout(reset);
    }

    if (!hasEntered) {
      // 시작 버튼을 누르기 전에 끝났다 — 다음 사람에게 앞사람 이름이 남지 않게만 한다
      const clearName = setTimeout(() => setNickname(""), 0);
      return () => clearTimeout(clearName);
    }

    const stopNow = setTimeout(() => {
      stopAllPlayback();
      scorerRef.current?.stopMicrophone();
      setIsMicActive(false);
      stopVirtualMic();
    }, 0);
    const backToAttract = setTimeout(() => {
      setShowScoreModal(false);
      setEnterNotice(null);
      setNickname("");
      setHasEntered(false);
    }, RETURN_TO_ATTRACT_MS);
    return () => {
      clearTimeout(stopNow);
      clearTimeout(backToAttract);
    };
  }, [isPowerOn, hasEntered, stopAllPlayback, stopVirtualMic]);

  /*
   * 순위에 올릴 이름은 인증한 사람의 이름으로 미리 채워 둔다 (예약자 이름 ·
   * 체험권에 적은 이름). 직접 고친 뒤에는 덮어쓰지 않는다.
   */
  const sessionNickname = isPowerOn ? session?.nickname ?? "" : "";
  useEffect(() => {
    if (!sessionNickname || hasEntered) return;
    const id = setTimeout(() => setNickname((cur) => cur || sessionNickname.slice(0, 10)), 0);
    return () => clearTimeout(id);
  }, [sessionNickname, hasEntered]);

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
      const yt = ytHandleRef.current;
      if (yt) {
        const at = yt.getCurrentTime();
        const total = yt.getDuration();
        setElapsed(Math.floor(at));

        // 곡 종료 이중 감지.
        // 유튜브의 ENDED 이벤트는 네트워크가 불안정할 때 누락되는 일이 있어,
        // 재생 위치가 끝에 닿았는지도 함께 본다. 실제 채점은 finishAndScore
        // 안의 scoredRef가 막아 주므로 두 경로가 동시에 걸려도 한 번만 돈다.
        if (total > 0 && total - at <= 1) {
          finishAndScoreRef.current?.();
        }
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
    usedVirtualRef.current = true;
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
    if (!media || !isPowerOn) return;

    scoredRef.current = false;
    // 이번 곡을 가상보컬로 시작했는지 (도중에 켜도 toggleVirtualMic 이 표시한다)
    usedVirtualRef.current = isVirtualMic;
    setShowScoreModal(false);
    setElapsed(0);
    scorerRef.current?.resetScore();
    scorerRef.current?.resumeAnalysis();

    if (media.source === "youtube") {
      const yt = ytHandleRef.current;
      if (!yt) {
        // 플레이어가 아직 준비되지 않았다. 예전에는 여기서 아래 else로 떨어져
        // 유튜브 모드인데 내장 신스 반주가 울렸다. 이제는 기다리라고 알린다.
        setPlayerError("영상을 불러오는 중입니다. 잠시 후 다시 눌러 주세요.");
        return;
      }
      // ⚠️ 이 지점까지 await가 하나도 없어야 한다.
      //    사용자 클릭과 play() 사이에 await가 끼면 제스처가 소실되어
      //    브라우저가 재생을 막는다 (마이크 권한은 입장 게이트에서 미리 받는다).
      yt.seekTo(0);
      yt.setVolume(mrVolume * 100);
      yt.play();
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
        console.warn(`[노래방] 반주 파일을 재생할 수 없습니다: ${media.localUrl}`);
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
  }, [media, isPowerOn, isVirtualMic, mrVolume, selectedSong, startTicker, finishAndScore]);

  const handlePause = useCallback(() => {
    stopAllPlayback();
    // 멈춰 있는 동안을 "안 부른 시간"으로 세면 박자 점수가 부당하게 깎인다
    scorerRef.current?.pauseAnalysis();
  }, [stopAllPlayback]);

  /**
   * 노래방 입장 — 여기서 마이크 권한과 주변 소음 측정을 한 번에 끝낸다.
   *
   * 예전에는 [반주 시작]을 누른 뒤에 마이크 권한을 물었다. 그런데 권한 창이
   * 뜨는 동안 사용자 제스처가 소실되어, 브라우저가 뒤이은 영상 재생까지
   * 막아 버렸다. 입장 시점으로 옮기면 재생 버튼은 곧바로 재생만 하면 된다.
   */
  const handleEnter = useCallback(async () => {
    if (isEntering || !isPowerOn) return;
    setIsEntering(true);
    setEnterNotice("마이크 권한을 확인하는 중...");

    const micOk = await startMicrophone();

    if (micOk) {
      setEnterNotice("주변 소음을 측정하는 중입니다. 잠시 조용히 해 주세요...");
      const { baseline, threshold } = (await scorerRef.current?.measureBaseline()) ?? {
        baseline: 0,
        threshold: 0,
      };
      setEnterNotice(
        `준비 완료! (주변 소음 ${baseline} · 발성 인식 기준 ${threshold})`
      );
    } else {
      setEnterNotice(
        "마이크를 쓸 수 없어 채점 없이 진행합니다. 채점을 원하면 브라우저 주소창의 사이트 권한에서 마이크를 허용한 뒤 새로고침해 주세요."
      );
    }

    setIsEntering(false);
    setHasEntered(true);
  }, [isEntering, isPowerOn, startMicrophone]);

  /** 목록에서 곡을 고르면 재생 중이던 것을 정리하고 새 곡을 준비한다 */
  const handleSelectSong = useCallback(
    (song: KaraokeSong) => {
      stopAllPlayback();
      scoredRef.current = false;
      setSelectedSong(song);
      setPlayerError(null);
      setAttemptIndex(0);
      setPlayerReady(false);
      setElapsed(0);
      setDuration(song.approxDurationSec);
      setShowScoreModal(false);
    },
    [stopAllPlayback]
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

  /** 유튜브 모드인데 플레이어가 아직 준비되지 않은 상태 */
  const waitingForPlayer = media?.source === "youtube" && !playerReady;

  // Tailwind는 클래스 문자열을 정적으로 훑기 때문에 `bg-${color}-950` 같은 조합은
  // 빌드에서 제거된다. 완성된 클래스 문자열을 그대로 적어 둔다.
  const sourceBadge = {
    local: {
      icon: HardDrive,
      label: "로컬 반주 파일",
      className: "bg-free-soft/50 border-free/40 text-free",
    },
    youtube: {
      icon: Tv,
      label: "유튜브 노래방 영상",
      className: "bg-live-soft/50 border-live/40 text-live",
    },
    synth: {
      icon: Radio,
      label: "내장 자동 반주",
      className: "bg-brass-soft/50 border-brass/40 text-brass",
    },
  }[media?.source ?? "synth"];
  const SourceIcon = sourceBadge.icon;

  return (
    <div className="space-y-6">
      {/*
        대기 화면 — 부록G §2-⑥
        노래방을 시작하기 전에는 조작부를 아예 그리지 않는다.
          전원 꺼짐(standby) → 키패드·QR·순위만. 노래방을 여는 버튼이 없다.
          전원 켜짐(ready)   → 인증한 사람에게 환영 인사와 [노래방 시작하기].
      */}
      {!hasEntered && (
        <AttractScreen
          mode={isPowerOn ? "ready" : "standby"}
          keypad={<BoothKeypad notice={authNotice} onVerified={onKeypadVerified} />}
          session={session}
          topToday={topToday}
          topAll={topAll}
          popularSongs={KARAOKE_SONGS.slice(0, 5).map((song) => ({
            id: song.id,
            title: song.title,
            singer: song.singer,
          }))}
          nickname={nickname}
          onNicknameChange={setNickname}
          onEnter={() => void handleEnter()}
          onEnterWithoutMic={() => {
            if (isPowerOn) setHasEntered(true);
          }}
          isEntering={isEntering}
          enterNotice={enterNotice}
          queue={queue}
        />
      )}

      {/* 누가 언제까지 쓰는지 · 종료 10분 전 알림 · 이용 종료 안내 */}
      {hasEntered && <SessionStrip session={session} isPowerOn={isPowerOn} ledBlink={ledBlink} />}

      {hasEntered && enterNotice && (
        <p className="text-[11px] text-ink-3 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-free/70 shrink-0" />
          {enterNotice}
        </p>
      )}

      {hasEntered && (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── 왼쪽: 노래방 화면 ─────────────────────────────── */}
        <div className="lg:col-span-8 bg-surface/90 border border-line rounded-2xl p-6 shadow-2xl flex flex-col space-y-4">
          {/* 헤더 */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="p-2 rounded-xl bg-brass text-on-accent shadow-md shrink-0">
                <Tv className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-bold text-ink flex items-center gap-2 flex-wrap">
                  <span className="truncate">{selectedSong.title}</span>
                  <span className="text-xs font-normal text-ink-3">- {selectedSong.singer}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-brass/20 text-brass border border-brass/30 shrink-0">
                    {selectedSong.tag}
                  </span>
                </h3>
                <p className="text-[11px] text-ink-3">
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
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-canvas border-2 border-brass/40 shadow-2xl">
            {media?.source === "youtube" ? (
              /* 유튜브 노래방 영상 — 가사는 영상이 직접 표시한다 */
              <div className="relative w-full h-full">
                <div ref={ytHostRef} className="w-full h-full" />
                {/* 구간 안내 오버레이 (영상 위, 클릭은 통과시킨다) */}
                {isPlaying && currentCue && (
                  <div className="absolute bottom-0 inset-x-0 pointer-events-none p-3 bg-gradient-to-t from-canvas/95 to-transparent">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="px-2 py-0.5 rounded-full bg-brass/25 text-brass border border-brass/40 font-bold shrink-0">
                        {currentCue.label}
                      </span>
                      {currentCue.hint && (
                        <span className="text-ink-2 truncate">{currentCue.hint}</span>
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
                canStart={isPowerOn}
              />
            ) : (
              /*
                내장 자동 반주 — 유튜브 후보를 모두 못 쓰거나 연결이 안 될 때.
                예전에는 여기에 "노래방 영상 등록하기" 폼과 실패한 영상 ID 목록,
                유튜브로 나가는 링크가 떠 있었다. 관람객이 쓰는 화면에 관리 도구가
                있을 이유가 없고(등록은 관리자 인증이 필요해 어차피 실패한다),
                링크를 누르면 키오스크 화면이 유튜브로 빠져나간다.
                영상 점검·등록은 /admin 의 [노래방 영상 점검]에서 한다.
              */
              <GuideScreen
                song={selectedSong}
                isPlaying={isPlaying}
                elapsed={elapsed}
                cueLabel={currentCue?.label}
                cueHint={currentCue?.hint}
                nextCueLabel={nextCue?.label}
                volume={audioData.volume}
                headline="내장 자동 반주로 재생 중"
                onStart={handlePlay}
                canStart={isPowerOn}
              />
            )}
          </div>

          {/* 진행 바 */}
          <div className="space-y-1">
            <div className="h-1.5 w-full rounded-full bg-raised overflow-hidden">
              <div
                className="h-full rounded-full bg-brass transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-ink-3">
              <span>{formatSeconds(elapsed)}</span>
              <span>{duration > 0 ? formatSeconds(duration) : "--:--"}</span>
            </div>
          </div>

          {/* 재생 근거 안내 — 전시회 관람객에게 보여 줄 문구 */}
          {media && (
            <p className="flex items-center gap-1.5 text-[11px] text-ink-3">
              <ShieldCheck className="w-3.5 h-3.5 text-free/70 shrink-0" />
              {media.reason}
            </p>
          )}
          {playerError && (
            <p className="flex items-center gap-1.5 text-xs text-brass">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {playerError}
            </p>
          )}

          {/* 컨트롤 바 */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => (isPlaying ? handlePause() : void handlePlay())}
                disabled={!media || !hasEntered || !isPowerOn || waitingForPlayer}
                title={
                  !isPowerOn
                    ? "이용 시간이 끝났습니다"
                    : waitingForPlayer
                    ? "영상을 불러오는 중입니다"
                    : undefined
                }
                className="px-4 py-2 rounded-xl bg-raised hover:bg-line-strong/90 disabled:opacity-40 disabled:cursor-not-allowed text-ink-2 border border-line-strong text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                {waitingForPlayer ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : isPlaying ? (
                  <Pause className="w-3.5 h-3.5" />
                ) : (
                  <Play className="w-3.5 h-3.5 fill-current" />
                )}
                {waitingForPlayer ? "영상 불러오는 중" : isPlaying ? "일시정지" : "반주 시작"}
              </button>

              <button
                onClick={finishAndScore}
                disabled={!isPowerOn}
                className="px-4 py-2 rounded-xl bg-brass text-on-accent font-black text-xs flex items-center gap-1.5 shadow-lg transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Trophy className="w-4 h-4" />
                노래 완료 &amp; 점수 채점! 💯
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* MR 볼륨 */}
              <div className="flex items-center gap-2 bg-canvas/80 px-3 py-1.5 rounded-xl border border-line text-xs">
                <SlidersHorizontal className="w-3.5 h-3.5 text-brass" />
                <span className="text-[11px] text-ink-3">반주 볼륨</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={mrVolume}
                  onChange={(e) => setMrVolume(parseFloat(e.target.value))}
                  className="w-16 sm:w-20 h-1.5 bg-raised rounded-lg appearance-none cursor-pointer accent-brass"
                />
                <span className="font-mono text-[10px] text-brass w-7 text-right">
                  {Math.round(mrVolume * 100)}%
                </span>
              </div>

              {/* 마이크 미터 */}
              <div className="flex items-center gap-3 bg-canvas/80 px-3 py-1.5 rounded-xl border border-line text-xs">
                <button
                  onClick={() => void toggleMicrophone()}
                  className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                    isMicActive
                      ? "bg-live-soft text-live border-live/50"
                      : "bg-raised text-ink-3 border-line-strong"
                  }`}
                  title={isMicActive ? "마이크 끄기" : "마이크 켜기"}
                >
                  {isMicActive ? (
                    <Mic className="w-4 h-4 text-live animate-pulse" />
                  ) : (
                    <MicOff className="w-4 h-4" />
                  )}
                </button>

                <button
                  onClick={toggleVirtualMic}
                  className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
                    isVirtualMic
                      ? "bg-free-soft text-free border-free/50"
                      : "bg-raised text-ink-3 border-line-strong"
                  }`}
                  title="마이크가 없을 때 채점을 체험해 보는 모드 — 이 점수는 순위·애창곡 기록에 남지 않습니다"
                >
                  {isVirtualMic ? "가상보컬 ON · 순위 제외" : "가상보컬"}
                </button>

                <div className="flex items-center gap-1.5">
                  <Volume2 className="w-3.5 h-3.5 text-ink-3" />
                  <div className="w-20 sm:w-24 h-2.5 rounded-full bg-raised overflow-hidden p-0.5 flex items-center">
                    <div
                      className={`h-full rounded-full transition-all duration-75 ${
                        audioData.volume > 70
                          ? "bg-live"
                          : audioData.volume > 40
                          ? "bg-brass"
                          : "bg-free"
                      }`}
                      style={{ width: `${Math.max(4, audioData.volume)}%` }}
                    />
                  </div>
                </div>

                {/* 음정 정확도 게이지 — 가운데에 가까울수록 정확 */}
                <div className="hidden sm:flex items-center gap-1.5" title="음정 정확도">
                  <span className="font-mono text-[10px] text-ink-3">{audioData.note}</span>
                  <div className="relative w-14 h-2.5 rounded-full bg-raised overflow-hidden">
                    <div className="absolute left-1/2 top-0 w-px h-full bg-line-strong" />
                    {audioData.pitch > 0 && (
                      <div
                        className={`absolute top-0.5 w-1.5 h-1.5 rounded-full transition-all duration-75 ${
                          Math.abs(audioData.cents) < 15 ? "bg-free" : "bg-brass"
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
        <div className="lg:col-span-4 bg-surface/90 border border-line rounded-2xl p-5 shadow-xl flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h3 className="text-sm font-bold text-ink flex items-center gap-2">
              <Music className="w-4 h-4 text-brass" />
              학생 애창곡 TOP 10
            </h3>
            <span className="text-[11px] text-ink-3">2026.09 기준</span>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 text-ink-3 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="곡명 또는 가수 검색..."
              className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-canvas border border-line text-xs text-ink placeholder-ink-3 focus:outline-none focus:border-brass"
            />
          </div>

          <div className="space-y-2 overflow-y-auto pr-1 flex-1 max-h-[520px]">
            {filteredSongs.map((song) => {
              const isCurrent = selectedSong.id === song.id;
              return (
                <button
                  key={song.id}
                  onClick={() => handleSelectSong(song)}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isCurrent
                      ? "bg-brass-soft/60 border-brass text-ink shadow-md"
                      : "bg-canvas/50 border-line/80 hover:bg-raised/50 text-ink-2"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-5 text-center text-[11px] font-black shrink-0 ${
                        isCurrent ? "text-brass" : "text-ink-3"
                      }`}
                    >
                      {KARAOKE_SONGS.indexOf(song) + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold truncate">{song.title}</span>
                        <span className="text-[9px] px-1.5 py-px rounded bg-raised text-brass shrink-0">
                          {song.tag}
                        </span>
                      </div>
                      <p className="text-[11px] text-ink-3 truncate mt-0.5">
                        {song.singer} · {song.genre}
                      </p>
                    </div>
                  </div>
                  {isCurrent && (
                    <p className="text-[10px] text-brass/80 mt-1.5 pl-7 leading-relaxed">
                      {song.pickReason}
                    </p>
                  )}
                </button>
              );
            })}
          </div>

          <div className="pt-3 border-t border-line/80 text-[11px] text-ink-3 leading-relaxed">
            <p className="flex items-start gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-free/70 shrink-0 mt-0.5" />
              <span>
                노래방 영상은 <strong className="text-ink-3">내려받지 않고</strong> 유튜브 공식
                플레이어로 재생합니다.
              </span>
            </p>
          </div>
        </div>
      </div>
      )}

      {/* ── 점수 결과 모달 ─────────────────────────────────── */}
      {showScoreModal && (
        <div className="fixed inset-0 bg-canvas/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md bg-surface border-2 border-brass/60 rounded-3xl p-6 shadow-2xl text-center relative overflow-hidden space-y-5">
            <div className="absolute inset-0 pointer-events-none opacity-40">
              <div className="absolute w-2 h-2 rounded-full bg-brass top-6 left-12 animate-ping" />
              <div className="absolute w-3 h-3 rounded-full bg-live top-16 right-10 animate-bounce" />
              <div className="absolute w-2.5 h-2.5 rounded-full bg-free bottom-10 left-16 animate-pulse" />
              <div className="absolute w-2 h-2 rounded-full bg-free bottom-16 right-12 animate-ping" />
            </div>

            <div className="relative">
              <span className="text-[11px] uppercase tracking-wider px-3 py-1 rounded-full bg-brass/20 text-brass font-bold border border-brass/30">
                KARAOKE SCORE
              </span>
              <h3 className="text-xl font-black text-ink mt-2">{selectedSong.title}</h3>
              <p className="text-xs text-ink-3">{selectedSong.singer}</p>
            </div>

            <div className="relative py-2">
              <div className="w-36 h-36 mx-auto rounded-full bg-brass/15 border-4 border-brass/80 flex flex-col items-center justify-center shadow-xl">
                <span className="text-[10px] font-bold text-brass">FINAL SCORE</span>
                <div className="text-5xl font-black text-brass tracking-tighter my-0.5">
                  {animatedScore}
                  <span className="text-2xl font-bold text-brass">점</span>
                </div>
                <div className="px-2.5 py-0.5 rounded-full bg-brass text-on-accent font-black text-xs">
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
                    className="bg-surface/70 border border-line rounded-xl p-2"
                  >
                    <p className="text-[10px] text-ink-3">{item.label}</p>
                    <p className="text-sm font-black text-brass">
                      {item.value}
                      <span className="text-[10px] font-normal text-ink-3">/{item.max}</span>
                    </p>
                    <div className="h-1 mt-1 rounded-full bg-raised overflow-hidden">
                      <div
                        className="h-full rounded-full bg-brass"
                        style={{ width: `${(item.value / item.max) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="relative bg-surface/80 border border-line rounded-2xl p-3.5 shadow-inner">
              <p className="text-sm font-bold text-ink flex items-center justify-center gap-1.5">
                <Sparkles className="w-4 h-4 text-brass shrink-0" />
                {isCalculatingScore ? "점수를 채점하고 있습니다..." : finalScore?.comment}
              </p>
              {finalScore?.sangSomething && !isCalculatingScore && recordStatus && (
                <p
                  className={`text-[11px] mt-1 ${
                    recordStatus === "failed" ? "text-live" : "text-ink-3"
                  }`}
                  data-testid="record-status"
                >
                  {recordStatus === "excluded"
                    ? "가상보컬로 부른 점수는 순위와 애창곡 기록에 올리지 않습니다."
                    : recordStatus === "saving"
                    ? "순위에 올리는 중…"
                    : recordStatus === "saved"
                    ? `${nickname.trim() || "익명"} 이름으로 순위와 애창곡 기록에 올렸습니다!`
                    : "기록을 저장하지 못했습니다. (이용 시간이 끝났거나 서버 연결이 끊겼습니다)"}
                </p>
              )}
            </div>

            <div className="relative flex items-center justify-center gap-3">
              <button
                onClick={() => setShowScoreModal(false)}
                className="px-5 py-2.5 rounded-xl bg-raised hover:bg-line-strong/90 text-ink-2 border border-line-strong font-bold text-xs transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                닫기
              </button>
              <button
                onClick={() => {
                  setShowScoreModal(false);
                  void handlePlay();
                }}
                disabled={!isPowerOn}
                className="px-5 py-2.5 rounded-xl bg-brass text-on-accent font-black text-xs shadow-lg transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
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
  canStart = true,
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
  /** 부스 전원이 꺼지면 false — 시작 버튼을 막는다 */
  canStart?: boolean;
}) {
  return (
    <div className="h-full flex flex-col justify-between p-6">
      <div className="flex items-center justify-between text-xs text-brass/80 font-mono border-b border-brass/20 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-free animate-ping" />
          <span className="font-bold text-ink uppercase tracking-wider">KARAOKE LIVE</span>
        </div>
        <span>{headline}</span>
      </div>

      <div className="flex flex-col items-center justify-center text-center my-auto space-y-4 px-4">
        {isPlaying ? (
          <>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brass/20 text-brass text-xs font-bold border border-brass/30">
              🎤 {formatTime(elapsed)}
            </div>
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-black text-transparent bg-clip-text text-brass drop-shadow-[0_0_20px_rgba(234,179,8,0.4)] leading-snug">
              {cueLabel}
            </h2>
            {cueHint && <p className="text-sm text-ink-2">{cueHint}</p>}
            {nextCueLabel && (
              <p className="text-xs text-ink-3">다음 구간: {nextCueLabel}</p>
            )}
          </>
        ) : (
          <div className="space-y-3">
            <div className="w-16 h-16 rounded-full bg-brass/30 border border-brass/50 flex items-center justify-center text-brass shadow-lg mx-auto">
              <Play className="w-8 h-8 fill-current ml-1" />
            </div>
            <h4 className="text-xl font-black text-ink">{song.title}</h4>
            <p className="text-xs text-ink-3">{song.singer}</p>
            <button
              onClick={onStart}
              disabled={!canStart}
              className="px-6 py-2.5 rounded-xl bg-brass text-on-accent font-bold text-xs shadow-lg transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              반주 시작 &amp; 가창하기
            </button>
          </div>
        )}
      </div>

      {/* 그래픽 이퀄라이저 */}
      <div className="flex items-center gap-1.5 h-6 pt-3 border-t border-brass/20">
        {[40, 75, 55, 90, 65, 80, 45, 100, 60, 85, 50, 70].map((h, i) => (
          <div
            key={i}
            className={`w-1.5 rounded-full transition-all duration-150 ${
              isPlaying ? "bg-brass" : "bg-raised"
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
