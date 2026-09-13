/**
 * 우리 팀 화면 (app/page.tsx) — ★ 팀이 자유롭게 고치는 파일
 * =============================================================================
 * 4개 팀(wakeup · classroom · study · subway)이 **공통으로 여기서 시작합니다.**
 * 지금 상태로도 바로 동작합니다 — 배치표에 적은 부품이 카드로 나오고,
 * 카메라가 감지한 것이 로그에 들어옵니다.
 *
 *   키트가 주는 것   슬롯 카드 자동 생성(SlotGrid), 실시간 상태, 알림, 비전 로그
 *   팀이 만드는 것   아래 "우리 팀 시나리오" 자리에 들어갈 화면과 판정 규칙
 *
 * ── 시나리오를 넣는 방법 (docs/00 매뉴얼 5장) ────────────────────────────────
 *  1. 판정 규칙을 `scenarios/<우리팀>Engine.ts`에 **React 없는 순수 함수**로 씁니다.
 *     (그러면 브라우저 없이 `node --experimental-strip-types`로 테스트할 수 있습니다)
 *  2. 진행을 `scenarios/use<우리팀>.ts`에 `useScenario()`를 써서 씁니다.
 *  3. 이 파일의 "우리 팀 시나리오" 자리에 그 훅을 불러 화면을 그립니다.
 *
 * 완성된 본보기가 `/wakeup` 주소에 있습니다 (`app/wakeup/page.tsx`).
 * 구조만 보고, 우리 팀 것은 우리 팀 시나리오로 만드세요.
 *
 * 하드웨어 구성·자동화 규칙·영상인식 설정은 `/kit`에 있습니다 (고치지 않아도 됩니다).
 */
"use client";

import { Bell, Lightbulb, Settings2, Wifi, WifiOff, X } from "lucide-react";
import Link from "next/link";
import React from "react";

import SlotGrid from "@/components/kit/SlotGrid";
import VisionLogCard from "@/components/kit/VisionLogCard";
import { useScenario } from "@/lib/scenario";

/** 팀 이름은 코드가 아니라 `frontend/.env.local`의 NEXT_PUBLIC_TEAM_NAME에서 옵니다. */
const TEAM_NAME = process.env.NEXT_PUBLIC_TEAM_NAME || "우리 팀 IoT 시스템";
const TEAM_TAGLINE =
  process.env.NEXT_PUBLIC_TEAM_TAGLINE ||
  "배치표에 적은 부품이 아래에 자동으로 나타납니다";

const NOTICE_STYLES: Record<string, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  alert: "border-rose-200 bg-rose-50 text-rose-800",
};

