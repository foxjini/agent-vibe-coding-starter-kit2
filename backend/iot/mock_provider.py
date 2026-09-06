import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import DeviceProvider

logger = logging.getLogger("backend.iot.mock")

# DB 모듈 임포트 시도 (DB 연결이 없어도 Mock은 정상 작동하도록 fallback 지원)
try:
    from db import database as db
except ImportError:
    try:
        import db.database as db  # type: ignore
    except ImportError:
        db = None  # type: ignore


class MockDeviceProvider(DeviceProvider):
    """
    개발 전반부(Mock 모드)용 IoT 디바이스 제어 제공자.
    AGENTS.md 팀 정보 및 devices 테이블(init.sql)의 id와 1:1 매핑됩니다.
    """

    def __init__(self) -> None:
        # 메모리 기반 디바이스 기본 상태 사전 (DB 장애 시에도 fallback 유지)
        self._devices: Dict[str, Dict[str, Any]] = {
            # 액추에이터 목록
            "door_lock_1": {
                "id": "door_lock_1",
                "name": "솔레노이드 도어락",
                "kind": "door_lock",
                "desired_state": "locked",
                "current_state": "locked",
                "desired_value": None,
                "current_value": None,
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "relay_1": {
                "id": "relay_1",
                "name": "기기 전원 릴레이",
                "kind": "relay",
                "desired_state": "off",
                "current_state": "off",
                "desired_value": None,
                "current_value": None,
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "led_1": {
                "id": "led_1",
                "name": "부스 조명 LED",
                "kind": "led",
                "desired_state": "off",
                "current_state": "off",
                "desired_value": {"brightness_pct": 100, "mode": "normal"},
                "current_value": {"brightness_pct": 100, "mode": "normal"},
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "speaker_1": {
                "id": "speaker_1",
                "name": "스피커/오디오 모듈",
                "kind": "speaker",
                "desired_state": "idle",
                "current_state": "idle",
                "desired_value": {"track": None, "volume": 70},
                "current_value": {"track": None, "volume": 70},
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            # 센서 목록
            "keypad_1": {
                "id": "keypad_1",
                "name": "4x4 비밀번호 키패드",
                "kind": "keypad",
                "desired_state": None,
                "current_state": "ready",
                "desired_value": None,
                "current_value": {"last_key": None, "buffer": ""},
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "pir_1": {
                "id": "pir_1",
                "name": "입장 감지 센서",
                "kind": "pir",
                "desired_state": None,
                "current_state": "standby",
                "desired_value": None,
                "current_value": {"detected": False},
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        }

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 디바이스의 최신 상태를 반환합니다.
        DB 조회가 가능하면 DB 레코드를 우선 반환하고, 실패 시 메모리 상태를 반환합니다.
        """
        if db:
            try:
                db_device = db.get_device(device_id)
                if db_device:
                    # 메모리 상태도 동기화
                    self._devices[device_id] = db_device
                    return db_device
            except Exception as exc:
                logger.warning(f"DB read failed for device {device_id}, fallback to memory: {exc}")

        return self._devices.get(device_id)

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user"
    ) -> Dict[str, Any]:
        """
        액추에이터의 상태를 제어합니다.
        Mock 모드에서는 즉시 반영(desired_state -> current_state)을 시뮬레이션하며,
        DB 업데이트 및 제어 로그를 함께 기록합니다.
        """
        if device_id not in self._devices:
            raise ValueError(f"Unknown device_id: {device_id}")

        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        dev = self._devices[device_id]
        dev["desired_state"] = desired_state
        dev["current_state"] = desired_state  # Mock 환경에서는 즉시 반영
        dev["desired_value"] = value
        dev["current_value"] = value
        dev["updated_at"] = now_str

        # DB 동기화 및 제어 로그 기록
        if db:
            try:
                db.update_desired_state(device_id, desired_state, value)
                db.update_current_state(device_id, desired_state, value)
                db.log_control_action(device_id, desired_state, value, actor=operator)
            except Exception as exc:
                logger.warning(f"DB update failed during set_actuator_state for {device_id}: {exc}")

        return dev

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        센서의 최신 측정값을 시뮬레이션하여 반환합니다.
        Random Walk 및 주기적 감지 로직을 적용하고, DB에 측정값을 기록합니다.
        """
        if device_id not in self._devices:
            raise ValueError(f"Unknown device_id: {device_id}")

        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        dev = self._devices[device_id]
        reading_result: Dict[str, Any] = {
            "device_id": device_id,
            "kind": dev["kind"],
            "reported_at": now_str
        }

        if device_id == "pir_1":
            # 20% 확률로 재실/입장 감지 시뮬레이션
            is_detected = random.random() < 0.20
            dev["current_state"] = "detected" if is_detected else "standby"
            dev["current_value"] = {"detected": is_detected}
            dev["updated_at"] = now_str

            reading_result["value"] = 1.0 if is_detected else 0.0
            reading_result["unit"] = "detection"
            reading_result["value_json"] = {"detected": is_detected}

            if db:
                try:
                    db.update_current_state(device_id, dev["current_state"], dev["current_value"])
                    db.log_sensor_reading(
                        device_id=device_id,
                        value=reading_result["value"],
                        unit=reading_result["unit"],
                        value_json=reading_result["value_json"]
                    )
                except Exception as exc:
                    logger.warning(f"DB logging failed for {device_id}: {exc}")

        elif device_id == "keypad_1":
            # 키패드 상태 시뮬레이션
            dev["updated_at"] = now_str
            current_buf = (dev.get("current_value") or {}).get("buffer", "")
            reading_result["value"] = None
            reading_result["unit"] = "keypad"
            reading_result["value_json"] = {
                "buffer_len": len(current_buf),
                "is_ready": True
            }

            if db:
                try:
                    db.log_sensor_reading(
                        device_id=device_id,
                        value=None,
                        unit="keypad",
                        value_json=reading_result["value_json"]
                    )
                except Exception as exc:
                    logger.warning(f"DB logging failed for {device_id}: {exc}")

        else:
            # 기타 디바이스
            reading_result["value"] = None
            reading_result["unit"] = "unknown"
            reading_result["value_json"] = dev.get("current_value")

        return reading_result

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """
        모든 디바이스의 최신 상태 목록을 반환합니다.
        """
        if db:
            try:
                db_devices = db.get_all_devices()
                if db_devices:
                    for d in db_devices:
                        if d.get("id"):
                            self._devices[d["id"]] = d
                    return db_devices
            except Exception as exc:
                logger.warning(f"DB get_all_devices failed, fallback to memory: {exc}")

        return list(self._devices.values())
