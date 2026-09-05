"use client";

import React, { useState } from "react";
import { Gamepad2, Trophy, HelpCircle, CheckCircle2, XCircle, RotateCcw } from "lucide-react";


interface QuizItem {
  consonant: string;
  singer: string;
  hint: string;
  answer: string;
}

const QUIZ_LIST: QuizItem[] = [
  { consonant: "ㄷㅅ ㅁㄴ", singer: "더윈드", hint: "우리 학교 노래방 퇴실 하이라이트곡!", answer: "다시 만나" },
  { consonant: "ㅊ ㅁㄴㅇ ㄱㅎㄷㄹ ㄷㅈ ㅇㅇ", singer: "TWS (투어스)", hint: "2024년 상반기 대히트 신인곡", answer: "첫 만남은 계획대로 되지 않아" },
  { consonant: "ㅅㅍㄴㅂ", singer: "aespa", hint: "쇠맛 신드롬 노래", answer: "Supernova" },
  { consonant: "ㄹㅂ ㅇㅈ ㅇ", singer: "아이유", hint: "뷔와 함께한 뮤직비디오", answer: "Love wins all" },
  { consonant: "ㅎㅇㅍ ㅂㅇ", singer: "NewJeans", hint: "홍대 가려면 어떻게 가요?", answer: "Hype Boy" },
];

export function MiniGameSection() {
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [userGuess, setUserGuess] = useState<string>("");
  const [score, setScore] = useState<number>(0);
  const [showHint, setShowHint] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<"correct" | "wrong" | null>(null);
  const [isGameOver, setIsGameOver] = useState<boolean>(false);

  const currentQuiz = QUIZ_LIST[currentIndex];

  const handleCheck = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userGuess.trim() || feedback !== null) return;

    const normalizedGuess = userGuess.trim().replace(/\s+/g, "").toLowerCase();
    const normalizedAnswer = currentQuiz.answer.replace(/\s+/g, "").toLowerCase();

    if (normalizedGuess === normalizedAnswer) {
      setFeedback("correct");
      setScore((prev) => prev + 20);
    } else {
      setFeedback("wrong");
    }

    setTimeout(() => {
      setFeedback(null);
      setUserGuess("");
      setShowHint(false);

      if (currentIndex + 1 < QUIZ_LIST.length) {
        setCurrentIndex((prev) => prev + 1);
      } else {
        setIsGameOver(true);
      }
    }, 1500);
  };

  const handleRestart = () => {
    setCurrentIndex(0);
    setUserGuess("");
    setScore(0);
    setShowHint(false);
    setFeedback(null);
    setIsGameOver(false);
  };

  return (
    <div className="max-w-2xl mx-auto bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Gamepad2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              K-POP 노래 제목 초성 퀴즈
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Q4 미니게임
              </span>
            </h3>
            <p className="text-xs text-slate-400">초성과 가수를 보고 노래 제목을 맞춰보세요!</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 font-mono text-xs font-bold text-amber-400">
          <Trophy className="w-4 h-4 text-amber-400" />
          <span>점수: {score}점</span>
        </div>
      </div>

      {!isGameOver ? (
        <div className="space-y-6">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              문제 <strong>{currentIndex + 1}</strong> / {QUIZ_LIST.length}
            </span>
            <span className="text-indigo-400 font-medium">가수: {currentQuiz.singer}</span>
          </div>

          {/* Consonant Quiz Display Box */}
          <div className="p-8 rounded-2xl bg-gradient-to-br from-indigo-950/60 to-slate-950 border border-indigo-500/40 text-center space-y-3 relative overflow-hidden shadow-inner">
            <span className="text-[11px] uppercase tracking-widest text-indigo-300 block font-semibold">
              노래 제목 초성
            </span>
            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-wider">
              {currentQuiz.consonant}
            </div>

            {showHint ? (
              <div className="text-xs text-amber-300 bg-amber-950/40 py-1 px-3 rounded-lg border border-amber-500/30 inline-block animate-fade-in">
                💡 힌트: {currentQuiz.hint}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowHint(true)}
                className="text-[11px] text-slate-400 hover:text-amber-300 flex items-center gap-1 mx-auto transition-colors cursor-pointer"
              >
                <HelpCircle className="w-3.5 h-3.5" /> 힌트 보기
              </button>
            )}

            {feedback && (
              <div
                className={`absolute inset-0 flex items-center justify-center gap-2 text-xl font-bold backdrop-blur-sm animate-fade-in ${
                  feedback === "correct"
                    ? "bg-emerald-950/90 text-emerald-300 border-2 border-emerald-500"
                    : "bg-rose-950/90 text-rose-300 border-2 border-rose-500"
                }`}
              >
                {feedback === "correct" ? (
                  <>
                    <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                    정답입니다! (+20점)
                  </>
                ) : (
                  <>
                    <XCircle className="w-8 h-8 text-rose-400" />
                    틀렸습니다! (정답: {currentQuiz.answer})
                  </>
                )}
              </div>
            )}
          </div>

          {/* Answer Input Form */}
          <form onSubmit={handleCheck} className="flex gap-2">
            <input
              type="text"
              placeholder="노래 제목을 입력하세요"
              value={userGuess}
              onChange={(e) => setUserGuess(e.target.value)}
              disabled={feedback !== null}
              className="flex-1 px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              autoFocus
            />
            <button
              type="submit"
              disabled={feedback !== null || !userGuess.trim()}
              className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-bold text-sm shadow-md transition-all cursor-pointer disabled:opacity-50"
            >
              정답 확인
            </button>
          </form>
        </div>
      ) : (
        /* Game Over Screen */
        <div className="text-center py-8 space-y-5">
          <div className="w-16 h-16 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center justify-center mx-auto animate-bounce">
            <Trophy className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h4 className="text-2xl font-bold text-white">퀴즈 종료!</h4>
            <p className="text-sm text-slate-400">
              최종 획득 점수: <strong className="text-amber-400 text-lg">{score}점</strong> / 100점
            </p>
          </div>

          <button
            onClick={handleRestart}
            className="px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition-all inline-flex items-center gap-2 cursor-pointer shadow-md"
          >
            <RotateCcw className="w-4 h-4" /> 다시 도전하기
          </button>
        </div>
      )}
    </div>
  );
}
