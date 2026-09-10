"use client";

import React from "react";
import { Camera, Fingerprint, Radio } from "lucide-react";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import { parseJsonValue } from "@/lib/api";

interface SensorCardProps {
  device: {
    id: string;
    name: string;
    kind: string;
    current_state?: string | null;
    current_value?: unknown;
    updated_at?: string | null;
  };
}

interface TouchValue {
  pressed?: boolean;
  touch_x?: number;
  touch_y?: number;
  gesture?: string;
}

interface CameraValue {
  person_detected?: boolean;
  confidence?: number;
  gesture?: string;
  motion_detected?: boolean;
}

/** 값이 아직 들어오지 않았을 때 쓰는 표시 (그럴듯한 가짜 숫자를 만들지 않는다) */
const NO_DATA = "—";

export const SensorCard: React.FC<SensorCardProps> = ({ device }) => {
  const isTouchPad = device.kind === "touch_pad" || device.id.includes("touch");
  const isCamera = device.kind === "camera" || device.id.includes("camera");

  // MySQL JSON 컬럼이 문자열로 와도 안전하게 객체로 되돌린다
  const value = parseJsonValue<Record<string, unknown>>(device.current_value);
  const hasReading = value !== null;

  const touchData = isTouchPad ? (value as TouchValue | null) : null;
  const cameraData = isCamera ? (value as CameraValue | null) : null;

  const isTouched =
    Boolean(touchData?.pressed) || device.current_state === "touched";

  // 카메라: 실제로 보고된 값이 있을 때만 표시한다 (없으면 '미수신')
  const personDetected = cameraData?.person_detected;
  const confidence =
    typeof cameraData?.confidence === "number"
      ? Math.round(cameraData.confidence * 100)
      : null;
  const detectedGesture = cameraData?.gesture ?? null;

  // 상태 배지 레이블 및 클래스
  let badgeStatus = "off";
  let badgeLabel = "대기 중";

  if (isTouchPad) {
    if (!hasReading && !device.current_state) {
      badgeStatus = "disconnected";
      badgeLabel = "보고 없음";
    } else {
      badgeStatus = isTouched ? "alert" : "info";
      badgeLabel = isTouched ? "터치 감지됨" : "입력 대기 중";
    }
  } else if (isCamera) {
    if (personDetected === undefined) {
      badgeStatus = "disconnected";
      badgeLabel = "보고 없음";
    } else {
      badgeStatus = personDetected ? "on" : "off";
      badgeLabel = personDetected ? "기상 모니터링 중" : "미감지";
    }
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
                {hasReading || device.current_state
                  ? isTouched
                    ? "TOUCHED"
                    : "IDLE"
                  : NO_DATA}
              </span>
              <span className="text-sm font-medium text-slate-500">
                {hasReading || device.current_state
                  ? isTouched
                    ? "입력 발생"
                    : "터치 없음"
                  : "아직 보고 없음"}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-lg p-2.5 border border-slate-100">
              <div>
                <span className="text-slate-400">좌표: </span>
                <span className="font-mono font-medium text-slate-700">
                  {touchData
                    ? `${touchData.touch_x ?? 0}px, ${touchData.touch_y ?? 0}px`
                    : NO_DATA}
                </span>
              </div>
              <div>
                <span className="text-slate-400">제스처: </span>
                <span className="font-semibold text-slate-700 uppercase">
                  {touchData?.gesture ?? NO_DATA}
                </span>
              </div>
            </div>
          </div>
        )}

        {isCamera && (
          <div>
            <div className="flex items-baseline gap-2">
              <span
                className={`text-3xl font-bold tracking-tight ${
                  confidence === null ? "text-slate-400" : "text-emerald-600"
                }`}
              >
                {confidence === null ? NO_DATA : `${confidence}%`}
              </span>
              <span className="text-sm font-medium text-slate-500">
                {confidence === null
                  ? "비전 클라이언트 보고 대기"
                  : "인물 감지 신뢰도"}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-lg p-2.5 border border-slate-100">
              <div>
                <span className="text-slate-400">인식 상태: </span>
                <span className="font-semibold text-slate-700">
                  {personDetected === undefined
                    ? NO_DATA
                    : personDetected
                      ? "사람 감지됨"
                      : "감지 없음"}
                </span>
              </div>
              <div>
                <span className="text-slate-400">손동작 미션: </span>
                <span className="font-semibold text-sky-700 uppercase">
                  {detectedGesture && detectedGesture !== "none"
                    ? detectedGesture
                    : "대기 중"}
                </span>
              </div>
            </div>
          </div>
        )}

        {!isTouchPad && !isCamera && (
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-slate-800">
              {device.current_state ?? NO_DATA}
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
