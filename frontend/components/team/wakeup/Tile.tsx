/**
 * wakeup 7인치 화면의 기본 조각 — 버튼 · 상태 표시 · 묶음 · "배치표에 없음" 안내
 * 색은 모두 app/wakeup/wakeup.css의 의미 변수(--wk-*)를 씁니다. 밤·새벽 상태에 따라 저절로 바뀝니다.
 * 규칙은 DESIGN.md (같은 폴더)를 봅니다.
 */
"use client";

import React, { useEffect, useRef } from "react";

/** 화면 안의 한 묶음. 카드 상자를 남발하지 않도록 테두리 대신 살짝 떠 있는 바탕만 씁니다. */
export function Panel({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "section" | "div";
}) {
  return <Tag className={`rounded-[var(--wk-radius-panel)] bg-(--wk-raised) ${className}`}>{children}</Tag>;
}

const TONES = {
  /** 보통 버튼 — 선만 */
  plain: "border border-(--wk-line-strong) text-(--wk-text) active:bg-(--wk-press)",
  /** 그 화면의 주된 행동 하나 — 앰버(밤) / 짙은 흙색(새벽) */
  accent: "bg-(--wk-accent) text-(--wk-on-accent) font-semibold",
  /** 지금 선택된 값 */
  selected: "border border-(--wk-accent) bg-(--wk-press) text-(--wk-accent) font-semibold",
  /** 글자만 */
  quiet: "text-(--wk-dim) active:bg-(--wk-press)",
} as const;

export type Tone = keyof typeof TONES;

export function TouchButton({
  children,
  onClick,
  disabled,
  tone = "plain",
  className = "",
  ariaLabel,
  ariaPressed,
  repeat = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: Tone;
  className?: string;
  ariaLabel?: string;
  /** 켜짐/꺼짐처럼 눌린 상태가 있는 버튼 */
  ariaPressed?: boolean;
  /** 꾹 누르고 있으면 계속 반복 (시각 ▲▼처럼 여러 번 누를 일이 많은 버튼) */
  repeat?: boolean;
}) {
  const hold = useRef<{ delay: number | null; tick: number | null; fired: boolean }>({
    delay: null,
    tick: null,
    fired: false,
  });
  const stopHold = () => {
    if (hold.current.delay !== null) window.clearTimeout(hold.current.delay);
    if (hold.current.tick !== null) window.clearInterval(hold.current.tick);
    hold.current.delay = null;
    hold.current.tick = null;
  };
  useEffect(() => stopHold, []);

  const holdProps = repeat
    ? {
        onPointerDown: (e: React.PointerEvent<HTMLButtonElement>) => {
          if (disabled || e.button !== 0) return;
          stopHold();
          hold.current.fired = true;       // 이 누름은 여기서 처리 — 뒤따르는 click은 건너뜀
          onClick();
          hold.current.delay = window.setTimeout(() => {
            hold.current.tick = window.setInterval(onClick, 90);
          }, 450);
        },
        onPointerUp: stopHold,
        onPointerLeave: stopHold,
        onPointerCancel: stopHold,
        onContextMenu: (e: React.MouseEvent) => e.preventDefault(),   // 길게 누를 때 메뉴가 뜨지 않게
      }
    : {};

  return (
    <button
      type="button"
      {...holdProps}
      onClick={() => {
        if (repeat && hold.current.fired) {
          hold.current.fired = false;       // 포인터로 이미 처리한 누름
          return;
        }
        onClick();                          // 키보드(Enter·Space)로 누른 경우
      }}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      className={`wk-press flex min-h-12 items-center justify-center gap-2 rounded-[var(--wk-radius-control)] px-4 text-base disabled:opacity-35 ${TONES[tone]} ${className}`}
    >
      {children}
    </button>
  );
}

/** 짧은 상태 글자 (켜짐 · 누워 있음 …). on이면 초록 점이 붙습니다. */
export function State({ on, children }: { on: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-2 text-base ${on ? "text-(--wk-ok)" : "text-(--wk-dim)"}`}>
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${on ? "bg-(--wk-ok)" : "border border-(--wk-dim)"}`}
      />
      {children}
    </span>
  );
}

/** 배치표에 그 부품이 없을 때 */
export function MissingSlot({ slotId }: { slotId: string }) {
  return (
    <p className="text-sm text-(--wk-dim)">
      배치표에 {slotId}가 없습니다. 파이 담당에게 확인하세요.
    </p>
  );
}
