"use client";

import { Activity, CheckCircle2, XCircle } from "lucide-react";

export interface VisionEventItem {
  id?: number | string;
  event_type: string;
  detected: boolean;
  count: number;
  confidence?: number | null;
  created_at?: string | null;
}

interface VisionLogListProps {
  events: VisionEventItem[];
}

export const VisionLogList: React.FC<VisionLogListProps> = ({ events }) => {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-800">
            실시간 영상인식(YOLO / MediaPipe) 감지 로그
          </h3>
        </div>
        <span className="text-xs text-slate-400">최근 {events.length}개</span>
      </div>

      {events.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-400 border border-dashed border-slate-100 rounded-lg">
          수신된 영상인식 이벤트가 없습니다. (비전 클라이언트를 실행하세요)
        </div>
      ) : (
        <div className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-100">
          {events.map((evt, idx) => {
            const isSuccess = evt.detected;
            const timeStr = evt.created_at
              ? new Date(evt.created_at).toLocaleTimeString("ko-KR")
              : "방금 전";
            const itemKey =
              evt.id !== undefined && evt.id !== null
                ? `evt-id-${evt.id}`
                : `evt-idx-${idx}-${evt.created_at || ""}`;

            return (
              <div
                key={itemKey}
                className="flex items-center justify-between p-3 text-xs transition-colors hover:bg-slate-50/80"
              >
                <div className="flex items-center gap-2.5">
                  {isSuccess ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-slate-400 shrink-0" />
                  )}
                  <div>
                    <span className="font-semibold text-slate-800 uppercase">
                      {evt.event_type}
                    </span>
                    <span className="ml-2 text-slate-400">
                      감지 수: <strong>{evt.count}</strong>
                    </span>
                    {evt.confidence !== null && evt.confidence !== undefined && (
                      <span className="ml-2 text-slate-400">
                        신뢰도:{" "}
                        <strong className="text-slate-600">
                          {Math.round(evt.confidence * 100)}%
                        </strong>
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                      isSuccess
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-slate-100 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {isSuccess ? "성공" : "미감지"}
                  </span>
                  <span
                    suppressHydrationWarning
                    className="font-mono text-[11px] text-slate-400"
                  >
                    {timeStr}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default VisionLogList;
