/**
 * 기타 (wakeup 7인치 화면) — 카메라가 본 것 · 알림 · 지금 설정값
 */
"use client";

import { Settings2, X } from "lucide-react";
import Link from "next/link";
import React from "react";

import VisionLog from "@/components/team/wakeup/VisionLog";
import { API_BASE_URL } from "@/lib/api";
import type { WakeupApi } from "@/scenarios/useWakeup";

export default function MoreScreen({ wakeup }: { wakeup: WakeupApi }) {
  const { notices, dismissNotice, connected } = wakeup.scenario;
  const { device, config } = wakeup;
  const settings: [string, string][] = [
    ["미션", config.mode === "pattern" ? "패턴 그리기" : "가위바위보와 물건"],
    ["누워 있다고 볼 압력", `${device.bedPressureThreshold} 이상`],
    ["모션 베드", `${device.bedAngle}°까지, ${device.bedShakeSeconds}초마다`],
    ["커튼", `열기 ${device.curtainOpenAngle}°, 닫기 ${device.curtainCloseAngle}°`],
    ["기상 조명", `${device.lightColor}, 밝기 ${device.lightBrightness}`],
    ["백엔드", connected ? "연결됨" : "연결 대기"],
  ];

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-8 px-6 pb-4">
      <div className="min-h-0 overflow-y-auto">
        <VisionLog limit={8} />
      </div>

      <div className="flex min-h-0 flex-col gap-5 overflow-y-auto">
        <section>
          <h2 className="mb-2 text-lg font-medium">알림 {notices.length > 0 ? notices.length : ""}</h2>
          {notices.length === 0 ? (
            <p className="text-base text-(--wk-dim)">새 알림이 없어요.</p>
          ) : (
            <ul>
              {notices.map((notice) => (
                <li key={notice.id} className="flex items-center gap-2 border-b border-(--wk-line) text-base last:border-0">
                  <span className="flex-1 py-2">{notice.message}</span>
                  <button
                    type="button"
                    onClick={() => dismissNotice(notice.id)}
                    aria-label="이 알림 지우기"
                    className="wk-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-(--wk-dim) active:bg-(--wk-press)"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="mb-1 text-lg font-medium">지금 설정</h2>
          <dl className="text-base">
            {settings.map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3 border-b border-(--wk-line) py-2 last:border-0">
                <dt className="text-(--wk-dim)">{key}</dt>
                <dd className="truncate text-right">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-sm text-(--wk-dim)">
            값은 frontend/.env.local에서 바꿉니다.
            <span className="block truncate">백엔드 주소 {API_BASE_URL}</span>
          </p>
        </section>

        <Link
          href="/kit"
          className="wk-press flex min-h-12 items-center justify-center gap-2 rounded-[var(--wk-radius-control)] border border-(--wk-line-strong) text-base active:bg-(--wk-press)"
        >
          <Settings2 className="h-5 w-5 text-(--wk-dim)" aria-hidden="true" />
          하드웨어와 규칙 설정
        </Link>
      </div>
    </div>
  );
}
