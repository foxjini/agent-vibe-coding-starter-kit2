"use client";

import React, { useState, useEffect, useRef } from "react";

import {
  Lock,
  Unlock,
  Power,
  Lightbulb,
  Volume2,
  VolumeX,
  UserCheck,
  ShieldCheck,
  AlertTriangle,
  PlayCircle,
  Sparkles,
  Delete,
  CheckCircle2,
  XCircle,
  Music,
  Play,
  Pause,
  Mic,
} from "lucide-react";
import { Device } from "@/types";

interface VirtualBoothSimulatorProps {
  devices: Device[];
  onDeviceControl: (deviceId: string, state: string, value?: unknown) => Promise<void>;
  onVerifyPin: (pin: string) => Promise<{ success: boolean; mode?: string; message?: string }>;
  onSimulateEntry: () => Promise<void>;
  onSimulateWarning: () => Promise<void>;
  onSimulateEnd: () => Promise<void>;
  lastEventMessage?: string;
  onOpenKaraoke?: () => void;
  /** 관리자 인증 여부 — false면 기기 제어·시나리오 강제 실행을 막는다 (부록G §3-4) */
  isAdmin?: boolean;
}


export function VirtualBoothSimulator({
  devices,
  onDeviceControl,
  onVerifyPin,
  onSimulateEntry,
  onSimulateWarning,
  onSimulateEnd,
  lastEventMessage,
  onOpenKaraoke,
  isAdmin = false,
}: VirtualBoothSimulatorProps) {
  // Keypad State
  const [pinInput, setPinInput] = useState<string>("");
  const [displayMessage, setDisplayMessage] = useState<string>("비밀번호 4자리를 입력하세요");
  const [displayStatus, setDisplayStatus] = useState<"idle" | "success" | "admin" | "error">("idle");
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  // Device Map for Quick Lookup
  const devMap = devices.reduce<Record<string, Device>>((acc, d) => {
    acc[d.id] = d;
    return acc;
  }, {});

  const doorLock = devMap["door_lock_1"] || { current_state: "locked" };
  const relay = devMap["relay_1"] || { current_state: "off" };
  const led = devMap["led_1"] || { current_state: "off" };
  const speaker = devMap["speaker_1"] || { current_state: "idle" };
  const pir = devMap["pir_1"] || { current_state: "standby" };

  const isDoorUnlocked = doorLock.current_state === "unlocked" || doorLock.current_state === "open";
  const isPowerOn = relay.current_state === "on";
  const isLedOn = led.current_state === "on";
  const isLedBlink = led.current_state === "blink";
  const isSpeakerPlaying = speaker.current_state === "playing";
  const isPersonDetected = pir.current_state === "detected";

  // Voice Audio (TTS) & Mute State
  const [isVoiceEnabled, setIsVoiceEnabled] = useState<boolean>(true);

  // Real Audio Player for Closing Song ('더윈드 - 다시 만나' 0:58~)
  const closingAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlayingClosingAudio, setIsPlayingClosingAudio] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const audio = new Audio("/audio/closing_song.wav");
      audio.volume = 0.85;
      audio.onplay = () => setIsPlayingClosingAudio(true);
      audio.onpause = () => setIsPlayingClosingAudio(false);
      audio.onended = () => setIsPlayingClosingAudio(false);
      closingAudioRef.current = audio;
    }
    return () => {
      if (closingAudioRef.current) {
        closingAudioRef.current.pause();
        closingAudioRef.current = null;
      }
    };
  }, []);

  const playClosingSong = () => {
    if (!closingAudioRef.current) {
      playEndingChime();
      return;
    }
    closingAudioRef.current.currentTime = 0;
    closingAudioRef.current.volume = 0.85;
    closingAudioRef.current.play().catch((err) => {
      console.warn("Closing song play error (browser policy):", err);
      playEndingChime();
    });
  };

  const pauseClosingSong = () => {
    if (closingAudioRef.current) {
      closingAudioRef.current.pause();
    }
  };

  const toggleClosingSong = () => {
    if (isPlayingClosingAudio) {
      pauseClosingSong();
    } else {
      playClosingSong();
    }
  };

  // Web Speech API (TTS) 한국어 음성 출력
  const speakVoice = (text: string) => {
    if (!isVoiceEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ko-KR";
      utterance.rate = 1.0;
      utterance.pitch = 1.05;
      window.speechSynthesis.speak(utterance);
    } catch {
      // ignore
    }
  };

  // Web Audio 멜로디 / 효과음 합성기
  const playMelody = (notes: number[], noteDuration: number = 0.12) => {
    if (!isVoiceEnabled || typeof window === "undefined") return;
    try {
      const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtxClass();

      notes.forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        const startTime = audioCtx.currentTime + idx * noteDuration;
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, startTime);
        gain.gain.setValueAtTime(0.12, startTime);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + noteDuration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(startTime);
        osc.stop(startTime + noteDuration);
      });
    } catch {
      // Audio not permitted yet
    }
  };

  // '더윈드 - 다시 만나' 하이라이트 풍 멜로디 챠임 (솔-도-레-미-솔-도)
  const playEndingChime = () => {
    playMelody([392, 523, 587, 659, 784, 1046], 0.18);
  };

  // Play Keypad Beep
  const playBeep = (freq: number = 800, duration: number = 0.08) => {
    try {
      const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtxClass();

      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch {
      // Audio not permitted yet
    }
  };

  const handleKeypadPress = (key: string) => {
    playBeep(900, 0.06);
    if (pinInput.length < 4) {
      const nextPin = pinInput + key;
      setPinInput(nextPin);
      setDisplayMessage(`PIN: ${"*".repeat(nextPin.length)}`);
      setDisplayStatus("idle");
    }
  };

  const handleClear = () => {
    playBeep(400, 0.1);
    setPinInput("");
    setDisplayMessage("비밀번호 4자리를 입력하세요");
    setDisplayStatus("idle");
  };

  const handleEnter = async () => {
    if (pinInput.length !== 4) {
      playBeep(300, 0.2);
      setDisplayMessage("4자리를 모두 입력하세요!");
      setDisplayStatus("error");
      speakVoice("비밀번호 4자리를 모두 입력해 주세요.");
      return;
    }

    setIsVerifying(true);
    playBeep(1200, 0.1);
    const res = await onVerifyPin(pinInput);
    setIsVerifying(false);

    if (res.success) {
      if (res.mode === "admin") {
        playMelody([440, 554, 659], 0.15);
        setDisplayMessage("관리자 인증 성공");
        setDisplayStatus("admin");
        speakVoice("관리자 모드로 인증되었습니다. 도어락을 해제합니다.");
      } else {
        playMelody([523, 659, 784, 1046], 0.14);
        setDisplayMessage("학생 인증 성공! 환영합니다");
        setDisplayStatus("success");
        speakVoice("인증에 성공하였습니다. 환영합니다! 노래방 전원이 켜졌습니다.");
      }
      setTimeout(() => {
        setPinInput("");
      }, 2500);
    } else {
      playBeep(250, 0.3);
      setDisplayMessage(res.message || "비밀번호 불일치!");
      setDisplayStatus("error");
      speakVoice("등록되지 않은 비밀번호입니다. 다시 확인해 주세요.");
      setTimeout(() => {
        setPinInput("");
        setDisplayMessage("비밀번호 4자리를 입력하세요");
        setDisplayStatus("idle");
      }, 2000);
    }
  };

  // Wrappers with Actual Voice Output
  const handleTriggerEntryWithVoice = async () => {
    playMelody([523, 659, 784], 0.12);
    speakVoice("부스에 입장하셨습니다. 즐거운 시간 되세요!");
    await onSimulateEntry();
  };

  const handleTriggerWarningWithVoice = async () => {
    playMelody([784, 659, 784, 659], 0.15);
    speakVoice("이용 종료 10분 전입니다. 다음 이용자를 위해 정리를 준비해 주세요.");
    await onSimulateWarning();
  };

  const handleTriggerEndWithVoice = async () => {
    // 1. 실제 퇴실곡 음원 재생 (더윈드 - 다시 만나 0:58~)
    playClosingSong();
    // 2. 한국어 음성 안내 (TTS)
    speakVoice("이용 시간이 종료되었습니다. 퇴실 음악 '더윈드 - 다시 만나'를 재생하며 부스 전원을 차단합니다. 안녕히 가세요!");
    // 3. 백엔드 시뮬레이션 상태 갱신
    await onSimulateEnd();
  };


  // Speak incoming lastEventMessage if updated
  useEffect(() => {
    if (lastEventMessage && isVoiceEnabled) {
      speakVoice(lastEventMessage);
    }
  }, [lastEventMessage]);

  return (
    <div className="space-y-6">
      {/* Top Notification Banner */}
      {lastEventMessage && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-200 text-sm animate-fade-in shadow-inner">
          <Sparkles className="w-5 h-5 text-indigo-400 shrink-0" />
          <span className="font-medium">{lastEventMessage}</span>
        </div>
      )}

      {/* Main Grid: Left is 3D-styled Booth State, Right is Keypad Controller */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Virtual Booth Physical State (7 Cols) */}
        <div className="lg:col-span-7 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                가상 노래방 부스 실시간 물리 상태
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                라즈베리파이 5 액추에이터 4종 & 센서 2종의 가동 상태를 시뮬레이션합니다.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
                className={`text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer flex items-center gap-1.5 ${
                  isVoiceEnabled
                    ? "bg-indigo-950 text-indigo-300 border-indigo-500/50"
                    : "bg-slate-800 text-slate-500 border-slate-700"
                }`}
                title="음성 안내 (TTS) 켜기/끄기"
              >
                {isVoiceEnabled ? <Volume2 className="w-3.5 h-3.5 text-indigo-400" /> : <VolumeX className="w-3.5 h-3.5 text-slate-500" />}
                음성(TTS) {isVoiceEnabled ? "ON" : "OFF"}
              </button>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Mockup 100% 모드
              </span>
            </div>
          </div>


          {/* Booth Visual Room Simulator */}
          <div
            className={`relative w-full h-64 rounded-xl border-2 transition-all duration-500 flex flex-col justify-between p-6 overflow-hidden ${
              isPowerOn
                ? "bg-slate-950 border-emerald-500/50 shadow-emerald-950/30 shadow-2xl"
                : "bg-slate-950/60 border-slate-800"
            }`}
          >
            {/* Ceiling LED Light Visual */}
            <div className="flex justify-center">
              <div
                className={`px-8 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2 transition-all duration-300 ${
                  isLedBlink
                    ? "bg-amber-400 text-slate-950 animate-bounce shadow-lg shadow-amber-400/50"
                    : isLedOn
                    ? "bg-yellow-300 text-slate-950 shadow-md shadow-yellow-300/40"
                    : "bg-slate-800 text-slate-500"
                }`}
              >
                <Lightbulb className={`w-4 h-4 ${isLedBlink ? "animate-spin" : ""}`} />
                <span>
                  부스 조명 LED:{" "}
                  {isLedBlink ? "10분 전 깜빡임 (BLINK)" : isLedOn ? "점등 (ON)" : "소등 (OFF)"}
                </span>
              </div>
            </div>

            {/* Middle Section: Screen & Person Presence */}
            <div className="flex items-center justify-between px-4">
              {/* Karaoke Machine Screen & Amp Power */}
              <div
                className={`w-40 h-28 rounded-lg border flex flex-col items-center justify-center p-3 text-center transition-all duration-500 ${
                  isPowerOn
                    ? "bg-gradient-to-br from-indigo-900/60 to-purple-900/60 border-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                    : "bg-slate-900 border-slate-800 text-slate-600"
                }`}
              >
                <Power className={`w-6 h-6 mb-1 ${isPowerOn ? "text-emerald-400 animate-pulse" : "text-slate-600"}`} />
                <span className="text-xs font-bold">노래방 반주기 & 앰프</span>
                <span className="text-[10px] text-slate-400 mt-0.5">
                  릴레이 전원: {isPowerOn ? "ON (공급 중)" : "OFF (차단됨)"}
                </span>
                {isPowerOn && onOpenKaraoke && (
                  <button
                    onClick={onOpenKaraoke}
                    className="mt-1 px-2 py-0.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold shadow transition-all cursor-pointer flex items-center gap-1"
                  >
                    <Mic className="w-2.5 h-2.5" />
                    노래방 시작
                  </button>
                )}
              </div>

              {/* Center Door Lock Visual */}
              <div
                className={`flex flex-col items-center justify-center w-36 h-28 rounded-lg border transition-all duration-300 ${
                  isDoorUnlocked
                    ? "bg-emerald-950/40 border-emerald-500/60 text-emerald-300"
                    : "bg-rose-950/40 border-rose-500/60 text-rose-300"
                }`}
              >
                {isDoorUnlocked ? (
                  <Unlock className="w-8 h-8 text-emerald-400 mb-1 animate-bounce" />
                ) : (
                  <Lock className="w-8 h-8 text-rose-400 mb-1" />
                )}
                <span className="text-xs font-bold">솔레노이드 도어락</span>
                <span className="text-[10px] mt-0.5 font-mono">
                  {isDoorUnlocked ? "UNLOCKED (개방)" : "LOCKED (잠김)"}
                </span>
              </div>

              {/* Audio Speaker Box */}
              <div
                className={`w-36 h-28 rounded-lg border flex flex-col items-center justify-center p-2 text-center transition-all duration-300 ${
                  isSpeakerPlaying || isPlayingClosingAudio
                    ? "bg-amber-950/40 border-amber-500/60 text-amber-300 animate-pulse"
                    : "bg-slate-900 border-slate-800 text-slate-600"
                }`}
              >
                {isSpeakerPlaying || isPlayingClosingAudio ? (
                  <Volume2 className="w-7 h-7 text-amber-400 mb-1 animate-bounce" />
                ) : (
                  <VolumeX className="w-7 h-7 text-slate-600 mb-1" />
                )}
                <span className="text-xs font-bold">안내 스피커</span>
                <span className="text-[10px] text-slate-400 truncate max-w-[120px]">
                  {isPlayingClosingAudio
                    ? "더윈드 - 다시 만나 🎵"
                    : isSpeakerPlaying
                    ? (speaker.desired_value && typeof speaker.desired_value === "object" && "track" in speaker.desired_value
                        ? String((speaker.desired_value as Record<string, unknown>).track)
                        : "음성 안내 중")
                    : "대기 중 (IDLE)"}
                </span>
              </div>
            </div>

            {/* Bottom: Presence Sensor & Foot Floor */}
            <div className="flex items-center justify-between border-t border-slate-800/80 pt-2 text-xs">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isPersonDetected ? "bg-cyan-400 animate-ping" : "bg-slate-600"
                  }`}
                />
                <span className="text-slate-400">
                  입장 감지 센서 (PIR):{" "}
                  <strong className={isPersonDetected ? "text-cyan-400" : "text-slate-500"}>
                    {isPersonDetected ? "사람 입장 감지됨" : "대기 중"}
                  </strong>
                </span>
              </div>
              <button
                onClick={handleTriggerEntryWithVoice}
                disabled={!isAdmin}
                className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                입장 감지 테스트
              </button>
            </div>
          </div>

          {/* Quick Scenario Test Buttons */}
          <div className="space-y-2 pt-2">
            <h4 className="text-xs font-semibold text-slate-400">PRD 자동화 시나리오 원클릭 시뮬레이션</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                onClick={handleTriggerWarningWithVoice}
                disabled={!isAdmin}
                className="px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-amber-300 flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                종료 10분 전 (LED 깜빡임)
              </button>
              <button
                onClick={handleTriggerEndWithVoice}
                disabled={!isAdmin}
                className="px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-rose-300 flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                <PlayCircle className="w-4 h-4 text-rose-400" />
                이용 종료 (퇴실곡+전원차단)
              </button>
            </div>
          </div>

          {/* Closing Song Player Banner */}
          <div className="p-3.5 rounded-xl bg-slate-950/80 border border-amber-500/30 flex items-center justify-between gap-3 shadow-inner">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${isPlayingClosingAudio ? "bg-amber-500/20 text-amber-400 animate-pulse" : "bg-slate-800 text-slate-400"}`}>
                <Music className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-200 truncate">더윈드(The Wind) - 다시 만나</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                    퇴실곡 (0:58~)
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 truncate">
                  {isPlayingClosingAudio ? "🎵 실제 음원 재생 중... (부스 전원 차단과 함께 울림)" : "이용 종료 시 자동 재생되는 공식 퇴실곡 음원"}
                </p>
              </div>
            </div>
            <button
              onClick={toggleClosingSong}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shrink-0 transition-all cursor-pointer ${
                isPlayingClosingAudio
                  ? "bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20"
                  : "bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-500/30"
              }`}
            >
              {isPlayingClosingAudio ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  정지
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  음원 테스트
                </>
              )}
            </button>
          </div>

          {/* Manual Device Toggle Controls */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            <button
              onClick={() => onDeviceControl("door_lock_1", isDoorUnlocked ? "locked" : "unlocked")}
              disabled={!isAdmin}
              className={`p-3 rounded-xl border text-xs font-medium flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                isDoorUnlocked
                  ? "bg-emerald-950/30 border-emerald-500/50 text-emerald-300"
                  : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              {isDoorUnlocked ? <Unlock className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
              도어락 {isDoorUnlocked ? "수동 잠금" : "수동 해제"}
            </button>

            <button
              onClick={() => onDeviceControl("relay_1", isPowerOn ? "off" : "on")}
              disabled={!isAdmin}
              className={`p-3 rounded-xl border text-xs font-medium flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                isPowerOn
                  ? "bg-indigo-950/30 border-indigo-500/50 text-indigo-300"
                  : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              <Power className="w-4 h-4" />
              릴레이 전원 {isPowerOn ? "끄기" : "켜기"}
            </button>

            <button
              onClick={() => onDeviceControl("led_1", isLedOn ? "off" : "on")}
              disabled={!isAdmin}
              className={`p-3 rounded-xl border text-xs font-medium flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                isLedOn
                  ? "bg-yellow-950/30 border-yellow-500/50 text-yellow-300"
                  : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              <Lightbulb className="w-4 h-4" />
              조명 {isLedOn ? "끄기" : "켜기"}
            </button>

            <button
              onClick={() => onDeviceControl("speaker_1", isSpeakerPlaying ? "idle" : "playing", { message: "테스트 음성" })}
              disabled={!isAdmin}
              className={`p-3 rounded-xl border text-xs font-medium flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                isSpeakerPlaying
                  ? "bg-amber-950/30 border-amber-500/50 text-amber-300"
                  : "bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              <Volume2 className="w-4 h-4" />
              스피커 {isSpeakerPlaying ? "정지" : "테스트"}
            </button>
          </div>
        </div>

        {/* Right: Interactive 4x4 Physical Keypad (5 Cols) */}
        <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400"></span>
                부스 4x4 도어 키패드
              </h3>
              <span className="text-[11px] text-slate-400">F-02 인증 모듈</span>
            </div>

            {/* LCD Matrix Screen */}
            <div
              className={`w-full p-4 rounded-xl border font-mono text-center mb-6 transition-all duration-300 shadow-inner ${
                displayStatus === "success"
                  ? "bg-emerald-950/80 border-emerald-500 text-emerald-300"
                  : displayStatus === "admin"
                  ? "bg-indigo-950/80 border-indigo-500 text-indigo-300"
                  : displayStatus === "error"
                  ? "bg-rose-950/80 border-rose-500 text-rose-300 animate-shake"
                  : "bg-slate-950 border-slate-700 text-slate-200"
              }`}
            >
              <div className="text-[11px] text-slate-400 uppercase tracking-widest mb-1 flex items-center justify-center gap-1.5">
                {displayStatus === "success" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                {displayStatus === "admin" && <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />}
                {displayStatus === "error" && <XCircle className="w-3.5 h-3.5 text-rose-400" />}
                {displayStatus === "idle" && "SMART BOOTH SECURITY SYSTEM"}
              </div>
              <div className="text-xl font-bold tracking-wider py-1">{displayMessage}</div>
              <div className="text-xs text-slate-500 mt-1">
                {displayStatus === "idle" && "예약자 4자리 PIN 또는 관리자 PIN"}
              </div>
            </div>

            {/* 4x4 Keypad Button Matrix */}
            <div className="grid grid-cols-3 gap-3 max-w-[280px] mx-auto">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((num) => (
                <button
                  key={num}
                  onClick={() => handleKeypadPress(num)}
                  disabled={isVerifying}
                  className="h-14 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700/80 text-xl font-semibold text-white shadow-md active:scale-95 transition-all cursor-pointer flex items-center justify-center disabled:opacity-50"
                >
                  {num}
                </button>
              ))}
              <button
                onClick={handleClear}
                disabled={isVerifying}
                className="h-14 rounded-xl bg-rose-900/40 hover:bg-rose-900/60 border border-rose-700/60 text-xs font-bold text-rose-300 shadow-md active:scale-95 transition-all cursor-pointer flex items-center justify-center gap-1 disabled:opacity-50"
              >
                <Delete className="w-4 h-4" />
                지움
              </button>
              <button
                onClick={() => handleKeypadPress("0")}
                disabled={isVerifying}
                className="h-14 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-slate-600 border border-slate-700/80 text-xl font-semibold text-white shadow-md active:scale-95 transition-all cursor-pointer flex items-center justify-center disabled:opacity-50"
              >
                0
              </button>
              <button
                onClick={handleEnter}
                disabled={isVerifying}
                className="h-14 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 border border-emerald-500 text-sm font-bold text-white shadow-lg shadow-emerald-900/30 active:scale-95 transition-all cursor-pointer flex items-center justify-center gap-1 disabled:opacity-50"
              >
                {isVerifying ? "확인중..." : "확인"}
              </button>
            </div>
          </div>

          {/* Quick Guide */}
          <div className="mt-6 pt-4 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <p className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <strong>예약자 PIN 입력 시:</strong> 도어락 해제 + 기기 전원 ON + 조명 ON
            </p>
            <p className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              <strong>관리자 PIN 입력 시:</strong> 도어락 해제 + 조명 ON (기기 전원 OFF 유지)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
