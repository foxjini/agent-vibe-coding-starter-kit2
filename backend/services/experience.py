"""
전시 체험 모드 — QR 즉석 체험권 + 대기열 (부록G §2-③)

전시장 관람객에게는 예약 PIN이 없다. 예약은 학교 학생이 전날 신청하는 것이고,
전시회에 온 사람은 지금 이 자리에서 한 번 해 보고 싶을 뿐이다.

그래서 이런 흐름을 만든다.

    부스 화면의 QR을 폰으로 찍는다
      → 체험권 발급 (대기 번호 + 4자리 PIN)
      → 앞사람이 끝나면 "OO번 입장하세요" 호출
      → 그 PIN으로 부스 키패드를 누르면 문이 열린다
      → 정해진 시간이 지나면 자동 종료, 다음 사람 호출

줄 서는 문제까지 시스템이 푸는 그림이고, 학생들이 "다음 분 들어가세요"를 종일
외치지 않아도 된다.

상태 흐름:  waiting → called → active → done
                          ↘ expired (호출했는데 오지 않음)
"""

import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from booth_time import now_local, today_str
from db import database as db
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.experience")


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


ENABLED = os.getenv("EXPERIENCE_ENABLED", "true").strip().lower() != "false"
# 한 사람이 쓰는 시간. 전시장에서는 3분이면 한 곡을 부르기에 충분하고,
# 줄이 길어져도 회전이 돈다.
EXPERIENCE_MINUTES = _int_env("EXPERIENCE_MINUTES", 3)
# 호출했는데 이 시간 안에 오지 않으면 다음 사람에게 넘긴다.
CALL_GRACE_MINUTES = _int_env("EXPERIENCE_CALL_GRACE_MIN", 2)

ACTIVE_STATUSES = ("waiting", "called", "active")


def _parse(dt: Any) -> Optional[datetime]:
    """DB가 돌려준 시각 문자열을 부스 시간대 기준 datetime 으로."""
    if not dt:
        return None
    text = str(dt).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    tz = now_local().tzinfo
    return parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)


def _generate_pin(used: List[str]) -> str:
    """쓰이지 않는 4자리를 고른다. 관리자 PIN 과 개발용 만능 PIN 은 피한다."""
    from auth import get_admin_pin

    blocked = set(used) | {"1234", str(get_admin_pin())}
    for _ in range(200):
        pin = f"{random.randint(1000, 9999)}"
        if pin not in blocked:
            return pin
    # 여기까지 오면 번호가 동났다는 뜻 — 전시장에서 일어날 일은 아니다
    raise RuntimeError("쓸 수 있는 PIN 을 찾지 못했습니다.")


async def issue_ticket(nickname: str) -> Dict[str, Any]:
    """체험권을 발급한다. 앞에 아무도 없으면 곧바로 호출까지 이어진다."""
    day = today_str()
    pin = _generate_pin(db.pins_in_use(day))
    ticket = db.issue_queue_ticket(nickname.strip()[:20] or "관람객", pin, day)

    await ws_manager.broadcast({
        "type": "queue_updated",
        "event": "issued",
        "ticket_no": ticket.get("ticket_no"),
        "nickname": ticket.get("nickname"),
    })

    # 대기 줄이 비어 있었다면 바로 자기 차례다
    await advance()
    return db.get_queue_ticket(int(ticket["id"])) or ticket


def position_of(ticket: Dict[str, Any], tickets: List[Dict[str, Any]]) -> int:
    """앞에 몇 명이 남았는지 (0이면 내 차례)."""
    status = str(ticket.get("status") or "")
    if status in ("called", "active"):
        return 0
    if status not in ("waiting",):
        return -1
    ahead = [
        t for t in tickets
        if str(t.get("status")) in ACTIVE_STATUSES
        and int(t.get("ticket_no") or 0) < int(ticket.get("ticket_no") or 0)
    ]
    return len(ahead)


