"use client";

import React from "react";
import { KaraokeRoomSection } from "@/components/booth/KaraokeRoomSection";
import { useBoothData } from "@/hooks/useBoothData";

/**
 * `/booth` — 부스 대형 화면 (부록G §3-2)
 *
 * 이 화면은 부스 안 모니터에 **계속 띄워 두는 키오스크 화면**이다. 그래서
 *   - 상단 헤더도, 탭도, 다른 화면으로 가는 링크도 두지 않는다
 *   - 이용자가 실수로 다른 화면으로 빠져나갈 길을 만들지 않는다
 *
 * 관리자가 이 화면으로 오고 싶을 때는 `/admin` 의 [부스 화면] 버튼을 쓴다.
 *
 * ⚠️ 2~3m 떨어져서 보는 화면이다. 노트북에서 적당해 보이는 글자 크기는 여기서
 *    읽히지 않는다 — 실제로 띄워 놓고 뒤로 물러나서 확인할 것 (부록J §4).
 */
export default function BoothPage() {
  const { devices, isConnected, topToday, topAll, queue, fetchSongs, fetchScores } =
    useBoothData();

  return (
    <div className="theme-stage min-h-screen bg-canvas text-ink">
      <main className="max-w-7xl mx-auto px-4 lg:px-8 py-6">
        <KaraokeRoomSection
          devices={devices}
          onSongCompleted={fetchSongs}
          topToday={topToday}
          topAll={topAll}
          queue={queue}
          onScoreRecorded={fetchScores}
        />
      </main>

      {/*
        부스 화면에는 헤더가 없어서, 백엔드와 끊긴 것을 알아챌 방법이 없다.
        노래를 방해하지 않도록 구석에 점 하나로만 표시한다.
      */}
      <div
        className="fixed bottom-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-full
                   bg-surface/70 border border-line text-[10px] font-mono text-ink-3
                   pointer-events-none select-none"
        aria-live="polite"
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            isConnected ? "bg-free" : "bg-live"
          }`}
        />
        {isConnected ? "연결됨" : "서버 끊김"}
      </div>
    </div>
  );
}
