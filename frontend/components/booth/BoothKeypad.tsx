"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";
import { apiUrl } from "@/utils/apiConfig";
import type { BoothAuthNotice } from "@/hooks/useBoothData";

/**
 * 부스 화면 키패드 (4x4)
 *
 * 부스 앞 실물 키패드(라즈베리파이, pi/main.py)와 **똑같이** 동작한다.
 *   - 숫자 4개를 누르면 곧바로 확인한다 (확인 키가 따로 없다)
 *   - `*` 는 지움, `#` 과 A~D 는 쓰지 않는다
 *   - 누르다 만 채로 8초가 지나면 지운다
 * 둘 다 같은 API(`POST /api/booth/verify-keypad`)를 부르므로, 개발 전반부(Mock)에는
 * 이 화면 키패드가 실물 키패드를 대신하고, 실물을 붙인 뒤에는 둘 다 쓸 수 있다.
 *
 * 예전에는 이 키패드가 선생님 화면(/admin)에 있었다. 비밀번호를 누르는 사람은
 * 부스 앞에 선 학생·관람객이므로 부스 화면으로 옮겼다.
 *
 * 실물 키패드로 누른 결과는 이 화면이 HTTP 응답을 받지 못한다. 그래서 서버가
 * 방송하는 인증 결과(notice)도 받아서 같은 자리에 띄운다.
 */

const KEY_ROWS = [
  ["1", "2", "3", "A"],
  ["4", "5", "6", "B"],
  ["7", "8", "9", "C"],
  ["*", "0", "#", "D"],
];

/** pi/main.py 의 KEYPAD_BUFFER_TIMEOUT_SEC 와 같다 */
const BUFFER_TIMEOUT_MS = 8_000;
/** 결과 문구를 보여 주는 시간 */
const RESULT_HOLD_MS = 6_000;
/** 이 화면에서 누른 직후에 오는 방송은 같은 결과이므로 겹쳐 띄우지 않는다 */
const OWN_RESULT_MS = 3_000;

type Tone = "idle" | "busy" | "ok" | "admin" | "warn" | "error";

const TONE_CLASS: Record<Tone, string> = {
  idle: "bg-canvas border-line-strong text-ink-2",
  busy: "bg-canvas border-line-strong text-ink-2",
  ok: "bg-free-soft border-free text-free",
  admin: "bg-brass-soft border-brass text-brass",
  warn: "bg-brass-soft border-brass text-ink",
  error: "bg-live-soft border-live text-live",
};

/* 키 누름 소리 — 실물 키패드처럼 삑. AudioContext 는 하나만 만들어 돌려 쓴다
   (누를 때마다 새로 만들면 브라우저가 정한 개수 제한에 걸린다). */
let beepCtx: AudioContext | null = null;
function beep(freq: number, ms: number) {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    beepCtx = beepCtx ?? new Ctx();
    if (beepCtx.state === "suspended") void beepCtx.resume();
    const osc = beepCtx.createOscillator();
    const gain = beepCtx.createGain();
    const t = beepCtx.currentTime;
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, t);
    gain.gain.setValueAtTime(0.08, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + ms / 1000);
    osc.connect(gain);
    gain.connect(beepCtx.destination);
    osc.start(t);
    osc.stop(t + ms / 1000);
  } catch {
    /* 소리가 안 나도 키패드는 동작한다 */
  }
}

interface BoothKeypadProps {
  /** 서버가 방송한 인증 결과 (실물 키패드로 누른 것 포함) */
  notice?: BoothAuthNotice | null;
  /** 확인이 끝났을 때 — 기기 상태를 곧바로 다시 받아 오게 한다 */
  onVerified?: () => void;
}

