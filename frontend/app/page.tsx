"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  HelpCircle,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";


import ActuatorCard from "@/components/dashboard/ActuatorCard";
import AlarmScheduleCard from "@/components/dashboard/AlarmScheduleCard";
import AlertCard from "@/components/dashboard/AlertCard";
import ConnectionBadge from "@/components/dashboard/ConnectionBadge";
import SensorCard from "@/components/dashboard/SensorCard";
import VisionLogList, { VisionEventItem } from "@/components/dashboard/VisionLogList";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

interface DeviceItem {
  id: string;
  name: string;
  kind: string;
  desired_state?: string | null;
  current_state?: string | null;
  desired_value?: unknown;
  current_value?: unknown;
  actor?: string;
  updated_at?: string | null;
}

export default function DashboardPage() {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [visionEvents, setVisionEvents] = useState<VisionEventItem[]>([]);
  const [connected, setConnected] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // 2차 수면 방지 기상 확인 팝업 상태
  const [wakeupModal, setWakeupModal] = useState<{
    open: boolean;
    message: string;
    timeLeft: number;
  } | null>(null);

  // 미션 성공 / 재알람 상태 안내 배너
  const [statusNotice, setStatusNotice] = useState<{
    type: "success" | "alarm";
    message: string;
  } | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const modalCountdownRef = useRef<NodeJS.Timeout | null>(null);

  // 1. 상단 시계 렌더링 (Hydration 안전)
  useEffect(() => {
    const updateTime = () => {
      setCurrentTime(
        new Date().toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // 2. 초기 디바이스 목록 및 비전 로그 로드
  const fetchInitialData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // 디바이스 목록
      const devRes = await fetch(`${API_BASE_URL}/api/devices`);
      if (devRes.ok) {
        const json = await devRes.json();
        if (json.data && Array.isArray(json.data)) {
          setDevices(json.data);
        }
      }

      // 비전 이벤트 목록
      const visRes = await fetch(`${API_BASE_URL}/api/events/vision?limit=15`);
      if (visRes.ok) {
        const json = await visRes.json();
        if (json.data && Array.isArray(json.data)) {
          setVisionEvents(json.data);
        }
      }
    } catch (err) {
      console.warn("초기 데이터 로드 중 오류 발생:", err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-floating-promises
    fetchInitialData();
  }, [fetchInitialData]);

  // 3. 팝업 카운트다운 타이머 관리
  useEffect(() => {
    if (!wakeupModal?.open) {
      if (modalCountdownRef.current) clearInterval(modalCountdownRef.current);
      return;
    }

    modalCountdownRef.current = setInterval(() => {
      setWakeupModal((prev) => {
        if (!prev || prev.timeLeft <= 1) {
          if (modalCountdownRef.current) clearInterval(modalCountdownRef.current);
          return null;
        }
        return { ...prev, timeLeft: prev.timeLeft - 1 };
      });
    }, 1000);

    return () => {
      if (modalCountdownRef.current) clearInterval(modalCountdownRef.current);
    };
  }, [wakeupModal?.open]);

  // 4. WebSocket 자동 재연결 및 실시간 이벤트 핸들러
  useEffect(() => {
    let unmounted = false;

    const connectWebSocket = () => {
      if (unmounted) return;

      try {
        const ws = new WebSocket(WS_URL);
        socketRef.current = ws;

        ws.onopen = () => {
          if (unmounted) return;
          setConnected(true);
          console.log("[WebSocket] 백엔드 연결 성공:", WS_URL);
        };

        ws.onmessage = (event) => {
          if (unmounted) return;
          try {
            const msg = JSON.parse(event.data);

            // A. 디바이스 상태 업데이트 수신
            if (msg.type === "device_state") {
              setDevices((prev) =>
                prev.map((d) =>
                  d.id === msg.device_id
                    ? {
                        ...d,
                        desired_state: msg.state,
                        current_state: msg.state,
                        current_value: msg.value ?? d.current_value,
                        actor: msg.actor ?? d.actor,
                        updated_at: msg.updated_at,
                      }
                    : d
                )
              );
            }

            // B. 센서 측정값 보고 수신
            else if (msg.type === "sensor_reading") {
              setDevices((prev) =>
                prev.map((d) =>
                  d.id === msg.device_id
                    ? {
                        ...d,
                        current_value: msg.value,
                        updated_at: msg.updated_at,
                      }
                    : d
                )
              );
            }

            // C. 비전 감지 이벤트 수신
            else if (msg.type === "vision_event") {
              const newEvt: VisionEventItem = {
                id: msg.id ?? `ws-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
                event_type: msg.event_type,
                detected: msg.detected,
                count: msg.count,
                confidence: msg.confidence,
                created_at: msg.created_at,
              };
              setVisionEvents((prev) => {
                const filtered = prev.filter((item) => !item.id || item.id !== newEvt.id);
                return [newEvt, ...filtered.slice(0, 19)];
              });
            }

            // D. 기상 미션 성공 알림
            else if (msg.type === "mission_success") {
              setStatusNotice({
                type: "success",
                message: msg.message || "기상 미션 성공! 알람이 해제되었습니다.",
              });
            }

            // E. 2차 수면 방지 확인 팝업 오픈
            else if (msg.type === "wakeup_check_popup") {
              setWakeupModal({
                open: true,
                message: msg.message || "2차 수면 방지: 기상 상태를 확인해 주세요!",
                timeLeft: msg.timeout || 15,
              });
            }

            // F. 2차 수면 감지로 인한 재알람 발생
            else if (msg.type === "re_alarm") {
              setWakeupModal(null);
              setStatusNotice({
                type: "alarm",
                message: msg.message || "기상 확인 미응답으로 인해 알람이 다시 동작합니다!",
              });
            }

            // G. 기상 확인 완료 수신
            else if (msg.type === "wakeup_confirmed") {
              setWakeupModal(null);
              setStatusNotice({
                type: "success",
                message: msg.message || "기상 확인이 완료되었습니다!",
              });
            }
          } catch (e) {
            console.error("[WebSocket] 메시지 파싱 오류:", e);
          }
        };

        ws.onclose = () => {
          if (unmounted) return;
          setConnected(false);
          console.warn("[WebSocket] 연결 종료됨. 3초 후 재연결 시도...");
          reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.warn("[WebSocket] 통신 에러 발생:", error);
          ws.close();
        };
      } catch (err) {
        console.error("[WebSocket] 소켓 생성 실패:", err);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  // 5. 액추에이터 제어 핸들러 (API 호출)
  const handleControlActuator = async (
    deviceId: string,
    desiredState: string,
    value?: unknown
  ) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/control`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          desired_state: desiredState,
          value: value ?? null,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        alert(`제어 실패: ${errorData?.error?.message || "알 수 없는 오류"}`);
        return;
      }

      const resJson = await res.json();
      if (resJson.data) {
        setDevices((prev) =>
          prev.map((d) => (d.id === deviceId ? { ...d, ...resJson.data } : d))
        );
      }
    } catch (err) {
      console.error("액추에이터 제어 중 에러:", err);
      alert("백엔드 서버와 통신할 수 없습니다.");
    }
  };

  // 6. 2차 수면 방지 팝업에서 "기상 완료" 확인 버튼 클릭
  const handleConfirmWakeup = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/alarm/confirm-wakeup`, {
        method: "POST",
      });
      if (res.ok) {
        setWakeupModal(null);
        setStatusNotice({
          type: "success",
          message: "기상 확인이 완료되었습니다. 활기찬 하루 되세요!",
        });
      }
    } catch (err) {
      console.error("기상 확인 전송 실패:", err);
    }
  };

  // 알람 피에조 부저 찾기
  const buzzerDevice = devices.find(
    (d) => d.id === "buzzer_1" || d.kind === "buzzer"
  );
  const isAlarmRinging =
    buzzerDevice?.current_state === "ringing" ||
    buzzerDevice?.desired_state === "ringing" ||
    buzzerDevice?.current_state === "on";

  // 센서 디바이스 목록 (읽기 전용)
  const sensorDevices = devices.filter(
    (d) => d.kind === "touch_pad" || d.kind === "camera" || d.id !== buzzerDevice?.id
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* 1. 상단 내비게이션 바 */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur-md px-4 sm:px-8 py-3.5">
        <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-900 text-white shadow-sm">
              <Zap className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-slate-900">
                  스마트 기상 시스템
                </h1>
                <span className="text-[11px] font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                  v1.0
                </span>
              </div>
              <p className="text-xs text-slate-500">
                알람 기상 미션 & 2차 수면 방지 제어 대시보드
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* 실시간 시계 (Hydration 안전) */}
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100/70 border border-slate-200 text-xs font-mono font-medium text-slate-700">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span suppressHydrationWarning>{currentTime || "--:--:--"}</span>
            </div>

            {/* 수동 새로고침 버튼 */}
            <button
              type="button"
              onClick={fetchInitialData}
              disabled={isRefreshing}
              className="cursor-pointer p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors disabled:opacity-50"
              title="데이터 새로고침"
            >
              <RefreshCw
                className={`w-4 h-4 ${isRefreshing ? "animate-spin text-slate-800" : ""}`}
              />
            </button>

            {/* 사전 탑재된 ConnectionBadge */}
            <ConnectionBadge connected={connected} />
          </div>
        </div>
      </header>

      {/* 2. 대시보드 본문 */}
      <main className="flex-1 mx-auto max-w-7xl w-full p-4 sm:p-8 space-y-6">
        {/* 알람 동작 시 표시되는 AlertCard */}
        <AlertCard
          active={Boolean(isAlarmRinging)}
          title="기상 알람이 활성화되었습니다!"
          description="현재 피에조 부저 알람이 울리고 있습니다. 카메라 앞에서 기상 미션(사물/인물)을 수행하거나 수동으로 해제하세요."
          onDismiss={() =>
            handleControlActuator(buzzerDevice?.id || "buzzer_1", "off")
          }
        />

        {/* 알람 시각 설정 및 기상 미션 예약 컨트롤러 */}
        <AlarmScheduleCard
          apiBaseUrl={API_BASE_URL}
          isAlarmRinging={Boolean(isAlarmRinging)}
          onAlarmStateChanged={fetchInitialData}
        />


        {/* 상태 알림 배너 (미션 성공 / 2차 수면 재알람) */}
        {statusNotice && (
          <div
            className={`rounded-xl border p-4 text-xs flex items-center justify-between gap-3 transition-all duration-200 ${
              statusNotice.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-rose-200 bg-rose-50 text-rose-900 animate-pulse"
            }`}
          >
            <div className="flex items-center gap-2.5">
              {statusNotice.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              <span>{statusNotice.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setStatusNotice(null)}
              className="text-[11px] underline opacity-70 hover:opacity-100 cursor-pointer"
            >
              닫기
            </button>
          </div>
        )}

        {/* 안내 배너 */}
        <div className="rounded-xl border border-sky-100 bg-sky-50/50 p-4 text-xs text-sky-900 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-4 h-4 text-sky-600 shrink-0" />
            <span>
              <strong>트리거 규칙:</strong> 알람 동작 시 카메라 앞에서 기상 미션을 수행하면 알람이 자동 종료되며, 약 25초 후 2차 수면 방지 확인 팝업이 나타납니다.
            </span>
          </div>
          <span className="shrink-0 text-[11px] font-mono text-sky-700 bg-sky-100/60 px-2 py-0.5 rounded">
            트리거 연동 완료
          </span>
        </div>

        {/* 3. 디바이스 그리드 (액추에이터 제어 + 센서 읽기 전용) */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-slate-800 tracking-tight">
              디바이스 상태 및 제어
            </h2>
            <span className="text-xs text-slate-400">
              총 {devices.length}개 디바이스 연동됨
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* 1) 액추에이터 카드 (알람 피에조 부저) */}
            {buzzerDevice && (
              <div className="md:col-span-2 lg:col-span-1">
                <ActuatorCard
                  device={buzzerDevice}
                  onControl={handleControlActuator}
                />
              </div>
            )}

            {/* 2) 센서 카드들 (터치패드 및 카메라 — 읽기 전용) */}
            {sensorDevices.map((dev) => (
              <SensorCard key={dev.id} device={dev} />
            ))}

            {devices.length === 0 && !isRefreshing && (
              <div className="col-span-full py-12 text-center rounded-xl border border-dashed border-slate-200 bg-white">
                <p className="text-sm font-medium text-slate-600">
                  연결된 디바이스가 없습니다.
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  백엔드 서버(uvicorn)가 실행 중인지 확인해 주세요.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* 4. 실시간 영상인식 이벤트 로그 */}
        <div className="pt-2">
          <VisionLogList events={visionEvents} />
        </div>
      </main>

      {/* 2차 수면 방지 기상 확인 모달 팝업 */}
      {wakeupModal?.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-slate-100 text-center space-y-5">
            <div className="mx-auto w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center text-amber-600 animate-bounce">
              <HelpCircle className="w-8 h-8" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-900">
                2차 수면 방지 기상 확인
              </h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                {wakeupModal.message}
              </p>
            </div>

            {/* 제한시간 카운트다운 게이지 */}
            <div className="rounded-xl bg-amber-50 border border-amber-200/80 p-3">
              <span className="text-xs font-semibold text-amber-800">
                남은 확인 시간:{" "}
                <strong className="text-sm font-bold font-mono text-amber-900">
                  {wakeupModal.timeLeft}초
                </strong>
              </span>
              <p className="text-[11px] text-amber-700/80 mt-0.5">
                시간 내 미확인 시 피에조 부저 알람이 다시 울립니다.
              </p>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleConfirmWakeup}
                className="w-full cursor-pointer py-3 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold shadow-md transition-all duration-200"
              >
                완전히 일어났습니다! (기상 확인)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. 푸터 */}
      <footer className="border-t border-slate-200 bg-white py-4 px-4 sm:px-8 text-center text-xs text-slate-400">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>스마트 기상 시스템 · 팀 IoT & Vision 대시보드</span>
          <span className="font-mono text-[11px]">
            백엔드: {API_BASE_URL} · 웹소켓: {WS_URL}
          </span>
        </div>
      </footer>
    </div>
  );
}
