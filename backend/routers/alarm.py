import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import verify_user_auth
from schemas.common import DataResponse
from services.trigger_service import trigger_service
from websocket_manager import ws_manager
from db.database import get_device, log_control_action, update_current_state, update_desired_state

logger = logging.getLogger("backend.routers.alarm")

router = APIRouter(prefix="/api/alarm", tags=["Alarm"])

# 전역 알람 스케줄러 상태
_alarm_schedule: Dict[str, Any] = {
    "scheduled_time": None,  # "HH:MM"
    "is_active": False,
    "last_triggered_at": None,
}
_schedule_task: Optional[asyncio.Task] = None


class ScheduleAlarmRequest(BaseModel):
    alarm_time: Optional[str] = Field(
        default=None,
        description="설정할 알람 시각 (HH:MM 형식, 예: '07:00')",
        examples=["07:30"]
    )
    in_seconds: Optional[int] = Field(
        default=None,
        description="테스트용: N초 후 즉시 알람 작동 (예: 5)",
        examples=[5]
    )


@router.get(
    "/status",
    response_model=DataResponse[Dict[str, Any]],
    summary="현재 알람 설정 및 상태 조회",
)
async def get_alarm_status(user=Depends(verify_user_auth)):
    """현재 설정된 알람 시각 및 피에조 부저의 동작 상태를 조회합니다."""
    buzzer = get_device("buzzer_1")
    is_ringing = buzzer and buzzer.get("current_state") in ("ringing", "on")

    return {
        "data": {
            "scheduled_time": _alarm_schedule["scheduled_time"],
            "is_scheduled": _alarm_schedule["is_active"],
            "is_ringing": bool(is_ringing),
            "last_triggered_at": _alarm_schedule["last_triggered_at"],
            "second_sleep_guard_active": bool(
                trigger_service._second_sleep_task
                and not trigger_service._second_sleep_task.done()
            ),
        }
    }


async def _trigger_alarm_now(reason: str = "scheduled_alarm") -> None:
    """피에조 부저를 울리고 기상 미션을 시작합니다."""
    now_iso = datetime.now(timezone.utc).isoformat()
    _alarm_schedule["last_triggered_at"] = now_iso

    # 1. DB desired_state & current_state 갱신
    update_desired_state("buzzer_1", "ringing", {"volume": 85, "frequency": 1000})
    update_current_state("buzzer_1", "ringing", {"volume": 85, "frequency": 1000})
    log_control_action(
        device_id="buzzer_1",
        action="ringing",
        value={"volume": 85, "frequency": 1000, "reason": reason},
        actor="system",
    )


    # 2. WebSocket 대시보드 브로드캐스트
    await ws_manager.broadcast({
        "type": "device_state",
        "device_id": "buzzer_1",
        "kind": "buzzer",
        "state": "ringing",
        "value": {"volume": 85, "frequency": 1000},
        "actor": "system",
        "updated_at": now_iso,
    })

    await ws_manager.broadcast({
        "type": "alarm_triggered",
        "reason": reason,
        "message": "기상 알람이 시작되었습니다! 카메라 앞에서 기상 미션을 수행하세요.",
        "updated_at": now_iso,
    })
    logger.info(f"[알람 시작] {reason}에 의해 알람(buzzer_1)이 울리기 시작했습니다.")


async def _countdown_timer_task(seconds: int):
    """N초 후 알람을 발동하는 비동기 태스크"""
    try:
        await asyncio.sleep(seconds)
        await _trigger_alarm_now(reason="timer_countdown")
    except asyncio.CancelledError:
        logger.info("[알람 스케줄러] 타이머가 취소되었습니다.")


