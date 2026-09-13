import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_device_api_key, verify_user_auth
from db.database import get_recent_vision_events, log_vision_event
from schemas.common import DataResponse
from schemas.slot import DetectorReportRequest, VisionConfigUpdate
from schemas.vision import VisionEventRequest
from services.rule_engine import rule_engine
from services.vision_config import get_vision_config, save_detectors, save_vision_config
from websocket_manager import ws_manager


logger = logging.getLogger("backend.routers.vision")

router = APIRouter(tags=["Vision"])


def _db_required(what: str) -> HTTPException:
    """설정은 DB에만 저장되므로, 꺼져 있으면 저장된 척하지 않고 503으로 알려 준다."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": (
                    f"데이터베이스에 연결되지 않아 {what}을 저장할 수 없습니다. "
                    "MySQL/MariaDB를 켜고 다시 시도하세요 (상태는 GET /health)."
                ),
            }
        },
    )


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

    **무엇을 감지했는지에 대한 판단은 하지 않습니다.** 승패·성공 여부 같은 시나리오 판정은
    프론트엔드가 이 브로드캐스트를 받아서 처리합니다 (docs/부록F 9-2절).

    `extra`는 라벨 하나로 표현하기 어려운 값(좌석 번호·측정 점수 등)을 함께 보내는 곳입니다.
    **실시간 중계로만 가고 DB에는 저장되지 않습니다** — 나중에 다시 볼 이력은 `label`로 남기세요.
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
    # `extra`는 여기까지만 옵니다 — DB에는 저장하지 않고 화면으로 바로 넘깁니다.
    # 시나리오 판정은 프론트엔드가 하므로 '지금 값'이 필요하고, 이력은 라벨로 남습니다.
    await ws_manager.broadcast({
        "type": "vision_event",
        "id": inserted_id,
        "event_type": payload.event_type,
        "label": payload.label,
        "detected": payload.detected,
        "count": payload.count,
        "confidence": payload.confidence,
        "extra": payload.extra,
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


# ==============================================================================
# 감지 설정 (부록F 10장) — vision이 '무엇을 찾을지'를 코드가 아니라 여기서 받아 갑니다
# ==============================================================================

@router.get(
    "/api/v1/vision/config",
    response_model=DataResponse[Dict[str, Any]],
    summary="[비전] 감지 대상 설정 조회",
)
async def read_vision_config(device_key=Depends(verify_device_api_key)):
    """
    비전 클라이언트가 시작할 때와 주기적으로 호출합니다.

    감지 대상은 **자동화 규칙의 vision_label 트리거 + 대시보드 설정**에서 자동으로 산출됩니다.
    팀이 감지 대상을 바꿔도 `vision/main.py`는 고치지 않습니다.
    DB가 꺼져 있어도 기본값으로 응답합니다 — 설정을 못 읽었다고 감지를 멈추면 수업이 멈춥니다.
    """
    return {"data": await asyncio.to_thread(get_vision_config)}


@router.get(
    "/api/vision/config",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 감지 대상 설정 조회 (대시보드용)",
)
async def read_vision_config_for_dashboard(user=Depends(verify_user_auth)):
    """설정 화면이 현재 감지 대상을 보여주기 위해 호출합니다."""
    return {"data": await asyncio.to_thread(get_vision_config)}


@router.put(
    "/api/vision/config",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 감지 대상 설정 변경",
)
async def update_vision_config(payload: VisionConfigUpdate, user=Depends(verify_user_auth)):
    """
    감지 대상을 바꿉니다 — **코드가 아니라 데이터를 바꾸는 작업입니다.**
    비전 클라이언트는 다음 설정 조회 주기에 자동으로 새 대상을 적용합니다.
    """
    fields = payload.model_dump(exclude_unset=True)
    config = await asyncio.to_thread(save_vision_config, fields)
    if not config.get("persisted"):
        raise _db_required("감지 설정")
    await ws_manager.broadcast({"type": "vision_config", **config})
    return {"data": config}


@router.post(
    "/api/v1/vision/detectors",
    response_model=DataResponse[Dict[str, Any]],
    summary="[비전] 내가 가진 검출기 신고 (부팅 시 1회)",
)
async def report_detectors(
    payload: DetectorReportRequest,
    device_key=Depends(verify_device_api_key),
):
    """
    비전 클라이언트가 `detectors/` 폴더에서 찾은 검출기와 **그 검출기가 내보내는 라벨**을
    알려 줍니다.

    이 신고 덕분에 백엔드는 팀 고유 라벨을 코드에 하나도 두지 않습니다.
    팀이 `detectors/`에 파일 하나를 추가하면 백엔드도 대시보드도 자동으로 알게 됩니다.
    """
    result = await asyncio.to_thread(
        save_detectors, [d.model_dump() for d in payload.detectors]
    )
    saved = result["detectors"]
    persisted = result["persisted"]
    if persisted:
        await ws_manager.broadcast({"type": "vision_detectors", "detectors": saved})
    else:
        # 감지는 계속 돌아야 하므로 에러로 끊지 않고, 저장 여부만 솔직하게 알려 줍니다
        logger.warning("검출기 신고를 받았지만 DB가 꺼져 있어 저장하지 못했습니다.")
    return {"data": {
        "registered": [d["name"] for d in saved],
        "detectors": saved,
        "persisted": persisted,
    }}
