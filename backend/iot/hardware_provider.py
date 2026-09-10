import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.database import (
    get_all_devices,
    get_device,
    log_control_action,
    update_desired_state,
)

from .base import DeviceProvider
from .device_catalog import build_default_devices

logger = logging.getLogger("backend.iot.hardware_provider")


class HardwareDeviceProvider(DeviceProvider):
    """
    라즈베리파이 5 실기기 연동 모드 (DEVICE_MODE=hardware)를 위한 백엔드 Provider.
    - 백엔드는 GPIO를 직접 제어하지 않으며, desired-state를 보관하고 중계하는 역할만 수행합니다.
    - 액추에이터 상태 변경 요청 시 desired_state만 갱신하며, 라즈베리파이가
      실제 GPIO를 제어한 후 POST /api/v1/devices/{id}/state로 보고할 때 비로소 current_state가 확정됩니다.
      (이 규칙 덕분에 배선이 빠지면 대시보드에 '하드웨어 반영 대기'로 남아 문제를 바로 볼 수 있습니다.)
    """

    def __init__(self) -> None:
        super().__init__(build_default_devices(simulated=False))

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 디바이스의 최신 상태를 반환합니다."""
        db_dev = await asyncio.to_thread(get_device, device_id)
        if db_dev:
            return db_dev
        return self.get_cached_device(device_id)

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user",
    ) -> Dict[str, Any]:
        """
        액추에이터의 목표 상태(desired-state)를 갱신합니다.
        하드웨어 모드에서는 current_state를 즉시 변경하지 않고,
        라즈베리파이 5 데몬이 폴링 후 실기기 반영 결과를 보고할 때까지 대기합니다.
        """
        dev = self._devices.get(device_id)
        if not dev:
            raise ValueError(f"디바이스를 찾을 수 없습니다: {device_id}")

        if not dev.get("is_actuator", False):
            raise ValueError(f"디바이스 '{device_id}'는 액추에이터가 아닌 센서입니다.")

        now_iso = datetime.now(timezone.utc).isoformat()
        dev["desired_state"] = desired_state
        if value is not None:
            dev["desired_value"] = value
        dev["updated_at"] = now_iso

        # desired_state 및 제어 로그만 저장 — current_state는 파이의 보고로만 바뀐다
        await asyncio.to_thread(
            update_desired_state, device_id, desired_state, dev.get("desired_value")
        )
        await asyncio.to_thread(
            log_control_action, device_id, desired_state, dev.get("desired_value"), operator
        )

        logger.info(
            f"[Hardware Gateway] {device_id} desired_state 설정: '{desired_state}' "
            f"(요청자: {operator}, 파이 폴링 대기 중)"
        )

        db_dev = await asyncio.to_thread(get_device, device_id)
        return db_dev or dict(dev)

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        실기기 센서(터치패드, 카메라 등)의 최신 보고값을 조회합니다.
        (Mock과 달리 임의의 랜덤 워크를 생성하지 않고, 라즈베리파이가 실제로 보고한 최신 상태를 반환합니다.)
        """
        db_dev = await asyncio.to_thread(get_device, device_id)
        if db_dev:
            return {
                "device_id": device_id,
                "kind": db_dev.get("kind"),
                "value": db_dev.get("current_value"),
                "reported_at": str(db_dev.get("updated_at") or ""),
            }

        dev = self._devices.get(device_id)
        if not dev:
            raise ValueError(f"디바이스를 찾을 수 없습니다: {device_id}")

        return {
            "device_id": device_id,
            "kind": dev.get("kind"),
            "value": dev.get("current_value"),
            "reported_at": dev.get("updated_at"),
        }

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """등록된 모든 디바이스의 최신 상태 목록을 반환합니다."""
        db_devices = await asyncio.to_thread(get_all_devices)
        if db_devices:
            return db_devices
        return [dict(dev) for dev in self._devices.values()]
