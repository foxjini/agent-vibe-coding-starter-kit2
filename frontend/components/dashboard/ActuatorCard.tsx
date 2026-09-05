"use client";

import React, { useState } from "react";
import { Bell, BellOff, BellRing, Volume2 } from "lucide-react";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";

interface ActuatorCardProps {
  device: {
    id: string;
    name: string;
    kind: string;
    desired_state?: string | null;
    current_state?: string | null;
    desired_value?: any;
    current_value?: any;
    actor?: string;
    updated_at?: string | null;
  };
  onControl: (deviceId: string, desiredState: string, value?: any) => Promise<void>;
  loading?: boolean;
}

export const ActuatorCard: React.FC<ActuatorCardProps> = ({
  device,
  onControl,
  loading = false,
}) => {
  const [volume, setVolume] = useState<number>(
    device.current_value?.volume ?? 80
  );
  const [submitting, setSubmitting] = useState(false);

  const isRinging =
    device.current_state === "ringing" ||
    device.current_state === "on" ||
    device.desired_state === "ringing";

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
        isRinging
          ? "border-rose-300 ring-2 ring-rose-100 bg-rose-50/20"
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
            isRinging ? "alert" : "off"
          )}`}
        >
          {isRinging ? "알람 울림 (RINGING)" : "알람 대기 (OFF)"}
        </span>
      </div>

      {/* 중앙: 상태 시각화 및 제어 버튼 */}
      <div className="py-2 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-3.5 rounded-full transition-colors duration-200 ${
              isRinging
                ? "bg-rose-100 text-rose-600 animate-pulse"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {isRinging ? (
              <BellRing className="w-8 h-8" />
            ) : (
              <BellOff className="w-8 h-8" />
            )}
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight text-slate-900">
              {isRinging ? "알람 동작 중" : "정상 대기"}
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
              <Volume2 className="w-3.5 h-3.5 text-slate-400" />
              볼륨: {volume}% · 1000Hz
            </div>
          </div>
        </div>

        {/* 제어 버튼 */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          {isRinging ? (
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
