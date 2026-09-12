"""
servo — 각도를 지정하는 서보모터 (자동문, 커튼, 급식 배급구).

slot_map.py 예시:
    "actuator_01": {"label": "자동문", "kind": "servo",
                    "driver": "servo", "pin": 12, "control_type": "servo",
                    "value_schema": {"min": 0, "max": 180, "step": 5}},

백엔드에서 내려오는 값: {"angle": 90}
state가 off면 `rest_angle`(기본 0도)로 돌아갑니다.
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.servo")


class Driver(ActuatorDriver):
    control_type = "servo"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        schema = config.get("value_schema") or {}
        self.min_angle = float(schema.get("min", config.get("min_angle", 0)))
        self.max_angle = float(schema.get("max", config.get("max_angle", 180)))
        self.rest_angle = float(config.get("rest_angle", self.min_angle))
        self.device, self.simulated = make_device("AngularServo", config["pin"],
                                                  min_angle=self.min_angle,
                                                  max_angle=self.max_angle,
                                                  initial_angle=None)
        self._angle: Optional[float] = None

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if self.is_on(state):
            angle = self.number_from(value, "angle", self.max_angle)
            result = "on"
        else:
            angle = self.rest_angle
            result = "off"

        angle = max(self.min_angle, min(self.max_angle, angle))
        if self._angle is not None and abs(self._angle - angle) < 0.5:
            return result

        try:
            self.device.angle = angle
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 각도 {angle}도 반영 실패: {exc}")
            return "off" if self._angle is None else result
        self._angle = angle
        logger.info(f"[{self.slot_id}] {self.label} → {result} ({angle:.0f}도)")
        return result

    def close(self) -> None:
        try:
            # 서보는 끌 때 힘을 빼 줘야 떨림(지터)과 발열이 없습니다.
            self.device.detach() if hasattr(self.device, "detach") else None
            self.device.close()
        except Exception:
            pass
