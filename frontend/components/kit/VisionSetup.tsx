/**
 * 영상인식 설정 (키트 제공) — 감지 대상을 **코드가 아니라 데이터로** 바꿉니다.
 * =============================================================================
 * 여기서 바꾸면 비전 클라이언트가 몇 초 안에 새 대상을 찾기 시작합니다
 * (프로그램을 다시 켜지 않아도 됩니다 — docs/부록F 10장).
 *
 * 자동화 규칙의 `vision_label` 트리거에 쓴 라벨은 **자동으로 포함**되므로
 * 여기에 따로 적지 않아도 됩니다.
 */
"use client";

import { Camera, Loader2, Plus, X } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

/** 비전 클라이언트가 부팅할 때 신고한 검출기 하나 (부록F 10장). */
interface KnownDetector {
  name: string;
  labels: string[];
  description?: string;
  available: boolean;
  reason?: string;
}

interface VisionConfig {
  object_labels: string[];
  /** 돌릴 검출기 이름. 비어 있으면 "가진 것 전부"라는 뜻입니다. */
  detectors: string[];
  min_confidence: number;
  cooldown_seconds: number;
  source?: string;
  /** 비전 클라이언트가 신고한 검출기 — 화면은 이 목록을 보고 그립니다. */
  known_detectors?: KnownDetector[];
}

/** 사물 탐지 검출기의 이름. 위의 '감지 대상' 목록을 받는 주인입니다. */
const OBJECT_DETECTOR = "objects";

/** 학생이 고르기 쉽도록 자주 쓰는 COCO 클래스만 추려 둡니다 (직접 입력도 가능). */
const SUGGESTED: { label: string; ko: string }[] = [
  { label: "person", ko: "사람" },
  { label: "bottle", ko: "물병" },
  { label: "cup", ko: "컵" },
  { label: "book", ko: "책" },
  { label: "cell phone", ko: "휴대폰" },
  { label: "chair", ko: "의자" },
  { label: "laptop", ko: "노트북" },
  { label: "backpack", ko: "가방" },
  { label: "umbrella", ko: "우산" },
  { label: "clock", ko: "시계" },
  { label: "dog", ko: "개" },
  { label: "cat", ko: "고양이" },
];

const KO_OF = Object.fromEntries(SUGGESTED.map((s) => [s.label, s.ko]));

