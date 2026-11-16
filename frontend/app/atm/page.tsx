"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Banknote,
  CheckCircle2,
  Headset,
  Info,
  KeyRound,
  Loader2,
  QrCode,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Timer,
  WifiOff,
} from "lucide-react";
import { VoiceToggle } from "@/components/VoiceToggle";
import { useSpeech } from "@/hooks/useSpeech";
import { ApiError, atmDaemon } from "@/lib/api";
import type { AtmDaemonState } from "@/types/api";

const POLL_INTERVAL_MS = 1000;
// 숫자와 함께 읽는 법도 적는다 — 0이 많은 숫자는 어르신이 자릿수를 세다 틀리기 쉽다
const AMOUNTS: { value: number; reading: string }[] = [
  { value: 50_000, reading: "오만 원" },
  { value: 100_000, reading: "십만 원" },
  { value: 300_000, reading: "삼십만 원" },
  { value: 500_000, reading: "오십만 원" },
];

type NoticeTone = "info" | "busy" | "success" | "warn";

/**
 * ATM 7인치 터치 디스플레이 (FR-10).
 * 라즈베리파이 로컬 데몬(pi/main.py)의 /state를 폴링한다 — 위험 판단과 현금 배출
 * 제어는 전부 파이 안에서 끝나므로 이 화면은 상태를 크게 보여주는 역할만 한다.
 */
