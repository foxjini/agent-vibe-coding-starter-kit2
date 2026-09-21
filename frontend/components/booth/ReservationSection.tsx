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
        <div className="p-6 rounded-2xl bg-free-soft border-2 border-free shadow-2xl animate-fade-in relative overflow-hidden">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-1">
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-free/20 text-free border border-free/40 inline-flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-free" />
                예약 확정 완료 (일회성 비밀번호 발급)
              </span>
              <h3 className="text-xl font-bold text-ink">
                {issuedVoucher.student_name} 학생의 노래방 부스 예약이 완료되었습니다!
              </h3>
              <p className="text-xs text-ink-3">
                {issuedVoucher.reservation_date} |{" "}
                {issuedVoucher.time_slot === "lunch" ? "점심 타임 (12:30~13:20)" : "저녁 타임 (17:30~18:30)"} | 인원{" "}
                {issuedVoucher.user_count}명
              </p>
            </div>

            {/* PIN Code Display Box */}
            <div className="flex items-center gap-4 bg-canvas/90 p-4 rounded-xl border border-free/40 shadow-inner">
              <div>
                <span className="text-[10px] text-ink-3 block uppercase font-mono">발급된 OTP PIN</span>
                <span className="text-3xl font-extrabold font-mono tracking-widest text-free">
                  {issuedVoucher.pin_code}
                </span>
              </div>
              <button
                onClick={() => copyPin(issuedVoucher.pin_code)}
                className="p-2.5 rounded-lg bg-raised hover:bg-line-strong/90 text-ink-2 transition-colors cursor-pointer"
                title="PIN 복사"
              >
                {copied ? <CheckCircle2 className="w-4 h-4 text-free" /> : <Copy className="w-4 h-4" />}
              </button>
              {onSelectPinForSimulator && (
                <button
                  onClick={() => onSelectPinForSimulator(issuedVoucher.pin_code)}
                  className="px-3 py-2 rounded-lg bg-free hover:bg-free/90 text-on-accent text-xs font-bold transition-all shadow-md active:scale-95 flex items-center gap-1.5 cursor-pointer"
                >
                  시뮬레이터에 입력 <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {!onSelectPinForSimulator && (
            <p className="mt-4 text-sm text-free/90 flex items-start gap-2">
              <ArrowRight className="w-4 h-4 shrink-0 mt-0.5 text-free" />
              <span>
                이용 시간에 <strong className="text-ink">부스 앞 키패드</strong>에 위 4자리를 입력하면 문이 열립니다.
                <strong className="text-ink"> 한 번만 쓸 수 있으니</strong> 다른 사람에게 알려주지 마세요.
              </span>
            </p>
          )}
        </div>
      )}

      {/* Main Content: Left Form, Right Existing Reservations */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Reservation Form (5 Cols) */}
        <div className="lg:col-span-5 bg-surface/90 border border-line rounded-2xl p-6 shadow-xl space-y-6">
          <div className="border-b border-line pb-4">
            <h3 className="text-lg font-bold text-ink flex items-center gap-2">
              <Calendar className="w-5 h-5 text-brass" />
              학교 노래방 부스 예약 신청
            </h3>
            <p className="text-xs text-ink-3 mt-1">
              동일 시간대 중복 예약은 방지되며, 당일 예약은 불가합니다.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {errorMessage && (
              <div className="p-3 rounded-lg bg-live-soft/50 border border-live/50 text-live text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Grade & Department */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-ink-2 mb-1.5">학년</label>
                <select
                  value={grade}
                  onChange={(e) => setGrade(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
                >
                  <option value={1}>1학년</option>
                  <option value={2}>2학년</option>
                  <option value={3}>3학년</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-2 mb-1.5 flex items-center gap-1">
                  <Building className="w-3.5 h-3.5 text-ink-3" />
                  학과
                </label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
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
                <label className="block text-xs font-semibold text-ink-2 mb-1.5 flex items-center gap-1">
                  <User className="w-3.5 h-3.5 text-ink-3" />
                  신청자 이름
                </label>
                <input
                  type="text"
                  placeholder="예: 김민제"
                  value={studentName}
                  onChange={(e) => setStudentName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none placeholder:text-ink-3"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-2 mb-1.5 flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-ink-3" />
                  이용 인원 (최대 10명)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={userCount}
                  onChange={(e) => setUserCount(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
                  required
                />
              </div>
            </div>

            {/* Date Picker */}
            <div>
              <label className="block text-xs font-semibold text-ink-2 mb-1.5 flex items-center justify-between">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-ink-3" />
                  예약 일자 선택
                </span>
                <span className="text-[10px] text-brass">※ 당일 예약 불가</span>
              </label>
              <input
                type="date"
                min={todayStr}
                value={reservationDate}
                onChange={(e) => setReservationDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-raised border border-line-strong text-ink text-xs focus:ring-2 focus:ring-brass outline-none"
                required
              />
            </div>

            {/* Time Slot Selection */}
            <div>
              <label className="block text-xs font-semibold text-ink-2 mb-1.5 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-ink-3" />
                타임슬롯
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setTimeSlot("lunch")}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    timeSlot === "lunch"
                      ? "bg-brass-soft/60 border-brass text-ink shadow-md"
                      : "bg-raised/40 border-line-strong text-ink-3 hover:text-ink"
                  }`}
                >
                  <span className="text-xs font-bold block">점심 타임</span>
                  <span className="text-[10px] text-ink-3">12:30 ~ 13:20 (50분)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setTimeSlot("dinner")}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    timeSlot === "dinner"
                      ? "bg-brass-soft/60 border-brass text-ink shadow-md"
                      : "bg-raised/40 border-line-strong text-ink-3 hover:text-ink"
                  }`}
                >
                  <span className="text-xs font-bold block">저녁 타임</span>
                  <span className="text-[10px] text-ink-3">17:30 ~ 18:30 (60분)</span>
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl bg-brass hover:bg-brass/90 active:bg-brass/80 text-on-accent text-xs font-bold transition-all shadow-lg active:scale-98 cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 mt-2"
            >
              {isSubmitting ? "예약 처리 중..." : "예약 신청 및 비밀번호 발급"}
            </button>
          </form>
        </div>

        {/* Existing Reservations Table (7 Cols) */}
        <div className="lg:col-span-7 bg-surface/90 border border-line rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-line pb-4">
            <div>
              <h3 className="text-lg font-bold text-ink flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-free" />
                노래방 예약 현황 목록
              </h3>
              <p className="text-xs text-ink-3 mt-0.5">
                등록된 예약 정보와 발급된 4자리 일회성 비밀번호를 확인합니다.
              </p>
            </div>
            <span className="whitespace-nowrap text-xs font-semibold px-2.5 py-1 rounded bg-raised text-ink-2">
              총 {reservations.length}건
            </span>
          </div>

          <div className="overflow-x-auto">
            {reservations.length === 0 ? (
              <div className="py-12 text-center text-ink-3 text-xs">
                아직 예약이 없습니다. 위 양식으로 첫 예약을 신청해 보세요.
              </div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-line text-ink-3 text-[11px]">
                    <th className="pb-2 font-medium">예약일 / 타임</th>
                    <th className="pb-2 font-medium">신청자</th>
                    <th className="pb-2 font-medium">인원</th>
                    <th className="pb-2 font-medium">상태</th>
                    <th className="pb-2 font-medium">비밀번호 (OTP)</th>
                    <th className="pb-2 font-medium text-right">테스트</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {reservations.map((r) => (
                    <tr key={r.id} className="hover:bg-raised/30 transition-colors">
                      <td className="py-3 font-mono text-ink-2">
                        {r.reservation_date}
                        <span className="block text-[10px] text-ink-3">
                          {r.time_slot === "lunch" ? "점심 (12:30~13:20)" : "저녁 (17:30~18:30)"}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="font-semibold text-ink">{r.student_name}</span>
                        <span className="block text-[10px] text-ink-3">
                          {r.grade}학년 {r.department}
                        </span>
                      </td>
                      <td className="py-3 text-ink-2">{r.user_count}명</td>
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            r.status === "active"
                              ? "bg-free-soft border-free text-free"
                              : r.status === "completed"
                              ? "bg-raised border-line-strong text-ink-3"
                              : "bg-brass-soft border-brass text-brass"
                          }`}
                        >
                          {r.status === "active" ? "이용 중" : r.status === "completed" ? "이용 완료" : "예약됨"}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="font-mono font-bold text-free bg-canvas px-2 py-1 rounded border border-line">
                          {r.pin_code}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        {onSelectPinForSimulator && (
                          <button
                            onClick={() => onSelectPinForSimulator(r.pin_code)}
                            className="px-2.5 py-1 rounded bg-raised hover:bg-line-strong/90 text-ink-2 text-[11px] border border-line-strong transition-colors cursor-pointer"
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
