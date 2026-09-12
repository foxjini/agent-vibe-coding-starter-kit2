"""
pwm_out — 세기를 0~100%로 조절하는 출력 부품 (진동모터, LED 밝기, DC모터 속도).

slot_map.py 예시:
    "actuator_03": {"label": "진동 모터", "kind": "vibration_motor",
                    "driver": "pwm_out", "pin": 13, "control_type": "pwm"},

백엔드에서 내려오는 값: {"duty": 70}  (부록F 3-1절 규약, 0~100)
                       {"level": 70} / {"value": 70} 도 같은 뜻으로 받아들입니다.
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.pwm_out")


class Driver(ActuatorDriver):
    control_type = "pwm"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.default_level = float(config.get("default_duty", config.get("default_level", 100)))
        self.min_level = float(config.get("min_level", 0))
        self.device, self.simulated = make_device(
            "PWMOutputDevice",
            config["pin"],
            frequency=int(config.get("frequency", 100)),
            initial_value=0,
        )
        self._state = "off"

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if not self.is_on(state):
            self.device.value = 0
            if self._state != "off":
                logger.info(f"[{self.slot_id}] {self.label} → off")
            self._state = "off"
            return "off"

        level = self.number_from(value, "duty", self.default_level, "level")
        level = max(self.min_level, min(100.0, level))
        self.device.value = level / 100.0
        reflected = self.reflected(state)
        if self._state != reflected:
            logger.info(f"[{self.slot_id}] {self.label} → {reflected} (세기 {level:.0f}%)")
        self._state = reflected
        return reflected

    def close(self) -> None:
        try:
            self.device.value = 0
            self.device.close()
        except Exception:
            pass
