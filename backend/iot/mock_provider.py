"""Mock 디바이스 Provider — 라즈베리파이 없이 전체 흐름을 검증할 때 쓴다.

hardware-rules.md: 실기기에 처음 연결하기 전에 반드시 Mock 상태에서 로직을 먼저
검증한다. Mock과 실기기는 동일한 DeviceProvider 인터페이스를 구현한다.
"""
import logging
from typing import Any, Optional

from .base import DeviceProvider
from .outlets import check_amount

logger = logging.getLogger("mock_provider")

# 현금 배출 장치 상태값
DISPENSER_IDLE = "IDLE"
DISPENSER_DISPENSING = "DISPENSING"


class MockDeviceProvider(DeviceProvider):
    """메모리 상태만 바꾸는 시뮬레이터. 서보는 실제로 돌지 않는다."""

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {
            "cash_dispenser_1": {
                "device_id": "cash_dispenser_1",
                "name": "현금 배출 시연 장치 (SG-90 x1)",
                "kind": "cash_dispenser",
                "state": DISPENSER_IDLE,
                "last_operator": None,
            },
            "qr_scanner_1": {
                "device_id": "qr_scanner_1",
                "name": "QR 인식 카메라",
                "kind": "qr_scanner",
                "state": "READY",
                "last_operator": None,
            },
            "buzzer_1": {
                "device_id": "buzzer_1",
                "name": "경고 부저 (선택)",
                "kind": "buzzer",
                "state": "OFF",
                "last_operator": None,
            },
        }
        # 시연 검증용 — 실제로 배출 동작이 몇 번 일어났는지 센다
        self.dispense_count: int = 0

    async def get_device_status(self, device_id: str) -> Optional[dict[str, Any]]:
        return self._states.get(device_id)

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user",
    ) -> dict[str, Any]:
        device = self._states.get(device_id)
        if device is None:
            raise KeyError(f"등록되지 않은 디바이스입니다: {device_id}")

        if device_id == "cash_dispenser_1" and desired_state == DISPENSER_DISPENSING:
            # 실기기와 같은 표로 금액을 확인한다 — 없는 금액은 상태를 바꾸기 전에 거절
            check_amount(value)
            self.dispense_count += 1
            logger.info("[MOCK] %s원 — 배출구 덮개 열고 닫음 (누적 %d회)", f"{value:,}", self.dispense_count)
        device["state"] = desired_state
        device["last_operator"] = operator
        return device

    async def read_sensor_value(self, device_id: str) -> dict[str, Any]:
        # 이 프로젝트에는 상시 폴링 센서가 없다 (PRD 5.5)
        return {"device_id": device_id, "value": None, "unit": None}

    async def get_all_statuses(self) -> list[dict[str, Any]]:
        return list(self._states.values())
