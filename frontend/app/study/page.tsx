/**
 * study 팀 화면 (app/study/page.tsx) — ★ study 팀이 고치는 파일
 * =============================================================================
 * **한 사람의 집중도를 봅니다.** FHD 웹캠 한 대로 얼굴을 보고,
 * 눈이 감겼는지 · 고개를 숙였는지 · 시선이 벗어났는지를 재서 점수로 바꿉니다.
 *
 *   카메라   vision/detectors/study_focus.py   ← 재기만 함
 *   판정     scenarios/studyEngine.ts          ← 졸음·딴짓을 여기서 정함
 *   값 받기  scenarios/useStudy.ts
 *   화면     이 파일 + components/team/FocusPanel.tsx
 *
 * 이 주소(`/study`)는 **본보기**입니다. 우리 팀 기본 화면으로 쓰려면
 * 이 파일을 `app/page.tsx`로 복사하세요 (다른 팀 화면은 그대로 둡니다).
 *
 * 준비물
 * ------
 *  1. FHD 웹캠을 얼굴에서 0.5~1.0m 앞에 둡니다
 *  2. `vision/.env` 에  CAMERA_WIDTH=1920  CAMERA_HEIGHT=1080
 *  3. `pip install mediapipe`
 *  4. `/kit` → 영상인식 설정에서 `study_focus`를 켭니다
 */
"use client";

import { AlertTriangle, Camera, RotateCcw, Settings2, Wifi, WifiOff, X } from "lucide-react";
import Link from "next/link";
import React from "react";

import SlotGrid from "@/components/kit/SlotGrid";
import VisionLogCard from "@/components/kit/VisionLogCard";
import {
  MeasureRow,
  NowCard,
  SummaryGrid,
  Timeline,
} from "@/components/team/FocusPanel";
import { GOOD_FACE_PX, formatDuration } from "@/scenarios/studyEngine";
import { useStudy, useStudyActuators } from "@/scenarios/useStudy";

const TEAM_NAME = process.env.NEXT_PUBLIC_TEAM_NAME || "집중 관리 책상";

/**
 * 졸았을 때 울릴 장치 · 자리를 비우면 끌 장치.
 * `pi/slot_map.py`에 적은 슬롯 번호와 맞추세요. 비워 두면 아무것도 하지 않습니다.
 */
const DROWSY_SLOT = "actuator_03";   // 방석 진동 모터
const LAMP_SLOT = "actuator_04";     // 스탠드 전원 릴레이

