/**
 * 제어 (wakeup 7인치 화면) — 알람 · 커튼 · 모션 베드 · 조명을 한 줄씩
 * 왼쪽에 부품과 지금 상태, 오른쪽에 누를 버튼. 오른쪽 아래 "모두 끄기"(FAB)는
 * 알람·조명을 끄고 모션 베드를 0°로 돌립니다.
 */
"use client";

import { BedDouble, Bell, Blinds, Lightbulb, Power } from "lucide-react";
import React from "react";

import Fab from "@/components/team/wakeup/Fab";
import { State, TouchButton } from "@/components/team/wakeup/Tile";
import { asObject, numberFrom, slotLabel } from "@/lib/slots";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

function servoAngle(wakeup: WakeupApi, slotId: string): number | null {
  const slot = wakeup.scenario.slotOf(slotId);
  const angle = numberFrom(slot?.current_value ?? slot?.desired_value, ["angle"], Number.NaN);
  return Number.isFinite(angle) ? angle : null;
}

function Row({
  icon,
  name,
  state,
  missing,
  children,
}: {
  icon: React.ReactNode;
  name: string;
  state: React.ReactNode;
  /** 배치표에 없으면 버튼 대신 안내 */
  missing?: string;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex min-h-[72px] items-center gap-4 border-b border-(--wk-line) last:border-0">
      <span className="text-(--wk-dim)" aria-hidden="true">
        {icon}
      </span>
      <div className="w-40 shrink-0">
        <div className="truncate text-lg font-medium">{name}</div>
        <div className="text-base">{state}</div>
      </div>
      <div className="flex flex-1 justify-end gap-2">
        {missing ? <span className="text-base text-(--wk-dim)">배치표에 {missing}가 없어요</span> : children}
      </div>
    </li>
  );
}

export default function ControlScreen({ wakeup }: { wakeup: WakeupApi }) {
  const { scenario, device } = wakeup;
  const { setActuator, slotOf } = scenario;
  const curtain = slotOf(WAKEUP_SLOTS.curtain);
  const bed = slotOf(WAKEUP_SLOTS.bed);
  const light = slotOf(WAKEUP_SLOTS.light);
  const buzzer = slotOf(WAKEUP_SLOTS.buzzer);
  const curtainAngle = servoAngle(wakeup, WAKEUP_SLOTS.curtain);
  const bedAngle = servoAngle(wakeup, WAKEUP_SLOTS.bed);
  const lightColor = String(asObject(light?.desired_value)?.color ?? "").toLowerCase();
  const curtainOpen = curtainAngle !== null && curtainAngle > device.curtainCloseAngle;

  const colors = [
    { label: "새벽빛", color: device.lightColor.toLowerCase() },
    { label: "흰빛", color: "#ffffff" },
  ];

  return (
    <div className="relative h-full">
      <ul className="h-full overflow-y-auto px-6 pb-20">
        <Row
          icon={<Bell className="h-6 w-6" />}
          name={buzzer ? slotLabel(buzzer) : "알람"}
          state={<State on={wakeup.ringing}>{wakeup.ringing ? "울리는 중" : "조용함"}</State>}
          missing={buzzer ? undefined : WAKEUP_SLOTS.buzzer}
        >
          <TouchButton onClick={() => void wakeup.startAlarm()} disabled={wakeup.ringing}>
            울려 보기
          </TouchButton>
          <TouchButton onClick={() => void wakeup.stopAlarm()} disabled={!wakeup.ringing}>
            끄기
          </TouchButton>
        </Row>

        <Row
          icon={<Blinds className="h-6 w-6" />}
          name={curtain ? slotLabel(curtain) : "커튼"}
          state={<State on={curtainOpen}>{curtainAngle === null ? "확인 중" : curtainOpen ? `열림 ${curtainAngle}°` : "닫힘"}</State>}
          missing={curtain ? undefined : WAKEUP_SLOTS.curtain}
        >
          <TouchButton
            onClick={() => void setActuator(WAKEUP_SLOTS.curtain, "move", { angle: device.curtainOpenAngle })}
            tone={curtainOpen ? "selected" : "plain"}
            ariaPressed={curtainOpen}
          >
            열기
          </TouchButton>
          <TouchButton
            onClick={() => void setActuator(WAKEUP_SLOTS.curtain, "move", { angle: device.curtainCloseAngle })}
            tone={!curtainOpen && curtainAngle !== null ? "selected" : "plain"}
            ariaPressed={!curtainOpen && curtainAngle !== null}
          >
            닫기
          </TouchButton>
        </Row>

        <Row
          icon={<BedDouble className="h-6 w-6" />}
          name={bed ? slotLabel(bed) : "모션 베드"}
          state={
            <State on={wakeup.bedShaking}>
              {wakeup.bedShaking ? "흔드는 중" : bedAngle ? `올라감 ${bedAngle}°` : "내려감"}
            </State>
          }
          missing={bed ? undefined : WAKEUP_SLOTS.bed}
        >
          <TouchButton
            onClick={() => void setActuator(WAKEUP_SLOTS.bed, "move", { angle: device.bedAngle })}
            disabled={wakeup.bedShaking}
          >
            올리기
          </TouchButton>
          <TouchButton
            onClick={() => void setActuator(WAKEUP_SLOTS.bed, "move", { angle: 0 })}
            disabled={wakeup.bedShaking}
          >
            내리기
          </TouchButton>
        </Row>

        <Row
          icon={<Lightbulb className="h-6 w-6" />}
          name={light ? slotLabel(light) : "조명"}
          state={<State on={wakeup.lightOn}>{wakeup.lightOn ? "켜짐" : "꺼짐"}</State>}
          missing={light ? undefined : WAKEUP_SLOTS.light}
        >
          {colors.map((preset) => {
            const on = wakeup.lightOn && lightColor === preset.color;
            return (
              <TouchButton
                key={preset.label}
                onClick={() =>
                  void setActuator(WAKEUP_SLOTS.light, "on", {
                    color: preset.color,
                    brightness: device.lightBrightness,
                  })
                }
                tone={on ? "selected" : "plain"}
                ariaPressed={on}
              >
                <span
                  aria-hidden="true"
                  className="h-4 w-4 rounded-full border border-(--wk-line-strong)"
                  style={{ backgroundColor: preset.color }}
                />
                {preset.label}
              </TouchButton>
            );
          })}
          <TouchButton onClick={() => void setActuator(WAKEUP_SLOTS.light, "off")} disabled={!wakeup.lightOn}>
            끄기
          </TouchButton>
        </Row>
      </ul>
      <Fab icon={<Power className="h-5 w-5" aria-hidden="true" />} label="모두 끄기" onClick={() => void wakeup.stopAll()} />
    </div>
  );
}