def snapshot() -> Dict[str, Any]:
    """대기열 현황. 부스 화면·관람객 폰·관리자 화면이 같은 것을 본다."""
    day = today_str()
    try:
        tickets = db.get_queue_tickets(day, list(ACTIVE_STATUSES))
    except Exception as exc:
        logger.warning(f"대기열 조회 실패: {exc}")
        tickets = []

    serving = next(
        (t for t in tickets if str(t.get("status")) in ("called", "active")), None
    )
    waiting = [t for t in tickets if str(t.get("status")) == "waiting"]

    return {
        "enabled": ENABLED,
        "experience_minutes": EXPERIENCE_MINUTES,
        "call_grace_minutes": CALL_GRACE_MINUTES,
        "now": now_local().isoformat(timespec="seconds"),
        "now_serving": (
            {
                "id": serving.get("id"),
                "ticket_no": serving.get("ticket_no"),
                "nickname": serving.get("nickname"),
                "status": serving.get("status"),
                "called_at": serving.get("called_at"),
                "started_at": serving.get("started_at"),
            }
            if serving
            else None
        ),
        "waiting_count": len(waiting),
        # 대기 줄에는 PIN 을 싣지 않는다 — 부스 대형 화면에 남의 번호가 보이면 안 된다
        "waiting": [
            {"id": t.get("id"), "ticket_no": t.get("ticket_no"), "nickname": t.get("nickname")}
            for t in waiting
        ],
        "estimated_wait_min": len(waiting) * EXPERIENCE_MINUTES,
    }


async def start_ticket(ticket: Dict[str, Any]) -> None:
    """키패드에서 체험권 PIN 이 통과했을 때 — 이용 시작으로 넘긴다."""
    db.update_ticket_status(int(ticket["id"]), "active")
    await ws_manager.broadcast({
        "type": "queue_updated",
        "event": "started",
        "ticket_no": ticket.get("ticket_no"),
        "nickname": ticket.get("nickname"),
    })


async def advance() -> List[Dict[str, Any]]:
    """
    대기열을 한 칸 굴린다. 스케줄러가 1분마다 부르고, 발급·종료 직후에도 부른다.

      1. 호출해 뒀는데 오지 않은 사람 → 만료
      2. 이용 시간이 끝난 사람 → 종료 처리 + 부스 전원 차단
      3. 부스가 비어 있으면 → 다음 사람 호출

    DB가 꺼져 있으면 아무 일도 하지 않는다.
    """
    if not ENABLED:
        return []

    day = today_str()
    now = now_local()
    actions: List[Dict[str, Any]] = []

    try:
        tickets = db.get_queue_tickets(day, list(ACTIVE_STATUSES))
    except Exception as exc:
        logger.warning(f"대기열 진행 실패: {exc}")
        return []

    # 1) 호출했는데 오지 않은 체험권 만료
    for t in tickets:
        if str(t.get("status")) != "called":
            continue
        called_at = _parse(t.get("called_at"))
        if called_at and now >= called_at + timedelta(minutes=CALL_GRACE_MINUTES):
            db.update_ticket_status(int(t["id"]), "expired")
            actions.append({"event": "expired", "ticket_no": t.get("ticket_no")})
            logger.info(f"[queue] {t.get('ticket_no')}번 체험권 만료 (호출 후 미입장)")

    # 2) 이용 시간이 끝난 체험권 종료
    for t in tickets:
        if str(t.get("status")) != "active":
            continue
        started_at = _parse(t.get("started_at"))
        if started_at and now >= started_at + timedelta(minutes=EXPERIENCE_MINUTES):
            from services.booth_service import BoothService

            await BoothService.trigger_session_end()
            db.update_ticket_status(int(t["id"]), "done")
            actions.append({"event": "finished", "ticket_no": t.get("ticket_no")})
            logger.info(f"[queue] {t.get('ticket_no')}번 체험 종료 ({EXPERIENCE_MINUTES}분 경과)")

    # 3) 부스가 비었으면 다음 사람 호출
    try:
        tickets = db.get_queue_tickets(day, list(ACTIVE_STATUSES))
    except Exception:
        tickets = []

    busy = any(str(t.get("status")) in ("called", "active") for t in tickets)
    if not busy:
        nxt = next((t for t in tickets if str(t.get("status")) == "waiting"), None)
        if nxt:
            db.update_ticket_status(int(nxt["id"]), "called")
            actions.append({"event": "called", "ticket_no": nxt.get("ticket_no")})
            logger.info(f"[queue] {nxt.get('ticket_no')}번 호출")
            await ws_manager.broadcast({
                "type": "queue_called",
                "ticket_no": nxt.get("ticket_no"),
                "nickname": nxt.get("nickname"),
                "message": f"{nxt.get('ticket_no')}번 {nxt.get('nickname')}님, 입장해 주세요!",
            })

    if actions:
        await ws_manager.broadcast({"type": "queue_updated", "event": "advanced"})
    return actions
