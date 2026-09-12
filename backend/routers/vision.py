import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from auth import verify_device_api_key, verify_user_auth
from db.database import get_recent_vision_events, log_vision_event
from schemas.common import DataResponse
from schemas.vision import VisionEventRequest
from services.rule_engine import rule_engine
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
    이벤트를 DB에 저장하고 WebSocket으로 대시보드에 실시간 전달한 뒤, 자동화 규칙에 넘깁니다.

    **무엇을 감지했는지에 대한 판단은 하지 않습니다.** 가위바위보 승패 같은 시나리오 판정은
    프론트엔드가 이 브로드캐스트를 받아서 처리합니다 (docs/부록F 9-2절).
    """
    # 1. DB 기록 (DB가 없으면 inserted_id가 None이고, 시스템은 계속 동작한다)
    inserted_id = await asyncio.to_thread(
        log_vision_event,
        payload.event_type,
        payload.detected,
        payload.count,
        payload.confidence,
        payload.label,
    )

    # 2. WebSocket 실시간 브로드캐스트 (비전 이벤트)
    now_iso = datetime.now(timezone.utc).isoformat()
    await ws_manager.broadcast({
        "type": "vision_event",
        "id": inserted_id,
        "event_type": payload.event_type,
        "label": payload.label,
        "detected": payload.detected,
        "count": payload.count,
        "confidence": payload.confidence,
        "created_at": now_iso,
    })

    # 3. 플랫폼 키트 자동화 규칙 연계 (vision_label 트리거)
    try:
        await rule_engine.on_vision_event(
            label=payload.label,
            detected=payload.detected,
            confidence=payload.confidence,
            count=payload.count,
        )
    except Exception as exc:
        logger.warning(f"규칙 엔진 실행 중 오류: {exc}", exc_info=True)

    logger.info(
        f"[Vision Event] type={payload.event_type}, label={payload.label}, "
        f"detected={payload.detected}, count={payload.count}, conf={payload.confidence}"
    )

    return {
        "data": {
            "recorded": True,
            "event_type": payload.event_type,
            "label": payload.label,
            "detected": payload.detected,
        }
    }


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
    events = await asyncio.to_thread(get_recent_vision_events, limit)
    return {"data": events}
