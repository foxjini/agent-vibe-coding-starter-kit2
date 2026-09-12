import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.database import (
    get_all_devices,
    get_device,
    log_control_action,
    log_sensor_reading,
    update_current_state,
    update_desired_state,
)

from .base import DeviceProvider
from .device_catalog import build_default_devices

logger = logging.getLogger("backend.iot.mock_provider")


class MockDeviceProvider(DeviceProvider):
    """
    개발 전반부(Mock 모드)를 위한 IoT 디바이스 시뮬레이터.
    AGENTS.md 팀 정보에 정의된 알람 피에조 부저(액추에이터)와
    터치 패드, 기상 감지 카메라(센서)의 동작을 시뮬레이션합니다.

    Mock 모드에서는 '가상 하드웨어가 즉시 반응한다'고 보고 current_state도 함께 갱신합니다.
    실기기 모드(HardwareDeviceProvider)에서는 라즈베리파이 보고 전까지 current_state를 건드리지 않습니다.

    DB 헬퍼는 DB 장애 시 예외 대신 안전한 기본값을 돌려주므로(db/database.py `_tolerant`),
    여기서는 별도의 try/except 없이 호출하고 결과가 비어 있으면 메모리 캐시로 폴백합니다.
    """

    def __init__(self) -> None:
        super().__init__(build_default_devices(simulated=True))

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 디바이스의 현재 상태 및 측정값을 반환합니다."""
        db_dev = await asyncio.to_thread(get_device, device_id)
        if db_dev:
            return db_dev
        return self.get_cached_device(device_id)

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user"
    ) -> Dict[str, Any]:
        """
        액추에이터의 desired-state를 갱신합니다.
        Mock 모드에서는 가상 하드웨어가 즉시 반응하여 current_state도 함께 동기화됩니다.
        """
        # DB를 우선 조회한다 — 슬롯 메타데이터(enabled/role)는 DB가 기준이다.
        target = await asyncio.to_thread(get_device, device_id) or self._devices.get(device_id)
        if not target:
            raise ValueError(f"디바이스를 찾을 수 없습니다: {device_id}")
        if not self.is_actuator(target):
            raise ValueError(f"디바이스 '{device_id}'는 액추에이터가 아닌 센서입니다.")
        if self.is_disabled_slot(target):
            raise ValueError(
                f"슬롯 '{device_id}'이 비활성 상태입니다. "
                "하드웨어 구성에서 사용 설정(enabled)을 먼저 켜 주세요."
            )

        dev = self._devices.get(device_id)
        if dev is None:
            # 메모리 캐시에 없는 디바이스(레거시 팀 데이터 등)도 DB 기준으로 제어한다
            dev = dict(target)
            self._devices[device_id] = dev

        now_iso = datetime.now(timezone.utc).isoformat()
        dev["desired_state"] = desired_state
        dev["current_state"] = desired_state  # Mock 환경에서는 즉시 반영
        if value is not None:
            dev["desired_value"] = value
            dev["current_value"] = value
        dev["updated_at"] = now_iso

        # DB 동기화 (DB가 없으면 내부적으로 무시되고 메모리 상태만 유지된다)
        await asyncio.to_thread(
            update_desired_state, device_id, desired_state, dev.get("desired_value")
        )
        await asyncio.to_thread(
            update_current_state, device_id, desired_state, dev.get("current_value")
        )
        await asyncio.to_thread(
            log_control_action, device_id, desired_state, dev.get("current_value"), operator
        )

        logger.info(
            f"[Mock Actuator] {device_id} state changed to '{desired_state}' "
            f"by '{operator}' (value={value})"
        )
        return dict(dev)

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        센서의 최신 측정값을 시뮬레이션(Random Walk)하여 반환합니다.
        """
        dev = self._devices.get(device_id)
        if not dev:
            raise ValueError(f"디바이스를 찾을 수 없습니다: {device_id}")

        now = datetime.now(timezone.utc)
        dev["updated_at"] = now.isoformat()

        # 디바이스별 센서 시뮬레이션
        if device_id == "touch_pad_1":
            # 터치패드: 랜덤 워크 / 이벤트 시뮬레이션
            # 평소에는 false, 15% 확률로 터치 입력 이벤트 발생
            is_pressed = random.random() < 0.15
            touch_x = random.randint(100, 700) if is_pressed else 0
            touch_y = random.randint(100, 500) if is_pressed else 0
            gesture = random.choice(["tap", "swipe_right", "none"]) if is_pressed else "none"

            reading = {
                "pressed": is_pressed,
                "touch_x": touch_x,
                "touch_y": touch_y,
                "gesture": gesture,
            }
            dev["current_state"] = "touched" if is_pressed else "idle"
            dev["current_value"] = reading

            await asyncio.to_thread(
                log_sensor_reading, device_id, 1.0 if is_pressed else 0.0, "pressed", reading
            )
            await asyncio.to_thread(update_current_state, device_id, dev["current_state"], reading)

            return {
                "device_id": device_id,
                "kind": dev["kind"],
                "value": reading,
                "reported_at": now.isoformat(),
            }

        elif device_id == "camera_1":
            # 카메라: 사람 감지 신뢰도 Random Walk (0.70 ~ 0.99 사이)
            current_value = dev.get("current_value") or {}
            cur_conf = current_value.get("confidence", 0.90)
            delta = random.uniform(-0.03, 0.03)
            new_conf = round(max(0.70, min(0.99, cur_conf + delta)), 2)

            motion = random.random() < 0.3
            gestures = ["rock", "scissors", "paper", "none"]
            gesture = random.choice(gestures)

            reading = {
                "person_detected": True,
                "confidence": new_conf,
                "gesture": gesture,
                "motion_detected": motion,
            }
            dev["current_state"] = "detecting" if motion else "idle"
            dev["current_value"] = reading

            await asyncio.to_thread(
                log_sensor_reading, device_id, new_conf, "confidence", reading
            )
            await asyncio.to_thread(update_current_state, device_id, dev["current_state"], reading)

            return {
                "device_id": device_id,
                "kind": dev["kind"],
                "value": reading,
                "reported_at": now.isoformat(),
            }

        else:
            # 기타 또는 액추에이터 상태 조회
            return {
                "device_id": device_id,
                "kind": dev.get("kind"),
                "value": dev.get("current_value"),
                "reported_at": now.isoformat(),
            }

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """등록된 모든 디바이스의 현재 상태 목록을 반환합니다."""
        db_devices = await asyncio.to_thread(get_all_devices)
        if db_devices:
            return db_devices
        return self.visible_cached_devices()