export default function VisionSetup() {
  const [config, setConfig] = useState<VisionConfig | null>(null);
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    const res = await apiFetch<VisionConfig>("/api/vision/config");
    if (res.ok && res.data) setConfig(res.data);
    else setMessage({ text: res.errorMessage ?? "설정을 읽지 못했습니다.", ok: false });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  const save = async (patch: Partial<VisionConfig>) => {
    setBusy(true);
    const res = await apiFetch<VisionConfig>("/api/vision/config", {
      method: "PUT",
      body: JSON.stringify(patch),
    });
    setBusy(false);
    if (!res.ok) {
      setMessage({ text: res.errorMessage ?? "저장하지 못했습니다.", ok: false });
      return;
    }
    if (res.data) setConfig(res.data);
    setMessage({ text: "저장했습니다. 비전 클라이언트가 몇 초 안에 반영합니다.", ok: true });
  };

  if (!config) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
        영상인식 설정을 불러오는 중…
      </div>
    );
  }

  const labels = config.object_labels ?? [];
  const known = config.known_detectors ?? [];
  const enabled = config.detectors ?? [];
  /** 설정이 비어 있으면 "전부 사용"이라는 뜻입니다. */
  const isRunning = (name: string) => enabled.length === 0 || enabled.includes(name);
  const toggleDetector = (name: string) => {
    const next = known
      .map((d) => d.name)
      .filter((n) => (n === name ? !isRunning(n) : isRunning(n)));
    // 전부 켜면 빈 목록으로 저장합니다 — 나중에 추가한 검출기도 자동으로 돌게 하려고요.
    void save({ detectors: next.length === known.length ? [] : next });
  };
  const toggleLabel = (label: string) =>
    void save({
      object_labels: labels.includes(label)
        ? labels.filter((l) => l !== label)
        : [...labels, label],
    });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">영상인식 설정</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          카메라가 무엇을 찾을지 정합니다. <strong className="text-slate-700">코드는 고치지 않습니다</strong> —
          비전 클라이언트가 몇 초 안에 새 대상을 적용합니다.
        </p>
      </div>

      {message && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            message.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Camera className="h-3.5 w-3.5 text-slate-500" />
          감지 대상 {busy && <Loader2 className="h-3 w-3 animate-spin" />}
        </div>

        {labels.length === 0 ? (
          <p className="mb-3 text-sm text-slate-500">선택된 대상이 없습니다 (기본값으로 동작합니다).</p>
        ) : (
          <div className="mb-4 flex flex-wrap gap-2">
            {labels.map((label) => (
              <span
                key={label}
                className="flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-sm text-sky-800"
              >
                {KO_OF[label] ?? label}
                <button
                  type="button"
                  onClick={() => toggleLabel(label)}
                  aria-label={`${label} 감지 대상에서 제거`}
                  className="opacity-60 hover:opacity-100"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="mb-3 text-sm text-slate-600">자주 쓰는 대상</div>
        <div className="mb-4 flex flex-wrap gap-2">
          {SUGGESTED.filter((s) => !labels.includes(s.label)).map((s) => (
            <button
              key={s.label}
              type="button"
              disabled={busy}
              onClick={() => toggleLabel(s.label)}
              className="flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 hover:border-slate-300 disabled:opacity-50"
            >
              <Plus className="h-3 w-3" />
              {s.ko}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={custom}
            placeholder="직접 입력 (COCO 클래스명, 예: teddy bear)"
            onChange={(e) => setCustom(e.target.value)}
            className="h-10 min-w-56 flex-1 rounded-lg border border-slate-200 px-3 text-sm focus:border-sky-400 focus:outline-none"
          />
          <button
            type="button"
            disabled={busy || !custom.trim()}
            onClick={() => {
              const label = custom.trim().toLowerCase();
              if (label && !labels.includes(label)) void save({ object_labels: [...labels, label] });
              setCustom("");
            }}
            className="h-10 rounded-lg border border-slate-200 px-4 text-sm font-medium text-slate-700 hover:border-slate-300 disabled:opacity-50"
          >
            추가
          </button>
        </div>
        <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
          자동화 규칙의 &apos;카메라가 무언가를 감지하면&apos; 트리거에 쓴 라벨은 여기에 적지 않아도
          자동으로 포함됩니다.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
          검출기 (감지 방법)
        </div>
        <p className="mb-3 text-xs text-slate-500">
          비전 클라이언트가 <code className="rounded bg-slate-100 px-1">vision/detectors/</code> 폴더에서
          찾은 것을 그대로 보여 줍니다. 팀이 파일을 하나 추가하면 여기에도 자동으로 나타납니다.
        </p>

        {known.length === 0 ? (
          <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            아직 신고된 검출기가 없습니다. 비전 클라이언트(<code>python vision/main.py</code>)를 켜면
            자기가 가진 검출기를 알려 주고, 그때 이 목록이 채워집니다.
          </p>
        ) : (
          <ul className="mb-1 space-y-2">
            {known.map((detector) => (
              <li key={detector.name} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  id={`detector-${detector.name}`}
                  checked={isRunning(detector.name)}
                  disabled={busy || !detector.available}
                  onChange={() => toggleDetector(detector.name)}
                  className="mt-0.5 h-4 w-4 cursor-pointer accent-sky-600 disabled:opacity-50"
                />
                <label htmlFor={`detector-${detector.name}`} className="text-sm">
                  <span className="font-medium text-slate-800">
                    {detector.description || detector.name}
                  </span>
                  <span className="ml-1.5 font-mono text-xs text-slate-400">{detector.name}</span>
                  {detector.name === OBJECT_DETECTOR ? (
                    <span className="block text-xs text-slate-500">위에서 고른 감지 대상을 찾습니다.</span>
                  ) : detector.labels.length > 0 ? (
                    <span className="block text-xs text-slate-500">
                      내보내는 라벨: {detector.labels.join(", ")}
                    </span>
                  ) : null}
                  {!detector.available && (
                    <span className="block text-xs text-rose-600">
                      사용할 수 없음{detector.reason ? ` — ${detector.reason}` : ""}
                    </span>
                  )}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
          감지 민감도
        </div>

        <SliderRow
          label="최소 신뢰도"
          hint="이보다 확신이 낮으면 보고하지 않습니다. 오감지가 많으면 올리세요."
          value={config.min_confidence}
          min={0.1}
          max={0.95}
          step={0.05}
          format={(v) => `${Math.round(v * 100)}%`}
          disabled={busy}
          onCommit={(v) => void save({ min_confidence: v })}
        />
        <SliderRow
          label="보고 간격"
          hint="같은 상태를 다시 보고하기까지 기다리는 시간입니다."
          value={config.cooldown_seconds}
          min={0.5}
          max={10}
          step={0.5}
          format={(v) => `${v.toFixed(1)}초`}
          disabled={busy}
          onCommit={(v) => void save({ cooldown_seconds: v })}
        />
      </div>
    </div>
  );
}

function SliderRow({
  label,
  hint,
  value,
  min,
  max,
  step,
  format,
  disabled,
  onCommit,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  disabled: boolean;
  onCommit: (value: number) => void;
}) {
  const [local, setLocal] = useState<number | null>(null);
  const shown = local ?? value;

  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium tabular-nums text-slate-800">{format(shown)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={shown}
        disabled={disabled}
        onChange={(e) => setLocal(Number(e.target.value))}
        onMouseUp={() => {
          if (local !== null) onCommit(local);
          setLocal(null);
        }}
        onTouchEnd={() => {
          if (local !== null) onCommit(local);
          setLocal(null);
        }}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-sky-600 disabled:opacity-50"
      />
      <p className="mt-1 text-xs text-slate-400">{hint}</p>
    </div>
  );
}
