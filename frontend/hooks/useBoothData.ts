"use client";

import { useState, useEffect, useCallback, useSyncExternalStore } from "react";
import { apiUrl } from "@/utils/apiConfig";
import {
  adminFetch,
  subscribeAdminSession,
  getAdminSnapshot,
  getAdminServerSnapshot,
} from "@/utils/adminSession";
import { useKaraokeSocket } from "@/hooks/useKaraokeSocket";
import {
  Device,
  QueueSnapshot,
  Reservation,
  ScoreRecord,
  Song,
  WebSocketMessage,
} from "@/types";

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
  // 순위 (부록G §2-④) — 오늘 기록과 명예의 전당을 따로 본다
  const [topToday, setTopToday] = useState<ScoreRecord[]>([]);
  const [topAll, setTopAll] = useState<ScoreRecord[]>([]);
  // 전시 체험 대기열 (부록G §2-③)
  const [queue, setQueue] = useState<QueueSnapshot | null>(null);
  // 이용이 끝날 때마다 1씩 오른다 (예약 종료·체험 3분 종료·[이용 종료] 버튼).
  // 퇴실곡처럼 "끝났을 때 한 번" 해야 하는 일이 이 숫자를 지켜본다.
  const [sessionEndCount, setSessionEndCount] = useState(0);

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

  // 예약 PIN은 서버가 관리자에게만 내려준다. adminFetch 는 관리자 토큰이 있을 때만
  // 헤더에 붙이므로, 학생·부스 화면에서는 PIN 없이 목록만 받는다.
  const fetchReservations = useCallback(async () => {
    try {
      const res = await adminFetch("/api/reservations");
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

  const fetchScores = useCallback(async () => {
    try {
      const [todayRes, allRes] = await Promise.all([
        fetch(apiUrl("/api/scores/top?period=today&limit=5")),
        fetch(apiUrl("/api/scores/top?period=all&limit=5")),
      ]);
      if (todayRes.ok) setTopToday((await todayRes.json()).data || []);
      if (allRes.ok) setTopAll((await allRes.json()).data || []);
    } catch {
      // 순위를 못 받아도 노래방은 돌아가야 한다
    }
  }, []);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/experience/queue"));
      if (res.ok) setQueue((await res.json()).data ?? null);
    } catch {
      // 대기열을 못 받아도 노래방은 돌아가야 한다
    }
  }, []);

  // 관리자로 로그인·로그아웃하면 예약 목록을 다시 받는다 (PIN이 보였다 사라졌다 한다)
  const adminAuthed = useSyncExternalStore(
    subscribeAdminSession,
    getAdminSnapshot,
    getAdminServerSnapshot
  );

  useEffect(() => {
    // effect 본문에서 곧바로 상태를 바꾸지 않도록 첫 조회를 한 틱 미룬다
    // (React 19 규칙 react-hooks/set-state-in-effect)
    const id = setTimeout(() => {
      fetchDevices();
      fetchSongs();
      fetchScores();
      fetchQueue();
    }, 0);
    return () => clearTimeout(id);
  }, [fetchDevices, fetchSongs, fetchScores, fetchQueue]);

  useEffect(() => {
    const id = setTimeout(fetchReservations, 0);
    return () => clearTimeout(id);
  }, [fetchReservations, adminAuthed]);

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
        if (msg.event === "session_ended") setSessionEndCount((n) => n + 1);
        fetchDevices();
      } else if (msg.type === "reservation_created") {
        fetchReservations();
      } else if (msg.type === "song_recorded") {
        fetchSongs();
      } else if (msg.type === "score_recorded") {
        // 누군가 점수를 받으면 부스 화면의 순위가 즉시 바뀐다
        setLastEventMsg(
          `${msg.nickname ?? "익명"}님이 ${msg.title ?? "노래"}로 ${msg.score ?? 0}점을 받았습니다!`
        );
        fetchScores();
      } else if (msg.type === "queue_called") {
        setLastEventMsg(msg.message || `${msg.ticket_no ?? ""}번 입장해 주세요!`);
        fetchQueue();
      } else if (msg.type === "queue_updated") {
        fetchQueue();
      }
    },
    [fetchDevices, fetchReservations, fetchSongs, fetchScores, fetchQueue]
  );

  const { isConnected } = useKaraokeSocket(handleWsMessage);

  return {
    devices,
    reservations,
    allSongs,
    favoriteSongs,
    lastEventMsg,
    topToday,
    topAll,
    queue,
    sessionEndCount,
    isConnected,
    fetchDevices,
    fetchReservations,
    fetchSongs,
    fetchScores,
    fetchQueue,
  };
}

/** 헤더 시계 — 서버에서 렌더링하면 시간이 어긋나므로 브라우저에서만 돈다 */
export function useClock(): string {
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    // ko-KR 기본 형식은 "1시 16분 39초"라 자리수가 들쭉날쭉하고 제품 화면에 어울리지 않는다.
    // 두 자리로 고정해 숫자가 흔들리지 않게 한다 (.tnum 과 함께 쓴다).
    const pad = (n: number) => String(n).padStart(2, "0");
    const tick = () => {
      const d = new Date();
      setTimeStr(`${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return timeStr;
}
