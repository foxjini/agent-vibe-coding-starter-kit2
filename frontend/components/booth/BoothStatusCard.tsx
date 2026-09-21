"use client";

import React from "react";
import { Mic, DoorOpen, DoorClosed, WifiOff } from "lucide-react";
import { Device, Reservation } from "@/types";

interface BoothStatusCardProps {
  devices: Device[];
  reservations: Reservation[];
  isConnected: boolean;
}

/** 타임슬롯 정의 — 백엔드의 lunch/dinner 와 같은 값을 쓴다 */
const SLOTS = [
  { key: "lunch", label: "점심 타임", time: "12:30 ~ 13:20" },
  { key: "dinner", label: "저녁 타임", time: "17:30 ~ 18:30" },
] as const;

function todayString(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
}

/**
 * 부스 현재 상태 (관람객 화면 맨 위)
 *
 * 관람객이 이 화면에 와서 가장 먼저 궁금한 것은 "지금 쓸 수 있나, 줄을 서야 하나"다.
 * 예전에는 그 답이 상단 헤더의 작은 배지 하나뿐이었고, 예약 폼이 먼저 나왔다.
 * 순서를 뒤집어 상태를 맨 위로 올렸다.
 *
 * 상태를 색으로만 구분하지 않는다 — 아이콘과 글자가 함께 바뀐다.
 */
export function BoothStatusCard({ devices, reservations, isConnected }: BoothStatusCardProps) {
  const relay = devices.find((d) => d.id === "relay_1");
  const doorLock = devices.find((d) => d.id === "door_lock_1");

  const inUse = relay?.current_state === "on";
  const unlocked =
    doorLock?.current_state === "unlocked" || doorLock?.current_state === "open";

  const today = todayString();
  const takenSlots = new Set(
    reservations
      .filter(
        (r) =>
          String(r.reservation_date ?? "").slice(0, 10) === today &&
          (r.status === "reserved" || r.status === "active")
      )
      .map((r) => r.time_slot)
  );

  const status = !isConnected
    ? {
        Icon: WifiOff,
        label: "상태를 확인할 수 없습니다",
        detail: "부스 시스템과 연결되지 않았습니다. 잠시 후 다시 확인해 주세요.",
        tone: "text-ink-3",
        chip: "bg-raised text-ink-3 border-line",
      }
    : inUse
    ? {
        Icon: Mic,
        label: "지금 이용 중",
        detail: "다른 팀이 사용하고 있습니다. 아래에서 다음 타임을 예약하세요.",
        tone: "text-live",
        chip: "bg-live-soft text-live border-live/30",
      }
    : {
        Icon: unlocked ? DoorOpen : DoorClosed,
        label: "비어 있음",
        detail: unlocked
          ? "문이 열려 있습니다. 예약한 팀이 입장하는 중일 수 있습니다."
          : "예약한 시간에 부스 앞 키패드로 비밀번호를 누르면 들어갈 수 있습니다.",
        tone: "text-free",
        chip: "bg-free-soft text-free border-free/30",
      };

  const { Icon } = status;

  return (
    <section
      aria-label="부스 현재 상태"
      className="rounded-2xl bg-surface border border-line p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-5"
    >
      <div className="flex items-start gap-3.5 min-w-0 flex-1">
        <span
          className={`w-11 h-11 shrink-0 rounded-xl border flex items-center justify-center ${status.chip}`}
        >
          <Icon className="w-5 h-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-wider uppercase text-ink-3">
            노래방 부스
          </p>
          <p className={`text-xl font-extrabold leading-tight ${status.tone}`}>{status.label}</p>
          <p className="text-xs text-ink-2 mt-1 leading-relaxed">{status.detail}</p>
        </div>
      </div>

      {/* 오늘 타임 현황 — 예약할지 말지 바로 판단할 수 있게 */}
      <div className="shrink-0 flex flex-col gap-2 sm:min-w-[15rem]">
        {SLOTS.map((slot) => {
          const taken = takenSlots.has(slot.key);
          return (
            <div
              key={slot.key}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
                taken ? "bg-raised border-line text-ink-3" : "bg-free-soft border-free/25 text-free"
              }`}
            >
              <span className="font-bold">{slot.label}</span>
              <span className="font-mono tnum text-[11px] opacity-80 whitespace-nowrap">{slot.time}</span>
              <span className="ml-auto font-bold whitespace-nowrap">
                {taken ? "예약됨" : "예약 가능"}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
