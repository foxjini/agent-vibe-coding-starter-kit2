"""
슬롯 상태 중계 서비스 (플랫폼 키트 코어).

라즈베리파이의 배치 폴링·배치 보고를 처리합니다. 이 모듈은 **부품의 의미를 모릅니다** —
슬롯 ID와 값만 다루므로, 팀이 부품을 바꿔도 이 코드는 그대로입니다.

부록F 계약:
- desired_state는 백엔드가 내린 명령, current_state는 하드웨어가 보고한 결과.
  백엔드는 current_state를 직접 쓰지 않고, 오직 여기(보고 처리)에서만 갱신합니다.
- 숫자 센서는 {"value": 24.5} 형식으로 보고하면 sensor_readings.value에 적재되어
  차트·통계가 코드 수정 없이 동작합니다.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from db.database import (
    get_device,
    get_slots,
    log_control_action,
    log_sensor_reading,
    update_current_state,
)
from iot.provider_factory import get_device_provider
from services.device_control import broadcast_device_state
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.slot_service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sensor_state_from_value(value: Any) -> str:
    """센서 보고값으로부터 표시용 상태 문자열을 만듭니다 (대시보드 배지용)."""
    if isinstance(value, dict):
        if "pressed" in value:
            return "touched" if value.get("pressed") else "idle"
        if "detected" in value:
            return "detected" if value.get("detected") else "idle"
    return "active"


def numeric_from_value(value: Any) -> Optional[float]:
    """
    차트용 숫자를 뽑아냅니다.

    - {"value": 24.5} → 24.5   (부록F 3-2절 규약)
    - {"pressed": true} → 1.0  (버튼도 이력 그래프를 볼 수 있게)
    - 24.5 → 24.5
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        raw = value.get("value")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        for key in ("pressed", "detected"):
            if key in value:
                return 1.0 if value.get(key) else 0.0
    return None


async def build_desired_states() -> Dict[str, Any]:
    """
    GET /api/v1/devices/desired-states 응답 본문.

    활성 액추에이터 슬롯만 담습니다. 슬롯 20개를 개별 폴링하면 초당 20요청이 되므로,
    라즈베리파이는 이 엔드포인트 하나만 1초 주기로 호출합니다.
    """
    slots = await asyncio.to_thread(get_slots, "actuator", True)
    if not slots:
        # DB 장애 중에도 파이가 마지막 목표 상태를 계속 따라가도록 메모리 캐시로 폴백한다
        slots = get_device_provider().cached_slots("actuator", enabled_only=True)
    return {
        "server_time": _now_iso(),
        "slots": {
            slot["id"]: {
                "slot_id": slot["id"],
                "desired_state": slot.get("desired_state"),
                "value": slot.get("desired_value"),
                "control_type": slot.get("control_type"),
                "label": slot.get("label"),
                "updated_at": str(slot.get("updated_at") or ""),
            }
            for slot in slots
        },
    }


async def apply_state_reports(
    reports: List[Dict[str, Any]],
    reported_at: Optional[str] = None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    POST /api/v1/devices/states 처리.

    하나가 잘못되어도 나머지는 정상 처리하고, 거부된 항목만 이유와 함께 돌려줍니다.
    (배치 하나가 전부 실패하면 파이가 어느 슬롯 때문인지 알 수 없습니다.)
    """
    provider = get_device_provider()
    now_iso = reported_at or _now_iso()
    accepted: List[str] = []
    rejected: List[Dict[str, str]] = []

    # 규칙 엔진은 순환 임포트를 피하려고 여기서 지연 임포트합니다.
    from services.rule_engine import rule_engine

    for report in reports:
        slot_id = report.get("slot_id")
        device = await asyncio.to_thread(get_device, slot_id)

        if not device:
            cached = provider.get_cached_device(slot_id) if slot_id else None
            if not cached:
                rejected.append({"slot_id": str(slot_id), "reason": "UNKNOWN_SLOT"})
                continue
            device = cached

        # 비활성 슬롯 보고는 조용히 거부한다 (부품을 뗀 뒤 남은 보고)
        if device.get("slot_index") and not device.get("enabled"):
            rejected.append({"slot_id": str(slot_id), "reason": "SLOT_DISABLED"})
            continue

        state = report.get("state")
        value = report.get("value")

        if state is not None:
            # --- 액추에이터 반영 결과 ---
            await asyncio.to_thread(update_current_state, slot_id, state, value)
            await asyncio.to_thread(log_control_action, slot_id, state, value, "device")
            provider.update_cached_state(slot_id, state=state, value=value)

            snapshot = await provider.get_device_status(slot_id) or device
            await broadcast_device_state(snapshot, actor="device", updated_at=now_iso)
            accepted.append(slot_id)
            continue

        if value is None:
            rejected.append({"slot_id": str(slot_id), "reason": "NO_STATE_OR_VALUE"})
            continue

        # --- 센서 측정값 ---
        numeric = numeric_from_value(value)
        value_json = value if isinstance(value, (dict, list)) else None
        sensor_state = sensor_state_from_value(value)

        await asyncio.to_thread(
            log_sensor_reading, slot_id, numeric, report.get("unit"), value_json
        )
        await asyncio.to_thread(update_current_state, slot_id, sensor_state, value)
        provider.update_cached_state(slot_id, state=sensor_state, value=value)

        await ws_manager.broadcast({
            "type": "sensor_reading",
            "slot_id": slot_id,
            "device_id": slot_id,      # 구버전 프론트 호환
            "kind": device.get("kind"),
            "label": device.get("label"),
            "current_state": sensor_state,
            "value": value,
            "unit": report.get("unit"),
            "updated_at": now_iso,
        })
        accepted.append(slot_id)

        # 자동화 규칙 판정 (센서 임계값 트리거)
        try:
            await rule_engine.on_sensor_value(slot_id, value, numeric)
        except Exception as exc:
            logger.warning(f"규칙 판정 중 오류 (slot={slot_id}): {exc}", exc_info=True)

    return accepted, rejected
