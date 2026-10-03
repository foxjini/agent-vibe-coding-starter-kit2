from datetime import datetime, timezone
import logging
import random
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from auth import get_admin_pin, verify_admin_token, is_valid_admin_token
from booth_time import today_str as booth_today
from db import database as db
from login_guard import client_key, keypad_guard
from schemas.reservation import (
    KeypadVerifyRequest,
    ReservationCreateRequest,
    ScoreRecordRequest,
    SongRecordRequest,
    SongVideoRequest,
    TicketIssueRequest,
)
from services.booth_service import BoothService
from services import scheduler, experience
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routers.reservations")

reservations_router = APIRouter(prefix="/api/reservations", tags=["reservations"])
booth_router = APIRouter(prefix="/api/booth", tags=["booth-automation"])
songs_router = APIRouter(prefix="/api/songs", tags=["songs"])
videos_router = APIRouter(prefix="/api/song-videos", tags=["song-videos"])
scores_router = APIRouter(prefix="/api/scores", tags=["scores"])
scheduler_router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
experience_router = APIRouter(prefix="/api/experience", tags=["experience"])


# ==============================================================================
# 예약 엔드포인트 (F-01, F-02)
# ==============================================================================

@reservations_router.get("")
async def list_reservations(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    """예약 목록 조회

    ⚠️ PIN은 관리자에게만 보여 준다. 이 목록은 부스 화면·학생 폰도 가져가는데,
    예전에는 모든 예약의 PIN이 그대로 실려 있어서 주소창에 이 API를 치기만 하면
    남의 예약 시간에 들어갈 수 있었다. 학생 본인은 신청할 때 받은 응답으로 PIN을 안다.
    """
    try:
        items = db.get_reservations()
    except Exception as exc:
        logger.error(f"Failed to fetch reservations: {exc}")
        return {"data": []}

    if not is_valid_admin_token(x_admin_token):
        items = [{k: v for k, v in r.items() if k != "pin_code"} for r in items]
    return {"data": items}


@reservations_router.post("")
async def create_new_reservation(req: ReservationCreateRequest) -> Dict[str, Any]:
    """
    새 노래방 부스 예약 신청
    - 당일 예약 차단: 오늘 날짜 이하로 예약 신청 시 차단 ("당일 예약은 불가능합니다")
    - 중복 예약 차단: 동일 날짜/타임슬롯 중복 신청 차단
    - 4자리 일회성 비밀번호(OTP) 자동 생성
    """
    # 1. 날짜 유효성 검사 (당일 예약 불가)
    #    서버 시계가 아니라 부스 시간으로 판단한다. Render(UTC)에서 datetime.now()를
    #    쓰면 한국 시간 0시~9시 사이에는 "어제"로 계산되어 당일 예약이 통과했다.
    today_str = booth_today()
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
    #    전체 목록(최근 50건)을 훑으면 예약이 많이 쌓였을 때 같은 날짜가 목록에서
    #    잘려 중복이 통과할 수 있다. 그 날짜·시간대만 콕 집어서 묻는다.
    try:
        existing = db.find_live_reservation(req.reservation_date, req.time_slot)
    except Exception as exc:
        logger.warning(f"Error checking duplicate reservation: {exc}")
        existing = None
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SLOT_ALREADY_RESERVED",
                "message": f"선택하신 날짜({req.reservation_date})의 해당 시간대는 이미 예약이 완료되었습니다."
            }
        )

    # 4. 무작위 4자리 OTP PIN 생성
    #    관리자 PIN(.env 값 — 9179로 고정된 게 아니다)과 개발용 PIN, 그리고 지금
    #    살아 있는 다른 예약·체험권의 PIN과 겹치지 않게 고른다. 겹치면 키패드가
    #    엉뚱한 사람의 예약을 열거나, 학생이 관리자 모드로 들어가 버린다.
    try:
        taken = set(db.pins_in_use(today_str))
    except Exception as exc:
        logger.warning(f"Could not read PINs in use: {exc}")
        taken = set()
    taken |= {get_admin_pin(), "1234"}
    for _ in range(500):
        pin = f"{random.randint(1000, 9999)}"
        if pin not in taken:
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
        # 다른 저장 API(점수·노래·체험권)와 같이 503 — "잠시 뒤 다시"가 맞는 상황이다
        logger.error(f"Failed to create reservation in DB: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "RESERVATION_CREATION_FAILED",
                "message": "예약을 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요."
            }
        )

    # WebSocket 브로드캐스트
    await ws_manager.broadcast({
        "type": "reservation_created",
        "reservation_id": reservation.get("id"),
        "student_name": req.student_name,
        "reservation_date": req.reservation_date,
        "time_slot": req.time_slot,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })

    return {"data": reservation}


