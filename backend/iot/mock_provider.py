import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import DeviceProvider

logger = logging.getLogger("backend.iot.mock_provider")

# DB 모듈 임포트 시도 (로컬 DB가 실행 중이면 DB 동기화 지원)
try:
    from db.database import (
        get_all_devices,
        get_device,
        log_control_action,
        log_sensor_reading,
        update_current_state,
        update_desired_state,
    )
    HAS_DB = True
except ImportError:
    HAS_DB = False


class MockDeviceProvider(DeviceProvider):
    """
    개발 전반부(Mock 모드)를 위한 IoT 디바이스 시뮬레이터.
    AGENTS.md 팀 정보에 정의된 알람 피에조 부저(액추에이터)와
    터치 패드, 기상 감지 카메라(센서)의 동작을 시뮬레이션합니다.
    """

    def __init__(self) -> None:
        # In-Memory 기본 디바이스 상태 정의 (devices 테이블의 id와 100% 일치)
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
                    "person_detected": True,
                    "confidence": 0.92,
                    "gesture": "none",
                    "motion_detected": False,
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 디바이스의 현재 상태 및 측정값을 반환합니다."""
        # 1. DB 조회가 가능하면 DB 상태 우선 조회
        if HAS_DB:
            try:
                db_dev = get_device(device_id)
                if db_dev:
                    return db_dev
            except Exception as exc:
                logger.warning(f"DB lookup failed in get_device_status ({device_id}): {exc}")

        # 2. 메모리 상태 fallback
        dev = self._devices.get(device_id)
        if not dev:
            return None
        return dict(dev)

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
        dev = self._devices.get(device_id)
        if not dev:
            raise ValueError(f"디바이스를 찾을 수 없습니다: {device_id}")

        if not dev.get("is_actuator", False):
            raise ValueError(f"디바이스 '{device_id}'는 액추에이터가 아닌 센서입니다.")

        now_iso = datetime.now(timezone.utc).isoformat()
        dev["desired_state"] = desired_state
        dev["current_state"] = desired_state  # Mock 환경에서는 즉시 반영
        if value is not None:
            dev["desired_value"] = value
            dev["current_value"] = value
        dev["updated_at"] = now_iso

        # DB가 동작 중이면 DB 및 제어 로그 동기화
        if HAS_DB:
            try:
                update_desired_state(device_id, desired_state, dev.get("desired_value"))
                update_current_state(device_id, desired_state, dev.get("current_value"))
                log_control_action(
                    device_id=device_id,
                    action=desired_state,
                    value=dev.get("current_value"),
                    actor=operator,
                )
            except Exception as exc:
                logger.warning(f"Failed to sync set_actuator_state to DB: {exc}")

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

            if HAS_DB:
                try:
                    log_sensor_reading(
                        device_id=device_id,
                        value=1.0 if is_pressed else 0.0,
                        unit="pressed",
                        value_json=reading,
                    )
                    update_current_state(device_id, dev["current_state"], reading)
                except Exception as exc:
                    logger.warning(f"Failed to log sensor reading to DB: {exc}")

            return {
                "device_id": device_id,
                "kind": dev["kind"],
                "value": reading,
                "reported_at": now.isoformat(),
            }

        elif device_id == "camera_1":
            # 카메라: 사람 감지 신뢰도 Random Walk (0.85 ~ 0.99 사이)
            cur_conf = dev["current_value"].get("confidence", 0.90)
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

            if HAS_DB:
                try:
                    log_sensor_reading(
                        device_id=device_id,
                        value=new_conf,
                        unit="confidence",
                        value_json=reading,
                    )
                    update_current_state(device_id, dev["current_state"], reading)
                except Exception as exc:
                    logger.warning(f"Failed to log camera reading to DB: {exc}")

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
        if HAS_DB:
            try:
                db_devices = get_all_devices()
                if db_devices:
                    return db_devices
            except Exception as exc:
                logger.warning(f"DB lookup failed in get_all_statuses: {exc}")

        return [dict(dev) for dev in self._devices.values()]
