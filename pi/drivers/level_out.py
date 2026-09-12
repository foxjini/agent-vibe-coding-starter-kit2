"""
level_out — 단계 표시등 (LED 여러 개로 혼잡도·진행률을 보여 줄 때).

slot_map.py 예시:
    "actuator_05": {"label": "혼잡도 표시등", "kind": "level_led",
                    "driver": "level_out", "pins": [5, 6, 13],
                    "control_type": "level",
                    "value_schema": {"min": 0, "max": 3, "step": 1}},

백엔드에서 내려오는 값: {"level": 2}  → 앞에서부터 LED 2개를 켭니다.
"""
import logging
from typing import Any, Dict, List, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.level_out")


class Driver(ActuatorDriver):
    control_type = "level"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        pins: List[int] = list(config.get("pins") or ([config["pin"]] if "pin" in config else []))
        if not pins:
            raise ValueError(f"{slot_id}: level_out에는 pins 목록이 필요합니다 (예: [5, 6, 13]).")

        self.devices = []
        simulated = False
        for pin in pins:
            device, sim = make_device("OutputDevice", pin,
                                      active_high=bool(config.get("active_high", True)),
                                      initial_value=False)
            self.devices.append(device)
            simulated = simulated or sim
        self.simulated = simulated
        self.max_level = len(self.devices)
        self._level = -1

    def apply(self, state: Optional[str], value: Any = None) -> str:
        level = int(self.number_from(value, "level", self.max_level)) if self.is_on(state) else 0
        level = max(0, min(self.max_level, level))
        if level == self._level:
            return self.reflected(state) if level else "off"

        for index, device in enumerate(self.devices):
            device.on() if index < level else device.off()
        self._level = level
        logger.info(f"[{self.slot_id}] {self.label} → 단계 {level}/{self.max_level}")
        return self.reflected(state) if level else "off"

    def close(self) -> None:
        for device in self.devices:
            try:
                device.off()
                device.close()
            except Exception:
                pass
