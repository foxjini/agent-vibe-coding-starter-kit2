"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Mic2,
  Sliders,
  Calendar,
  Music,
  Gamepad2,
  Clock,
} from "lucide-react";

import { ConnectionBadge } from "@/components/dashboard/ConnectionBadge";
import { VirtualBoothSimulator } from "@/components/booth/VirtualBoothSimulator";
import { ReservationSection } from "@/components/booth/ReservationSection";
import { KaraokeRoomSection } from "@/components/booth/KaraokeRoomSection";
import { apiUrl } from "@/utils/apiConfig";
import { SongHistorySection } from "@/components/booth/SongHistorySection";
import { MiniGameSection } from "@/components/booth/MiniGameSection";
import { useKaraokeSocket } from "@/hooks/useKaraokeSocket";
import { Device, Reservation, Song, WebSocketMessage } from "@/types";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<"simulator" | "reservation" | "karaoke" | "songs" | "minigame">("simulator");
  const [devices, setDevices] = useState<Device[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [allSongs, setAllSongs] = useState<Song[]>([]);
  const [favoriteSongs, setFavoriteSongs] = useState<Song[]>([]);
  const [lastEventMsg, setLastEventMsg] = useState<string>("부스 시스템이 정상 대기 중입니다.");
  const [currentTimeStr, setCurrentTimeStr] = useState<string>("");

  // Update Clock every second (Client-side)
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTimeStr(now.toLocaleTimeString("ko-KR", { hour12: false }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch Initial Data from Backend
  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/devices"));
      if (res.ok) {
        const json = await res.json();
        setDevices(json.data || []);
      }
    } catch {
      // Backend not yet reachable
    }
  }, []);

  const fetchReservations = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/reservations"));
      if (res.ok) {
        const json = await res.json();
        setReservations(json.data || []);
      }
    } catch {
      // Backend not yet reachable
    }
  }, []);

  const fetchSongs = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/songs"));
      if (res.ok) {
        const json = await res.json();
        setAllSongs(json.data?.all || []);
        setFavoriteSongs(json.data?.favorites || []);
      }
    } catch {
      // Backend not yet reachable
    }
  }, []);

  useEffect(() => {
    fetchDevices();
    fetchReservations();
    fetchSongs();
  }, [fetchDevices, fetchReservations, fetchSongs]);

  // WebSocket Message Handler
  const handleWsMessage = useCallback((msg: WebSocketMessage) => {
    if (msg.type === "device_state" && msg.device_id) {
      setDevices((prev) =>
        prev.map((d) =>
          d.id === msg.device_id
            ? { ...d, current_state: msg.state ?? d.current_state, current_value: msg.value ?? d.current_value }
            : d
        )
      );
    } else if (msg.type === "booth_auth") {
      setLastEventMsg(msg.message || (msg.success ? "인증 성공!" : "인증 실패!"));
      fetchDevices();
    } else if (msg.type === "booth_event") {
      setLastEventMsg(msg.message || "부스 이벤트 감지됨");
      fetchDevices();
    } else if (msg.type === "reservation_created") {
      fetchReservations();
    } else if (msg.type === "song_recorded") {
      fetchSongs();
    }
  }, [fetchDevices, fetchReservations, fetchSongs]);

  const { isConnected } = useKaraokeSocket(handleWsMessage);

  // Device Manual Control Handler
  const handleDeviceControl = async (deviceId: string, state: string, value?: unknown) => {

    try {
      await fetch(apiUrl(`/api/devices/${deviceId}/control`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ desired_state: state, value }),
      });
      fetchDevices();
    } catch (e) {
      console.error(e);
    }
  };

  // Keypad PIN Verification Handler
  const handleVerifyPin = async (pin: string) => {
    try {
      const res = await fetch(apiUrl("/api/booth/verify-keypad"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      fetchDevices();
      return {
        success: res.ok,
        mode: data.data?.mode,
        message: data.data?.message || data.error?.message,
      };
    } catch {
      return { success: false, message: "서버 연결에 실패했습니다." };
    }
  };

  // Quick Trigger Handlers
  const handleSimulateEntry = async () => {
    try {
      await fetch(apiUrl("/api/booth/simulate-entry"), { method: "POST" });
      fetchDevices();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSimulateWarning = async () => {
    try {
      await fetch(apiUrl("/api/booth/simulate-10min-warning"), { method: "POST" });
      fetchDevices();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSimulateEnd = async () => {
    try {
      await fetch(apiUrl("/api/booth/simulate-end"), { method: "POST" });
      fetchDevices();
    } catch (e) {
      console.error(e);
    }
  };

  // Pre-fill PIN from Reservation and switch to Simulator tab
  const handleSelectPinForSimulator = (pin: string) => {
    setActiveTab("simulator");
    // Trigger prompt
    handleVerifyPin(pin);
  };

  // Active status indicators
  const relayDevice = devices.find((d) => d.id === "relay_1");
  const doorLockDevice = devices.find((d) => d.id === "door_lock_1");
  const isPowerOn = relayDevice?.current_state === "on";
  const isUnlocked = doorLockDevice?.current_state === "unlocked" || doorLockDevice?.current_state === "open";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Top Global Navigation Bar */}
      <header className="sticky top-0 z-50 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-4 lg:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-600/30">
              <Mic2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-extrabold tracking-tight text-white flex items-center gap-2">
                스마트 학교 노래방 부스 관리 시스템
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-500/40">
                  v1.0 Mockup
                </span>
              </h1>
              <p className="text-[11px] text-slate-400">
                인천전자마이스터고 정보통신과 2학년 팀 프로젝트 (PRD v2 연동)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Real-time Status Badges */}
            <div className="hidden md:flex items-center gap-2 text-xs font-mono">
              <span
                className={`px-2.5 py-1 rounded-full border ${
                  isPowerOn
                    ? "bg-emerald-950 text-emerald-300 border-emerald-500/40"
                    : "bg-slate-800 text-slate-400 border-slate-700"
                }`}
              >
                전원: {isPowerOn ? "ON" : "OFF"}
              </span>
              <span
                className={`px-2.5 py-1 rounded-full border ${
                  isUnlocked
                    ? "bg-cyan-950 text-cyan-300 border-cyan-500/40"
                    : "bg-slate-800 text-slate-400 border-slate-700"
                }`}
              >
                도어락: {isUnlocked ? "열림" : "잠김"}
              </span>
            </div>

            {/* SSR-safe Connection Badge */}
            <ConnectionBadge connected={isConnected} />

            {/* Local Clock */}
            <div
              suppressHydrationWarning
              className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800/80 border border-slate-700 font-mono text-xs text-slate-300"
            >
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{currentTimeStr || "--:--:--"}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-slate-800/80">
          <button
            onClick={() => setActiveTab("simulator")}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === "simulator"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:bg-slate-800"
            }`}
          >
            <Sliders className="w-4 h-4" />
            가상 부스 관제 & 키패드 시뮬레이터
          </button>

          <button
            onClick={() => setActiveTab("reservation")}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === "reservation"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:bg-slate-800"
            }`}
          >
            <Calendar className="w-4 h-4" />
            노래방 예약 신청 & PIN 발급
          </button>

          <button
            onClick={() => setActiveTab("karaoke")}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === "karaoke"
                ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-600/30"
                : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:bg-slate-800"
            }`}
          >
            <Mic2 className="w-4 h-4 text-purple-400" />
            실시간 노래방 반주 & 채점 🎤
          </button>

          <button
            onClick={() => setActiveTab("songs")}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === "songs"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:bg-slate-800"
            }`}
          >
            <Music className="w-4 h-4" />
            나의 18번 & 노래 기록
          </button>

          <button
            onClick={() => setActiveTab("minigame")}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === "minigame"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800 hover:bg-slate-800"
            }`}
          >
            <Gamepad2 className="w-4 h-4" />
            노래 퀴즈 미니게임
          </button>
        </div>

        {/* Tab Content Display */}
        {activeTab === "simulator" && (
          <VirtualBoothSimulator
            devices={devices}
            onDeviceControl={handleDeviceControl}
            onVerifyPin={handleVerifyPin}
            onSimulateEntry={handleSimulateEntry}
            onSimulateWarning={handleSimulateWarning}
            onSimulateEnd={handleSimulateEnd}
            lastEventMessage={lastEventMsg}
            onOpenKaraoke={() => setActiveTab("karaoke")}
          />
        )}

        {activeTab === "reservation" && (
          <ReservationSection
            reservations={reservations}
            onReservationCreated={fetchReservations}
            onSelectPinForSimulator={handleSelectPinForSimulator}
          />
        )}

        {activeTab === "karaoke" && (
          <KaraokeRoomSection devices={devices} onSongCompleted={fetchSongs} />
        )}

        {activeTab === "songs" && (
          <SongHistorySection
            allSongs={allSongs}
            favoriteSongs={favoriteSongs}
            onSongRecorded={fetchSongs}
            onOpenKaraoke={() => setActiveTab("karaoke")}
          />
        )}

        {activeTab === "minigame" && <MiniGameSection />}
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-4 lg:px-8 py-8 mt-12 border-t border-slate-900 text-center text-xs text-slate-600 space-y-1">
        <p>웹 예약 연동 자동화 학교 노래방 부스 관리 시스템 · 1차 완성 Mockup</p>
        <p>학생A(H/W조장) · 학생B(H/W기구) · 학생C(BE/FE) · 학생D(BE/FE)</p>
      </footer>
    </div>
  );
}
