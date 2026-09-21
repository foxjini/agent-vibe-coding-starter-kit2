"use client";

import React, { useState } from "react";
import {
  Calendar,
  Clock,
  User,
  Users,
  Building,
  KeyRound,
  AlertCircle,
  CheckCircle2,
  Copy,
  ArrowRight,
} from "lucide-react";
import { Reservation } from "@/types";
import { apiUrl } from "@/utils/apiConfig";

interface ReservationSectionProps {
  reservations: Reservation[];
  onReservationCreated: () => void;
  /**
   * 발급된 PIN을 키패드 시뮬레이터에 바로 넣어 보는 동작.
   *
   * 관리자 화면(`/admin`)에만 시뮬레이터가 있으므로 그쪽에서만 내려온다.
   * 관람객 화면(`/`)에서는 넘기지 않으며, 그때는 관련 버튼을 숨기고 대신
   * "부스 앞 키패드에 입력하세요" 안내를 보여 준다. (부록G §3-3)
   */
  onSelectPinForSimulator?: (pin: string) => void;
}

export function ReservationSection({
  reservations,
  onReservationCreated,
  onSelectPinForSimulator,
}: ReservationSectionProps) {
  // Form State
  const [grade, setGrade] = useState<number>(2);
  const [department, setDepartment] = useState<string>("정보통신과");
  const [studentName, setStudentName] = useState<string>("");
  const [userCount, setUserCount] = useState<number>(4);
  const [reservationDate, setReservationDate] = useState<string>("");
  const [timeSlot, setTimeSlot] = useState<"lunch" | "dinner">("lunch");

  // Status & Voucher State
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [issuedVoucher, setIssuedVoucher] = useState<Reservation | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // Today string for min attribute and validation
  const todayStr = new Date().toISOString().split("T")[0];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // 1. 당일 예약 차단 클라이언트 1차 체크
    if (reservationDate <= todayStr) {
      setErrorMessage("당일 예약은 불가능합니다. 내일 이후의 날짜를 선택해 주세요.");
      return;
    }

    if (!studentName.trim()) {
      setErrorMessage("신청자 이름을 입력해 주세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(apiUrl("/api/reservations"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade: Number(grade),
          department,
          student_name: studentName.trim(),
          user_count: Number(userCount),
          reservation_date: reservationDate,
          time_slot: timeSlot,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMessage(data?.error?.message || "예약 신청 중 오류가 발생했습니다.");
        setIsSubmitting(false);
        return;
      }

      setIssuedVoucher(data.data);
      setStudentName("");
      onReservationCreated();
    } catch {
      setErrorMessage("서버와 통신할 수 없습니다. 백엔드 구동 상태를 확인하세요.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyPin = (pin: string) => {
    navigator.clipboard.writeText(pin);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Issued Voucher Notification Card */}
      {issuedVoucher && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-emerald-950/80 to-slate-900 border-2 border-emerald-500 shadow-2xl animate-fade-in relative overflow-hidden">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-1">
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 inline-flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                예약 확정 완료 (일회성 비밀번호 발급)
              </span>
              <h3 className="text-xl font-bold text-white">
                {issuedVoucher.student_name} 학생의 노래방 부스 예약이 완료되었습니다!
              </h3>
              <p className="text-xs text-slate-400">
                {issuedVoucher.reservation_date} |{" "}
                {issuedVoucher.time_slot === "lunch" ? "점심 타임 (12:30~13:20)" : "저녁 타임 (17:30~18:30)"} | 인원{" "}
                {issuedVoucher.user_count}명
              </p>
            </div>

            {/* PIN Code Display Box */}
            <div className="flex items-center gap-4 bg-slate-950/90 p-4 rounded-xl border border-emerald-500/40 shadow-inner">
              <div>
                <span className="text-[10px] text-slate-400 block uppercase font-mono">발급된 OTP PIN</span>
                <span className="text-3xl font-extrabold font-mono tracking-widest text-emerald-400">
                  {issuedVoucher.pin_code}
                </span>
              </div>
              <button
                onClick={() => copyPin(issuedVoucher.pin_code)}
                className="p-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
                title="PIN 복사"
              >
                {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
              {onSelectPinForSimulator && (
                <button
                  onClick={() => onSelectPinForSimulator(issuedVoucher.pin_code)}
                  className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-md active:scale-95 flex items-center gap-1.5 cursor-pointer"
                >
                  시뮬레이터에 입력 <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {!onSelectPinForSimulator && (
            <p className="mt-4 text-sm text-emerald-200/90 flex items-start gap-2">
              <ArrowRight className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
              <span>
                이용 시간에 <strong className="text-white">부스 앞 키패드</strong>에 위 4자리를 입력하면 문이 열립니다.
                <strong className="text-white"> 한 번만 쓸 수 있으니</strong> 다른 사람에게 알려주지 마세요.
              </span>
            </p>
          )}
        </div>
      )}

      {/* Main Content: Left Form, Right Existing Reservations */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Reservation Form (5 Cols) */}
        <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="border-b border-slate-800 pb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Calendar className="w-5 h-5 text-indigo-400" />
              학교 노래방 부스 예약 신청
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              동일 시간대 중복 예약은 방지되며, 당일 예약은 불가합니다.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {errorMessage && (
              <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-500/50 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Grade & Department */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">학년</label>
                <select
                  value={grade}
                  onChange={(e) => setGrade(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value={1}>1학년</option>
                  <option value={2}>2학년</option>
                  <option value={3}>3학년</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                  <Building className="w-3.5 h-3.5 text-slate-400" />
                  학과
                </label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="정보통신과">정보통신과</option>
                  <option value="전자제어과">전자제어과</option>
                  <option value="스마트소프트웨어과">스마트소프트웨어과</option>
                  <option value="자동화기계과">자동화기계과</option>
                </select>
              </div>
            </div>

            {/* Student Name & User Count */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  신청자 이름
                </label>
                <input
                  type="text"
                  placeholder="예: 김민제"
                  value={studentName}
                  onChange={(e) => setStudentName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none placeholder:text-slate-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  이용 인원 (최대 10명)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={userCount}
                  onChange={(e) => setUserCount(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                  required
                />
              </div>
            </div>

            {/* Date Picker */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center justify-between">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  예약 일자 선택
                </span>
                <span className="text-[10px] text-amber-400">※ 당일 예약 불가</span>
              </label>
              <input
                type="date"
                min={todayStr}
                value={reservationDate}
                onChange={(e) => setReservationDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              />
            </div>

            {/* Time Slot Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                타임슬롯
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setTimeSlot("lunch")}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    timeSlot === "lunch"
                      ? "bg-indigo-950/60 border-indigo-500 text-white shadow-md shadow-indigo-950"
                      : "bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <span className="text-xs font-bold block">점심 타임</span>
                  <span className="text-[10px] text-slate-400">12:30 ~ 13:20 (50분)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setTimeSlot("dinner")}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    timeSlot === "dinner"
                      ? "bg-indigo-950/60 border-indigo-500 text-white shadow-md shadow-indigo-950"
                      : "bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <span className="text-xs font-bold block">저녁 타임</span>
                  <span className="text-[10px] text-slate-400">17:30 ~ 18:30 (60분)</span>
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-950/40 active:scale-98 cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 mt-2"
            >
              {isSubmitting ? "예약 처리 중..." : "예약 신청 및 비밀번호 발급"}
            </button>
          </form>
        </div>

        {/* Existing Reservations Table (7 Cols) */}
        <div className="lg:col-span-7 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-emerald-400" />
                노래방 예약 현황 목록
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                등록된 예약 정보와 발급된 4자리 일회성 비밀번호를 확인합니다.
              </p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-800 text-slate-300">
              총 {reservations.length}건
            </span>
          </div>

          <div className="overflow-x-auto">
            {reservations.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                등록된 예약 내역이 없습니다. 좌측에서 새 예약을 신청해 보세요.
              </div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                    <th className="pb-2 font-medium">예약일 / 타임</th>
                    <th className="pb-2 font-medium">신청자</th>
                    <th className="pb-2 font-medium">인원</th>
                    <th className="pb-2 font-medium">상태</th>
                    <th className="pb-2 font-medium">비밀번호 (OTP)</th>
                    <th className="pb-2 font-medium text-right">테스트</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {reservations.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 font-mono text-slate-200">
                        {r.reservation_date}
                        <span className="block text-[10px] text-slate-400">
                          {r.time_slot === "lunch" ? "점심 (12:30~13:20)" : "저녁 (17:30~18:30)"}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="font-semibold text-white">{r.student_name}</span>
                        <span className="block text-[10px] text-slate-400">
                          {r.grade}학년 {r.department}
                        </span>
                      </td>
                      <td className="py-3 text-slate-300">{r.user_count}명</td>
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            r.status === "active"
                              ? "bg-emerald-950 border-emerald-500 text-emerald-400"
                              : r.status === "completed"
                              ? "bg-slate-800 border-slate-700 text-slate-400"
                              : "bg-indigo-950 border-indigo-500 text-indigo-400"
                          }`}
                        >
                          {r.status === "active" ? "이용 중" : r.status === "completed" ? "이용 완료" : "예약됨"}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="font-mono font-bold text-emerald-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">
                          {r.pin_code}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        {onSelectPinForSimulator && (
                          <button
                            onClick={() => onSelectPinForSimulator(r.pin_code)}
                            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] border border-slate-700 transition-colors cursor-pointer"
                          >
                            입력
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