async def _time_scheduler_task(alarm_time_str: str):
    """
    지정된 시각(HH:MM)에 도달하면 알람을 작동시키는 비동기 스케줄러 태스크.
    매일 설정된 시각마다 반복 실행됩니다.
    """
    try:
        parts = [int(p) for p in alarm_time_str.strip().split(":")]
        target_hour = parts[0]
        target_minute = parts[1]
        target_second = parts[2] if len(parts) > 2 else 0

        logger.info(f"[알람 스케줄러] 매일 {target_hour:02d}:{target_minute:02d}:{target_second:02d} 예약 모니터링을 시작합니다.")

        while True:
            now = datetime.now()
            target_dt = now.replace(
                hour=target_hour,
                minute=target_minute,
                second=target_second,
                microsecond=0,
            )
            # 오늘 시각이 이미 지난 경우 내일 같은 시각으로 설정
            if target_dt <= now:
                target_dt += timedelta(days=1)

            delay = (target_dt - now).total_seconds()
            logger.info(f"[알람 스케줄러] 지정 시각({alarm_time_str})까지 {delay:.1f}초 대기합니다.")

            # 남은 시간 동안 비동기 대기
            if delay > 0:
                await asyncio.sleep(delay)

            # 알람 시각 도달!
            logger.info(f"[알람 스케줄러] 설정된 알람 시각({alarm_time_str}) 도달! 알람을 시작합니다.")
            await _trigger_alarm_now(reason=f"scheduled_time_{alarm_time_str}")

            # 동일 분 내 중복 재발동 방지를 위해 60초 대기 후 다음날 루프 대기
            await asyncio.sleep(60)

    except asyncio.CancelledError:
        logger.info(f"[알람 스케줄러] 알람 예약({alarm_time_str}) 태스크가 정상 취소되었습니다.")
    except Exception as exc:
        logger.error(f"[알람 스케줄러] 알람 태스크 실행 중 예외 발생: {exc}", exc_info=True)


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
    """
    global _schedule_task

    if _schedule_task and not _schedule_task.done():
        _schedule_task.cancel()

    now_iso = datetime.now(timezone.utc).isoformat()

    # N초 후 테스트 알람
    if payload.in_seconds and payload.in_seconds > 0:
        _alarm_schedule["is_active"] = True
        _alarm_schedule["scheduled_time"] = f"{payload.in_seconds}초 후"
        _schedule_task = asyncio.create_task(_countdown_timer_task(payload.in_seconds))

        await ws_manager.broadcast({
            "type": "alarm_scheduled",
            "scheduled_time": _alarm_schedule["scheduled_time"],
            "in_seconds": payload.in_seconds,
            "updated_at": now_iso,
        })

        return {
            "data": {
                "message": f"{payload.in_seconds}초 후 기상 알람이 작동합니다.",
                "scheduled_time": _alarm_schedule["scheduled_time"],
                "remaining_seconds": payload.in_seconds,
            }
        }

    # 시각(HH:MM) 지정 알람
    if payload.alarm_time:
        parts = [int(p) for p in payload.alarm_time.strip().split(":")]
        target_hour = parts[0]
        target_minute = parts[1]
        target_second = parts[2] if len(parts) > 2 else 0

        now = datetime.now()
        target_dt = now.replace(
            hour=target_hour,
            minute=target_minute,
            second=target_second,
            microsecond=0,
        )
        if target_dt <= now:
            target_dt += timedelta(days=1)

        delay_seconds = int((target_dt - now).total_seconds())
        hours_left = delay_seconds // 3600
        mins_left = (delay_seconds % 3600) // 60
        secs_left = delay_seconds % 60

        time_desc = []
        if hours_left > 0:
            time_desc.append(f"{hours_left}시간")
        if mins_left > 0:
            time_desc.append(f"{mins_left}분")
        time_desc.append(f"{secs_left}초")
        remaining_str = " ".join(time_desc)

        _alarm_schedule["is_active"] = True
        _alarm_schedule["scheduled_time"] = payload.alarm_time
        _alarm_schedule["remaining_seconds"] = delay_seconds

        # 비동기 스케줄러 태스크 구동
        _schedule_task = asyncio.create_task(_time_scheduler_task(payload.alarm_time))

        await ws_manager.broadcast({
            "type": "alarm_scheduled",
            "scheduled_time": payload.alarm_time,
            "remaining_seconds": delay_seconds,
            "updated_at": now_iso,
        })

        return {
            "data": {
                "message": f"매일 {payload.alarm_time} 기상 알람이 설정되었습니다. (약 {remaining_str} 후 작동)",
                "scheduled_time": payload.alarm_time,
                "remaining_seconds": delay_seconds,
            }
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": "INVALID_PARAM", "message": "alarm_time 또는 in_seconds를 입력해야 합니다."}}
    )


@router.post(
    "/trigger",
    response_model=DataResponse[Dict[str, Any]],
    summary="즉시 알람 시작 (기상 미션 개시)",
)
async def trigger_alarm_immediately(user=Depends(verify_user_auth)):
    """테스트 또는 즉시 기상 알람 및 미션을 시작합니다."""
    await _trigger_alarm_now(reason="manual_trigger")
    return {"data": {"triggered": True, "message": "기상 알람이 즉시 시작되었습니다."}}


@router.post(
    "/stop",
    response_model=DataResponse[Dict[str, Any]],
    summary="알람 강제 정지",
)
async def stop_alarm(user=Depends(verify_user_auth)):
    """현재 울리고 있는 알람을 강제 정지합니다."""
    now_iso = datetime.now(timezone.utc).isoformat()
    update_desired_state("buzzer_1", "off", None)
    update_current_state("buzzer_1", "off", None)
    log_control_action(
        device_id="buzzer_1",
        action="off",
        value=None,
        actor="user",
    )


    await ws_manager.broadcast({
        "type": "device_state",
        "device_id": "buzzer_1",
        "kind": "buzzer",
        "state": "off",
        "value": None,
        "actor": "user",
        "updated_at": now_iso,
    })

    return {"data": {"stopped": True, "message": "알람이 정지되었습니다."}}
