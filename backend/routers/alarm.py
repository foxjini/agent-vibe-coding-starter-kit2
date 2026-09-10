import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import verify_user_auth
from db.database import get_app_setting, get_db_status, set_app_setting
from schemas.common import DataResponse
from services.device_control import BUZZER_ID, set_actuator
from services.trigger_service import RINGING_STATES, trigger_service
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routers.alarm")

router = APIRouter(prefix="/api/alarm", tags=["Alarm"])

# 알람 예약은 '사용자가 사는 지역 시간'으로 해석해야 한다.
# Render 같은 클라우드 서버는 UTC로 동작하므로, 서버 로컬 시간을 쓰면 9시간이 밀린다.
ALARM_TIMEZONE = os.getenv("ALARM_TIMEZONE", "Asia/Seoul")
ALARM_SETTING_KEY = "alarm_schedule"

_ALARM_VALUE = {"volume": 85, "frequency": 1000}


def get_alarm_tzinfo() -> timezone:
    """설정된 지역 시간대를 반환합니다. (시간대 DB가 없으면 서버 로컬 시간으로 폴백)"""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(ALARM_TIMEZONE)  # type: ignore[return-value]
    except Exception as exc:  # ZoneInfoNotFoundError 포함 (윈도우에서 tzdata 미설치 시)
        logger.warning(
            f"시간대 '{ALARM_TIMEZONE}'를 불러오지 못해 서버 로컬 시간을 사용합니다: {exc} "
            "(해결: pip install tzdata)"
        )
        return datetime.now().astimezone().tzinfo  # type: ignore[return-value]


def _now_local() -> datetime:
    return datetime.now(get_alarm_tzinfo())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_hhmm(raw: str) -> Tuple[int, int, int]:
    """'07:30' 또는 '07:30:05'를 (시, 분, 초)로 변환하고 범위를 검증합니다."""
    parts = raw.strip().split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError("알람 시각은 'HH:MM' 형식이어야 합니다.")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        raise ValueError("알람 시각에는 숫자만 사용할 수 있습니다. (예: 07:30)")

    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError("알람 시각 범위가 올바르지 않습니다. (00:00 ~ 23:59)")
    return hour, minute, second


def _next_occurrence(hour: int, minute: int, second: int) -> datetime:
    """오늘(또는 내일)의 다음 알람 시각을 지역 시간 기준으로 계산합니다."""
    now = _now_local()
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _describe_remaining(seconds: int) -> str:
    hours_left = seconds // 3600
    mins_left = (seconds % 3600) // 60
    secs_left = seconds % 60
    parts = []
    if hours_left > 0:
        parts.append(f"{hours_left}시간")
    if mins_left > 0:
        parts.append(f"{mins_left}분")
    parts.append(f"{secs_left}초")
    return " ".join(parts)


