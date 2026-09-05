from datetime import datetime, timezone
import logging
import random
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from db import database as db
from schemas.reservation import (
    KeypadVerifyRequest,
    ReservationCreateRequest,
    SongRecordRequest,
)
from services.booth_service import BoothService
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routers.reservations")

reservations_router = APIRouter(prefix="/api/reservations", tags=["reservations"])
booth_router = APIRouter(prefix="/api/booth", tags=["booth-automation"])
songs_router = APIRouter(prefix="/api/songs", tags=["songs"])


# ==============================================================================
# 예약 엔드포인트 (F-01, F-02)
# ==============================================================================

@reservations_router.get("")
async def list_reservations() -> Dict[str, Any]:
    """예약 목록 조회"""
    try:
        items = db.get_reservations()
        return {"data": items}
    except Exception as exc:
        logger.error(f"Failed to fetch reservations: {exc}")
        return {"data": []}


@reservations_router.post("")
async def create_new_reservation(req: ReservationCreateRequest) -> Dict[str, Any]:
    """
    새 노래방 부스 예약 신청
    - 당일 예약 차단: 오늘 날짜 이하로 예약 신청 시 차단 ("당일 예약은 불가능합니다")
    - 중복 예약 차단: 동일 날짜/타임슬롯 중복 신청 차단
    - 4자리 일회성 비밀번호(OTP) 자동 생성
    """
    # 1. 날짜 유효성 검사 (당일 예약 불가)
    today_str = datetime.now().strftime("%Y-%m-%d")
    if req.reservation_date <= today_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SAME_DAY_NOT_ALLOWED",
                "message": "당일 예약은 불가능합니다. 최소 익일 이후 날짜를 선택해 주세요."
            }
        )

    # 2. 타임슬롯 유효성 검사
    if req.time_slot not in ("lunch", "dinner"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_TIME_SLOT",
                "message": "타임슬롯은 'lunch'(점심) 또는 'dinner'(저녁)여야 합니다."
            }
        )

    # 3. 중복 예약 여부 확인
    try:
        existing_list = db.get_reservations()
        for r in existing_list:
            # reservation_date가 datetime/str 혼용될 수 있으므로 문자열 변환
            r_date_str = str(r.get("reservation_date", ""))[:10]
            if r_date_str == req.reservation_date and r.get("time_slot") == req.time_slot:
                if r.get("status") in ("reserved", "active"):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "SLOT_ALREADY_RESERVED",
                            "message": f"선택하신 날짜({req.reservation_date})의 해당 시간대는 이미 예약이 완료되었습니다."
                        }
                    )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"Error checking duplicate reservation: {exc}")

    # 4. 무작위 4자리 OTP PIN 생성 (관리자 비번 9179 제외)
    while True:
        pin = f"{random.randint(1000, 9999)}"
        if pin != "9179":
            break

    try:
        reservation = db.create_reservation(
            grade=req.grade,
            department=req.department,
            student_name=req.student_name,
            user_count=req.user_count,
            reservation_date=req.reservation_date,
            time_slot=req.time_slot,
            pin_code=pin
        )
    except Exception as exc:
        logger.error(f"Failed to create reservation in DB: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "RESERVATION_CREATION_FAILED",
                "message": "예약 등록 중 데이터베이스 오류가 발생했습니다."
            }
        )

    # WebSocket 브로드캐스트
    await ws_manager.broadcast({
        "type": "reservation_created",
        "reservation_id": reservation.get("id"),
        "student_name": req.student_name,
        "reservation_date": req.reservation_date,
        "time_slot": req.time_slot,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    })

    return {"data": reservation}


# ==============================================================================
# 부스 자동화 및 시뮬레이터 제어 엔드포인트 (F-02 ~ F-04)
# ==============================================================================

@booth_router.post("/verify-keypad")
async def verify_keypad(req: KeypadVerifyRequest) -> Dict[str, Any]:
    """
    4x4 키패드 입력 비밀번호 검증 (사용자 OTP 또는 관리자 고정 비번 9179)
    """
    result = await BoothService.verify_and_trigger(req.pin)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PIN", "message": result.get("message")}
        )
    return {"data": result}


@booth_router.post("/simulate-entry")
async def simulate_entry() -> Dict[str, Any]:
    """입장 감지 센서(PIR) 또는 비전 사람 감지 트리거 시뮬레이션"""
    result = await BoothService.trigger_entry()
    return {"data": result}


@booth_router.post("/simulate-10min-warning")
async def simulate_10min_warning() -> Dict[str, Any]:
    """종료 10분 전 LED 깜빡임 및 사전 알림 트리거 시뮬레이션"""
    result = await BoothService.trigger_10min_warning()
    return {"data": result}


@booth_router.post("/simulate-end")
async def simulate_end() -> Dict[str, Any]:
    """이용 종료 및 퇴실곡 재생 + 전원/도어락 차단 트리거 시뮬레이션"""
    result = await BoothService.trigger_session_end()
    return {"data": result}


# ==============================================================================
# 노래 기록 및 나의 18번 엔드포인트 (F-05)
# ==============================================================================

@songs_router.get("")
async def list_songs(min_count: int = Query(3, ge=1)) -> Dict[str, Any]:
    """
    노래 목록 조회 (전체 및 나의 18번 애창곡 리스트)
    """
    all_songs = db.get_all_songs()
    favorites = db.get_favorite_songs(min_count=min_count)
    return {
        "data": {
            "all": all_songs,
            "favorites": favorites
        }
    }


@songs_router.post("")
async def add_song(req: SongRecordRequest) -> Dict[str, Any]:
    """부른 노래 기록 등록 (기존 곡이면 카운트 1 증가)"""
    recorded = db.record_song(title=req.title, singer=req.singer)
    await ws_manager.broadcast({
        "type": "song_recorded",
        "title": req.title,
        "singer": req.singer,
        "sing_count": recorded.get("sing_count"),
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    })
    return {"data": recorded}
