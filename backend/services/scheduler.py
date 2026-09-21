"""
예약 시간 자동 운영 엔진 (부록G §2-① · ⑨)

이 프로젝트의 하이라이트다. 지금까지 "종료 10분 전 알림"이나 "이용 종료"는
관리자가 버튼을 눌러야만 일어났다. 사람이 시계를 보고 있어야 하는 시스템은
'무인 자동화'라고 부를 수 없다.

이 모듈은 1분마다 깨어나 오늘 예약을 훑고, 시각이 되면 알아서 처리한다.

  예약 시작        → (사람이 4자리 PIN을 누르면 도어락·전원이 열린다)
  시작 + 유예시간  → 아무도 안 들어왔으면 노쇼 처리 (⑨)
  종료 10분 전     → LED 깜빡임 + 안내 음성
  종료 시각        → 퇴실곡 재생 → 전원·도어락 차단, 예약 완료 처리

⚠️ 전원을 켜는 것은 여기서 하지 않는다.
   팀 트리거 규칙(AGENTS.md)이 "일회성 4자리 비밀번호 인증 성공 시 도어락을
   해제하고 릴레이를 통해 전원을 공급한다"이기 때문이다. 시간이 됐다고 빈 부스에
   220V를 넣어 두는 것은 안전하지도 않다. 엔진은 **끄는 쪽**을 책임진다.

⚠️ 시간대(timezone)에 주의한다.
   Render 같은 클라우드에 올리면 서버 시계가 UTC다. 그대로 두면 점심 타임이
   새벽에 도는 일이 벌어진다. 그래서 항상 한국 시간으로 환산해서 판단한다.
"""

import asyncio
import logging
import os
from datetime import datetime, time as dtime, timedelta
from typing import Any, Dict, List, Optional

from db import database as db
from services.booth_service import BoothService
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.scheduler")

# ── 타임슬롯 정의 ─────────────────────────────────────────────────────────
# 프론트엔드(BoothStatusCard · ReservationSection)에 적힌 시간과 같아야 한다.
SLOT_WINDOWS: Dict[str, tuple] = {
    "lunch": (dtime(12, 30), dtime(13, 20)),
    "dinner": (dtime(17, 30), dtime(18, 30)),
}

# ── 설정 ──────────────────────────────────────────────────────────────────
def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


ENABLED = os.getenv("SCHEDULER_ENABLED", "true").strip().lower() != "false"
INTERVAL_SEC = _int_env("SCHEDULER_INTERVAL_SEC", 60)
WARN_BEFORE_MIN = _int_env("SCHEDULER_WARN_BEFORE_MIN", 10)
NO_SHOW_GRACE_MIN = _int_env("SCHEDULER_NO_SHOW_GRACE_MIN", 15)

# 경고를 쏘는 시간 창. 창을 좁게 두면, 서버가 그 사이에 재시작해도 중복 경고가
# 나가지 않는다 (기억은 메모리에만 있어서 재시작하면 지워지기 때문이다).
WARN_WINDOW_MIN = 2

try:
    from zoneinfo import ZoneInfo

    _TZ: Optional[ZoneInfo] = ZoneInfo(os.getenv("BOOTH_TIMEZONE", "Asia/Seoul"))
except Exception:  # tzdata가 없는 최소 이미지 등
    _TZ = None
    logger.warning("시간대 정보를 불러오지 못해 서버 로컬 시간으로 동작합니다.")


def now_local() -> datetime:
    """부스가 있는 곳의 현재 시각 (서버가 UTC여도 한국 시간으로 환산)"""
    return datetime.now(_TZ) if _TZ else datetime.now()


# ── 실행 상태 (관리자 화면에서 들여다본다) ───────────────────────────────
_state: Dict[str, Any] = {
    "last_tick": None,
    "last_error": None,
    "actions": [],       # 최근 처리 내역 (최신이 앞)
    "warned_ids": set(),  # 이번 실행 중 10분 전 알림을 이미 보낸 예약
}


def _remember(action: str, reservation: Dict[str, Any], message: str) -> Dict[str, Any]:
    entry = {
        "action": action,
        "reservation_id": reservation.get("id"),
        "student_name": reservation.get("student_name"),
        "time_slot": reservation.get("time_slot"),
        "message": message,
        "at": now_local().isoformat(timespec="seconds"),
    }
    _state["actions"] = ([entry] + _state["actions"])[:20]
    logger.info(f"[scheduler] {action}: {message}")
    return entry


def slot_bounds(day: datetime, time_slot: str) -> Optional[tuple]:
    """그 날짜의 타임슬롯 시작·종료 시각을 돌려준다."""
    window = SLOT_WINDOWS.get(time_slot)
    if not window:
        return None
    start = datetime.combine(day.date(), window[0], tzinfo=day.tzinfo)
    end = datetime.combine(day.date(), window[1], tzinfo=day.tzinfo)
    return start, end


