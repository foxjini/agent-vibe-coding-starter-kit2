"use client";

import React, { useCallback, useSyncExternalStore } from "react";
import Link from "next/link";
import { Monitor, Home } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { AdminGate } from "@/components/booth/AdminGate";
import { VirtualBoothSimulator } from "@/components/booth/VirtualBoothSimulator";
import { ReservationSection } from "@/components/booth/ReservationSection";
import { SongHistorySection } from "@/components/booth/SongHistorySection";
import { VideoCheckPanel } from "@/components/booth/VideoCheckPanel";
import { OpsSummary } from "@/components/admin/OpsSummary";
import { SchedulerPanel } from "@/components/admin/SchedulerPanel";
import { QueuePanel } from "@/components/admin/QueuePanel";
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
 *
 * 이 화면은 선생님 노트북에서 본다. 그래서 여기에는
 *   - 비밀번호 키패드가 없다 — 비밀번호는 부스 앞에서 누른다 (/booth 화면 키패드)
 *   - 소리가 나지 않는다 — 안내 음성과 퇴실곡은 부스 화면이 낸다
 * 학생 대신 인증해야 할 때는 예약 목록의 [대신 입력]을 쓴다.
 */
export default function AdminPage() {
  const {
    devices,
    reservations,
    allSongs,
    favoriteSongs,
    lastEventMsg,
    isConnected,
    fetchDevices,
    fetchReservations,
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

  /**
   * [대신 입력] — 학생 대신 부스 키패드에 PIN 을 넣는다.
   * 키패드와 같은 경로라 관리자 토큰을 붙이지 않고, 예약 시간 검사도 그대로 받는다.
   */
  const handleRemoteEntry = useCallback(
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
            {/*
              1. 지금 무슨 일이 벌어지고 있나 — 선생님이 이 화면을 여는 이유다.
                 예전에는 이 정보가 아래 시뮬레이터 카드 안의 작은 글자로 흩어져
                 있어서, 상황 파악에 스크롤이 필요했다.
            */}
            <OpsSummary
              devices={devices}
              reservations={reservations}
              isConnected={isConnected}
            />

            {/*
              2. 자동 운영 엔진 — 사람이 버튼을 누르지 않아도 도는 부분이다.
                 '지금 무슨 일이 예정돼 있나'가 개입 도구보다 먼저 와야 한다.
            */}
            <SchedulerPanel />

            <QueuePanel />

            {/* 3. 개입 — 기기 제어와 시나리오 강제 실행 */}
            <VirtualBoothSimulator
              devices={devices}
              onDeviceControl={handleDeviceControl}
              onSimulateEntry={() => runScenario("/api/booth/simulate-entry")}
              onSimulateWarning={() => runScenario("/api/booth/simulate-10min-warning")}
              onSimulateEnd={() => runScenario("/api/booth/simulate-end")}
              lastEventMessage={lastEventMsg}
              isAdmin={adminAuthed}
            />

            {/*
              4. 예약 관리 — 여기서는 '현황 목록'이 일이다. 신청 폼은 관람객
                 화면(`/`)의 몫이라 띄우지 않는다 (부록G §3-3).
            */}
            <ReservationSection
              reservations={reservations}
              onReservationCreated={fetchReservations}
              /* 학생이 비밀번호를 잃어버렸을 때·시연할 때 선생님이 대신 인증한다 */
              onRemoteEntry={handleRemoteEntry}
              sections="list"
            />

            {/*
              5. 준비 작업 — 노래방 영상 점검. 부스 화면(`/booth`)에 있던 것을
                 옮겨 왔다. 전시 중 관람객이 보는 화면에 설정 도구가 있을 이유가
                 없고, 영상 등록은 관리자 인증이 필요한 작업이다.
            */}
            <VideoCheckPanel />

            {/* 6. 기록 — 전체 노래 통계 (부스에서 부르고 채점한 곡이 쌓인다) */}
            <SongHistorySection allSongs={allSongs} favoriteSongs={favoriteSongs} />
          </>
        )}
      </main>

      <footer className="max-w-7xl mx-auto px-4 lg:px-8 py-8 mt-12 border-t border-line text-center text-xs text-ink-3 space-y-1">
        <p>관리자 운영 화면 · 전시 전에 backend/.env 의 ADMIN_PIN 을 바꾸고 ALLOW_TEST_PIN 을 false 로 두세요</p>
      </footer>
    </div>
  );
}
