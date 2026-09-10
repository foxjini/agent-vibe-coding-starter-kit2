"""
액추에이터 제어 및 상태 브로드캐스트 단일 창구.

부록A의 desired/current 계약을 한 곳에서 지키기 위한 모듈입니다.
- 백엔드(대시보드/알람/트리거)가 내리는 명령은 항상 desired_state로만 기록한다.
- current_state는 하드웨어가 POST /api/v1/devices/{id}/state로 보고할 때만 확정된다.
- 대시보드에는 두 값을 모두 보내 '명령됨 / 실제 반영됨'을 구분해 보여줄 수 있게 한다.

알람 라우터·트리거 서비스가 DB를 직접 건드리지 않고 이 모듈을 통해서만 제어하도록 하여
provider 캐시와 DB가 어긋나는 문제를 막습니다.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from iot.provider_factory import get_device_provider
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.device_control")

BUZZER_ID = "buzzer_1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_device_state_message(
    device: Dict[str, Any],
    actor: str,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """대시보드로 보낼 디바이스 상태 메시지를 만듭니다 (desired/current 모두 포함)."""
    return {
        "type": "device_state",
        "device_id": device.get("id"),
        "kind": device.get("kind"),
        "desired_state": device.get("desired_state"),
        "current_state": device.get("current_state"),
        "desired_value": device.get("desired_value"),
        "current_value": device.get("current_value"),
        "actor": actor,
        "updated_at": updated_at or str(device.get("updated_at") or _now_iso()),
    }


async def broadcast_device_state(
    device: Dict[str, Any],
    actor: str,
    updated_at: Optional[str] = None,
) -> None:
    """디바이스 상태를 연결된 모든 대시보드에 전송합니다."""
    await ws_manager.broadcast(build_device_state_message(device, actor, updated_at))


async def set_actuator(
    device_id: str,
    desired_state: str,
    value: Optional[Any] = None,
    operator: str = "system",
    broadcast: bool = True,
) -> Dict[str, Any]:
    """
    액추에이터의 목표 상태를 갱신하고(Provider 경유) 대시보드에 브로드캐스트합니다.

    Mock 모드에서는 가상 하드웨어가 즉시 반응하므로 current_state까지 갱신되고,
    실기기 모드에서는 desired_state만 바뀐 뒤 라즈베리파이 보고를 기다립니다.
    """
    provider = get_device_provider()
    updated = await provider.set_actuator_state(
        device_id=device_id,
        desired_state=desired_state,
        value=value,
        operator=operator,
    )
    if broadcast:
        await broadcast_device_state(updated, actor=operator)
    return updated


async def get_device_snapshot(device_id: str) -> Optional[Dict[str, Any]]:
    """현재 디바이스 상태를 Provider(DB 우선, 실패 시 메모리 캐시)에서 조회합니다."""
    provider = get_device_provider()
    return await provider.get_device_status(device_id)


async def is_buzzer_ringing() -> bool:
    """부저가 실제로 울리는 중인지(또는 울리도록 명령된 상태인지) 판단합니다."""
    dev = await get_device_snapshot(BUZZER_ID)
    if not dev:
        return False
    return (
        dev.get("current_state") in ("ringing", "on")
        or dev.get("desired_state") in ("ringing", "on")
    )
