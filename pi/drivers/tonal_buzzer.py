"""
tonal_buzzer — 주파수를 지정하는 부저.

부저는 두 종류가 있고 배선이 다릅니다. 소리가 안 나면 여기부터 확인하세요.
    passive(수동 피에조) : PWM으로 주파수를 만들어 줘야 소리가 납니다  ← 기본값
    active(능동 부저)    : 전원만 주면 정해진 음이 납니다 (주파수 조절 불가)

slot_map.py 예시:
    "actuator_01": {"label": "알람 부저", "kind": "buzzer",
                    "driver": "tonal_buzzer", "pin": 18,
                    "control_type": "tonal", "buzzer_type": "passive"},

백엔드에서 내려오는 값: {"frequency": 1000, "volume": 80}
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.tonal_buzzer")

DEFAULT_FREQUENCY = 1000
DEFAULT_VOLUME = 80


class Driver(ActuatorDriver):
    control_type = "tonal"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.buzzer_type = str(config.get("buzzer_type", "passive")).strip().lower()
        if self.buzzer_type == "passive":
            self.device, self.simulated = make_device(
                "PWMOutputDevice", config["pin"],
                frequency=DEFAULT_FREQUENCY, initial_value=0,
            )
        else:
            self.device, self.simulated = make_device("Buzzer", config["pin"])
        self._state = "off"

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if not self.is_on(state):
            self._silence()
            if self._state != "off":
                logger.info(f"[{self.slot_id}] {self.label} → off")
            self._state = "off"
            return "off"

        frequency = int(max(50, min(8000, self.number_from(value, "frequency", DEFAULT_FREQUENCY))))
        volume = int(max(0, min(100, self.number_from(value, "volume", DEFAULT_VOLUME))))

        if self.buzzer_type == "passive":
            # 사각파는 듀티비 0.5에서 가장 큽니다 — 볼륨을 듀티비로 근사합니다.
            self.device.frequency = frequency
            self.device.value = max(0.02, min(0.5, volume / 200))
        else:
            # 능동 부저는 주파수를 못 바꾸므로 경보 패턴으로 울립니다.
            self.device.beep(on_time=0.25, off_time=0.15)

        if self._state != "on":
            logger.info(
                f"[{self.slot_id}] {self.label} → on "
                f"({self.buzzer_type}, {frequency}Hz, 볼륨 {volume}%)"
            )
        self._state = "on"
        return "on"

    def _silence(self) -> None:
        try:
            if self.buzzer_type == "passive":
                self.device.value = 0
            else:
                self.device.off()
        except Exception:
            pass

    def close(self) -> None:
        self._silence()
        try:
            self.device.close()
        except Exception:
            pass
