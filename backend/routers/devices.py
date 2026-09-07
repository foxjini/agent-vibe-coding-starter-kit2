from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_admin_token, verify_device_api_key, verify_user_auth
from db import database as db
from iot.provider_factory import get_device_provider
from schemas.device import (
    DeviceControlRequest,
    DeviceStateReportRequest,
    VisionEventRequest,
)
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routers.devices")

# 1. 사용자향 라우터 (대시보드 / 프론트엔드용)
user_router = APIRouter(prefix="/api/devices", tags=["devices"])

# 2. 디바이스향 라우터 (라즈베리파이 폴링 및 비전 클라이언트용)
device_router = APIRouter(prefix="/api/v1", tags=["hardware-and-vision"])


# ==============================================================================
# [사용자향 엔드포인트] /api/devices (대시보드)
# ==============================================================================

@user_router.get("")
async def list_devices(
    _user: Dict[str, Any] = Depends(verify_user_auth)
) -> Dict[str, Any]:
    """모든 IoT 디바이스 목록 및 최신 상태 조회"""
    provider = get_device_provider()
    devices = await provider.get_all_statuses()
    return {"data": devices}


@user_router.get("/{device_id}")
async def get_device_detail(
    device_id: str,
    _user: Dict[str, Any] = Depends(verify_user_auth)
) -> Dict[str, Any]:
    """특정 디바이스 상세 상태 조회"""
    provider = get_device_provider()
    device = await provider.get_device_status(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"디바이스 '{device_id}'를 찾을 수 없습니다."}
        )
    return {"data": device}


@user_router.post("/{device_id}/control")
async def control_device(
    device_id: str,
    request: DeviceControlRequest,
    _admin: str = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    액추에이터 목표 상태 제어 (도어락 해제, 전원 릴레이 on/off, LED 점등 등)

    ⚠️ 관리자 전용이다. 관람객이 도어락을 열거나 남이 노래하는 중에 전원을
    끄지 못하도록 X-Admin-Token 헤더를 요구한다 (부록G §3-4).
    학생용 정상 경로는 /api/booth/verify-keypad(키패드 인증)이다.
    성공 시 WebSocket으로 낙관적 상태를 즉시 브로드캐스트합니다.
    """
    provider = get_device_provider()
    try:
        updated_device = await provider.set_actuator_state(
            device_id=device_id,
            desired_state=request.desired_state,
            value=request.value,
            operator="user"
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": str(exc)}
        )
    except Exception as exc:
        logger.error(f"Error controlling device {device_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "CONTROL_FAILED", "message": f"디바이스 제어에 실패했습니다: {exc}"}
        )

    # 대시보드 실시간 반영 브로드캐스트
    await ws_manager.broadcast({
        "type": "device_state",
        "device_id": device_id,
        "kind": updated_device.get("kind"),
        "state": request.desired_state,
        "value": request.value,
        "actor": "user",
        "updated_at": updated_device.get("updated_at")
    })

    return {"data": updated_device}


@user_router.get("/{device_id}/history")
async def get_device_history(
    device_id: str,
    limit: int = Query(50, ge=1, le=200),
    _user: Dict[str, Any] = Depends(verify_user_auth)
) -> Dict[str, Any]:
    """디바이스의 센서 측정 이력 또는 제어 로그 히스토리 조회"""
    provider = get_device_provider()
    device = await provider.get_device_status(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"디바이스 '{device_id}'를 찾을 수 없습니다."}
        )

    kind = device.get("kind", "")
    history: list = []
    if kind in ("keypad", "pir"):
        history = db.get_sensor_history(device_id=device_id, limit=limit)
    else:
        history = db.get_control_history(device_id=device_id, limit=limit)

    return {"data": history}


# ==============================================================================
# [디바이스향 엔드포인트] /api/v1/... (라즈베리파이 5 & 비전 클라이언트)
# ==============================================================================

@device_router.get("/devices/{device_id}/desired-state")
async def get_desired_state(
    device_id: str,
    _key: str = Depends(verify_device_api_key)
) -> Dict[str, Any]:
    """
    라즈베리파이 5 폴링 계약: 액추에이터의 목표 상태 조회
    """
    provider = get_device_provider()
    device = await provider.get_device_status(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": "device_id를 찾을 수 없습니다"}
        )

    return {
        "data": {
            "device_id": device_id,
            "kind": device.get("kind"),
            "desired_state": device.get("desired_state"),
            "value": device.get("desired_value"),
            "updated_at": device.get("updated_at")
        }
    }


@device_router.post("/devices/{device_id}/state")
async def report_device_state(
    device_id: str,
    request: DeviceStateReportRequest,
    _key: str = Depends(verify_device_api_key)
) -> Dict[str, Any]:
    """
    라즈베리파이 5 보고 계약: 실제 반영 결과(액추에이터) 또는 측정값(센서) 보고
    DB 갱신 후 대시보드에 확정 상태를 WebSocket으로 브로드캐스트합니다.
    """
    provider = get_device_provider()
    device = await provider.get_device_status(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": "device_id를 찾을 수 없습니다"}
        )

    now_str = request.reported_at or (datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    kind = device.get("kind", "")

    # 1. 액추에이터 반영 결과 보고 처리
    if request.state is not None:
        db.update_current_state(device_id, request.state, request.value)
        db.log_control_action(device_id, request.state, request.value, actor="device")

        await ws_manager.broadcast({
            "type": "device_state",
            "device_id": device_id,
            "kind": kind,
            "state": request.state,
            "value": request.value,
            "actor": "device",
            "updated_at": now_str
        })

    # 2. 센서 측정값 보고 처리
    elif request.value is not None or request.unit is not None:
        val_float: Optional[float] = None
        val_json: Optional[Dict[str, Any]] = None

        if isinstance(request.value, (int, float)):
            val_float = float(request.value)
        elif isinstance(request.value, dict):
            val_json = request.value

        db.log_sensor_reading(
            device_id=device_id,
            value=val_float,
            unit=request.unit,
            value_json=val_json
        )
        db.update_current_state(device_id, "reported", request.value)

        await ws_manager.broadcast({
            "type": "sensor_reading",
            "device_id": device_id,
            "kind": kind,
            "value": request.value,
            "unit": request.unit,
            "actor": "device",
            "updated_at": now_str
        })

    return {
        "data": {
            "device_id": device_id,
            "recorded": True
        }
    }


@device_router.post("/vision/events")
async def receive_vision_event(
    request: VisionEventRequest,
    _key: str = Depends(verify_device_api_key)
) -> Dict[str, Any]:
    """
    영상인식 클라이언트(웹캠/YOLOv8)의 감지 이벤트 수신
    """
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # DB에 비전 이벤트 기록
    try:
        db.log_vision_event(
            event_type=request.event_type,
            detected=request.detected,
            count=request.count,
            confidence=request.confidence
        )
    except Exception as exc:
        logger.warning(f"Failed to log vision event in DB: {exc}")

    # 대시보드에 실시간 브로드캐스트
    await ws_manager.broadcast({
        "type": "vision_event",
        "event_type": request.event_type,
        "detected": request.detected,
        "count": request.count,
        "confidence": request.confidence,
        "created_at": now_str
    })

    # [트리거 규칙 연동 - 3단계] 사람 감지 시 부스 환영 안내 및 스피커/조명 자동 연동
    if request.detected and "person" in request.event_type.lower():
        try:
            from services.booth_service import BoothService
            await BoothService.trigger_entry()
        except Exception as exc:
            logger.warning(f"Failed to auto-trigger booth entry on vision event: {exc}")

    return {
        "data": {
            "recorded": True
        }
    }

