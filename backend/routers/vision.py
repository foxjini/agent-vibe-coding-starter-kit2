import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from auth import verify_device_api_key, verify_user_auth
from db.database import (
    get_device,
    get_recent_vision_events,
    log_control_action,
    log_vision_event,
    update_current_state,
    update_desired_state,
)
from schemas.common import DataResponse
from schemas.vision import VisionEventRequest
from services.trigger_service import trigger_service
from websocket_manager import ws_manager


logger = logging.getLogger("backend.routers.vision")

router = APIRouter(tags=["Vision"])


@router.post(
    "/api/v1/vision/events",
    response_model=DataResponse[Dict[str, Any]],
    summary="[비전 클라이언트] 영상인식 감지 이벤트 수신",
)
async def receive_vision_event(
    payload: VisionEventRequest,
    device_key=Depends(verify_device_api_key),
):
    """
    Windows PC 웹캠 영상인식 클라이언트(YOLO / MediaPipe)가 감지한 이벤트를 수신합니다.
    이벤트를 DB에 저장하고 WebSocket을 통해 대시보드로 실시간 브로드캐스트합니다.
    """
    # 1. DB 기록
    inserted_id = log_vision_event(
        event_type=payload.event_type,
        detected=payload.detected,
        count=payload.count,
        confidence=payload.confidence,
    )

    # 2. WebSocket 실시간 브로드캐스트 (비전 이벤트)
    now_iso = datetime.now(timezone.utc).isoformat()
    await ws_manager.broadcast({
        "type": "vision_event",
        "id": inserted_id,
        "event_type": payload.event_type,
        "detected": payload.detected,
        "count": payload.count,
        "confidence": payload.confidence,
        "created_at": now_iso,
    })

    # 3. 스마트 기상 시스템 트리거 규칙 연계 (AGENTS.md)
    # 기상 미션 감지 성공 시 액추에이터(buzzer_1) desired-state 갱신 및 2차 수면 방지 루틴 시작
    try:
        await trigger_service.handle_vision_event(
            event_type=payload.event_type,
            detected=payload.detected,
            count=payload.count,
            confidence=payload.confidence,
        )
    except Exception as exc:
        logger.warning(f"트리거 서비스 실행 중 오류: {exc}", exc_info=True)

    logger.info(
        f"[Vision Event] type={payload.event_type}, detected={payload.detected}, "
        f"count={payload.count}, conf={payload.confidence}"
    )

    return {
        "data": {
            "recorded": True,
            "event_type": payload.event_type,
            "detected": payload.detected,
        }
    }


@router.post(
    "/api/alarm/confirm-wakeup",
    response_model=DataResponse[Dict[str, Any]],
    summary="[기상 확인] 2차 수면 방지 팝업 확인",
)
async def confirm_user_wakeup(user=Depends(verify_user_auth)):
    """
    사용자가 대시보드의 기상 확인 팝업을 클릭하여 2차 수면 알람을 취소합니다.
    """
    await trigger_service.confirm_wakeup(actor="user_dashboard")
    return {"data": {"confirmed": True, "message": "기상 확인이 정상 처리되었습니다."}}




@router.get(
    "/api/events/vision",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="최근 영상인식 이벤트 조회",
)
async def list_recent_vision_events(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(verify_user_auth),
):
    """대시보드에서 최근 수신된 영상인식 이벤트 목록을 조회합니다."""
    events = get_recent_vision_events(limit=limit)
    return {"data": events}