# ==============================================================================
# 부스 자동화 및 시뮬레이터 제어 엔드포인트 (F-02 ~ F-04)
# ==============================================================================

@booth_router.post("/verify-keypad")
async def verify_keypad(req: KeypadVerifyRequest, request: Request) -> Dict[str, Any]:
    """
    4x4 키패드 입력 비밀번호 검증 (사용자 OTP 또는 .env의 관리자 PIN)

    연속으로 틀리면 잠시 막는다 (login_guard.py) — 시판 도어락과 같은 동작이다.
    "PIN은 맞는데 예약 시간이 아님"은 틀린 것으로 세지 않는다.
    """
    key = client_key(request)
    keypad_guard.check(key)

    result = await BoothService.verify_and_trigger(req.pin)
    if not result.get("success"):
        if result.get("reason") == "not_now":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NOT_RESERVATION_TIME", "message": result.get("message")}
            )
        keypad_guard.fail(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PIN", "message": result.get("message")}
        )
    keypad_guard.succeed(key)
    return {"data": result}


@booth_router.post("/simulate-entry")
async def simulate_entry(_admin: str = Depends(verify_admin_token)) -> Dict[str, Any]:
    """입장 감지 센서(PIR) 또는 비전 사람 감지 트리거 시뮬레이션"""
    result = await BoothService.trigger_entry()
    return {"data": result}


@booth_router.post("/simulate-10min-warning")
async def simulate_10min_warning(_admin: str = Depends(verify_admin_token)) -> Dict[str, Any]:
    """종료 10분 전 LED 깜빡임 및 사전 알림 트리거 시뮬레이션"""
    result = await BoothService.trigger_10min_warning()
    return {"data": result}


