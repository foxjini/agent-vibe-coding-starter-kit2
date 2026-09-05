"use client";

import React, { useState, useEffect, useRef } from "react";
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
  ChevronRight,
  ChevronLeft,
  FolderPlus,
  SlidersHorizontal,
} from "lucide-react";
import { KaraokeAudioScorer, AudioAnalysisResult } from "@/utils/audioScorer";
import { KaraokeAccompanimentEngine } from "@/utils/karaokeAccompaniment";
import { Song, Device } from "@/types";

export interface PresetKaraokeSong {
  title: string;
  singer: string;
  youtubeId: string;
  genre: string;
  tag?: string;
  audioTrack?: string;
  lyrics: string[];
}

// 학생 인기곡 및 노래방 자막 가사 매핑
const POPULAR_KARAOKE_PRESETS: PresetKaraokeSong[] = [
  {
    title: "고민중독",
    singer: "QWER",
    youtubeId: "gT-8fB-D57Y",
    genre: "K-POP 밴드",
    tag: "인기 1위 🔥",
    lyrics: [
      "어쩌다 마주친 네 눈빛에 푹 빠져버린 나",
      "하루 종일 네 생각에 가슴이 두근두근 떨려와",
      "어떤 말을 전해야 내 솔직한 맘을 알까",
      "자꾸만 고민이 많아져 밤새 뒤척이네",
      "고민중독에 걸려버린 내 맘을 너는 아니?",
      "이제는 용기 내어 네게 다가갈 거야!",
    ],
  },
  {
    title: "한 페이지가 될 수 있게",
    singer: "DAY6",
    youtubeId: "0hWf5X22k9U",
    genre: "락/밴드",
    tag: "떼창 명곡 ✨",
    lyrics: [
      "솔직히 말할게 많이 기다려 왔어",
      "너도 그랬을 거라 믿고 싶어",
      "오늘이 오기까지 많은 밤을 지새웠어",
      "아름다운 청춘의 한 장 함께 써내려 가자",
      "너와의 모든 순간이 한 페이지가 될 수 있게!",
      "지금 이 순간을 영원히 기억하자!",
    ],
  },
  {
    title: "Hype Boy",
    singer: "NewJeans",
    youtubeId: "Rrf8uQFvICE",
    genre: "댄스",
    tag: "청량 보컬 💧",
    lyrics: [
      "1, 2, 3, 4! Baby, got me looking so crazy",
      "빠져버리는 daydream, 마음은 이미 너에게로",
      "Tell me what's the next move",
      "'Cause I know what you like boy",
      "You're my one and only hype boy!",
      "너와 눈이 마주친 그 순간 멈출 수 없어!",
    ],
  },
  {
    title: "I AM",
    singer: "IVE",
    youtubeId: "6ZUIwj3FgUY",
    genre: "댄스",
    tag: "고음 챌린지 🚀",
    lyrics: [
      "내가 가는 길은 내가 스스로 만들어 가",
      "어느 누구도 날 대신할 수는 없어",
      "That's my life is 아름다운 갤럭시",
      "Be a writer, 내 인생의 유일한 주인공",
      "어제보다 찬란한 내일이 날 기다려!",
      "세상 속에서 가장 빛나는 나를 봐!",
    ],
  },
  {
    title: "신호등",
    singer: "이무진",
    youtubeId: "sk6rU_phwio",
    genre: "포크/어쿠스틱",
    tag: "국민 애창곡 🚦",
    lyrics: [
      "붉은색 푸른색 그 사이 3초 그 짧은 시간",
      "노란색 빛을 내는 저기 저 신호등이",
      "내 머릿속을 텅 비워버려 혼란스럽게 해",
      "내가 건너야 할 곳은 과연 어디인가요",
      "괴물 같던 세상이 이젠 조금 익숙해져!",
      "내 작은 꿈을 향해 다시 걸어갈 거야!",
    ],
  },
  {
    title: "사건의 지평선",
    singer: "윤하",
    youtubeId: "BBdC1rl5sKY",
    genre: "발라드/락",
    tag: "레전드 🌌",
    lyrics: [
      "생각이 많은 밤 하늘을 올려다보면",
      "아득히 먼 우주 끝 어딘가로 흘러가",
      "사건의 지평선 너머로 사라진 추억들",
      "아낌없이 반짝였던 우리 지난 날들",
      "이제는 미련 없이 너를 보내줄게",
      "새로운 시작을 향해 높이 날아올라!",
    ],
  },
  {
    title: "Supernova",
    singer: "aespa",
    youtubeId: "phbcNZH4V48",
    genre: "댄스",
    tag: "트렌드 ⚡",
    lyrics: [
      "사건은 다가와 거세게 커져가",
      "질문은 계속돼 Where do we go?",
      "우주를 가르는 강력한 Supernova!",
      "내 안의 에너지가 폭발하듯 터져 나와",
      "새로운 차원의 문을 활짝 열어젖혀!",
    ],
  },
  {
    title: "다시 만나",
    singer: "더윈드",
    youtubeId: "bO2v5c4XQYw",
    genre: "K-POP",
    tag: "공식 퇴실곡 🎵",
    audioTrack: "/audio/closing_song.wav",
    lyrics: [
      "지나온 시간들이 마치 선물 같아서",
      "함께 웃고 노래했던 우리의 모든 순간들",
      "안녕이란 말 대신 밝은 미소로 인사해",
      "언젠가 다시 만날 그날을 기다릴게",
      "더 멋진 모습으로 꼭 다시 만나 우리!",
      "안녕, 우리들의 소중한 학교 노래방!",
    ],
  },
];

