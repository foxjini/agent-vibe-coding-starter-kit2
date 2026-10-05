"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import type { BoothAnnouncement } from "@/hooks/useBoothData";

/** 이 PC에서 안내 음성을 껐는지 기억해 두는 곳 */
const SOUND_KEY = "karaoke.boothSound.v1";
/** 퇴실곡 '더윈드 - 다시 만나' (0:58~ 하이라이트) */
const CLOSING_SONG_URL = "/audio/closing_song.wav";

/** 한국어로 읽어 준다. 다 읽으면(또는 못 읽으면) onDone 을 부른다 */
function speak(text: string, onDone?: () => void) {
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    onDone?.();
  };
  if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) {
    finish();
    return;
  }
  try {
    // cancel() 하지 않는다 — 이용 종료 안내 직후에 다음 체험 관람객 호출이 이어지는
    // 일이 잦다. 끊지 않고 차례로 읽게 둔다 (speechSynthesis 가 스스로 줄을 세운다)
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ko-KR";
    utterance.rate = 1.0;
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.speak(utterance);
    // 음성이 막혀 onend 가 오지 않는 브라우저가 있다 — 그래도 다음 일은 한다
    if (onDone) setTimeout(finish, Math.min(9_000, 1_500 + text.length * 130));
  } catch {
    finish();
  }
}

/**
 * 부스 안내 음성 · 퇴실곡 (부스 화면 전용)
 *
 * 팀 트리거 규칙의 소리는 모두 **부스에서** 나야 한다.
 *   인증 성공 → 환영 안내 / 입장 감지 → 환영 안내 / 종료 10분 전 → 안내
 *   이용 종료 → 안내 후 퇴실곡 / 체험 호출 → "N번 OO님, 입장해 주세요"
 * 예전에는 이 소리가 선생님 노트북(/admin)에서 났다. 라즈베리파이 데몬의 기본값
 * (pi/.env 의 SPEAKER_MODE=browser)도 "부스 화면이 소리를 낸다"는 약속이다.
 *
 * 브라우저는 한 번도 누르지 않은 페이지에서 소리를 못 내게 막는다. 부스 PC에서
 * 이 화면을 띄운 사람이 왼쪽 아래 [소리 켜기]를 한 번 눌러 둔다. (화면 키패드를
 * 누른 것으로도 풀린다)
 *
 * SPEAKER_MODE=pi 로 파이 스피커가 안내를 읽는 설치라면 소리가 두 번 나므로,
 * 버튼으로 이 화면의 안내 음성을 끈다 — 이 PC에 기억된다.
 */
export function BoothAudio({ announcement }: { announcement: BoothAnnouncement | null }) {
  const [enabled, setEnabled] = useState(true);
  const [unlocked, setUnlocked] = useState(false);
  const songRef = useRef<HTMLAudioElement | null>(null);
  const seenSeqRef = useRef(announcement?.seq ?? 0);

  // 이 PC에 저장해 둔 설정과, 이미 화면을 누른 적이 있는지 확인한다
  useEffect(() => {
    const id = setTimeout(() => {
      try {
        if (window.localStorage.getItem(SOUND_KEY) === "off") setEnabled(false);
      } catch {
        /* 저장소가 막혀 있으면 기본값(켜짐) */
      }
      const activation = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } })
        .userActivation;
      if (activation?.hasBeenActive) setUnlocked(true);
    }, 0);

    // 화면 어디든 한 번 누르면 소리가 풀린다.
    // 단, 이 버튼을 누른 것은 handleClick 이 처리한다 — 여기서 먼저 풀어 버리면
    // 이어지는 click 에서 "이미 풀렸다"로 보고 안내 음성을 꺼 버린다 (실제로 그랬다).
    const onFirstGesture = (e: Event) => {
      if ((e.target as Element | null)?.closest?.("[data-booth-sound]")) return;
      setUnlocked(true);
    };
    window.addEventListener("pointerdown", onFirstGesture, { capture: true });
    window.addEventListener("keydown", onFirstGesture, { capture: true });
    return () => {
      clearTimeout(id);
      window.removeEventListener("pointerdown", onFirstGesture, { capture: true });
      window.removeEventListener("keydown", onFirstGesture, { capture: true });
    };
  }, []);

  useEffect(
    () => () => {
      songRef.current?.pause();
      songRef.current = null;
    },
    []
  );

  const playClosingSong = useCallback(() => {
    if (!songRef.current) {
      songRef.current = new Audio(CLOSING_SONG_URL);
      songRef.current.volume = 0.85;
    }
    const song = songRef.current;
    song.currentTime = 0;
    song.play().catch(() => {
      /* 소리가 아직 풀리지 않았다 — [소리 켜기]를 눌러야 한다 */
    });
  }, []);

  // 새 안내가 올 때만 읽는다. (설정을 바꾸는 순간 지난 안내를 다시 읽지 않도록
  // enabled 는 의존성에 넣지 않고 그때그때 값을 본다)
  const enabledRef = useRef(enabled);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useEffect(() => {
    if (!announcement || announcement.seq <= seenSeqRef.current) return;
    seenSeqRef.current = announcement.seq;
    if (!enabledRef.current) return;

    if (announcement.event === "session_ended") {
      // 팀 트리거 규칙: "이용 종료 시 지정된 종료 음악을 재생한 후 전원과 마이크를 차단한다"
      // 안내를 먼저 읽고, 다 읽으면 퇴실곡을 튼다 (겹치면 둘 다 안 들린다)
      speak(announcement.text, playClosingSong);
      return;
    }
    if (announcement.event === "auth") {
      // 다음 사람이 들어왔다 — 앞사람의 퇴실곡은 멈춘다
      songRef.current?.pause();
    }
    speak(announcement.text);
  }, [announcement, playClosingSong]);

  const handleClick = () => {
    if (!unlocked) {
      setUnlocked(true);
      speak("안내 음성을 켰습니다.");
      return;
    }
    const next = !enabled;
    setEnabled(next);
    try {
      window.localStorage.setItem(SOUND_KEY, next ? "on" : "off");
    } catch {
      /* 이번 실행 동안만 유지된다 */
    }
    if (!next) {
      window.speechSynthesis?.cancel();
      songRef.current?.pause();
    } else {
      speak("안내 음성을 켰습니다.");
    }
  };

  const needsUnlock = enabled && !unlocked;

  return (
    <button
      type="button"
      onClick={handleClick}
      data-booth-sound
      data-testid="booth-sound"
      className={`fixed bottom-3 left-3 z-40 flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold transition-colors cursor-pointer ${
        needsUnlock
          ? "bg-brass text-on-accent border-brass animate-pulse"
          : "bg-surface/70 text-ink-3 border-line hover:text-ink"
      }`}
      title={
        needsUnlock
          ? "브라우저가 소리를 막고 있습니다. 한 번 눌러 안내 음성과 퇴실곡을 켜세요."
          : enabled
          ? "부스 안내 음성·퇴실곡 끄기 (파이 스피커가 읽어 줄 때)"
          : "부스 안내 음성·퇴실곡 켜기"
      }
    >
      {enabled ? <Volume2 className="w-3.5 h-3.5" aria-hidden /> : <VolumeX className="w-3.5 h-3.5" aria-hidden />}
      {needsUnlock ? "소리 켜기 — 한 번 눌러 주세요" : enabled ? "안내 음성 켜짐" : "안내 음성 꺼짐"}
    </button>
  );
}