export default function AtmScreen() {
  const [state, setState] = useState<AtmDaemonState | null>(null);
  const [daemonError, setDaemonError] = useState<string | null>(null);
  const [notice, setNoticeText] = useState<string | null>(null);
  const [noticeTone, setNoticeTone] = useState<NoticeTone>("info");
  const setNotice = useCallback((text: string | null, tone: NoticeTone = "info") => {
    setNoticeText(text);
    setNoticeTone(tone);
  }, []);
  // '처음으로'가 거절당했을 때만 직원 해제 버튼을 꺼내 놓는다 (평소에는 없다)
  const [askStaff, setAskStaff] = useState(false);
  // 실기기에서는 배출에 1.4초가 걸린다(배출구 덮개를 열고·기다리고·닫고). Mock에서는 즉시라
  // 눈치채지 못했지만, 파이에서는 그동안 화면이 아무 말도 하지 않으면 관람객이
  // 버튼을 다시 누른다.
  const [busy, setBusy] = useState(false);
  const speech = useSpeech();
  const lastStateRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await atmDaemon.get<AtmDaemonState>("/state");
      // 상태가 바뀌면 직전 안내(예: "현금이 나오지 않습니다")는 치운다.
      // 상담원이 제한을 풀어 화면이 초록으로 바뀌었는데 그 문구가 남아 있으면
      // 어르신은 아직 막혀 있다고 읽는다.
      if (lastStateRef.current !== null && lastStateRef.current !== next.state) {
        setNotice(null);
        setAskStaff(false);
      }
      lastStateRef.current = next.state;
      setState(next);
      setDaemonError(null);
    } catch (err) {
      setDaemonError(
        err instanceof ApiError ? err.message : "ATM 제어 장치에 연결할 수 없습니다.",
      );
    }
  }, [setNotice]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  // 지금 화면에서 가장 중요한 한 문장을 읽는다.
  // 방금 일어난 일(notice) > 오류 > 평상시 안내 순서다.
  useEffect(() => {
    if (notice) {
      speech.announce(`notice:${notice}`, notice);
      return;
    }
    if (state?.last_error) {
      speech.announce(`error:${state.last_error}`, state.last_error);
      return;
    }
    if (state) {
      speech.announce(
        `state:${state.state}:${state.callcenter_resolution ?? "-"}`,
        state.guidance,
      );
    }
  }, [notice, state, speech]);

  const withdraw = async (amount: number) => {
    if (busy) return;
    setBusy(true);
    // 나올지 안 나올지 아직 모르므로 결과를 앞질러 말하지 않는다
    setNotice("잠시만 기다려 주세요", "busy");
    try {
      const next = await atmDaemon.post<AtmDaemonState & { dispensed: boolean }>("/withdraw", {
        amount,
      });
      setState(next);
      if (next.dispensed) {
        setNotice(`${amount.toLocaleString("ko-KR")}원을 배출했습니다.`, "success");
      } else {
        setNotice("현금이 나오지 않습니다. 보이스피싱 위험으로 출금이 멈춰 있습니다.", "warn");
      }
    } catch (err) {
      setNotice(
        err instanceof ApiError ? err.message : "출금 요청을 처리하지 못했습니다.",
        "warn",
      );
    } finally {
      setBusy(false);
    }
  };

  const callCenter = async () => {
    setState(await atmDaemon.post<AtmDaemonState>("/call-center"));
    setNotice(null);
  };

  // '처음으로'는 화면을 정리하는 버튼이지 제한을 푸는 버튼이 아니다.
  // 이 버튼으로 차단이 풀린다면 막힌 사람은 그냥 이걸 누르면 그만이다.
  const reset = async () => {
    const next = await atmDaemon.post<AtmDaemonState & { reset: boolean }>("/reset");
    setState(next);
    if (next.reset) {
      setNotice(null);
      setAskStaff(false);
      return;
    }
    // 왜 거절됐는지에 따라 다르게 말한다 — 설정 오류인데 "보이스피싱"이라고
    // 하면, 고쳐야 할 사람이 엉뚱한 곳을 뒤진다
    if (next.state === "CALL_CENTER") {
      setNotice("상담원이 확인 중입니다. 확인이 끝나거나 은행 직원이 해제해야 열립니다.", "warn");
    } else if (next.restricted) {
      setNotice("보이스피싱 확인으로 잠긴 화면입니다. 은행 직원이 확인해야 다시 열립니다.", "warn");
    } else {
      setNotice("설정 오류로 멈춰 있습니다. 아래 안내대로 고친 뒤 다시 시작해 주세요.", "warn");
    }
    setAskStaff(true);
  };

  // 은행 직원 확인. 서버의 판정을 지우는 것이 아니라 기계를 다음 사람에게 넘기는
  // 것이므로, 같은 QR을 다시 비추면 즉시 다시 막힌다.
  const staffRelease = async () => {
    setState(await atmDaemon.post<AtmDaemonState>("/staff-release"));
    setNotice(null);
    setAskStaff(false);
  };

  if (daemonError) {
    return (
      <AtmShell tone="halted">
        <CenterPanel
          icon={<WifiOff size={56} aria-hidden />}
          tone="neutral"
          title="ATM 제어 장치에 연결할 수 없습니다"
          detail={daemonError}
        />
      </AtmShell>
    );
  }

  if (!state) {
    return (
      <AtmShell tone="halted">
        <CenterPanel
          icon={<Loader2 size={56} className="animate-spin" aria-hidden />}
          tone="neutral"
          title="준비 중입니다"
        />
      </AtmShell>
    );
  }

  // 제한 여부는 데몬이 판단한 값을 그대로 쓴다 — 같은 규칙을 화면에서 또 적으면
  // 언젠가 둘이 어긋난다 (어긋나는 순간 화면이 거짓말을 한다)
  const blocked = state.restricted;
  // 출금 화면도 차단 화면도 아닌 상태 — 확인을 하지 못해 잠시 멈춘 화면이다.
  const halted = !state.can_withdraw && !blocked;

  const footer = (
    <>
      <span className="font-mono text-base text-slate-500">{state.session_id ?? "세션 없음"}</span>
      {/* 다음 사람을 위한 자동 초기화. 상담원을 기다리는 동안에는 데몬이 세지 않으므로
          이 줄도 뜨지 않는다 — 기다리는 시간은 노는 시간이 아니다 */}
      {state.idle_reset_in !== null && <IdleCountdown seconds={state.idle_reset_in} />}
      <div className="ml-auto flex items-center gap-2">
        <VoiceToggle speech={speech} />
        <button
          type="button"
          onClick={reset}
          className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-base font-medium text-slate-700 transition-colors duration-200 hover:bg-slate-100"
        >
          <RotateCcw size={18} aria-hidden />
          처음으로
        </button>
      </div>
    </>
  );

  // 방금 누른 버튼 바로 아래에 결과를 띄운다 — 눈이 머물러 있는 자리다
  const feedback = (
    <>
      {notice && <NoticeBar tone={noticeTone}>{notice}</NoticeBar>}
      {askStaff && (
        <button
          type="button"
          onClick={staffRelease}
          /* 손님용 버튼처럼 보이면 안 된다 — 금액 버튼과 크기·굵기를 확실히 다르게 둔다 */
          className="inline-flex cursor-pointer items-center gap-2 self-center rounded-xl border-2 border-slate-400 bg-white px-5 py-3 text-lg font-medium text-slate-700 transition-colors duration-200 hover:bg-slate-50"
        >
          <KeyRound size={24} aria-hidden />
          직원 확인 후 해제
        </button>
      )}
    </>
  );

  // 어르신께 드리는 안내와 고치는 사람에게 주는 단서를 분리한다.
  // 작게 두어 시연을 방해하지 않으면서, 원인을 찾아 헤매지 않게 한다
  const diagnostics = (
    <>
      {state.offline && (
        <p className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-lg text-amber-900 break-keep">
          <WifiOff size={22} className="shrink-0" aria-hidden />
          서버에 연결되지 않아 QR 정보만으로 판단하고 있습니다
        </p>
      )}
      {/* 이미 큰 글씨로 띄운 문구(halted)를 아래에 또 적지 않는다 */}
      {state.last_error && !halted && (
        <p role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xl text-amber-900 break-keep">
          {state.last_error}
        </p>
      )}
      {state.operator_hint && (
        <p className="rounded-xl bg-amber-100 px-4 py-3 font-mono text-sm text-amber-800 break-keep">
          {state.operator_hint}
        </p>
      )}
    </>
  );

  if (halted) {
    return (
      <AtmShell tone="halted" footer={footer}>
        <CenterPanel
          icon={<AlertTriangle size={56} aria-hidden />}
          tone="warn"
          title={state.last_error ?? "잠시만 기다려 주세요"}
        >
          {diagnostics}
          {feedback}
        </CenterPanel>
      </AtmShell>
    );
  }

  return (
    <AtmShell tone={blocked ? "danger" : "normal"} footer={footer}>
      <div className="grid w-full gap-6 lg:grid-cols-[5fr_7fr] lg:items-stretch">
        {/* 왼쪽: 지금 무슨 상황인가 */}
        <section className={`flex flex-col justify-center text-left ${blocked ? "gap-3" : "gap-5"}`}>
          {/* ATM은 공용 기계다. 평상시에는 보통 ATM처럼 돈이 나오고, 위험이 확인된
              세션에서만 막는다. QR을 못 내민다고 막으면 이 시스템과 아무 상관 없는
              사람까지 출금하지 못한다 */}
          {!blocked && (
            <>
              <p className="flex items-center gap-2 text-lg font-semibold text-emerald-700">
                <Banknote size={26} aria-hidden />
                현금 출금
              </p>
              <h1 className="text-4xl font-bold leading-tight text-slate-900 break-keep">
                {state.guidance}
              </h1>
              {/* 아직 아무 QR도 읽지 않은 평상시에만, 이 기계가 무엇을 더 할 수 있는지 알린다 */}
              {state.state === "READY" && (
                <div className="card flex items-center gap-4 p-4">
                  <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-sky-700">
                    <QrCode size={32} aria-hidden />
                  </span>
                  <p className="text-xl leading-snug text-slate-700 break-keep">
                    보이스피싱 검사 QR이 있으시면 카메라에 보여 주세요
                  </p>
                </div>
              )}
            </>
          )}

          {blocked && (
            <>
              <p className="inline-flex items-center gap-2 self-start rounded-full bg-rose-700 px-4 py-1.5 text-lg font-bold text-white">
                <ShieldAlert size={22} aria-hidden />
                출금 제한
              </p>
              <h1 className="text-[2rem] font-extrabold leading-tight text-rose-900 break-keep">
                {state.guidance}
              </h1>
              {state.reasons.length > 0 && (
                <div className="rounded-2xl border border-rose-200 bg-white px-5 py-3 shadow-sm">
                  <p className="mb-1 text-base font-semibold text-slate-600">확인된 위험 신호</p>
                  <ul className="space-y-0.5 text-lg text-slate-800">
                    {state.reasons.map((reason) => (
                      <li key={reason} className="flex gap-2 break-keep">
                        <AlertTriangle size={18} className="mt-1 shrink-0 text-rose-600" aria-hidden />
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {diagnostics}
        </section>

        {/* 오른쪽: 누를 것 */}
        <section className="flex flex-col justify-center gap-4">
          {/* 차단 중에도 출금 버튼은 그대로 둔다 — 눌러도 현금이 나오지 않는 것을
              보여주는 것이 이 프로젝트의 핵심 시연 장면이다 (PRD 9.2 / FR-09) */}
          <AmountGrid onSelect={withdraw} disabled={busy} compact={blocked} />

          {/* 상담원이 이미 결론을 냈다면 다시 요청하게 두지 않는다 */}
          {blocked && state.state === "WITHDRAW_BLOCKED" && !state.callcenter_resolution && (
            <button
              type="button"
              onClick={callCenter}
              className="btn-danger flex items-center justify-center gap-3 shadow-md"
            >
              <Headset size={30} aria-hidden />
              상담원 확인 요청하기
            </button>
          )}

          {feedback}
        </section>
      </div>
    </AtmShell>
  );
}

function NoticeBar({ tone, children }: { tone: NoticeTone; children: React.ReactNode }) {
  const look = {
    info: { box: "border-slate-300 bg-white text-slate-900", icon: <Info size={28} aria-hidden /> },
    busy: {
      box: "border-slate-300 bg-white text-slate-900",
      icon: <Loader2 size={28} className="animate-spin" aria-hidden />,
    },
    success: {
      box: "border-emerald-600 bg-emerald-50 text-emerald-900",
      icon: <CheckCircle2 size={28} aria-hidden />,
    },
    warn: {
      box: "border-rose-600 bg-white text-rose-900",
      icon: <AlertTriangle size={28} aria-hidden />,
    },
  }[tone];
  return (
    <p
      role="status"
      className={`flex items-center gap-3 rounded-2xl border-2 px-5 py-4 text-left text-2xl font-bold shadow-sm break-keep transition-colors duration-200 ${look.box}`}
    >
      <span className="shrink-0">{look.icon}</span>
      {children}
    </p>
  );
}

function CenterPanel({
  icon,
  tone,
  title,
  detail,
  children,
}: {
  icon: React.ReactNode;
  tone: "neutral" | "warn";
  title: string;
  detail?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-5 text-center">
      <span
        className={`flex h-24 w-24 items-center justify-center rounded-full ${
          tone === "warn" ? "bg-amber-100 text-amber-600" : "bg-slate-200 text-slate-500"
        }`}
      >
        {icon}
      </span>
      <h1 className="text-4xl font-bold leading-snug text-slate-900 break-keep">{title}</h1>
      {detail && <p className="text-xl text-slate-600 break-keep">{detail}</p>}
      {children && <div className="flex w-full flex-col gap-4 text-left">{children}</div>}
    </div>
  );
}

function IdleCountdown({ seconds }: { seconds: number }) {
  // 마지막 10초는 눈에 띄게 — 관람객이 "곧 다음 사람 차례"라는 걸 알아야 한다
  const urgent = seconds <= 10;
  return (
    <p
      role="status"
      className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-base break-keep transition-colors duration-200 ${
        urgent ? "bg-slate-900 text-white" : "text-slate-600"
      }`}
    >
      <Timer size={18} className="shrink-0" aria-hidden />
      <span>
        <strong className="font-mono tabular-nums">{seconds}</strong>초 뒤 처음 화면으로 돌아갑니다
      </span>
    </p>
  );
}

function AmountGrid({
  onSelect,
  disabled = false,
  compact = false,
}: {
  onSelect: (amount: number) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className="grid w-full grid-cols-2 gap-4">
      {AMOUNTS.map(({ value, reading }) => (
        <button
          key={value}
          type="button"
          onClick={() => onSelect(value)}
          disabled={disabled}
          aria-label={`${value.toLocaleString("ko-KR")}원`}
          className={`group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-slate-300 bg-white shadow-md transition duration-200 hover:border-sky-700 hover:shadow-lg active:translate-y-0.5 active:bg-sky-50 active:shadow-sm disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400 disabled:shadow-none ${
            compact ? "py-4" : "py-7"
          }`}
        >
          <span className="whitespace-nowrap text-2xl font-extrabold tabular-nums text-slate-900 group-disabled:text-slate-400 sm:text-4xl">
            {value.toLocaleString("ko-KR")}
            <span className="ml-1 text-lg font-bold sm:text-2xl">원</span>
          </span>
          <span className="mt-1 text-lg font-medium text-slate-600 group-disabled:text-slate-400">
            {reading}
          </span>
        </button>
      ))}
    </div>
  );
}

function useClock(): string {
  // 서버 렌더링과 시각이 달라 어긋나지 않게, 브라우저에서 켜진 뒤에만 채운다
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () =>
      setNow(new Date().toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" }));
    tick();
    const timer = setInterval(tick, 10_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

function AtmShell({
  tone,
  footer,
  children,
}: {
  tone: "normal" | "danger" | "halted";
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  const clock = useClock();
  // 색만으로 말하지 않는다 — 머리띠에 상태를 글자로도 적는다
  const status = {
    normal: { label: "정상 운영", chip: "bg-emerald-500/15 text-emerald-200 ring-emerald-400/40", bar: "bg-slate-900" },
    danger: { label: "출금 제한 중", chip: "bg-white/15 text-white ring-white/50", bar: "bg-rose-800" },
    halted: { label: "확인 필요", chip: "bg-amber-400/15 text-amber-200 ring-amber-300/40", bar: "bg-slate-900" },
  }[tone];
  return (
    <div
      className={`flex min-h-screen w-full flex-col transition-colors duration-200 ${
        tone === "danger" ? "bg-rose-50" : "bg-slate-100"
      }`}
    >
      <header
        className={`flex items-center gap-3 px-6 py-3 text-white transition-colors duration-200 ${status.bar}`}
      >
        {tone === "danger" ? (
          <ShieldAlert size={28} className="shrink-0" aria-hidden />
        ) : (
          <ShieldCheck size={28} className="shrink-0" aria-hidden />
        )}
        <span className="truncate text-lg font-bold tracking-tight sm:text-xl">스마트 금융 보안 ATM</span>
        <span
          className={`ml-auto shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-base font-semibold ring-1 ${status.chip}`}
        >
          {status.label}
        </span>
        <span className="hidden min-w-[5.5rem] text-right text-lg tabular-nums text-white/80 sm:block">
          {clock}
        </span>
      </header>

      <main className="flex flex-1 items-center px-6 py-4">
        <div className="mx-auto w-full max-w-6xl">{children}</div>
      </main>

      {footer && (
        <footer className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-200 bg-white px-6 py-2.5">
          {footer}
        </footer>
      )}
    </div>
  );
}
