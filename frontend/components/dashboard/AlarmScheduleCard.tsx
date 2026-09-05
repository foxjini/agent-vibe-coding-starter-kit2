"use client";

import React, { useState } from "react";
import { AlarmClock, BellOff, CalendarClock, Play, Timer } from "lucide-react";


interface AlarmScheduleCardProps {
  apiBaseUrl: string;
  isAlarmRinging: boolean;
  onAlarmStateChanged?: () => void;
}

export const AlarmScheduleCard: React.FC<AlarmScheduleCardProps> = ({
  apiBaseUrl,
  isAlarmRinging,
  onAlarmStateChanged,
}) => {
  const [alarmTime, setAlarmTime] = useState("07:30");
  const [scheduledMsg, setScheduledMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 즉시 알람 시작
  const handleTriggerNow = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/alarm/trigger`, {
        method: "POST",
      });
      if (res.ok) {
        setScheduledMsg("기상 알람이 즉시 시작되었습니다!");
        onAlarmStateChanged?.();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // N초 후 테스트 알람
  const handleTriggerInSeconds = async (seconds: number) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/alarm/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ in_seconds: seconds }),
      });
      if (res.ok) {
        setScheduledMsg(`${seconds}초 후 알람이 시작됩니다. 웹캠 앞에서 대기하세요!`);
        onAlarmStateChanged?.();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 시각(HH:MM) 예약
  const handleScheduleTime = async () => {
    if (!alarmTime) return;
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/alarm/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alarm_time: alarmTime }),
      });
      if (res.ok) {
        const json = await res.json();
        setScheduledMsg(json.data?.message || `매일 ${alarmTime}에 기상 알람이 울립니다.`);
        onAlarmStateChanged?.();
      } else {
        const errJson = await res.json();
        setScheduledMsg(`설정 실패: ${errJson.detail?.error?.message || "입력값을 확인하세요."}`);
      }
    } catch (err) {
      console.error(err);
      setScheduledMsg("서버 통신 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // 알람 강제 정지
  const handleStopAlarm = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/alarm/stop`, {
        method: "POST",
      });
      if (res.ok) {
        setScheduledMsg("알람이 정지되었습니다.");
        onAlarmStateChanged?.();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-amber-50 text-amber-700 border border-amber-200">
            <AlarmClock className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">
              기상 알람 시간 설정 및 시연 컨트롤러
            </h3>
            <p className="text-xs text-slate-500">
              트리거 규칙: 알람 울림 → 웹캠 미션 수행 → 알람 해제 → 2차 수면 방지 팝업
            </p>
          </div>
        </div>

        {isAlarmRinging ? (
          <button
            type="button"
            disabled={loading}
            onClick={handleStopAlarm}
            className="cursor-pointer inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
          >
            <BellOff className="w-3.5 h-3.5" />
            알람 끄기
          </button>
        ) : (
          <button
            type="button"
            disabled={loading}
            onClick={handleTriggerNow}
            className="cursor-pointer inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            지금 즉시 알람 울리기
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* 1. 빠른 시연용 타이머 버튼 */}
        <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100 flex flex-col justify-between gap-2.5">
          <div>
            <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
              <Timer className="w-3.5 h-3.5 text-slate-500" />
              빠른 기상 미션 테스트 타이머
            </span>
            <p className="text-[11px] text-slate-500 mt-0.5">
              버튼을 누르면 잠시 후 알람이 작동하고 비전 기상 미션이 개시됩니다.
            </p>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              disabled={loading || isAlarmRinging}
              onClick={() => handleTriggerInSeconds(5)}
              className="flex-1 cursor-pointer py-2 px-3 rounded-md bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors disabled:opacity-50"
            >
              5초 후 작동
            </button>
            <button
              type="button"
              disabled={loading || isAlarmRinging}
              onClick={() => handleTriggerInSeconds(10)}
              className="flex-1 cursor-pointer py-2 px-3 rounded-md bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors disabled:opacity-50"
            >
              10초 후 작동
            </button>
          </div>
        </div>

        {/* 2. 기상 시각 예약 */}
        <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100 flex flex-col justify-between gap-2.5">
          <div>
            <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
              <CalendarClock className="w-3.5 h-3.5 text-slate-500" />
              매일 기상 알람 시각 설정
            </span>
            <p className="text-[11px] text-slate-500 mt-0.5">
              지정된 시간에 피에조 부저가 울리며 기상 미션이 시작됩니다.
            </p>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <input
              type="time"
              value={alarmTime}
              onChange={(e) => setAlarmTime(e.target.value)}
              className="cursor-pointer py-1.5 px-3 rounded-md border border-slate-200 bg-white text-slate-800 text-xs font-mono font-medium focus:outline-hidden focus:ring-1 focus:ring-slate-400"
            />
            <button
              type="button"
              disabled={loading}
              onClick={handleScheduleTime}
              className="flex-1 cursor-pointer py-2 px-3 rounded-md bg-slate-800 hover:bg-slate-900 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              알람 예약 저장
            </button>
          </div>
        </div>
      </div>

      {scheduledMsg && (
        <div className="mt-3 text-xs text-amber-800 bg-amber-50/80 border border-amber-200/60 rounded-md p-2 flex items-center justify-between">
          <span>{scheduledMsg}</span>
          <button
            type="button"
            onClick={() => setScheduledMsg(null)}
            className="text-[10px] text-amber-900 underline opacity-60 hover:opacity-100 cursor-pointer"
          >
            닫기
          </button>
        </div>
      )}
    </div>
  );
};

export default AlarmScheduleCard;
