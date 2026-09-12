"""
digital_out — 켜기/끄기만 하는 출력 부품 (LED, 릴레이, 능동 부저).

slot_map.py 예시:
    "actuator_02": {"label": "경보 LED", "kind": "led",
                    "driver": "digital_out", "pin": 23, "control_type": "onoff"},

옵션
    active_high: False로 두면 신호를 반대로 씁니다 (LOW에서 켜지는 릴레이 모듈용)
    blink      : True면 켤 때 깜빡입니다 (경보등)
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.digital_out")


class Driver(ActuatorDriver):
    control_type = "onoff"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.blink = bool(config.get("blink", False))
        self.device, self.simulated = make_device(
            "OutputDevice",
            config["pin"],
            active_high=bool(config.get("active_high", True)),
            initial_value=False,
        )
        self._state = "off"

    def apply(self, state: Optional[str], value: Any = None) -> str:
        want_on = self.is_on(state)
        if want_on == (self._state == "on"):
            return self._state

        if want_on:
            if self.blink and hasattr(self.device, "blink"):
                self.device.blink(on_time=0.4, off_time=0.4)
            else:
                self.device.on()
            self._state = "on"
        else:
            self.device.off()
            self._state = "off"

        logger.info(f"[{self.slot_id}] {self.label} → {self._state}")
        return self._state

    def close(self) -> None:
        try:
            self.device.off()
            self.device.close()
        except Exception:
            pass
