"use client";

import React from "react";
import Link from "next/link";
import { Settings, Hourglass } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { BoothStatusCard } from "@/components/booth/BoothStatusCard";
import { ReservationSection } from "@/components/booth/ReservationSection";
import { SongHistorySection } from "@/components/booth/SongHistorySection";
import { MiniGameSection } from "@/components/booth/MiniGameSection";
import { useBoothData } from "@/hooks/useBoothData";

/**
 * `/` — 학생·관람객 화면 (부록G §3-2)
 *
 * 폰으로 보는 화면이다. 부스를 움직이는 조작은 하나도 없다 — 도어락·전원·강제
 * 종료는 전부 `/admin` 에 있다.
 *
 * ── 화면 순서를 정한 기준 ─────────────────────────────────────────────
 * 관람객이 이 화면에서 하는 일은 셋뿐이고, 순서가 정해져 있다.
 *   1. 지금 쓸 수 있는지 본다      → 부스 상태
 *   2. (예약했다면) 내 비밀번호를 꺼낸다 → 예약권 카드
 *   3. 아직이면 예약한다            → 신청 폼
 * 그 뒤에 오는 것(애창곡·퀴즈)은 기다리는 동안 볼 것이라 한 단 접어 둔다.
 *
 * 예약 현황 '목록'은 여기 두지 않는다. 남의 예약 내역은 관람객에게 필요 없고,
 * 이름이 그대로 노출된다. 목록은 `/admin` 에만 둔다 (부록G §3-3).
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
    <div className="theme-day min-h-screen bg-canvas text-ink">
      <AppHeader
        title="학교 노래방 부스"
        subtitle="예약하고 비밀번호로 입장하세요"
        devices={devices}
        isConnected={isConnected}
      />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-5 space-y-5">
        {/* 1. 지금 쓸 수 있나 */}
        <BoothStatusCard
          devices={devices}
          reservations={reservations}
          isConnected={isConnected}
        />

        {/* 2·3. 내 예약권과 신청 폼 (예약권은 발급받았을 때만 뜬다) */}
        <ReservationSection
          reservations={reservations}
          onReservationCreated={fetchReservations}
          sections="form"
        />

        {/* 4. 기다리는 동안 */}
        <section className="pt-2 space-y-4">
          <h2 className="flex items-center gap-2 text-sm font-bold text-ink-2 px-1">
            <Hourglass className="w-4 h-4 text-ink-3" aria-hidden />
            기다리는 동안
          </h2>

          <SongHistorySection
            allSongs={allSongs}
            favoriteSongs={favoriteSongs}
            onSongRecorded={fetchSongs}
            /* onOpenKaraoke 를 넘기지 않는다 — 노래방 화면은 부스 모니터에만 띄운다 */
          />

          <MiniGameSection />
        </section>
      </main>

      <footer className="max-w-3xl mx-auto px-4 sm:px-6 py-8 mt-8 border-t border-line text-center text-xs text-ink-3 space-y-2">
        <p>웹 예약 연동 자동화 학교 노래방 부스 관리 시스템</p>
        <p>백승환(H/W조장) · 조민규(H/W기구) · 김민제(BE/FE) · 박민성(BE/FE)</p>
        <Link
          href="/admin"
          className="inline-flex items-center gap-1.5 mt-1 text-ink-3 hover:text-ink transition-colors"
        >
          <Settings className="w-3 h-3" aria-hidden />
          관리자
        </Link>
      </footer>
    </div>
  );
}
