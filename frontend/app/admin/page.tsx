"use client";

import React, { useCallback, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Monitor, Home } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { AdminGate } from "@/components/booth/AdminGate";
import { VirtualBoothSimulator } from "@/components/booth/VirtualBoothSimulator";
import { ReservationSection } from "@/components/booth/ReservationSection";
import { SongHistorySection } from "@/components/booth/SongHistorySection";
import { useBoothData } from "@/hooks/useBoothData";
import { apiUrl } from "@/utils/apiConfig";
import {
  adminFetch,
  clearAdminSession,
  subscribeAdminSession,
  getAdminSnapshot,
  getAdminServerSnapshot,
} from "@/utils/adminSession";

/**
 * `/admin` — 선생님 노트북 화면 (부록G §3-2)
 *
 * 부스를 실제로 움직이는 조작은 전부 여기에만 둔다. 도어락 해제, 220V 전원
 * 차단, 이용 강제 종료가 관람객 화면에 있으면 남이 노래하는 중에 전원이 꺼질 수
 * 있기 때문이다.
 *
 * 인증 전에는 제어 화면을 **비활성화하는 게 아니라 아예 그리지 않는다.**
 * disabled 로 막으면 무엇이 있는지는 다 보이고, 버튼만 못 누르는 상태가 된다.
 */
export default function AdminPage() {
  const router = useRouter();
  const {
    devices,
    reservations,
    allSongs,
    favoriteSongs,
    lastEventMsg,
    isConnected,
    fetchDevices,
    fetchReservations,
    fetchSongs,
  } = useBoothData();

  const adminAuthed = useSyncExternalStore(
    subscribeAdminSession,
    getAdminSnapshot,
    getAdminServerSnapshot
  );

  /** 관리자 토큰이 만료됐을 때 공통 처리 — 세션을 비우고 다시 인증하게 한다 */
  const handleExpired = useCallback(() => {
    clearAdminSession();
    alert("관리자 인증이 만료되었습니다. 관리자 PIN으로 다시 인증해 주세요.");
  }, []);

  const handleDeviceControl = useCallback(
    async (deviceId: string, state: string, value?: unknown) => {
      try {
        const res = await adminFetch(`/api/devices/${deviceId}/control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ desired_state: state, value }),
        });
        if (res.status === 401) {
          handleExpired();
          return;
        }
        fetchDevices();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchDevices, handleExpired]
  );

  /** 시나리오 강제 실행 3종은 호출 경로가 같아 하나로 묶는다 */
  const runScenario = useCallback(
    async (path: string) => {
      try {
        const res = await adminFetch(path, { method: "POST" });
        if (res.status === 401) {
          handleExpired();
          return;
        }
        fetchDevices();
      } catch (e) {
        console.error(e);
      }
    },
    [fetchDevices, handleExpired]
  );

  /** 키패드 인증은 관람객도 쓰는 경로라 관리자 토큰을 붙이지 않는다 */
  const handleVerifyPin = useCallback(
    async (pin: string) => {
      try {
        const res = await fetch(apiUrl("/api/booth/verify-keypad"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin }),
        });
        const data = await res.json();
        fetchDevices();
        fetchReservations();
        return {
          success: res.ok,
          mode: data.data?.mode,
          message: data.data?.message || data.error?.message,
        };
      } catch {
        return { success: false, message: "서버 연결에 실패했습니다." };
      }
    },
    [fetchDevices, fetchReservations]
  );

  return (
    <div className="theme-day min-h-screen bg-canvas text-ink">
      <AppHeader
        title="관리자 운영 화면"
        subtitle="기기 제어 · 시나리오 실행 · 예약 관리 (선생님 전용)"
        devices={devices}
        isConnected={isConnected}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/booth"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-raised hover:bg-line-strong/90 border border-line-strong text-xs font-bold text-ink-2 transition-colors"
            >
              <Monitor className="w-3.5 h-3.5" />
              부스 화면
            </Link>
            <Link
              href="/"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-raised hover:bg-line-strong/90 border border-line-strong text-xs font-bold text-ink-2 transition-colors"
            >
              <Home className="w-3.5 h-3.5" />
              예약 화면
            </Link>
          </div>
        }
      />

      <main className="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-6">
        <AdminGate isAuthed={adminAuthed} />

        {/*
          인증 전에는 아래를 통째로 그리지 않는다.
          화면을 나누는 것만으로는 부족하고, 백엔드도 X-Admin-Token 을 요구한다
          (부록G §3-4) — 둘이 세트로 막는다.
        */}
        {adminAuthed && (
          <>
            <VirtualBoothSimulator
              devices={devices}
              onDeviceControl={handleDeviceControl}
              onVerifyPin={handleVerifyPin}
              onSimulateEntry={() => runScenario("/api/booth/simulate-entry")}
              onSimulateWarning={() => runScenario("/api/booth/simulate-10min-warning")}
              onSimulateEnd={() => runScenario("/api/booth/simulate-end")}
              lastEventMessage={lastEventMsg}
              onOpenKaraoke={() => router.push("/booth")}
              isAdmin={adminAuthed}
            />

            <ReservationSection
              reservations={reservations}
              onReservationCreated={fetchReservations}
              /* 관리자 화면에서는 예약 PIN을 눌러 키패드 인증을 바로 시험할 수 있다 */
              onSelectPinForSimulator={handleVerifyPin}
            />

            <SongHistorySection
              allSongs={allSongs}
              favoriteSongs={favoriteSongs}
              onSongRecorded={fetchSongs}
              onOpenKaraoke={() => router.push("/booth")}
            />
          </>
        )}
      </main>

      <footer className="max-w-7xl mx-auto px-4 lg:px-8 py-8 mt-12 border-t border-line text-center text-xs text-ink-3 space-y-1">
        <p>관리자 운영 화면 · 전시 전에 backend/.env 의 ADMIN_PIN 을 바꾸고 ALLOW_TEST_PIN 을 false 로 두세요</p>
      </footer>
    </div>
  );
}
