from typing import Optional
from pydantic import BaseModel, Field


class ReservationCreateRequest(BaseModel):
    """예약 신청 요청 스키마"""
    grade: int = Field(..., ge=1, le=3, description="학년 (1~3)")
    department: str = Field(..., min_length=2, description="학과명")
    student_name: str = Field(..., min_length=2, description="신청자 이름")
    user_count: int = Field(..., ge=1, le=10, description="이용 인원 (최대 10명)")
    reservation_date: str = Field(..., description="예약 일자 (YYYY-MM-DD)")
    time_slot: str = Field(..., description="타임슬롯 ('lunch' 또는 'dinner')")


class KeypadVerifyRequest(BaseModel):
    """4x4 키패드 비밀번호 검증 요청"""
    pin: str = Field(..., min_length=4, max_length=4, description="4자리 비밀번호 (숫자)")


class SongRecordRequest(BaseModel):
    """노래 이력 등록 요청"""
    title: str = Field(..., min_length=1, description="곡 제목")
    singer: str = Field(..., min_length=1, description="가수 이름")
