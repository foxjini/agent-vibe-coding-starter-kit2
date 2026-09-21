"use client";

import React from "react";
import {
  Mic,
  Lock,
  LockOpen,
  Power,
  CalendarCheck,
  Cpu,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { Device, Reservation } from "@/types";

interface OpsSummaryProps {
  devices: Device[];
  reservations: Reservation[];
  isConnected: boolean;
}

type Tone = "ok" | "busy" | "warn" | "idle";

const TONE: Record<Tone, string> = {
  ok: "bg-free-soft text-free border-free/30",
  busy: "bg-brass-soft text-brass border-brass/30",
  warn: "bg-live-soft text-live border-live/30",
  idle: "bg-raised text-ink-3 border-line",
};

function todayString(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
}

function Tile({
  icon: Icon,
  label,
  value,
  note,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  note?: string;
  tone: Tone;
}) {
  return (
    <div className="bg-surface border border-line rounded-xl p-3.5 flex items-start gap-3 min-w-0">
      <span className={`w-9 h-9 shrink-0 rounded-lg border flex items-center justify-center ${TONE[tone]}`}>
        <Icon className="w-4 h-4" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold tracking-wide uppercase text-ink-3 truncate">
          {label}
        </p>
        <p className="text-sm font-bold text-ink truncate">{value}</p>
        {note && <p className="text-[11px] text-ink-3 truncate mt-0.5">{note}</p>}
      </div>
    </div>
  );
}

/**
 * 운영 현황 요약 (관리자 화면 맨 위)
 *
 * 선생님이 이 화면을 여는 이유는 "지금 무슨 일이 벌어지고 있나"를 확인하기
 * 위해서다. 예전에는 그 답을 찾으려면 아래 시뮬레이터 카드 안의 작은 글자들을
 * 하나씩 읽어야 했다. 한 줄로 올렸다.
 *
 * 색만으로 구분하지 않는다 — 타일마다 아이콘과 글자가 함께 바뀐다.
 *
 * 마지막 타일이 이 화면에서 가장 중요하다. 백엔드가 내린 지시(desired_state)와
 * 실기기가 보고한 결과(current_state)를 맞춰 보고, 어긋나 있으면 알려 준다.
 * 어긋남 = 라즈베리파이 데몬이 꺼졌거나 배선이 빠졌다는 신호다 (부록A §3).
 */
export function OpsSummary({ devices, reservations, isConnected }: OpsSummaryProps) {
  const find = (id: string) => devices.find((d) => d.id === id);
  const relay = find("relay_1");
  const door = find("door_lock_1");

  const inUse = relay?.current_state === "on";
  const unlocked = door?.current_state === "unlocked" || door?.current_state === "open";

  const today = todayString();
  const todays = reservations.filter(
    (r) =>
      String(r.reservation_date ?? "").slice(0, 10) === today &&
      (r.status === "reserved" || r.status === "active")
  );

  // 지시와 실제가 다른 액추에이터 — 실기기가 따라오지 못하고 있다는 뜻
  const pending = devices.filter(
    (d) =>
      d.desired_state != null &&
      d.current_state != null &&
      d.desired_state !== d.current_state
  );

  return (
    <section aria-label="운영 현황 요약" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Tile
        icon={Mic}
        label="부스"
        value={inUse ? "이용 중" : "비어 있음"}
        note={inUse ? "반주기 전원이 공급되고 있습니다" : "대기 상태"}
        tone={inUse ? "busy" : "ok"}
      />
      <Tile
        icon={unlocked ? LockOpen : Lock}
        label="도어락"
        value={unlocked ? "열림" : "잠김"}
        note={unlocked ? "입장 가능 상태" : "인증 대기"}
        tone={unlocked ? "busy" : "ok"}
      />
      <Tile
        icon={Power}
        label="기기 전원"
        value={relay?.current_state === "on" ? "ON" : "OFF"}
        note="반주기 · 앰프 릴레이"
        tone={relay?.current_state === "on" ? "busy" : "idle"}
      />
      <Tile
        icon={CalendarCheck}
        label="오늘 예약"
        value={`${todays.length}건`}
        note={todays.length ? todays.map((r) => r.student_name).join(", ") : "예약 없음"}
        tone={todays.length ? "busy" : "idle"}
      />
      <Tile
        icon={!isConnected ? AlertTriangle : pending.length ? Cpu : CheckCircle2}
        label="실기기 반영"
        value={
          !isConnected
            ? "서버 연결 끊김"
            : pending.length
            ? `${pending.length}건 미반영`
            : "지시대로 동작 중"
        }
        note={
          !isConnected
            ? "백엔드가 켜져 있는지 확인하세요"
            : pending.length
            ? pending.map((d) => `${d.name}: ${d.desired_state}`).join(" · ")
            : "모든 기기가 목표 상태와 일치"
        }
        tone={!isConnected ? "warn" : pending.length ? "warn" : "ok"}
      />
    </section>
  );
}