export function BoothKeypad({ notice = null, onVerified }: BoothKeypadProps) {
  const [digits, setDigits] = useState("");
  const [tone, setTone] = useState<Tone>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const digitsRef = useRef("");
  const busyRef = useRef(false);
  const lastOwnSubmitRef = useRef(0);
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 이 키패드가 그려지기 전에 온 방송은 지난 일이다 — 다시 띄우지 않는다
  const seenNoticeRef = useRef(notice?.seq ?? 0);

  /** 결과 문구를 잠시 보여 주고 처음 화면으로 돌아간다 */
  const showResult = useCallback((nextTone: Tone, text: string) => {
    setTone(nextTone);
    setMessage(text);
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    holdTimerRef.current = setTimeout(() => {
      setTone("idle");
      setMessage(null);
    }, RESULT_HOLD_MS);
  }, []);

  const clearDigits = useCallback(() => {
    digitsRef.current = "";
    setDigits("");
  }, []);

  const submit = useCallback(
    async (pin: string) => {
      busyRef.current = true;
      lastOwnSubmitRef.current = Date.now();
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
      setTone("busy");
      setMessage("확인 중입니다…");

      try {
        const res = await fetch(apiUrl("/api/booth/verify-keypad"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok) {
          const admin = body?.data?.mode === "admin";
          beep(1320, 120);
          showResult(
            admin ? "admin" : "ok",
            admin
              ? "관리자 인증 — 문이 열립니다 (노래방 전원은 켜지 않습니다)"
              : body?.data?.message ?? "인증 성공! 문이 열립니다"
          );
        } else {
          beep(220, 300);
          const code = body?.error?.code;
          showResult(
            code === "NOT_RESERVATION_TIME" ? "warn" : "error",
            body?.error?.message ??
              (res.status === 429
                ? "여러 번 틀려 잠시 막혔습니다. 잠시 뒤 다시 눌러 주세요."
                : "비밀번호가 맞지 않습니다.")
          );
        }
      } catch {
        beep(220, 300);
        showResult("error", "부스 서버에 연결할 수 없습니다. 선생님께 알려 주세요.");
      } finally {
        busyRef.current = false;
        clearDigits();
        onVerified?.();
      }
    },
    [clearDigits, onVerified, showResult]
  );

  const press = useCallback(
    (key: string) => {
      if (busyRef.current) return;
      if (key === "*") {
        beep(440, 90);
        clearDigits();
        if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
        setTone("idle");
        setMessage(null);
        return;
      }
      if (!/^[0-9]$/.test(key)) return; // # · A~D 는 실물 키패드에서도 쓰지 않는다

      beep(880, 60);
      const next = (digitsRef.current + key).slice(0, 4);
      digitsRef.current = next;
      setDigits(next);
      if (tone !== "idle") {
        if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
        setTone("idle");
        setMessage(null);
      }
      if (next.length === 4) void submit(next);
    },
    [clearDigits, submit, tone]
  );

  // 누르다 만 입력은 8초 뒤 지운다 (실물 키패드와 같다)
  useEffect(() => {
    if (!digits || digits.length >= 4) return;
    const id = setTimeout(clearDigits, BUFFER_TIMEOUT_MS);
    return () => clearTimeout(id);
  }, [digits, clearDigits]);

  // 부스 PC에 키보드가 붙어 있으면 숫자 키로도 누를 수 있다
  const pressRef = useRef(press);
  useEffect(() => {
    pressRef.current = press;
  }, [press]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (/^[0-9]$/.test(e.key)) pressRef.current(e.key);
      else if (e.key === "*" || e.key === "Escape" || e.key === "Backspace" || e.key === "Delete") {
        pressRef.current("*");
      } else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // 실물 키패드로 누른 결과 (서버 방송)
  useEffect(() => {
    if (!notice || notice.seq <= seenNoticeRef.current) return;
    seenNoticeRef.current = notice.seq;
    if (Date.now() - lastOwnSubmitRef.current < OWN_RESULT_MS) return;
    const nextTone: Tone = notice.success
      ? notice.mode === "admin"
        ? "admin"
        : "ok"
      : notice.reason === "not_now"
      ? "warn"
      : "error";
    const id = setTimeout(() => showResult(nextTone, notice.message), 0);
    return () => clearTimeout(id);
  }, [notice, showResult]);

  useEffect(
    () => () => {
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    },
    []
  );

  return (
    <div className="w-full max-w-[19rem] rounded-2xl bg-raised border border-line p-4 space-y-3">
      <div className="flex items-center gap-2">
        <KeyRound className="w-4 h-4 text-brass shrink-0" aria-hidden />
        <span className="text-sm font-bold text-ink">도어 키패드</span>
        <span className="ml-auto text-[11px] text-ink-3">4자리 · 자동 확인</span>
      </div>

      {/* 표시창 — 숫자는 보여 주지 않고 몇 개 눌렀는지만 */}
      <div
        className={`rounded-xl border px-3 py-3 min-h-[5.5rem] flex flex-col items-center justify-center text-center transition-colors ${TONE_CLASS[tone]}`}
        role="status"
        aria-live="polite"
        data-testid="keypad-display"
      >
        {message ? (
          <p className="text-sm font-bold leading-snug flex items-center gap-1.5">
            {tone === "busy" && <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden />}
            {message}
          </p>
        ) : (
          <>
            <span className="text-xs text-ink-3">예약 비밀번호 또는 체험권 비밀번호</span>
            <span className="mt-1.5 flex gap-3" aria-label={`${digits.length}자리 입력됨`}>
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className={`w-3.5 h-3.5 rounded-full border-2 ${
                    i < digits.length ? "bg-ink border-ink" : "border-line-strong"
                  }`}
                />
              ))}
            </span>
          </>
        )}
      </div>

      {/* 4x4 버튼 — 실물 키패드와 같은 배치 */}
      <div className="grid grid-cols-4 gap-2">
        {KEY_ROWS.flat().map((key) => {
          const isDigit = /^[0-9]$/.test(key);
          const isClear = key === "*";
          const usable = isDigit || isClear;
          return (
            <button
              key={key}
              type="button"
              onClick={() => press(key)}
              disabled={!usable}
              aria-label={isClear ? "지움" : usable ? key : `${key} (사용하지 않는 키)`}
              className={`h-14 rounded-xl border font-mono tnum transition-all select-none flex flex-col items-center justify-center leading-none ${
                isDigit
                  ? "bg-surface border-line-strong text-ink text-2xl font-bold hover:bg-canvas active:scale-95 cursor-pointer"
                  : isClear
                  ? "bg-live-soft border-live/40 text-live text-lg font-bold hover:bg-live-soft/70 active:scale-95 cursor-pointer"
                  : "bg-transparent border-line text-ink-3/50 text-base cursor-default"
              }`}
            >
              {key}
              {isClear && <span className="text-[10px] font-sans font-bold mt-0.5">지움</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
