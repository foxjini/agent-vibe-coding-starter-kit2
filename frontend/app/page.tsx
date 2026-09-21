"use client";

import React from "react";
import Link from "next/link";
import { Settings } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { ReservationSection } from "@/components/booth/ReservationSection";
import { SongHistorySection } from "@/components/booth/SongHistorySection";
import { MiniGameSection } from "@/components/booth/MiniGameSection";
import { useBoothData } from "@/hooks/useBoothData";

/**
 * `/` — 학생·관람객 화면 (부록G §3-2)
 *
 * 폰으로 보는 화면이다. 여기에는 **부스를 움직이는 조작이 하나도 없다** —
 * 도어락·전원·강제 종료는 전부 `/admin` 으로 옮겼다. 예약하고, 받은 PIN을
 * 부스 앞 키패드에 입력하는 것이 관람객의 전체 흐름이다.
 *
 * 탭을 쓰지 않고 세로로 이어 둔 이유: 폰에서는 탭을 눌러 화면을 바꾸는 것보다
 * 한 번에 쭉 내려보는 쪽이 빠르고, 지금 담긴 것이 세 덩어리뿐이다.
 */
export default function HomePage() {
  const {
    devices,
    reservations,
    allSongs,
    favoriteSongs,
    isConnected,
    fetchReservations,
    fetchSongs,
  } = useBoothData();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <AppHeader
        title="학교 노래방 부스 예약"
        subtitle="인천전자마이스터고 정보통신과 2학년 팀 프로젝트"
        devices={devices}
        isConnected={isConnected}
      />

      <main className="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-8">
        {/* 예약 신청 — 관람객이 가장 먼저 할 일이라 맨 위에 둔다 */}
        <ReservationSection
          reservations={reservations}
          onReservationCreated={fetchReservations}
          /* onSelectPinForSimulator 를 넘기지 않는다 — 여기에는 시뮬레이터가 없다 */
        />

        {/* 내 노래 기록 */}
        <SongHistorySection
          allSongs={allSongs}
          favoriteSongs={favoriteSongs}
          onSongRecorded={fetchSongs}
          /* onOpenKaraoke 도 넘기지 않는다 — 노래방 화면은 부스 모니터에만 띄운다 */
        />

        {/* 대기 중에 할 수 있는 미니게임 */}
        <MiniGameSection />
      </main>

      <footer className="max-w-7xl mx-auto px-4 lg:px-8 py-8 mt-12 border-t border-slate-900 text-center text-xs text-slate-600 space-y-2">
        <p>웹 예약 연동 자동화 학교 노래방 부스 관리 시스템</p>
        <p>백승환(H/W조장) · 조민규(H/W기구) · 김민제(BE/FE) · 박민성(BE/FE)</p>
        <Link
          href="/admin"
          className="inline-flex items-center gap-1.5 mt-2 text-slate-700 hover:text-slate-400 transition-colors"
        >
          <Settings className="w-3 h-3" />
          관리자
        </Link>
      </footer>
    </div>
  );
}