export default function StudyPage() {
  // ⚠️ `useScenario()`를 여기서 또 부르면 안 됩니다 — 부를 때마다 WebSocket·구독·알림이
  //    **따로** 생겨서, useStudy가 띄운 알림이 이 화면에 나타나지 않습니다.
  //    한 화면에 시나리오 훅은 하나입니다.
  const study = useStudy();
  const { slots, notices, dismissNotice, setActuator } = study.scenario;

  // 장치 연동은 **꺼진 상태로 시작**합니다 — /kit 규칙과 겹치지 않게.
  const [driveDevices, setDriveDevices] = React.useState(false);
  useStudyActuators(setActuator, study.state, driveDevices, {
    drowsy: DROWSY_SLOT,
    away: LAMP_SLOT,
  });

  const m = study.measure;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* 머리말 */}
        <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{TEAM_NAME}</h1>
            <p className="mt-1 text-sm text-slate-500">
              웹캠으로 눈·고개·시선을 보고 집중도를 기록합니다
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`flex h-9 items-center gap-1.5 rounded-full border px-3 text-sm font-medium ${
                study.connected
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {study.connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
              {study.connected ? "실시간 연결됨" : "연결 대기 중"}
            </span>
            <Link
              href="/kit"
              className="flex h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 hover:border-slate-300"
            >
              <Settings2 className="h-4 w-4" />
              설정
            </Link>
          </div>
        </header>

        {/* 알림 */}
        {notices.length > 0 && (
          <div className="mb-5 space-y-2">
            {notices.map((notice) => (
              <div
                key={notice.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
              >
                <span>{notice.message}</span>
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

        {/* 설치가 잘못됐을 때 — 여기서 막히는 학생이 가장 많습니다 */}
        <SetupHints
          signalLost={study.signalLost}
          hasMeasure={!!m}
          cameraTooFar={study.cameraTooFar}
          facePx={m?.facePx ?? 0}
        />

        {/* ★ 3초 안에 보여야 할 것 */}
        <div className="mb-6 grid gap-4 lg:grid-cols-[2fr_3fr]">
          <NowCard
            state={study.state}
            score={study.score}
            calibrating={study.calibrating}
          />

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-2 text-sm font-semibold text-slate-700">
              카메라가 보고 있는 것
            </h2>
            {m ? (
              <>
                <MeasureRow
                  label="눈이 떠 있는 정도"
                  value={m.eyesOpen.toFixed(2)}
                  hint="1.0이 완전히 뜬 상태"
                />
                <MeasureRow
                  label="이어서 감고 있던 시간"
                  value={`${m.closedRun.toFixed(1)}초`}
                  hint="깜빡임은 0.4초 이하"
                />
                <MeasureRow label="고개를 숙인 비율" value={`${Math.round(m.headDown * 100)}%`} />
                <MeasureRow label="시선이 벗어난 비율" value={`${Math.round(m.lookAway * 100)}%`} />
                <MeasureRow
                  label="얼굴 크기"
                  value={`${m.facePx}px`}
                  hint={`${GOOD_FACE_PX}px 이상 권장`}
                />
                <MeasureRow label="이번에 본 프레임" value={`${m.samples}장`} />
              </>
            ) : (
              <p className="py-6 text-center text-sm text-slate-400">
                아직 카메라에서 온 것이 없습니다.
              </p>
            )}
          </section>
        </div>

        {/* 시간에 따른 기록 */}
        <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">
              기록 · {formatDuration(study.summary.elapsed)} 경과
            </h2>
            <button
              type="button"
              onClick={study.resetSession}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-slate-300"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              새로 시작
            </button>
          </div>
          <Timeline session={study.session} />
        </section>

        <section className="mb-6">
          <SummaryGrid summary={study.summary} />
          <p className="mt-2 text-xs text-slate-400">
            기록은 <strong>이 브라우저에만</strong> 남습니다 — 카메라가 보낸 자세한 값은
            서버에 저장되지 않습니다. 다른 PC에서 열면 이어지지 않습니다.
          </p>
        </section>

        {/* 장치 연동 */}
        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={driveDevices}
              onChange={(e) => setDriveDevices(e.target.checked)}
              className="mt-1 h-4 w-4"
            />
            <span>
              <span className="text-sm font-medium text-slate-800">
                졸면 방석을 울리고, 자리를 비우면 스탠드를 끕니다
              </span>
              <span className="mt-1 block text-xs text-slate-500">
                같은 일을 <Link href="/kit" className="underline">/kit 규칙 편집기</Link>에서
                코드 없이 만들 수도 있습니다 (트리거 <code>eyes_closed</code> → 액션{" "}
                <code>{DROWSY_SLOT}</code> 켜기). <strong>둘 중 하나만 쓰세요</strong> —
                둘 다 켜면 서로 껐다 켰다 하며 싸웁니다.
              </span>
            </span>
          </label>
        </section>

        {/* 하드웨어 — 배치표가 바뀌면 카드도 알아서 바뀝니다 */}
        <SlotGrid
          slots={slots}
          onControl={setActuator}
          emptyHint={
            <>
              라즈베리파이에서 <code className="rounded bg-white px-1 py-0.5">python daemon.py</code>를
              실행하면 부품이 여기에 나타납니다.
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
 * 안 될 때 무엇을 해야 하는지 알려 줍니다.
 * "화면이 비어 있는데 왜인지 모르겠다"가 가장 흔한 막힘이라 여기에 붙였습니다.
 */
function SetupHints({
  signalLost,
  hasMeasure,
  cameraTooFar,
  facePx,
}: {
  signalLost: boolean;
  hasMeasure: boolean;
  cameraTooFar: boolean;
  facePx: number;
}) {
  const hints: { tone: string; Icon: React.ElementType; text: React.ReactNode }[] = [];

  if (!hasMeasure) {
    hints.push({
      tone: "border-sky-200 bg-sky-50 text-sky-800",
      Icon: Camera,
      text: (
        <>
          카메라에서 아직 소식이 없습니다. <code>vision</code> 폴더에서{" "}
          <code>python main.py</code>를 실행하고, <Link href="/kit" className="underline">/kit</Link>{" "}
          영상인식 설정에서 <strong>study_focus</strong>를 켰는지 확인하세요.
        </>
      ),
    });
  } else if (signalLost) {
    hints.push({
      tone: "border-amber-200 bg-amber-50 text-amber-800",
      Icon: AlertTriangle,
      text: <>카메라 소식이 끊겼습니다. <code>python main.py</code> 창이 아직 떠 있는지 보세요.</>,
    });
  }

  if (cameraTooFar) {
    hints.push({
      tone: "border-amber-200 bg-amber-50 text-amber-800",
      Icon: AlertTriangle,
      text: (
        <>
          얼굴이 <strong>{facePx}px</strong>로 작게 잡혀 눈을 정확히 재기 어렵습니다
          ({GOOD_FACE_PX}px 이상 권장). 카메라를 더 가까이 두거나{" "}
          <code>vision/.env</code>에 <code>CAMERA_WIDTH=1920 CAMERA_HEIGHT=1080</code>을 넣으세요.
        </>
      ),
    });
  }

  if (hints.length === 0) return null;

  return (
    <div className="mb-6 space-y-2">
      {hints.map((hint, i) => (
        <div key={i} className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${hint.tone}`}>
          <hint.Icon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{hint.text}</span>
        </div>
      ))}
    </div>
  );
}