class AlarmScheduler:
    """
    알람 예약 상태 관리자.

    예약 내용은 DB(app_settings)에 저장되어 서버를 재시작해도 살아남습니다.
    (메모리에만 두면 `uvicorn --reload` 한 번에 예약이 사라집니다 — 부록A 트러블슈팅 참고)
    """

    def __init__(self) -> None:
        self.mode: Optional[str] = None          # "daily" | "once"
        self.alarm_time: Optional[str] = None    # "HH:MM"
        self.label: Optional[str] = None         # 대시보드 표시용 문자열
        self.last_triggered_at: Optional[str] = None
        self.next_fire_at: Optional[str] = None  # 지역 시간 ISO
        self._task: Optional[asyncio.Task] = None

    # -- 상태 -------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return bool(self._task and not self._task.done())

    def snapshot(self) -> Dict[str, Any]:
        remaining = None
        if self.next_fire_at:
            try:
                remaining = max(
                    0,
                    int((datetime.fromisoformat(self.next_fire_at) - _now_local()).total_seconds()),
                )
            except ValueError:
                remaining = None
        return {
            "scheduled_time": self.label or self.alarm_time,
            "alarm_time": self.alarm_time,
            "mode": self.mode,
            "is_scheduled": self.is_active,
            "timezone": ALARM_TIMEZONE,
            "next_fire_at": self.next_fire_at,
            "remaining_seconds": remaining,
            "last_triggered_at": self.last_triggered_at,
        }

    # -- 예약/취소 ---------------------------------------------------------

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self.next_fire_at = None

    async def schedule_daily(self, alarm_time: str, persist: bool = True) -> Dict[str, Any]:
        hour, minute, second = _parse_hhmm(alarm_time)
        self.cancel()
        self.mode = "daily"
        self.alarm_time = alarm_time
        self.label = alarm_time
        self._task = asyncio.create_task(self._daily_loop(hour, minute, second))

        if persist:
            await asyncio.to_thread(
                set_app_setting,
                ALARM_SETTING_KEY,
                {"mode": "daily", "alarm_time": alarm_time, "timezone": ALARM_TIMEZONE},
            )
        return self.snapshot()

    async def schedule_countdown(self, seconds: int) -> Dict[str, Any]:
        self.cancel()
        self.mode = "once"
        self.alarm_time = None
        self.label = f"{seconds}초 후"
        self.next_fire_at = (_now_local() + timedelta(seconds=seconds)).isoformat()
        self._task = asyncio.create_task(self._countdown(seconds))
        return self.snapshot()

    async def clear(self) -> None:
        """예약을 해제하고 저장된 설정도 지웁니다."""
        self.cancel()
        self.mode = None
        self.alarm_time = None
        self.label = None
        await asyncio.to_thread(set_app_setting, ALARM_SETTING_KEY, None)

    async def restore(self) -> None:
        """서버 시작 시 저장된 예약을 복원합니다."""
        saved = await asyncio.to_thread(get_app_setting, ALARM_SETTING_KEY)
        if not saved or not isinstance(saved, dict):
            return
        alarm_time = saved.get("alarm_time")
        if saved.get("mode") == "daily" and alarm_time:
            try:
                await self.schedule_daily(alarm_time, persist=False)
                logger.info(f"[알람 스케줄러] 저장된 예약을 복원했습니다: 매일 {alarm_time}")
            except ValueError as exc:
                logger.warning(f"[알람 스케줄러] 저장된 예약이 올바르지 않아 무시합니다: {exc}")

    # -- 내부 태스크 -------------------------------------------------------

    async def _sleep_until(self, target: datetime) -> None:
        """
        목표 시각까지 나눠서 대기합니다.
        한 번에 몇 시간을 sleep하지 않으므로 노트북 절전/시간 변경 후에도 오차가 누적되지 않습니다.
        """
        while True:
            remaining = (target - _now_local()).total_seconds()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 30))

    async def _daily_loop(self, hour: int, minute: int, second: int) -> None:
        try:
            while True:
                target = _next_occurrence(hour, minute, second)
                self.next_fire_at = target.isoformat()
                logger.info(
                    f"[알람 스케줄러] 다음 알람: {target.isoformat()} ({ALARM_TIMEZONE}) "
                    f"— 약 {int((target - _now_local()).total_seconds())}초 후"
                )
                await self._sleep_until(target)
                await trigger_alarm_now(reason=f"scheduled_{self.alarm_time}")
                # 같은 분 안에서 중복 발동하지 않도록 한 번 넘긴다
                await asyncio.sleep(61)
        except asyncio.CancelledError:
            logger.info("[알람 스케줄러] 예약 태스크가 정상 취소되었습니다.")
            raise
        except Exception as exc:
            logger.error(f"[알람 스케줄러] 예약 실행 중 오류: {exc}", exc_info=True)

    async def _countdown(self, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            await trigger_alarm_now(reason="timer_countdown")
        except asyncio.CancelledError:
            logger.info("[알람 스케줄러] 타이머가 취소되었습니다.")
            raise
        except Exception as exc:
            logger.error(f"[알람 스케줄러] 타이머 실행 중 오류: {exc}", exc_info=True)


alarm_scheduler = AlarmScheduler()


async def trigger_alarm_now(reason: str = "scheduled_alarm") -> None:
    """
    피에조 부저를 울리고 기상 미션을 시작합니다.

    desired_state만 갱신하고 current_state는 건드리지 않습니다 —
    실기기 모드에서 부저가 실제로 울렸는지는 라즈베리파이의 보고로만 확정됩니다.
    """
    alarm_scheduler.last_triggered_at = _now_iso()

    await set_actuator(
        BUZZER_ID,
        "ringing",
        value=_ALARM_VALUE,
        operator="system",
    )

    await ws_manager.broadcast({
        "type": "alarm_triggered",
        "reason": reason,
        "message": "기상 알람이 시작되었습니다! 카메라 앞에서 기상 미션을 수행하세요.",
        "updated_at": _now_iso(),
    })
    logger.info(f"[알람 시작] {reason}에 의해 알람({BUZZER_ID})이 울리기 시작했습니다.")

    # 기상 미션 개시 (가위바위보 / 사물 미션)
    await trigger_service.start_mission(reason=reason)


class ScheduleAlarmRequest(BaseModel):
    alarm_time: Optional[str] = Field(
        default=None,
        description="설정할 알람 시각 (HH:MM 형식, 예: '07:00')",
        examples=["07:30"]
    )
    in_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=86400,
        description="테스트용: N초 후 즉시 알람 작동 (예: 5)",
        examples=[5]
    )