interface KaraokeRoomSectionProps {
  devices: Device[];
  allSongs?: Song[];
  onSongCompleted?: () => void;
}

export function KaraokeRoomSection({
  devices,
  onSongCompleted,
}: KaraokeRoomSectionProps) {
  // 부스 반주기 전원 (relay_1) 확인
  const relayDevice = devices.find((d) => d.id === "relay_1");
  const isPowerOn = relayDevice?.current_state === "on";

  // 화면 모드: 자체 가사 자막 모드 vs 유튜브 영상 모드
  const [screenMode, setScreenMode] = useState<"lyrics" | "youtube">("lyrics");

  // 현재 선곡된 노래 & 재생 상태
  const [selectedSong, setSelectedSong] = useState<PresetKaraokeSong>(POPULAR_KARAOKE_PRESETS[0]);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentLyricIndex, setCurrentLyricIndex] = useState<number>(0);
  const [playbackSeconds, setPlaybackSeconds] = useState<number>(0);

  // 검색 및 직접 유튜브 입력
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [customUrlInput, setCustomUrlInput] = useState<string>("");

  // 마이크 및 실시간 오디오 분석
  const [isMicActive, setIsMicActive] = useState<boolean>(false);
  const [isVirtualMic, setIsVirtualMic] = useState<boolean>(false);
  const [audioData, setAudioData] = useState<AudioAnalysisResult>({ volume: 0, pitch: 0, note: "-" });
  const scorerRef = useRef<KaraokeAudioScorer | null>(null);
  const virtualTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 실시간 K-POP MR 반주 엔진 및 MP3 플레이어
  const accompanimentRef = useRef<KaraokeAccompanimentEngine | null>(null);
  const bgAudioRef = useRef<HTMLAudioElement | null>(null);
  const [mrVolume, setMrVolume] = useState<number>(0.7);
  const [customAudioUrl, setCustomAudioUrl] = useState<string | null>(null);
  const [customAudioName, setCustomAudioName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 채점 결과 모달 상태
  const [showScoreModal, setShowScoreModal] = useState<boolean>(false);
  const [isCalculatingScore, setIsCalculatingScore] = useState<boolean>(false);
  const [finalScore, setFinalScore] = useState<{ score: number; comment: string; rank: string } | null>(null);
  const [animatedScore, setAnimatedScore] = useState<number>(0);

  // 오디오 스코어러 및 반주 엔진 초기화
  useEffect(() => {
    scorerRef.current = new KaraokeAudioScorer();
    accompanimentRef.current = new KaraokeAccompanimentEngine();
    return () => {
      if (scorerRef.current) {
        scorerRef.current.stopMicrophone();
      }
      if (accompanimentRef.current) {
        accompanimentRef.current.stop();
      }
      if (virtualTimerRef.current) {
        clearInterval(virtualTimerRef.current);
      }
      if (bgAudioRef.current) {
        bgAudioRef.current.pause();
      }
    };
  }, []);

  // MR 볼륨 변경 시 실시간 반영
  const handleVolumeChange = (newVol: number) => {
    setMrVolume(newVol);
    if (accompanimentRef.current) {
      accompanimentRef.current.setVolume(newVol);
    }
    if (bgAudioRef.current) {
      bgAudioRef.current.volume = newVol;
    }
  };

  // 사용자 MP3 반주 파일 불러오기
  const handleCustomAudioUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setCustomAudioUrl(url);
      setCustomAudioName(file.name);
      alert(`'${file.name}' 반주 음원이 등록되었습니다!\n[반주 시작]을 누르면 이 음악이 재생됩니다.`);
    }
  };

  // 노래 재생 타이머 & 가사 자동 롤링 (5초마다 다음 가사 라인)
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isPlaying) {
      interval = setInterval(() => {
        setPlaybackSeconds((prev) => {
          const nextSec = prev + 1;
          const lyricIdx = Math.floor(nextSec / 5) % selectedSong.lyrics.length;
          setCurrentLyricIndex(lyricIdx);
          return nextSec;
        });
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying, selectedSong.lyrics.length]);

  // 마이크 토글
  const toggleMicrophone = async () => {
    if (isMicActive) {
      if (scorerRef.current) {
        scorerRef.current.stopMicrophone();
      }
      setIsMicActive(false);
      setAudioData({ volume: 0, pitch: 0, note: "-" });
    } else {
      if (isVirtualMic) {
        stopVirtualMic();
      }
      if (scorerRef.current) {
        const success = await scorerRef.current.startMicrophone((data) => {
          setAudioData(data);
        });
        if (success) {
          setIsMicActive(true);
        } else {
          alert("마이크 권한을 허용하지 않았거나 연결된 마이크가 없습니다. 대신 '가상보컬' 모드로 채점할 수 있습니다.");
        }
      }
    }
  };

  // 가상 마이크 시뮬레이터
  const toggleVirtualMic = () => {
    if (isVirtualMic) {
      stopVirtualMic();
    } else {
      if (isMicActive && scorerRef.current) {
        scorerRef.current.stopMicrophone();
        setIsMicActive(false);
      }
      setIsVirtualMic(true);
      const notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"];
      virtualTimerRef.current = setInterval(() => {
        const randomVol = Math.floor(45 + Math.random() * 50);
        const randomPitch = Math.floor(220 + Math.random() * 400);
        const randomNote = notes[Math.floor(Math.random() * notes.length)];
        setAudioData({ volume: randomVol, pitch: randomPitch, note: randomNote });
      }, 150);
    }
  };

  const stopVirtualMic = () => {
    setIsVirtualMic(false);
    if (virtualTimerRef.current) {
      clearInterval(virtualTimerRef.current);
      virtualTimerRef.current = null;
    }
    setAudioData({ volume: 0, pitch: 0, note: "-" });
  };

  // 노래 시작
  const handleStartSinging = (song: PresetKaraokeSong) => {
    setSelectedSong(song);
    setCurrentLyricIndex(0);
    setPlaybackSeconds(0);
    setIsPlaying(true);
    setShowScoreModal(false);

    // 1. 반주 음원 재생 (사용자 등록 MP3 또는 내장 퇴실곡 파일)
    if (customAudioUrl || song.audioTrack) {
      if (bgAudioRef.current) {
        bgAudioRef.current.pause();
      }
      const audio = new Audio(customAudioUrl || song.audioTrack);
      audio.volume = mrVolume;
      audio.loop = true;
      audio.play().catch(() => {});
      bgAudioRef.current = audio;
    } else {
      // 2. 실시간 Web Audio K-POP MR 반주 엔진 가동!
      if (accompanimentRef.current) {
        accompanimentRef.current.setVolume(mrVolume);
        accompanimentRef.current.start(song.title);
      }
    }

    // 3. 마이크 자동 권한 요청
    if (!isMicActive && !isVirtualMic) {
      toggleMicrophone().catch(() => {});
    }
  };

  const handleStopSinging = () => {
    setIsPlaying(false);
    if (accompanimentRef.current) {
      accompanimentRef.current.stop();
    }
    if (bgAudioRef.current) {
      bgAudioRef.current.pause();
    }
  };

  // 노래 완료 & 점수 채점
  const handleFinishAndScore = async () => {
    handleStopSinging();
    setIsCalculatingScore(true);
    setShowScoreModal(true);

    // 1. 드럼롤 효과음
    KaraokeAudioScorer.playDrumrollSound();

    // 2. 점수 계산
    const result = scorerRef.current
      ? scorerRef.current.calculateFinalScore()
      : { score: 96, comment: "환상적인 무대 매너와 열창이었습니다!", rank: "SSS" };

    setFinalScore(result);

    // 3. 점수 카운트업
    let current = 0;
    const target = result.score;
    const step = Math.ceil(target / 25);
    const interval = setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(interval);
        setIsCalculatingScore(false);

        // 4. 팡파레 사운드
        KaraokeAudioScorer.playFanfareSound();

        // 5. TTS 축하 멘트
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          try {
            window.speechSynthesis.cancel();
            const text = `${result.score}점입니다! ${result.comment}`;
            const utt = new SpeechSynthesisUtterance(text);
            utt.lang = "ko-KR";
            utt.rate = 1.05;
            window.speechSynthesis.speak(utt);
          } catch {
            // ignore
          }
        }

        // 6. DB 애창곡 등록
        recordSongToDB(selectedSong.title, selectedSong.singer);
      }
      setAnimatedScore(current);
    }, 40);
  };

  const recordSongToDB = async (title: string, singer: string) => {
    try {
      await fetch("http://localhost:8000/api/songs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, singer }),
      });
      if (onSongCompleted) {
        onSongCompleted();
      }
    } catch {
      // ignore
    }
  };

  // 유튜브 새 탭 열기 (임베드 차단 문제 완벽 우회)
  const handleOpenYoutubeDirectly = () => {
    const url = `https://www.youtube.com/watch?v=${selectedSong.youtubeId}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  // 사용자 직접 입력
  const handleApplyCustomUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customUrlInput.trim()) return;

    let vid = customUrlInput.trim();
    if (vid.includes("youtube.com/watch?v=")) {
      const match = vid.match(/v=([^&]+)/);
      if (match) vid = match[1];
    } else if (vid.includes("youtu.be/")) {
      const parts = vid.split("youtu.be/");
      if (parts[1]) vid = parts[1].split("?")[0];
    }

    const newSong: PresetKaraokeSong = {
      title: "선택한 신청곡",
      singer: "사용자 선곡",
      youtubeId: vid,
      genre: "커스텀",
      tag: "신청곡 🎯",
      lyrics: [
        "내가 신청한 노래방 곡이 재생되고 있습니다",
        "음악과 리듬에 맞춰 즐겁게 노래해 보세요!",
        "마이크에 대고 멋진 가창력을 뽐내보세요!",
        "노래를 마치면 [점수 채점]을 눌러 결과를 확인하세요!",
      ],
    };
    handleStartSinging(newSong);
    setCustomUrlInput("");
  };

  const filteredPresets = POPULAR_KARAOKE_PRESETS.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.singer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  return (
    <div className="space-y-6">
      {/* Power Off Guard Warning */}
      {!isPowerOn && (
        <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-200 text-sm flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-3">
            <PowerOff className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="font-bold">현재 부스 반주기 전원(릴레이)이 차단되어 있습니다.</p>
              <p className="text-xs text-amber-300/80 mt-0.5">
                원활한 노래방 이용을 위해 첫 번째 탭의 키패드에 비밀번호를 입력하거나, 부스 반주기 전원을 켜주세요.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-900/60 text-amber-300 border border-amber-700">
            Relay Power: OFF
          </span>
        </div>
      )}

      {/* Main Karaoke Stage Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Karaoke Screen & Player (8 Cols) */}
        <div className="lg:col-span-8 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col justify-between space-y-4">
          {/* Screen Header & Mode Toggle */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-md">
                <Tv className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>{selectedSong.title}</span>
                  <span className="text-xs font-normal text-slate-400">- {selectedSong.singer}</span>
                  {selectedSong.tag && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                      {selectedSong.tag}
                    </span>
                  )}
                </h3>
                <p className="text-[11px] text-slate-400">
                  {isPlaying ? `가창 진행 중 (${formatSeconds(playbackSeconds)})` : "대기 중 · 선곡 후 반주를 시작하세요"}
                </p>
              </div>
            </div>

            {/* Screen Mode Switch: Lyrics Screen vs YouTube */}
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-950 border border-slate-800">
              <button
                onClick={() => setScreenMode("lyrics")}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  screenMode === "lyrics"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Music className="w-3.5 h-3.5" />
                가사 자막 화면 (추천)
              </button>
              <button
                onClick={() => setScreenMode("youtube")}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  screenMode === "youtube"
                    ? "bg-purple-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Tv className="w-3.5 h-3.5" />
                유튜브 영상
              </button>
            </div>
          </div>

          {/* Screen Display Frame */}
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-slate-950 border-2 border-indigo-500/40 shadow-2xl flex flex-col justify-between p-6">
            {screenMode === "lyrics" ? (
              /* Built-in Karaoke Screen with Glowing Subtitle Lyrics & Visualizer */
              <div className="h-full flex flex-col justify-between">
                {/* Screen Top Bar */}
                <div className="flex items-center justify-between text-xs text-indigo-300/80 font-mono border-b border-indigo-500/20 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                    <span className="font-bold text-white uppercase tracking-wider">KARAOKE LIVE ROOM</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span>{selectedSong.genre}</span>
                    <span className="bg-indigo-950 px-2 py-0.5 rounded border border-indigo-500/30">
                      TIME: {formatSeconds(playbackSeconds)}
                    </span>
                  </div>
                </div>

                {/* Center Karaoke Lyrics Presentation */}
                <div className="flex flex-col items-center justify-center text-center my-auto space-y-4 px-4">
                  {isPlaying ? (
                    <>
                      {/* Active Lyric with Neon Glow & Bouncing Marker */}
                      <div className="space-y-2 animate-fade-in">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-400/20 text-amber-300 text-xs font-bold border border-amber-400/30 animate-pulse">
                          <span>🎤 지금 부를 소절</span>
                        </div>
                        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 via-amber-200 to-pink-300 tracking-wide drop-shadow-[0_0_20px_rgba(234,179,8,0.4)] leading-snug">
                          {selectedSong.lyrics[currentLyricIndex] || selectedSong.title}
                        </h2>
                      </div>

                      {/* Next Upcoming Lyric Preview */}
                      <div className="pt-2">
                        <p className="text-xs sm:text-sm text-slate-400 font-medium">
                          다음 소절:{" "}
                          <span className="text-slate-300">
                            {selectedSong.lyrics[(currentLyricIndex + 1) % selectedSong.lyrics.length]}
                          </span>
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="space-y-3">
                      <div className="w-16 h-16 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shadow-lg mx-auto">
                        <Play className="w-8 h-8 fill-current ml-1" />
                      </div>
                      <h4 className="text-xl font-black text-white">{selectedSong.title}</h4>
                      <p className="text-xs text-slate-400">{selectedSong.singer} · 가사 자막 준비 완료</p>
                      <button
                        onClick={() => handleStartSinging(selectedSong)}
                        className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
                      >
                        반주 시작 & 가창하기
                      </button>
                    </div>
                  )}
                </div>

                {/* Bottom Graphic Equalizer Visualizer */}
                <div className="flex items-center justify-between pt-3 border-t border-indigo-500/20">
                  <div className="flex items-center gap-1.5 h-6">
                    {[40, 75, 55, 90, 65, 80, 45, 100, 60, 85, 50, 70].map((h, i) => (
                      <div
                        key={i}
                        className={`w-1.5 rounded-full transition-all duration-150 ${
                          isPlaying ? "bg-gradient-to-t from-indigo-500 to-pink-400" : "bg-slate-800"
                        }`}
                        style={{
                          height: isPlaying ? `${Math.max(20, (h * (audioData.volume + 30)) / 100)}%` : "20%",
                        }}
                      />
                    ))}
                  </div>

                  {/* Manual Lyric Skip Controls */}
                  {isPlaying && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setCurrentLyricIndex((prev) => Math.max(0, prev - 1))}
                        className="p-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white text-xs cursor-pointer"
                        title="이전 소절"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-[11px] font-mono text-slate-400 px-1.5">
                        {currentLyricIndex + 1} / {selectedSong.lyrics.length}
                      </span>
                      <button
                        onClick={() =>
                          setCurrentLyricIndex((prev) => (prev + 1) % selectedSong.lyrics.length)
                        }
                        className="p-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white text-xs cursor-pointer"
                        title="다음 소절"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* YouTube Mode with Open in New Tab Button */
              <div className="relative w-full h-full flex flex-col justify-between">
                {/* Embed Warning & Direct Link Banner */}
                <div className="absolute top-2 left-2 right-2 z-10 p-2.5 rounded-xl bg-slate-950/90 backdrop-blur border border-purple-500/40 flex items-center justify-between gap-2 text-xs shadow-xl">
                  <div className="flex items-center gap-2 min-w-0">
                    <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
                    <span className="text-slate-300 truncate">
                      유튜브에서 &apos;동영상을 재생할 수 없음&apos;이 뜰 경우, 아래 버튼으로 바로 열어보세요!
                    </span>
                  </div>
                  <button
                    onClick={handleOpenYoutubeDirectly}
                    className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-1.5 shrink-0 transition-colors shadow cursor-pointer"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    유튜브에서 반주 열기
                  </button>
                </div>

                <div className="w-full h-full pt-12">
                  <iframe
                    src={`https://www.youtube.com/embed/${selectedSong.youtubeId}?autoplay=1&enablejsapi=1`}
                    title={`${selectedSong.title} 노래방 영상`}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    className="w-full h-full rounded-xl border-0"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Bottom Karaoke Controller Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => (isPlaying ? handleStopSinging() : handleStartSinging(selectedSong))}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                {isPlaying ? "반주 일시정지" : "반주 시작"}
              </button>

              <button
                onClick={handleFinishAndScore}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 font-black text-xs flex items-center gap-1.5 shadow-lg shadow-amber-500/20 transition-all cursor-pointer"
              >
                <Trophy className="w-4 h-4" />
                노래 완료 & 점수 채점! 💯
              </button>

              {/* Custom MP3 File Load Button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                title="소장하고 있는 실제 노래방 MP3/WAV 반주 파일을 불러옵니다"
              >
                <FolderPlus className="w-3.5 h-3.5" />
                {customAudioName ? (
                  <span className="truncate max-w-[100px]">{customAudioName}</span>
                ) : (
                  "내 MP3 반주 넣기"
                )}
              </button>
              <input
                type="file"
                ref={fileInputRef}
                accept="audio/*"
                className="hidden"
                onChange={handleCustomAudioUpload}
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Accompaniment (MR) Volume Slider */}
              <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
                <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-[11px] text-slate-400">MR 볼륨</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={mrVolume}
                  onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                  className="w-16 sm:w-20 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <span className="font-mono text-[10px] text-indigo-300 w-7 text-right">
                  {Math.round(mrVolume * 100)}%
                </span>
              </div>

              {/* Vocal Microphone Meters */}
              <div className="flex items-center gap-3 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
                <button
                  onClick={toggleMicrophone}
                  className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                    isMicActive
                      ? "bg-rose-950 text-rose-300 border-rose-500/50"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}
                  title={isMicActive ? "실제 마이크 끄기" : "실제 마이크 켜기"}
                >
                  {isMicActive ? <Mic className="w-4 h-4 text-rose-400 animate-pulse" /> : <MicOff className="w-4 h-4" />}
                </button>

                <button
                  onClick={toggleVirtualMic}
                  className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
                    isVirtualMic
                      ? "bg-cyan-950 text-cyan-300 border-cyan-500/50"
                      : "bg-slate-800 text-slate-400 border-slate-700"
                  }`}
                  title="마이크가 없을 때 가상 보컬 데이터 시뮬레이션"
                >
                  {isVirtualMic ? "가상보컬 ON" : "가상보컬"}
                </button>

                {/* Volume VU Meter Bar */}
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
                  <span className="font-mono text-[10px] w-6 text-right text-slate-400">
                    {audioData.volume}%
                  </span>
                </div>

                {/* Pitch Note Badge */}
                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
                  음정: {audioData.note} ({audioData.pitch}Hz)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Song Selection List & Search (4 Cols) */}
        <div className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Music className="w-4 h-4 text-amber-400" />
                노래방 인기곡 선곡
              </h3>
              <span className="text-[11px] text-slate-400">TJ/금영 MR 연동</span>
            </div>

            {/* Search Input */}
            <div className="relative mb-3">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="곡명 또는 가수 검색..."
                className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Song Preset List */}
            <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
              {filteredPresets.map((preset) => {
                const isCurrent = selectedSong.title === preset.title;
                return (
                  <div
                    key={preset.title}
                    onClick={() => handleStartSinging(preset)}
                    className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                      isCurrent
                        ? "bg-indigo-950/60 border-indigo-500 text-white shadow-md shadow-indigo-950/40"
                        : "bg-slate-950/50 border-slate-800/80 hover:bg-slate-800/50 text-slate-300"
                    }`}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold truncate">{preset.title}</span>
                        {preset.tag && (
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-amber-300 shrink-0">
                            {preset.tag}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">
                        {preset.singer} · {preset.genre}
                      </p>
                    </div>

                    <button
                      className={`px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 shrink-0 ${
                        isCurrent
                          ? "bg-indigo-500 text-white"
                          : "bg-slate-800 hover:bg-slate-700 text-slate-300"
                      }`}
                    >
                      <Play className="w-2.5 h-2.5 fill-current" />
                      선곡
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Direct Custom YouTube Input */}
          <form onSubmit={handleApplyCustomUrl} className="pt-2 border-t border-slate-800/80 space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" />
              유튜브 링크/ID 직접 입력 (자유 선곡)
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={customUrlInput}
                onChange={(e) => setCustomUrlInput(e.target.value)}
                placeholder="유튜브 링크 또는 영상 ID"
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors shrink-0 cursor-pointer"
              >
                선곡
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Score Celebration Modal */}
      {showScoreModal && (
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="w-full max-w-md bg-gradient-to-b from-slate-900 to-indigo-950 border-2 border-amber-500/60 rounded-3xl p-6 shadow-2xl text-center relative overflow-hidden space-y-6">
            {/* Background Confetti Sparks Animation */}
            <div className="absolute inset-0 pointer-events-none opacity-40">
              <div className="absolute w-2 h-2 rounded-full bg-amber-400 top-6 left-12 animate-ping" />
              <div className="absolute w-3 h-3 rounded-full bg-rose-400 top-16 right-10 animate-bounce" />
              <div className="absolute w-2.5 h-2.5 rounded-full bg-cyan-400 bottom-10 left-16 animate-pulse" />
              <div className="absolute w-2 h-2 rounded-full bg-emerald-400 bottom-16 right-12 animate-ping" />
            </div>

            {/* Modal Header */}
            <div>
              <span className="text-[11px] uppercase tracking-wider px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">
                KARAOKE SCORE RESULT
              </span>
              <h3 className="text-xl font-black text-white mt-2">
                {selectedSong.title}
              </h3>
              <p className="text-xs text-slate-400">{selectedSong.singer}</p>
            </div>

            {/* Digital Scoreboard Display */}
            <div className="relative py-4">
              <div className="w-40 h-40 mx-auto rounded-full bg-gradient-to-br from-amber-500/20 via-purple-500/20 to-indigo-500/20 border-4 border-amber-400/80 flex flex-col items-center justify-center shadow-xl shadow-amber-500/20">
                <span className="text-xs font-bold text-amber-300">FINAL SCORE</span>
                <div className="text-5xl font-black text-amber-400 tracking-tighter my-1">
                  {animatedScore}
                  <span className="text-2xl font-bold text-amber-200">점</span>
                </div>
                <div className="px-2.5 py-0.5 rounded-full bg-amber-400 text-slate-950 font-black text-xs">
                  등급: {finalScore?.rank || "A"}
                </div>
              </div>
            </div>

            {/* Evaluation Comment */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-inner">
              <p className="text-sm font-bold text-slate-100 flex items-center justify-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-400" />
                {isCalculatingScore ? "점수를 정밀 채점하고 있습니다..." : finalScore?.comment}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                학교 노래방 애창곡 DB에 해당 가창 기록이 자동으로 반영되었습니다!
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-center gap-3 pt-2">
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
                  handleStartSinging(selectedSong);
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
