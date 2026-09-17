import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .mock_provider import MockDeviceProvider

logger = logging.getLogger("backend.iot.hardware")

try:
    from db import database as db
except ImportError:  # pragma: no cover - 로컬 실행 편의용 폴백
    try:
        import db.database as db  # type: ignore
    except ImportError:
        db = None  # type: ignore


class HardwareDeviceProvider(MockDeviceProvider):
    """
    DEVICE_MODE=hardware 전용 디바이스 프로바이더.

    Mock과 다른 점은 **딱 하나**다 — 실기기가 보고하기 전에는 `current_state`를
    건드리지 않는다.

    왜 중요한가:
        Mock은 "즉시 반영"을 흉내 내려고 desired_state를 current_state에도 그대로
        복사한다. 개발 단계에서는 편하지만, 실제 라즈베리파이를 붙인 뒤에도 그러면
        - 파이 데몬이 꺼져 있어도
        - 배선이 빠져 있어도
        - 솔레노이드가 고장 나 있어도
        대시보드는 늘 "열림"이라고 말한다. 즉 **실기기 고장을 화면에서 구분할 방법이
        사라진다.** 도어락과 220V 릴레이를 다루는 전시 환경에서는 위험하다.

        그래서 하드웨어 모드에서는 부록A의 시퀀스 계약을 그대로 지킨다.
          1) 대시보드 제어 → desired_state만 갱신 (낙관적 상태로 브로드캐스트)
          2) 파이가 GPIO 반영 → POST /api/v1/devices/{id}/state 로 보고
          3) 그 보고를 받았을 때에만 current_state 갱신 (확정 상태)

        current_state가 desired_state를 따라오지 않으면, 그것이 바로
        "파이가 지시를 수행하지 못하고 있다"는 신호다.

    GPIO를 직접 만지지 않는 이유는 부록A 2장에 적힌 그대로다 — 백엔드는 학생 PC나
    Render에서 돌고, GPIO는 물리적으로 다른 기기인 라즈베리파이에 있다. 백엔드는
    desired_state를 보관·제공하고 보고를 받아 적는 중계자다.
    """

    def __init__(self) -> None:
        super().__init__()
        logger.info(
            "HardwareDeviceProvider 활성화 — current_state는 라즈베리파이의 "
            "POST /api/v1/devices/{id}/state 보고로만 갱신됩니다."
        )

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user"
    ) -> Dict[str, Any]:
        """목표 상태만 갱신한다. 실제 반영 여부는 라즈베리파이의 보고를 기다린다."""
        if device_id not in self._devices:
            raise ValueError(f"Unknown device_id: {device_id}")

        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        dev = self._devices[device_id]
        dev["desired_state"] = desired_state
        dev["desired_value"] = value
        dev["updated_at"] = now_str
        # current_state / current_value 는 일부러 건드리지 않는다 (위 설명 참고)

        if db:
            try:
                db.update_desired_state(device_id, desired_state, value)
                db.log_control_action(device_id, desired_state, value, actor=operator)
            except Exception as exc:
                logger.warning(f"DB update failed during set_actuator_state for {device_id}: {exc}")

        return dev

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        하드웨어 모드에서는 센서값을 지어내지 않는다.
        PIR 감지 등 실제 측정값은 파이가 POST /state 로 보고하는 것이 유일한 경로다.
        """
        if device_id not in self._devices:
            raise ValueError(f"Unknown device_id: {device_id}")

        dev = self._devices[device_id]
        return {
            "device_id": device_id,
            "kind": dev.get("kind"),
            "value": None,
            "unit": None,
            "value_json": dev.get("current_value"),
            "reported_at": dev.get("updated_at"),
            "note": "하드웨어 모드 — 실제 측정값은 라즈베리파이 보고로만 들어옵니다.",
        }
