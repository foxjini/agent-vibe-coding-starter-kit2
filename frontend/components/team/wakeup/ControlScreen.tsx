/**
 * 제어 화면 (wakeup 7인치 화면) — 알람 · 커튼 · 모션 베드 · 조명을 손가락으로 직접 움직입니다.
 * 오른쪽 아래 "모두 끄기"(FAB)는 알람·조명을 끄고 모션 베드를 0°로 돌립니다.
 */
"use client";

import { BedDouble, Bell, Blinds, Lightbulb, Power } from "lucide-react";
import React from "react";

import Fab from "@/components/team/wakeup/Fab";
import { MissingSlot, Pill, Tile, TouchButton } from "@/components/team/wakeup/Tile";
import { asObject, numberFrom, slotLabel } from "@/lib/slots";
import type { WakeupApi } from "@/scenarios/useWakeup";
import { WAKEUP_SLOTS } from "@/scenarios/useWakeup";

/** 조명 색 버튼 — 첫 번째는 .env의 기상 조명 색 */
function lightPresets(defaultColor: string) {
  return [
    { label: "기상", color: defaultColor },
    { label: "흰색", color: "#ffffff" },
    { label: "파랑", color: "#4aa3ff" },
  ];
}

function servoAngle(wakeup: WakeupApi, slotId: string): number | null {
  const slot = wakeup.scenario.slotOf(slotId);
  const angle = numberFrom(slot?.current_value ?? slot?.desired_value, ["angle"], Number.NaN);
  return Number.isFinite(angle) ? angle : null;
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
  const lightColor = String(asObject(light?.desired_value)?.color ?? "");

  return (
    <div className="relative h-full">
      <div className="grid h-full grid-cols-2 grid-rows-2 gap-3 overflow-y-auto p-3 pb-[76px]">
        {/* 알람(부저) — 울리면 기상 미션이 시작됩니다 */}
        <Tile
          icon={<Bell className="h-5 w-5" />}
          title={buzzer ? slotLabel(buzzer) : "알람 부저"}
          badge={<Pill on={wakeup.ringing}>{wakeup.ringing ? "울리는 중" : "조용함"}</Pill>}
          muted={!buzzer}
        >
          {buzzer ? (
            <div className="mt-auto grid grid-cols-2 gap-2">
              <TouchButton onClick={() => void wakeup.startAlarm()} disabled={wakeup.ringing} tone="soft">
                울리기
              </TouchButton>
              <TouchButton onClick={() => void wakeup.stopAlarm()} disabled={!wakeup.ringing}>
                끄기
              </TouchButton>
            </div>
          ) : (
            <MissingSlot slotId={WAKEUP_SLOTS.buzzer} />
          )}
        </Tile>

        {/* 커튼 서보 */}
        <Tile
          icon={<Blinds className="h-5 w-5" />}
          title={curtain ? slotLabel(curtain) : "커튼"}
          badge={curtainAngle !== null ? <Pill on={curtainAngle > device.curtainCloseAngle}>{curtainAngle}°</Pill> : null}
          muted={!curtain}
        >
          {curtain ? (
            <div className="mt-auto grid grid-cols-2 gap-2">
              <TouchButton
                onClick={() => void setActuator(WAKEUP_SLOTS.curtain, "move", { angle: device.curtainOpenAngle })}
                tone="soft"
              >
                열기
              </TouchButton>
              <TouchButton
                onClick={() => void setActuator(WAKEUP_SLOTS.curtain, "move", { angle: device.curtainCloseAngle })}
              >
                닫기
              </TouchButton>
            </div>
          ) : (
            <MissingSlot slotId={WAKEUP_SLOTS.curtain} />
          )}
        </Tile>

        {/* 모션 베드 서보 */}
        <Tile
          icon={<BedDouble className="h-5 w-5" />}
          title={bed ? slotLabel(bed) : "모션 베드"}
          badge={
            <Pill on={wakeup.bedShaking}>
              {wakeup.bedShaking ? "흔드는 중" : bedAngle !== null ? `${bedAngle}°` : "대기"}
            </Pill>
          }
          muted={!bed}
        >
          {bed ? (
            <div className="mt-auto grid grid-cols-2 gap-2">
              <TouchButton
                onClick={() => void setActuator(WAKEUP_SLOTS.bed, "move", { angle: device.bedAngle })}
                disabled={wakeup.bedShaking}
                tone="soft"
              >
                올리기 {device.bedAngle}°
              </TouchButton>
              <TouchButton
                onClick={() => void setActuator(WAKEUP_SLOTS.bed, "move", { angle: 0 })}
                disabled={wakeup.bedShaking}
              >
                내리기 0°
              </TouchButton>
            </div>
          ) : (
            <MissingSlot slotId={WAKEUP_SLOTS.bed} />
          )}
        </Tile>

        {/* 조명 네오픽셀 */}
        <Tile
          icon={<Lightbulb className="h-5 w-5" />}
          title={light ? slotLabel(light) : "조명"}
          badge={<Pill on={wakeup.lightOn}>{wakeup.lightOn ? "켜짐" : "꺼짐"}</Pill>}
          muted={!light}
        >
          {light ? (
            <div className="mt-auto grid grid-cols-4 gap-2">
              {lightPresets(device.lightColor).map((preset) => (
                <TouchButton
                  key={preset.label}
                  onClick={() =>
                    void setActuator(WAKEUP_SLOTS.light, "on", {
                      color: preset.color,
                      brightness: device.lightBrightness,
                    })
                  }
                  tone={wakeup.lightOn && lightColor === preset.color ? "soft" : "plain"}
                  ariaLabel={`조명 ${preset.label}`}
                  className="flex-col gap-0.5 px-1 text-sm"
                >
                  <span
                    className="h-5 w-5 rounded-full border border-slate-300"
                    style={{ backgroundColor: preset.color }}
                  />
                  {preset.label}
                </TouchButton>
              ))}
              <TouchButton
                onClick={() => void setActuator(WAKEUP_SLOTS.light, "off")}
                ariaLabel="조명 끄기"
                className="text-sm"
              >
                끄기
              </TouchButton>
            </div>
          ) : (
            <MissingSlot slotId={WAKEUP_SLOTS.light} />
          )}
        </Tile>
      </div>
      <Fab icon={<Power className="h-5 w-5" />} label="모두 끄기" onClick={() => void wakeup.stopAll()} />
    </div>
  );
}
