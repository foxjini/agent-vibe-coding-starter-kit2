import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import DeviceProvider

logger = logging.getLogger("backend.iot.hardware_provider")

try:
    from db.database import (
        get_all_devices,
        get_device,
        log_control_action,
        update_desired_state,
    )
    HAS_DB = True
except ImportError:
    HAS_DB = False


class HardwareDeviceProvider(DeviceProvider):
    """
    라즈베리파이 5 실기기 연동 모드 (DEVICE_MODE=hardware)를 위한 백엔드 Provider.
    - 백엔드는 GPIO를 직접 제어하지 않으며, desired-state를 보관하고 중계하는 역할만 수행합니다.
    - 액추에이터 상태 변경 요청 시 desired_state만 갱신하며, 라즈베리파이가
      실제 GPIO를 제어한 후 POST /api/v1/devices/{id}/state로 보고할 때 비로소 current_state가 확정됩니다.
    """

    def __init__(self) -> None:
        # In-Memory 캐시 (DB가 없을 때의 fallback 및 빠른 조회를 위한 저장소)
        self._devices: Dict[str, Dict[str, Any]] = {
            "buzzer_1": {
                "id": "buzzer_1",
                "name": "알람 출력 장치(피에조 부저)",
                "kind": "buzzer",
                "is_actuator": True,
                "desired_state": "off",
                "current_state": "off",
                "desired_value": {"volume": 80, "frequency": 1000},
                "current_value": {"volume": 80, "frequency": 1000},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "touch_pad_1": {
                "id": "touch_pad_1",
                "name": "패드 화면/터치 입력",
                "kind": "touch_pad",
                "is_actuator": False,
                "desired_state": None,
                "current_state": "idle",
                "desired_value": None,
                "current_value": {
                    "pressed": False,
                    "touch_x": 0,
                    "touch_y": 0,
                    "gesture": "none",
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "camera_1": {
                "id": "camera_1",
                "name": "기상 감지 카메라",
                "kind": "camera",
                "is_actuator": False,
                "desired_state": None,
                "current_state": "idle",
                "desired_value": None,
                "current_value": {
                    "person_detected": False,
                    "confidence": 0.0,
                    "gesture": "none",
                    "motion_detected": False,
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 디바이스의 최신 상태를 반환합니다."""
        if HAS_DB:
            try:
                db_dev = get_device(device_id)
                if db_dev:
                    return db_dev
            except Exception as exc:
                logger.warning(f"DB 조회 실패 (get_device_status - {device_id}): {exc}")

        dev = self._devices.get(device_id)
        if not dev:
            return None
        return dict(dev)

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

        # DB가 활성화된 경우 desired_state 및 제어 로그 저장
        if HAS_DB:
            try:
                update_desired_state(device_id, desired_state, dev.get("desired_value"))
                log_control_action(
                    device_id=device_id,
                    action=desired_state,
                    value=dev.get("desired_value"),
                    actor=operator,
                )
            except Exception as exc:
                logger.warning(f"DB 동기화 실패 (set_actuator_state): {exc}")

        logger.info(
            f"[Hardware Gateway] {device_id} desired_state 설정: '{desired_state}' "
            f"(요청자: {operator}, 파이 폴링 대기 중)"
        )
        return dict(dev)

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        실기기 센서(터치패드, 카메라 등)의 최신 보고값을 조회합니다.
        (Mock과 달리 임의의 랜덤 워크를 생성하지 않고, 라즈베리파이가 실제로 보고한 최신 상태를 반환합니다.)
        """
        if HAS_DB:
            try:
                db_dev = get_device(device_id)
                if db_dev:
                    return {
                        "device_id": device_id,
                        "kind": db_dev.get("kind"),
                        "value": db_dev.get("current_value"),
                        "reported_at": str(db_dev.get("updated_at") or ""),
                    }
            except Exception as exc:
                logger.warning(f"DB 센서 조회 실패: {exc}")

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
        if HAS_DB:
            try:
                db_devices = get_all_devices()
                if db_devices:
                    return db_devices
            except Exception as exc:
                logger.warning(f"DB 디바이스 목록 조회 실패: {exc}")

        return [dict(dev) for dev in self._devices.values()]
