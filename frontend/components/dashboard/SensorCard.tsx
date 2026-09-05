"use client";

import React from "react";
import { Camera, Eye, Fingerprint, Hand, Radio } from "lucide-react";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";

interface SensorCardProps {
  device: {
    id: string;
    name: string;
    kind: string;
    current_state?: string | null;
    current_value?: any;
    updated_at?: string | null;
  };
}

export const SensorCard: React.FC<SensorCardProps> = ({ device }) => {
  const isTouchPad = device.kind === "touch_pad" || device.id.includes("touch");
  const isCamera = device.kind === "camera" || device.id.includes("camera");

  // 터치패드 데이터 파싱
  const touchData = isTouchPad ? device.current_value || {} : null;
  const isTouched =
    Boolean(touchData?.pressed) || device.current_state === "touched";

  // 카메라 데이터 파싱
  const cameraData = isCamera ? device.current_value || {} : null;
  const personDetected = Boolean(cameraData?.person_detected ?? true);
  const confidence = cameraData?.confidence
    ? Math.round(Number(cameraData.confidence) * 100)
    : 92;
  const detectedGesture = cameraData?.gesture || "none";

  // 상태 배지 레이블 및 클래스
  let badgeStatus = "off";
  let badgeLabel = "대기 중";

  if (isTouchPad) {
    badgeStatus = isTouched ? "alert" : "info";
    badgeLabel = isTouched ? "터치 감지됨" : "입력 대기 중";
  } else if (isCamera) {
    badgeStatus = personDetected ? "on" : "off";
    badgeLabel = personDetected ? "기상 모니터링 중" : "미감지";
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:border-slate-300">
      {/* 상단: 디바이스 이름(작은 라벨) 및 읽기 전용 배지 */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
            {isTouchPad ? (
              <Fingerprint className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <Camera className="w-3.5 h-3.5 text-slate-500" />
            )}
            센서(읽기 전용) · {device.kind}
          </div>
          <h3 className="text-base font-medium text-slate-800 truncate">
            {device.name}
          </h3>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-200 ${getStatusBadgeClass(
            badgeStatus
          )}`}
        >
          {badgeLabel}
        </span>
      </div>

      {/* 중앙: 큰 값(text-3xl 이상) + 단위 */}
      <div className="py-3">
        {isTouchPad && (
          <div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-3xl font-bold tracking-tight ${
                  isTouched ? "text-rose-600" : "text-slate-800"
                }`}
              >
                {isTouched ? "TOUCHED" : "IDLE"}
              </span>
              <span className="text-sm font-medium text-slate-500">
                {isTouched ? "입력 발생" : "터치 없음"}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-lg p-2.5 border border-slate-100">
              <div>
                <span className="text-slate-400">좌표: </span>
                <span className="font-mono font-medium text-slate-700">
                  {touchData?.touch_x || 0}px, {touchData?.touch_y || 0}px
                </span>
              </div>
              <div>
                <span className="text-slate-400">제스처: </span>
                <span className="font-semibold text-slate-700 uppercase">
                  {touchData?.gesture || "none"}
                </span>
              </div>
            </div>
          </div>
        )}

        {isCamera && (
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold tracking-tight text-emerald-600">
                {confidence}%
              </span>
              <span className="text-sm font-medium text-slate-500">
                인물 감지 신뢰도
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-lg p-2.5 border border-slate-100">
              <div>
                <span className="text-slate-400">인식 대상: </span>
                <span className="font-semibold text-slate-700">
                  사용자 (기상 중)
                </span>
              </div>
              <div>
                <span className="text-slate-400">손동작 미션: </span>
                <span className="font-semibold text-sky-700 uppercase">
                  {detectedGesture !== "none" ? detectedGesture : "대기 중"}
                </span>
              </div>
            </div>
          </div>
        )}

        {!isTouchPad && !isCamera && (
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-slate-800">
              {String(device.current_value ?? "ACTIVE")}
            </span>
            <span className="text-sm font-medium text-slate-500">상태</span>
          </div>
        )}
      </div>

      {/* 하단: 마지막 갱신 시각 (suppressHydrationWarning) */}
      <div className="mt-2 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <Radio className="w-3 h-3 text-slate-400" />
          실시간 폴링 수신
        </span>
        <span suppressHydrationWarning>
          마지막 갱신:{" "}
          {device.updated_at
            ? new Date(device.updated_at).toLocaleTimeString("ko-KR")
            : "수신 대기"}
        </span>
      </div>
    </div>
  );
};

export default SensorCard;
