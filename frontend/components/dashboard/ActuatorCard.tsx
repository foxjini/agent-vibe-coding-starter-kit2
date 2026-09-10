"use client";

import React, { useState } from "react";
import { Bell, BellOff, BellRing, Loader2, Volume2 } from "lucide-react";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import { parseJsonValue } from "@/lib/api";

interface ActuatorCardProps {
  device: {
    id: string;
    name: string;
    kind: string;
    desired_state?: string | null;
    current_state?: string | null;
    desired_value?: unknown;
    current_value?: unknown;
    actor?: string;
    updated_at?: string | null;
  };
  onControl: (deviceId: string, desiredState: string, value?: unknown) => Promise<void>;
  loading?: boolean;
}

const RINGING_STATES = ["ringing", "on"];

export const ActuatorCard: React.FC<ActuatorCardProps> = ({
  device,
  onControl,
  loading = false,
}) => {
  const desiredValue = parseJsonValue<{ volume?: number; frequency?: number }>(
    device.desired_value
  );
  const currentValue = parseJsonValue<{ volume?: number; frequency?: number }>(
    device.current_value
  );

  // 사용자가 슬라이더를 만지기 전에는 서버가 알려준 값(desired)을 그대로 보여준다.
  // 이펙트로 동기화하지 않고 파생값으로 계산해 불필요한 렌더를 만들지 않는다.
  const [userVolume, setUserVolume] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const volume = userVolume ?? desiredValue?.volume ?? currentValue?.volume ?? 80;
  const setVolume = setUserVolume;

  // 부록A 계약: 백엔드가 명령한 값(desired)과 하드웨어가 보고한 값(current)을 구분해서 보여준다
  const commandedRinging = RINGING_STATES.includes(device.desired_state ?? "");
  const actuallyRinging = RINGING_STATES.includes(device.current_state ?? "");
  const hasReport = device.current_state !== null && device.current_state !== undefined;
  const pendingHardware = hasReport
    ? device.desired_state !== device.current_state
    : commandedRinging;

  const frequency = desiredValue?.frequency ?? currentValue?.frequency ?? 1000;

  const handleToggle = async (targetState: string) => {
    setSubmitting(true);
    try {
      await onControl(device.id, targetState, {
        volume,
        frequency: 1000,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className={`relative rounded-xl border p-5 transition-all duration-200 shadow-sm bg-white ${
        actuallyRinging
          ? "border-rose-300 ring-2 ring-rose-100 bg-rose-50/20"
          : commandedRinging
            ? "border-amber-300 ring-2 ring-amber-100"
            : "border-slate-200 hover:border-slate-300"
      }`}
    >
      {/* 상단: 디바이스 이름 및 상태 배지 */}
      <div className="flex items-center justify-between gap-2 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            액추에이터 · {device.kind}
          </span>
          <h3 className="text-base font-medium text-slate-800 truncate">
            {device.name}
          </h3>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-200 ${getStatusBadgeClass(
            actuallyRinging ? "alert" : commandedRinging ? "warning" : "off"
          )}`}
        >
          {actuallyRinging
            ? "알람 울림 (RINGING)"
            : commandedRinging
              ? "명령 전송됨"
              : "알람 대기 (OFF)"}
        </span>
      </div>

      {/* 중앙: 상태 시각화 및 제어 버튼 */}
      <div className="py-2 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-3.5 rounded-full transition-colors duration-200 ${
              actuallyRinging
                ? "bg-rose-100 text-rose-600 animate-pulse"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {actuallyRinging ? (
              <BellRing className="w-8 h-8" />
            ) : (
              <BellOff className="w-8 h-8" />
            )}
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight text-slate-900">
              {actuallyRinging ? "알람 동작 중" : "정상 대기"}
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
              <Volume2 className="w-3.5 h-3.5 text-slate-400" />
              볼륨: {volume}% · {frequency}Hz
            </div>
          </div>
        </div>

        {/* 제어 버튼 */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          {commandedRinging ? (
            <button
              type="button"
              disabled={submitting || loading}
              onClick={() => handleToggle("off")}
              className="flex-1 sm:flex-none cursor-pointer inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium transition-colors duration-200 disabled:opacity-50"
            >
              <BellOff className="w-4 h-4" />
              알람 끄기
            </button>
          ) : (
            <button
              type="button"
              disabled={submitting || loading}
              onClick={() => handleToggle("ringing")}
              className="flex-1 sm:flex-none cursor-pointer inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium transition-colors duration-200 disabled:opacity-50"
            >
              <Bell className="w-4 h-4" />
              알람 테스트 울리기
            </button>
          )}
        </div>
      </div>

      {/* 명령(desired) vs 실제 반영(current) — 하드웨어가 응답하지 않으면 여기서 바로 보인다 */}
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
          <div className="text-slate-400">백엔드 명령 (desired)</div>
          <div className="font-semibold text-slate-700 uppercase">
            {device.desired_state ?? "—"}
          </div>
        </div>
        <div
          className={`rounded-lg border p-2.5 ${
            pendingHardware
              ? "border-amber-200 bg-amber-50"
              : "border-slate-100 bg-slate-50"
          }`}
        >
          <div className={pendingHardware ? "text-amber-700" : "text-slate-400"}>
            하드웨어 반영 (current)
          </div>
          <div
            className={`font-semibold uppercase flex items-center gap-1 ${
              pendingHardware ? "text-amber-800" : "text-slate-700"
            }`}
          >
            {pendingHardware && <Loader2 className="w-3 h-3 animate-spin" />}
            {hasReport ? device.current_state : "보고 없음"}
          </div>
        </div>
      </div>

      {pendingHardware && (
        <p className="mt-2 text-[11px] text-amber-700">
          라즈베리파이의 반영 보고를 기다리는 중입니다. 오래 지속되면 파이 데몬 실행과 배선을 확인하세요.
        </p>
      )}

      {/* 볼륨 조절 슬라이더 */}
      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-3 text-xs text-slate-500">
        <label htmlFor={`vol-${device.id}`} className="shrink-0 font-medium">
          출력 볼륨:
        </label>
        <input
          id={`vol-${device.id}`}
          type="range"
          min="10"
          max="100"
          step="5"
          value={volume}
          onChange={(e) => setVolume(Number(e.target.value))}
          className="w-full accent-slate-800 cursor-pointer"
        />
        <span className="w-8 text-right font-mono font-medium text-slate-700">
          {volume}%
        </span>
      </div>

      {/* 하단: 조작자 및 마지막 갱신 시각 (suppressHydrationWarning) */}
      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
        <span>
          조작자:{" "}
          <strong className="font-semibold text-slate-600 uppercase">
            {device.actor || "system"}
          </strong>
        </span>
        <span suppressHydrationWarning>
          마지막 갱신:{" "}
          {device.updated_at
            ? new Date(device.updated_at).toLocaleTimeString("ko-KR")
            : "동기화 대기"}
        </span>
      </div>
    </div>
  );
};

export default ActuatorCard;