export default function TeamDashboardPage() {
  // 시나리오 SDK — 여기서 받은 것으로 화면을 그립니다.
  // 쓸 수 있는 것: slots · connected · setActuator · onSensor · onVision
  //               onSlotChange · after · notify · serverTimer  (lib/scenario.ts)
  const { slots, connected, notices, dismissNotice, setActuator } = useScenario();

  const sensorCount = slots.filter((slot) => slot.role !== "actuator").length;
  const actuatorCount = slots.filter((slot) => slot.role === "actuator").length;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* 머리말 — 팀 이름은 .env.local에서 바꿉니다 */}
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{TEAM_NAME}</h1>
            <p className="mt-1 text-sm text-slate-500">{TEAM_TAGLINE}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`flex h-9 items-center gap-1.5 rounded-full border px-3 text-sm font-medium ${
                connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
              {connected ? "실시간 연결됨" : "연결 대기 중"}
            </span>
            <Link
              href="/kit"
              className="flex h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 hover:border-slate-300"
            >
              <Settings2 className="h-4 w-4" />
              하드웨어·규칙 설정
            </Link>
          </div>
        </header>

        {/* 알림 — notify()로 띄운 것과 자동화 규칙의 notify 액션이 여기로 들어옵니다 */}
        {notices.length > 0 && (
          <div className="mb-5 space-y-2">
            {notices.map((notice) => (
              <div
                key={notice.id}
                className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${
                  NOTICE_STYLES[notice.level] ?? NOTICE_STYLES.info
                }`}
              >
                <span className="flex items-start gap-2">
                  <Bell className="mt-0.5 h-4 w-4 shrink-0" />
                  {notice.message}
                </span>
                <button
                  type="button"
                  onClick={() => dismissNotice(notice.id)}
                  aria-label="알림 닫기"
                  className="shrink-0 opacity-60 hover:opacity-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ======================================================================
            ★ 우리 팀 시나리오 자리 — 이 블록을 우리 팀 화면으로 바꾸세요.
            아래 안내 카드는 지우고, 만든 시나리오 훅과 카드를 넣으면 됩니다.
            ====================================================================== */}
        <ScenarioPlaceholder
          sensorCount={sensorCount}
          actuatorCount={actuatorCount}
          connected={connected}
        />
        {/* ===================== 여기까지가 우리 팀 시나리오 ===================== */}

        {/* 하드웨어 — 배치표가 바뀌면 카드도 알아서 바뀝니다 (이 줄은 고치지 않아도 됩니다) */}
        <SlotGrid
          slots={slots}
          onControl={setActuator}
          emptyHint={
            <>
              라즈베리파이에서 <code className="rounded bg-white px-1 py-0.5">python daemon.py</code>를
              실행하면 <code className="rounded bg-white px-1 py-0.5">pi/slot_map.py</code>에 적은
              부품이 여기에 나타납니다.
            </>
          }
        />

        <section className="mt-8">
          <VisionLogCard />
        </section>
      </div>
    </main>
  );
}

/**
 * 시나리오를 아직 만들지 않았을 때 보여 주는 안내 카드입니다.
 * **우리 팀 시나리오를 만들면 이 컴포넌트는 지우세요.**
 */
function ScenarioPlaceholder({
  sensorCount,
  actuatorCount,
  connected,
}: {
  sensorCount: number;
  actuatorCount: number;
  connected: boolean;
}) {
  const ready = connected && sensorCount + actuatorCount > 0;

  return (
    <section className="mb-8 rounded-xl border border-dashed border-slate-300 bg-white p-6">
      <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
        <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
        우리 팀 시나리오를 여기에 만듭니다
      </div>

      <p className="text-sm text-slate-600">
        지금은 키트가 주는 것만 보이는 상태입니다 —{" "}
        <strong className="text-slate-800">
          센서 {sensorCount}개 · 액추에이터 {actuatorCount}개
        </strong>
        가 아래에 카드로 나와 있고, {connected ? "실시간 연결도 되어 있습니다." : "아직 백엔드에 연결되지 않았습니다."}
      </p>

      {!ready && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {!connected
            ? "백엔드(uvicorn)가 실행 중인지, frontend/.env.local의 NEXT_PUBLIC_API_BASE_URL이 맞는지 확인하세요."
            : "라즈베리파이에서 python daemon.py를 실행하면 부품 카드가 나타납니다."}
        </p>
      )}

      <ol className="mt-4 space-y-1.5 text-sm text-slate-600">
        <li>
          <strong className="text-slate-800">1.</strong> 판정 규칙을{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">scenarios/우리팀Engine.ts</code>에
          React 없는 순수 함수로 씁니다.
        </li>
        <li>
          <strong className="text-slate-800">2.</strong> 진행을{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">scenarios/use우리팀.ts</code>에{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">useScenario()</code>로 씁니다.
        </li>
        <li>
          <strong className="text-slate-800">3.</strong>{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">app/page.tsx</code>의 이 블록을
          우리 팀 카드로 바꿉니다.
        </li>
      </ol>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
        <Link
          href="/wakeup"
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-300"
        >
          완성된 본보기 보기 (wakeup 팀)
        </Link>
        <span className="text-xs text-slate-400">
          자세한 방법은 docs/00 매뉴얼 5장 · 화면 이름은 .env.local의 NEXT_PUBLIC_TEAM_NAME
        </span>
      </div>
    </section>
  );
}
