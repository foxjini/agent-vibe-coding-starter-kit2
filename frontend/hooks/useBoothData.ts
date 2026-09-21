"use client";

import { useState, useEffect, useCallback } from "react";
import { apiUrl } from "@/utils/apiConfig";
import { useKaraokeSocket } from "@/hooks/useKaraokeSocket";
import { Device, Reservation, Song, WebSocketMessage } from "@/types";

/**
 * 부스 공용 데이터 훅 (부록G §3 화면 분리 / 부록J 작업 1)
 *
 * 세 화면(`/`·`/booth`·`/admin`)이 똑같이 필요로 하는 것을 한곳에 모았다.
 *   - 기기 상태 / 예약 목록 / 노래 기록을 백엔드에서 가져온다
 *   - WebSocket으로 실시간 변경을 받아 위 목록을 갱신한다
 *
 * 예전에는 이 코드가 app/page.tsx 안에 화면과 뒤섞여 있었다. 그대로 두고
 * 라우트를 셋으로 나누면 같은 로직이 세 벌로 복제되고, 한 곳만 고치는 실수가
 * 반드시 생긴다. 그래서 라우트를 나누기 **전에** 먼저 뽑아냈다.
 *
 * 백엔드가 꺼져 있어도 화면은 떠야 하므로, 모든 조회는 실패 시 조용히 넘어가고
 * 빈 목록을 유지한다.
 */
export function useBoothData() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [allSongs, setAllSongs] = useState<Song[]>([]);
  const [favoriteSongs, setFavoriteSongs] = useState<Song[]>([]);
  const [lastEventMsg, setLastEventMsg] = useState<string>("부스 시스템이 정상 대기 중입니다.");

  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/devices"));
      if (res.ok) {
        const json = await res.json();
        setDevices(json.data || []);
      }
    } catch {
      // 백엔드가 아직 안 떴을 수 있다 — 화면은 그대로 둔다
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
      // 위와 같다
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
      // 위와 같다
    }
  }, []);

  useEffect(() => {
    fetchDevices();
    fetchReservations();
    fetchSongs();
  }, [fetchDevices, fetchReservations, fetchSongs]);

  const handleWsMessage = useCallback(
    (msg: WebSocketMessage) => {
      if (msg.type === "device_state" && msg.device_id) {
        setDevices((prev) =>
          prev.map((d) =>
            d.id === msg.device_id
              ? {
                  ...d,
                  current_state: msg.state ?? d.current_state,
                  current_value: msg.value ?? d.current_value,
                }
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
    },
    [fetchDevices, fetchReservations, fetchSongs]
  );

  const { isConnected } = useKaraokeSocket(handleWsMessage);

  return {
    devices,
    reservations,
    allSongs,
    favoriteSongs,
    lastEventMsg,
    isConnected,
    fetchDevices,
    fetchReservations,
    fetchSongs,
  };
}

/** 헤더 시계 — 서버에서 렌더링하면 시간이 어긋나므로 브라우저에서만 돈다 */
export function useClock(): string {
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const tick = () => setTimeStr(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return timeStr;
}
