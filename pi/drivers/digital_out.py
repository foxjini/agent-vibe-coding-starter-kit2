"""
digital_out — 켜기/끄기만 하는 출력 부품 (LED, 릴레이, 능동 부저).

slot_map.py 예시:
    "actuator_02": {"label": "경보 LED", "kind": "led",
                    "driver": "digital_out", "pin": 23, "control_type": "onoff"},

    # 깜빡이는 경보등이라면 control_type을 pulse로 두세요 — 대시보드에 점멸 주기 조절이 생깁니다.
    "actuator_03": {"label": "경보등", "kind": "led",
                    "driver": "digital_out", "pin": 26, "control_type": "pulse"},

옵션
    active_high: False로 두면 신호를 반대로 씁니다 (LOW에서 켜지는 릴레이 모듈용)
    blink      : True면 control_type과 상관없이 항상 깜빡입니다

백엔드에서 내려오는 값 (control_type이 pulse일 때, 부록F 3-1절)
    {"on_time": 0.25, "off_time": 0.15}   → 켜짐 0.25초 / 꺼짐 0.15초로 점멸
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
        # control_type이 pulse면 점멸이 기본 동작입니다 (부록F 3-1절)
        self.pulse = bool(config.get("blink", config.get("control_type") == "pulse"))
        if self.pulse:
            self.control_type = "pulse"
        self.device, self.simulated = make_device(
            "OutputDevice",
            config["pin"],
            active_high=bool(config.get("active_high", True)),
            initial_value=False,
        )
        self._state = "off"
        self._timing: Optional[tuple] = None

    def apply(self, state: Optional[str], value: Any = None) -> str:
        want_on = self.is_on(state)
        timing: Optional[tuple] = None
        if want_on and self.pulse:
            timing = (
                round(self.number_from(value, "on_time", 0.4), 3),
                round(self.number_from(value, "off_time", 0.4), 3),
            )

        # 점멸 주기가 바뀌면 켜져 있어도 다시 반영해야 합니다.
        if want_on == (self._state == "on") and timing == self._timing:
            return self._state

        if want_on:
            if timing and hasattr(self.device, "blink"):
                self.device.blink(on_time=timing[0], off_time=timing[1])
            else:
                self.device.on()
            self._state = self.reflected(state)
        else:
            self.device.off()
            self._state = "off"
        self._timing = timing

        detail = f" (점멸 {timing[0]}초/{timing[1]}초)" if timing else ""
        logger.info(f"[{self.slot_id}] {self.label} → {self._state}{detail}")
        return self._state

    def close(self) -> None:
        try:
            self.device.off()
            self.device.close()
        except Exception:
            pass