async def run_once() -> Dict[str, Any]:
    """
    한 번 훑는다. 스케줄러 루프가 부르고, 관리자가 수동으로도 부를 수 있다.

    DB가 꺼져 있으면 아무 일도 하지 않고 조용히 넘어간다 — 엔진이 죽어서
    백엔드 전체가 멈추면 안 된다.
    """
    now = now_local()
    today = now.strftime("%Y-%m-%d")
    done: List[Dict[str, Any]] = []

    try:
        reservations = db.get_reservations()
    except Exception as exc:
        _state["last_error"] = f"예약 목록을 읽지 못했습니다: {exc}"
        _state["last_tick"] = now.isoformat(timespec="seconds")
        return {"checked": 0, "actions": []}

    _state["last_error"] = None

    for r in reservations:
        if str(r.get("reservation_date") or "")[:10] != today:
            continue
        bounds = slot_bounds(now, str(r.get("time_slot") or ""))
        if not bounds:
            continue

        start, end = bounds
        status = str(r.get("status") or "")
        rid = r.get("id")

        # ── 노쇼 자동 취소 (⑨) ──────────────────────────────────────
        # 시작하고 유예 시간이 지나도록 아무도 PIN을 누르지 않았다.
        if status == "reserved" and now >= start + timedelta(minutes=NO_SHOW_GRACE_MIN):
            try:
                db.update_reservation_status(rid, "no_show")
            except Exception as exc:
                logger.warning(f"노쇼 처리 실패 (예약 {rid}): {exc}")
                continue
            entry = _remember(
                "no_show", r,
                f"{r.get('student_name')} 학생이 {NO_SHOW_GRACE_MIN}분 동안 입장하지 않아 "
                f"예약을 자동 취소했습니다."
            )
            done.append(entry)
            await ws_manager.broadcast({"type": "scheduler_action", **entry})
            continue

        if status != "active":
            continue

        # ── 종료 10분 전 알림 ───────────────────────────────────────
        warn_at = end - timedelta(minutes=WARN_BEFORE_MIN)
        if warn_at <= now < warn_at + timedelta(minutes=WARN_WINDOW_MIN) \
                and rid not in _state["warned_ids"]:
            await BoothService.trigger_10min_warning()
            _state["warned_ids"].add(rid)
            entry = _remember(
                "warn_10min", r,
                f"이용 종료 {WARN_BEFORE_MIN}분 전 — LED 알림과 안내 음성을 내보냈습니다."
            )
            done.append(entry)
            await ws_manager.broadcast({"type": "scheduler_action", **entry})

        # ── 종료 처리 ───────────────────────────────────────────────
        if now >= end:
            await BoothService.trigger_session_end()
            try:
                db.update_reservation_status(rid, "completed")
            except Exception as exc:
                logger.warning(f"종료 상태 갱신 실패 (예약 {rid}): {exc}")
            _state["warned_ids"].discard(rid)
            entry = _remember(
                "session_end", r,
                "이용 시간이 끝나 퇴실곡을 재생하고 전원·도어락을 차단했습니다."
            )
            done.append(entry)
            await ws_manager.broadcast({"type": "scheduler_action", **entry})

    _state["last_tick"] = now.isoformat(timespec="seconds")
    return {"checked": len(reservations), "actions": done}


def get_status() -> Dict[str, Any]:
    """관리자 화면이 '엔진이 살아 있나'를 확인할 때 쓴다."""
    now = now_local()
    today = now.strftime("%Y-%m-%d")

    upcoming: List[Dict[str, Any]] = []
    try:
        for r in db.get_reservations():
            if str(r.get("reservation_date") or "")[:10] != today:
                continue
            if str(r.get("status") or "") not in ("reserved", "active"):
                continue
            bounds = slot_bounds(now, str(r.get("time_slot") or ""))
            if not bounds:
                continue
            start, end = bounds
            upcoming.append({
                "reservation_id": r.get("id"),
                "student_name": r.get("student_name"),
                "time_slot": r.get("time_slot"),
                "status": r.get("status"),
                "starts_at": start.isoformat(timespec="minutes"),
                "warns_at": (end - timedelta(minutes=WARN_BEFORE_MIN)).isoformat(timespec="minutes"),
                "ends_at": end.isoformat(timespec="minutes"),
            })
    except Exception as exc:
        logger.warning(f"스케줄러 상태 조회 중 DB 오류: {exc}")

    return {
        "enabled": ENABLED,
        "interval_sec": INTERVAL_SEC,
        "warn_before_min": WARN_BEFORE_MIN,
        "no_show_grace_min": NO_SHOW_GRACE_MIN,
        "timezone": str(_TZ) if _TZ else "server-local",
        "now": now.isoformat(timespec="seconds"),
        "last_tick": _state["last_tick"],
        "last_error": _state["last_error"],
        "actions": _state["actions"],
        "upcoming": sorted(upcoming, key=lambda u: u["starts_at"]),
    }


# ── 백그라운드 루프 ───────────────────────────────────────────────────────

_task: Optional[asyncio.Task] = None


async def _loop() -> None:
    logger.info(
        f"예약 자동 운영 엔진 시작 — {INTERVAL_SEC}초 주기, "
        f"종료 {WARN_BEFORE_MIN}분 전 알림, 노쇼 유예 {NO_SHOW_GRACE_MIN}분"
    )
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 한 번 실패했다고 엔진이 멈추면 안 된다
            _state["last_error"] = str(exc)
            logger.error(f"스케줄러 tick 실패: {exc}")
        await asyncio.sleep(INTERVAL_SEC)


def start() -> None:
    """FastAPI 시작 시 호출한다."""
    global _task
    if not ENABLED:
        logger.info("SCHEDULER_ENABLED=false — 예약 자동 운영 엔진을 켜지 않습니다.")
        return
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop())


async def stop() -> None:
    """FastAPI 종료 시 호출한다."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
