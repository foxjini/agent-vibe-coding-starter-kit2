import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_device_api_key, verify_user_auth
from db.database import (
    get_all_devices,
    get_device,
    get_sensor_history,
    log_control_action,
    log_sensor_reading,
    update_current_state,
    update_desired_state,
)
from iot.provider_factory import get_device_provider
from schemas.common import DataResponse, ErrorResponse
from schemas.device import (
    ActuatorControlRequest,
    DesiredStateResponse,
    DeviceResponse,
    DeviceStateReportRequest,
)
from services.trigger_service import trigger_service
from websocket_manager import ws_manager


logger = logging.getLogger("backend.routers.devices")

router = APIRouter(tags=["Devices"])


# ==============================================================================
# 사용자/대시보드향 엔드포인트 (/api/devices)
# ==============================================================================

@router.get(
    "/api/devices",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="전체 디바이스 목록 및 상태 조회",
)
async def list_devices(user=Depends(verify_user_auth)):
    """대시보드에서 등록된 모든 디바이스(센서 및 액추에이터)의 상태를 조회합니다."""
    provider = get_device_provider()
    devices = await provider.get_all_statuses()
    return {"data": devices}


@router.get(
    "/api/devices/{device_id}",
    response_model=DataResponse[Dict[str, Any]],
    summary="특정 디바이스 상태 조회",
)
async def get_device_detail(device_id: str, user=Depends(verify_user_auth)):
    """특정 디바이스의 최신 상태를 조회합니다."""
    provider = get_device_provider()
    dev = await provider.get_device_status(device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DEVICE_NOT_FOUND",
                    "message": f"디바이스 ID '{device_id}'를 찾을 수 없습니다.",
                }
            },
        )
    return {"data": dev}


@router.post(
    "/api/devices/{device_id}/control",
    response_model=DataResponse[Dict[str, Any]],
    summary="액추에이터 상태 제어",
)
async def control_actuator(
    device_id: str,
    payload: ActuatorControlRequest,
    user=Depends(verify_user_auth),
):
    """
    대시보드 또는 사용자가 액추에이터(예: 피에조 부저)의 목표 상태(desired_state)를 제어합니다.
    제어 후 WebSocket으로 실시간 상태가 브로드캐스트됩니다.
    """
    provider = get_device_provider()
    try:
        updated_dev = await provider.set_actuator_state(
            device_id=device_id,
            desired_state=payload.desired_state,
            value=payload.value,
            operator="user",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_DEVICE_OPERATION", "message": str(exc)}},
        )

    # WebSocket 브로드캐스트 (대시보드 실시간 동기화)
    now_iso = datetime.now(timezone.utc).isoformat()
    await ws_manager.broadcast({
        "type": "device_state",
        "device_id": device_id,
        "kind": updated_dev.get("kind"),
        "state": updated_dev.get("desired_state"),
        "value": updated_dev.get("desired_value"),
        "actor": "user",
        "updated_at": now_iso,
    })

    return {"data": updated_dev}


@router.get(
    "/api/devices/{device_id}/readings",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="센서 측정 이력 조회",
)
async def get_device_readings(
    device_id: str,
    limit: int = Query(50, ge=1, le=500),
    user=Depends(verify_user_auth),
):
    """특정 센서의 과거 측정 기록 이력을 조회합니다."""
    history = get_sensor_history(device_id=device_id, limit=limit)
    return {"data": history}


# ==============================================================================
# 디바이스향 엔드포인트 (/api/v1/devices — 라즈베리파이 5 및 센서 하드웨어 전용)
# ==============================================================================

@router.get(
    "/api/v1/devices/{device_id}/desired-state",
    response_model=DataResponse[Dict[str, Any]],
    summary="[하드웨어] 액추에이터 목표 상태 폴링",
)
async def poll_desired_state(
    device_id: str,
    device_key=Depends(verify_device_api_key),
):
    """
    라즈베리파이가 주기적으로 호출하여 액추에이터의 목표 상태(desired_state)를 조회합니다.
    """
    dev = get_device(device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DEVICE_NOT_FOUND",
                    "message": f"디바이스 ID '{device_id}'를 찾을 수 없습니다.",
                }
            },
        )

    return {
        "data": {
            "device_id": dev["id"],
            "kind": dev["kind"],
            "desired_state": dev.get("desired_state"),
            "value": dev.get("desired_value"),
            "updated_at": str(dev.get("updated_at") or ""),
        }
    }


@router.post(
    "/api/v1/devices/{device_id}/state",
    response_model=DataResponse[Dict[str, Any]],
    summary="[하드웨어] 실제 반영 상태 또는 센서값 보고",
)
async def report_device_state(
    device_id: str,
    payload: DeviceStateReportRequest,
    device_key=Depends(verify_device_api_key),
):
    """
    라즈베리파이가 액추에이터 실제 반영 결과(state) 또는 센서 측정값(value, unit)을 보고합니다.
    DB를 갱신하고 WebSocket으로 대시보드에 브로드캐스트합니다.
    """
    dev = get_device(device_id)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DEVICE_NOT_FOUND",
                    "message": f"디바이스 ID '{device_id}'를 찾을 수 없습니다.",
                }
            },
        )

    now_iso = payload.reported_at or datetime.now(timezone.utc).isoformat()

    # 1. 액추에이터 상태 보고인 경우
    if payload.state is not None:
        update_current_state(device_id, payload.state, payload.value)
        log_control_action(
            device_id=device_id,
            action=payload.state,
            value=payload.value,
            actor="device",
        )
        # WebSocket 브로드캐스트
        await ws_manager.broadcast({
            "type": "device_state",
            "device_id": device_id,
            "kind": dev["kind"],
            "state": payload.state,
            "value": payload.value,
            "actor": "device",
            "updated_at": now_iso,
        })

    # 2. 센서 측정값 보고인 경우
    if payload.value is not None and payload.state is None:
        val_float = float(payload.value) if isinstance(payload.value, (int, float)) else None
        val_json = payload.value if isinstance(payload.value, (dict, list)) else None
        log_sensor_reading(
            device_id=device_id,
            value=val_float,
            unit=payload.unit,
            value_json=val_json,
        )
        update_current_state(device_id, "active", payload.value)
        # WebSocket 브로드캐스트
        await ws_manager.broadcast({
            "type": "sensor_reading",
            "device_id": device_id,
            "kind": dev["kind"],
            "value": payload.value,
            "unit": payload.unit,
            "updated_at": now_iso,
        })

        # 터치패드에서 터치가 감지된 경우 기상 확인 트리거 처리
        if device_id == "touch_pad_1" and isinstance(payload.value, dict) and payload.value.get("pressed"):
            await trigger_service.confirm_wakeup(actor="touch_pad")


    return {
        "data": {
            "device_id": device_id,
            "recorded": True,
        }
    }
