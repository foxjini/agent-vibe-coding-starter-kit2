"""
rgb_out — 3핀 RGB LED (R·G·B 각각 PWM 핀 하나씩).

네오픽셀(`neopixel_out`)과 다릅니다. 어느 쪽인지 헷갈리면 핀 개수로 구분하세요.
    핀이 3개(+공통) → 이 드라이버 (rgb_out)
    핀이 1개(데이터선 하나로 여러 알 제어) → neopixel_out

네오픽셀과 달리 추가 라이브러리도 sudo 권한도 필요 없습니다.

slot_map.py 예시:
    "actuator_01": {
        "label": "스탠드 조명", "kind": "rgb_led",
        "driver": "rgb_out", "pins": {"r": 17, "g": 27, "b": 22},
        "control_type": "rgb",
        # 공통 양극(common anode) 모듈이면 True — 색이 반대로 나오면 이 값을 바꾸세요
        "common_anode": False,
    },

백엔드에서 내려오는 값: {"r": 255, "g": 0, "b": 85}  또는  {"color": "#ff0055"}
                        {"brightness": 60}  (0~100, 함께 주면 밝기를 곱합니다)
"""
import logging
from typing import Any, Dict, Optional, Tuple

from drivers.base import ActuatorDriver
from drivers.gpio import make_device
from drivers.neopixel_out import parse_color

logger = logging.getLogger("pi.drivers.rgb_out")


class Driver(ActuatorDriver):
    control_type = "rgb"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)

        pins = config.get("pins")
        if not isinstance(pins, dict) or not {"r", "g", "b"} <= set(pins):
            raise ValueError(
                'rgb_out에는 pins가 필요합니다 — 예: "pins": {"r": 17, "g": 27, "b": 22}'
            )

        # 공통 양극 모듈은 신호가 반대입니다 (LOW일 때 켜짐)
        self.common_anode = bool(config.get("common_anode", False))
        self.default_color = parse_color(config.get("default_color", "#ffffff"))

        self.channels: Dict[str, Any] = {}
        simulated = False
        for name in ("r", "g", "b"):
            device, sim = make_device(
                "PWMOutputDevice",
                pins[name],
                frequency=int(config.get("frequency", 200)),
                initial_value=1 if self.common_anode else 0,
            )
            self.channels[name] = device
            simulated = simulated or sim
        self.simulated = simulated
        self._state = "off"

    def _write(self, color: Tuple[int, int, int]) -> None:
        for name, value in zip(("r", "g", "b"), color):
            ratio = max(0.0, min(1.0, value / 255.0))
            self.channels[name].value = (1.0 - ratio) if self.common_anode else ratio

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if self.is_on(state):
            color = parse_color(value, self.default_color)
            brightness = max(0.0, min(100.0, self.number_from(value, "brightness", 100))) / 100.0
            color = tuple(int(channel * brightness) for channel in color)  # type: ignore[assignment]
        else:
            color = (0, 0, 0)

        try:
            self._write(color)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 색 반영 실패: {exc}")
            return self._state

        result = self.reflected(state)
        if self._state != result:
            logger.info(f"[{self.slot_id}] {self.label} → {result} RGB{color}")
        self._state = result
        return result

    def close(self) -> None:
        for device in self.channels.values():
            try:
                device.value = 1 if self.common_anode else 0
                device.close()
            except Exception:
                pass