@router.get(
    "/status",
    response_model=DataResponse[Dict[str, Any]],
    summary="현재 알람 설정 및 상태 조회",
)
async def get_alarm_status(user=Depends(verify_user_auth)):
    """현재 설정된 알람 시각, 부저 상태, 진행 중인 기상 미션 상태를 조회합니다."""
    from services.device_control import get_device_snapshot

    buzzer = await get_device_snapshot(BUZZER_ID)
    data = alarm_scheduler.snapshot()
    data.update({
        "is_ringing": bool(buzzer and buzzer.get("current_state") in RINGING_STATES),
        "is_commanded_ringing": bool(buzzer and buzzer.get("desired_state") in RINGING_STATES),
        "second_sleep_guard_active": trigger_service.is_second_sleep_guard_active(),
        "mission": trigger_service.get_mission_status(),
        "database": get_db_status(),
    })
    return {"data": data}


@router.post(
    "/schedule",
    response_model=DataResponse[Dict[str, Any]],
    summary="알람 시각 예약 또는 타이머 설정",
)
async def schedule_alarm(
    payload: ScheduleAlarmRequest,
    user=Depends(verify_user_auth),
):
    """
    설정한 알람 시간 또는 N초 후 알람을 동작시키고 기상 미션을 시작하도록 예약합니다.
    (예약 내용은 DB에 저장되어 서버를 재시작해도 유지됩니다.)
    """
    # N초 후 테스트 알람
    if payload.in_seconds:
        snapshot = await alarm_scheduler.schedule_countdown(payload.in_seconds)
        await ws_manager.broadcast({
            "type": "alarm_scheduled",
            **snapshot,
            "updated_at": _now_iso(),
        })
        return {
            "data": {
                **snapshot,
                "message": f"{payload.in_seconds}초 후 기상 알람이 작동합니다.",
            }
        }

    # 시각(HH:MM) 지정 알람
    if payload.alarm_time:
        try:
            snapshot = await alarm_scheduler.schedule_daily(payload.alarm_time)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_ALARM_TIME", "message": str(exc)}},
            )

        remaining = snapshot.get("remaining_seconds") or 0
        await ws_manager.broadcast({
            "type": "alarm_scheduled",
            **snapshot,
            "updated_at": _now_iso(),
        })
        return {
            "data": {
                **snapshot,
                "message": (
                    f"매일 {payload.alarm_time} 기상 알람이 설정되었습니다. "
                    f"(약 {_describe_remaining(int(remaining))} 후 작동 · {ALARM_TIMEZONE})"
                ),
            }
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": "INVALID_PARAM", "message": "alarm_time 또는 in_seconds를 입력해야 합니다."}}
    )


@router.delete(
    "/schedule",
    response_model=DataResponse[Dict[str, Any]],
    summary="알람 예약 해제",
)
async def cancel_schedule(user=Depends(verify_user_auth)):
    """저장된 알람 예약을 해제합니다."""
    await alarm_scheduler.clear()
    await ws_manager.broadcast({
        "type": "alarm_scheduled",
        **alarm_scheduler.snapshot(),
        "updated_at": _now_iso(),
    })
    return {"data": {"cleared": True, "message": "알람 예약이 해제되었습니다."}}


@router.post(
    "/trigger",
    response_model=DataResponse[Dict[str, Any]],
    summary="즉시 알람 시작 (기상 미션 개시)",
)
async def trigger_alarm_immediately(user=Depends(verify_user_auth)):
    """테스트 또는 즉시 기상 알람 및 미션을 시작합니다."""
    await trigger_alarm_now(reason="manual_trigger")
    return {
        "data": {
            "triggered": True,
            "message": "기상 알람이 즉시 시작되었습니다.",
            "mission": trigger_service.get_mission_status(),
        }
    }


@router.post(
    "/confirm-wakeup",
    response_model=DataResponse[Dict[str, Any]],
    summary="[기상 확인] 2차 수면 방지 팝업 확인",
)
async def confirm_user_wakeup(user=Depends(verify_user_auth)):
    """
    사용자가 대시보드의 기상 확인 팝업을 클릭하여 2차 수면 알람을 취소합니다.
    (하드웨어 버튼/터치는 POST /api/v1/devices/touch_pad_1/state 로 보고하면 자동 처리됩니다 — 부록A)
    """
    await trigger_service.confirm_wakeup(actor="user_dashboard")
    return {"data": {"confirmed": True, "message": "기상 확인이 정상 처리되었습니다."}}


@router.post(
    "/stop",
    response_model=DataResponse[Dict[str, Any]],
    summary="알람 강제 정지",
)
async def stop_alarm(user=Depends(verify_user_auth)):
    """현재 울리고 있는 알람을 강제 정지하고 진행 중인 기상 미션을 취소합니다."""
    await set_actuator(BUZZER_ID, "off", value=None, operator="user")
    await trigger_service.cancel_mission(reason="manual_stop")
    return {"data": {"stopped": True, "message": "알람이 정지되었습니다."}}