@booth_router.post("/simulate-end")
async def simulate_end(_admin: str = Depends(verify_admin_token)) -> Dict[str, Any]:
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

    DB가 아직 안 떠 있어도 노래방 화면 자체는 동작해야 하므로,
    다른 조회 엔드포인트와 같이 빈 목록으로 degrade한다.
    """
    try:
        all_songs = db.get_all_songs()
        favorites = db.get_favorite_songs(min_count=min_count)
    except Exception as exc:
        logger.error(f"Failed to fetch songs: {exc}")
        all_songs, favorites = [], []

    return {
        "data": {
            "all": all_songs,
            "favorites": favorites
        }
    }


@songs_router.post("")
async def add_song(req: SongRecordRequest) -> Dict[str, Any]:
    """부른 노래 기록 등록 (기존 곡이면 카운트 1 증가)"""
    try:
        recorded = db.record_song(title=req.title, singer=req.singer)
    except Exception as exc:
        # 다른 저장 API(점수)와 같이 503으로 알려 준다 — 정체 모를 500을 내지 않는다
        logger.error(f"Failed to record song: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SONG_SAVE_FAILED", "message": "노래 기록을 저장하지 못했습니다."}
        )
    await ws_manager.broadcast({
        "type": "song_recorded",
        "title": req.title,
        "singer": req.singer,
        "sing_count": recorded.get("sing_count"),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })
    return {"data": recorded}


# ==============================================================================
# 노래방 영상 등록 (F-06)
#
# 조회는 누구나 할 수 있다 — 부스 화면과 관람객 폰이 같은 영상을 봐야 하므로.
# 등록·삭제는 관리자만 할 수 있다 — 모든 사람이 보는 화면을 바꾸는 일이므로.
# ==============================================================================

@videos_router.get("")
async def list_song_videos() -> Dict[str, Any]:
    """등록된 곡별 영상 ID 목록. DB가 없어도 빈 목록으로 degrade한다."""
    try:
        return {"data": db.get_song_videos()}
    except Exception as exc:
        logger.error(f"Failed to fetch song videos: {exc}")
        return {"data": {}}


@videos_router.put("/{song_id}")
async def register_song_video(
    song_id: str,
    req: SongVideoRequest,
    _admin: str = Depends(verify_admin_token),
) -> Dict[str, Any]:
    """곡의 노래방 영상을 등록합니다 (관리자 전용)."""
    saved = db.set_song_video(song_id, req.video_id)
    logger.info(f"Song video registered: {song_id} -> {req.video_id}")
    return {"data": saved}


@videos_router.delete("/{song_id}")
async def unregister_song_video(
    song_id: str,
    _admin: str = Depends(verify_admin_token),
) -> Dict[str, Any]:
    """등록을 지우고 기본 후보 목록으로 되돌립니다 (관리자 전용)."""
    db.delete_song_video(song_id)
    return {"data": {"song_id": song_id, "removed": True}}


# ==============================================================================
# 점수 기록과 랭킹 (부록G §2-④)
#
# 기록은 부스 화면이 채점을 마치면 바로 올린다 — 관리자 인증을 걸지 않는다.
# 전시장에서는 관람객이 직접 부르고 바로 순위에 오르는 것이 이 기능의 전부라,
# 여기에 인증을 걸면 기능 자체가 성립하지 않는다.
# 조회도 열어 둔다 — 부스 대형 화면과 관람객 폰이 같은 순위를 봐야 한다.
# ==============================================================================

@scores_router.post("")
async def record_score(req: ScoreRecordRequest) -> Dict[str, Any]:
    """채점 결과를 남기고 대시보드에 실시간으로 알립니다."""
    try:
        saved = db.record_score(
            nickname=(req.nickname or "익명").strip() or "익명",
            title=req.title,
            singer=req.singer,
            score=req.score,
            rank_label=req.rank_label,
            pitch=req.pitch,
            timing=req.timing,
            volume=req.volume,
            expression=req.expression,
        )
    except Exception as exc:
        # 점수를 못 남겼다고 해서 부스 화면이 멈추면 안 된다
        logger.error(f"Failed to record score: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SCORE_SAVE_FAILED", "message": "점수를 저장하지 못했습니다."}
        )

    await ws_manager.broadcast({
        "type": "score_recorded",
        "nickname": saved.get("nickname"),
        "title": saved.get("title"),
        "score": saved.get("score"),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })
    return {"data": saved}


@scores_router.get("/top")
async def list_top_scores(
    period: str = Query("today", pattern="^(today|all)$"),
    limit: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    """오늘의 순위(today) 또는 명예의 전당(all). DB가 없어도 빈 목록으로 degrade한다."""
    try:
        return {"data": db.get_top_scores(period=period, limit=limit)}
    except Exception as exc:
        logger.error(f"Failed to fetch top scores: {exc}")
        return {"data": []}


@scores_router.get("/recent")
async def list_recent_scores(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    """최근 기록 순."""
    try:
        return {"data": db.get_recent_scores(limit=limit)}
    except Exception as exc:
        logger.error(f"Failed to fetch recent scores: {exc}")
        return {"data": []}


# ==============================================================================
# 예약 시간 자동 운영 엔진 (부록G §2-①)
#
# 상태 조회는 열어 둔다 — 관리자 화면이 "엔진이 살아 있나"를 계속 보여 줘야 한다.
# 수동 실행은 관리자만 할 수 있다. 시연이나 점검 때 1분을 기다리지 않고
# 곧바로 한 바퀴 돌려 보기 위한 것이다.
# ==============================================================================

@scheduler_router.get("/status")
async def scheduler_status() -> Dict[str, Any]:
    """엔진 설정·마지막 실행 시각·최근 처리 내역·오늘 남은 일정."""
    try:
        return {"data": scheduler.get_status()}
    except Exception as exc:
        logger.error(f"Failed to read scheduler status: {exc}")
        return {"data": {"enabled": False, "last_error": str(exc), "actions": [], "upcoming": []}}


@scheduler_router.post("/run")
async def scheduler_run_once(_admin: str = Depends(verify_admin_token)) -> Dict[str, Any]:
    """지금 즉시 한 바퀴 돌립니다 (관리자 전용)."""
    result = await scheduler.run_once()
    return {"data": result}


# ==============================================================================
# 전시 체험 모드 — QR 체험권 + 대기열 (부록G §2-③)
#
# 발급과 조회는 인증 없이 열어 둔다. 관람객이 QR을 찍자마자 바로 써야 하는데
# 여기에 로그인을 붙이면 줄이 더 길어진다.
# 줄을 건너뛰는 조작(강제 호출·취소)만 관리자 전용이다.
# ==============================================================================

@experience_router.post("/tickets")
async def issue_experience_ticket(req: TicketIssueRequest) -> Dict[str, Any]:
    """QR을 찍은 관람객에게 체험권을 발급합니다."""
    if not experience.ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "EXPERIENCE_DISABLED", "message": "지금은 체험 모드를 운영하지 않습니다."}
        )
    try:
        ticket = await experience.issue_ticket(req.nickname)
    except Exception as exc:
        logger.error(f"Failed to issue experience ticket: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "TICKET_ISSUE_FAILED", "message": "체험권을 발급하지 못했습니다."}
        )
    return {"data": ticket}


@experience_router.get("/queue")
async def experience_queue() -> Dict[str, Any]:
    """대기열 현황 — 부스 대형 화면과 관람객 폰이 같은 것을 봅니다."""
    return {"data": experience.snapshot()}


@experience_router.get("/tickets/{ticket_id}")
async def experience_ticket(
    ticket_id: int,
    pin: Optional[str] = None,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    """내 체험권 상태와 남은 순번. 관람객 폰이 주기적으로 확인합니다.

    체험권 번호는 1, 2, 3... 으로 이어지므로 남의 번호를 넣어 보는 것은 쉽다.
    그래서 비밀번호는 발급받을 때 한 번만 알려 주고, 이 조회에서는
    자기 비밀번호를 같이 보낸 사람(= 실제 체험권 주인)에게만 돌려준다.
    그러지 않으면 호출된 사람의 비밀번호를 옆에서 읽어 새치기할 수 있다.
    관리자 화면은 예외다 — 관람객이 폰에서 비밀번호를 놓쳤을 때 선생님이
    읽어 줄 수 있어야 하므로, 관리자 토큰이 있으면 같이 돌려준다.
    """
    try:
        ticket = db.get_queue_ticket(ticket_id)
    except Exception as exc:
        logger.error(f"Failed to read ticket {ticket_id}: {exc}")
        ticket = None

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TICKET_NOT_FOUND", "message": "체험권을 찾을 수 없습니다."}
        )

    try:
        same_day = db.get_queue_tickets(str(ticket.get("issued_on"))[:10], list(experience.ACTIVE_STATUSES))
    except Exception:
        same_day = []

    safe = {k: v for k, v in ticket.items() if k != "pin_code"}
    owner = bool(pin) and secrets.compare_digest(str(pin), str(ticket.get("pin_code") or ""))
    if owner or is_valid_admin_token(x_admin_token):
        safe["pin_code"] = ticket.get("pin_code")

    return {
        "data": {
            **safe,
            "position": experience.position_of(ticket, same_day),
            "estimated_wait_min": max(0, experience.position_of(ticket, same_day))
            * experience.EXPERIENCE_MINUTES,
        }
    }


@experience_router.post("/advance")
async def experience_advance(_admin: str = Depends(verify_admin_token)) -> Dict[str, Any]:
    """대기열을 지금 한 칸 굴립니다 (관리자 전용)."""
    return {"data": {"actions": await experience.advance()}}


@experience_router.post("/tickets/{ticket_id}/cancel")
async def experience_cancel(
    ticket_id: int,
    _admin: str = Depends(verify_admin_token),
) -> Dict[str, Any]:
    """체험권을 취소합니다 (관리자 전용). 취소 후 다음 사람을 호출합니다."""
    db.update_ticket_status(ticket_id, "expired")
    await experience.advance()
    return {"data": {"ticket_id": ticket_id, "cancelled": True}}
