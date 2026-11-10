"""
neopixel_out — RGB LED 스트립 (네오픽셀 / WS2812).

slot_map.py 예시:
    "actuator_04": {"label": "좌석 표시등", "kind": "neopixel",
                    "driver": "neopixel_out", "pin": 18,
                    "control_type": "rgb", "count": 8},

백엔드에서 내려오는 값: {"color": "#ff3355"}  또는  {"r":255,"g":51,"b":85}
                        {"brightness": 60}  (0~100)

라이브러리가 없거나 PC에서 실행하면 색만 로그로 보여 주고 넘어갑니다.
라즈베리파이 5에서는 RP1 PIO를 쓰는 전용 라이브러리가 필요합니다 (sudo 불필요, requirements.txt 참고):
    pip install adafruit-blinka adafruit-circuitpython-neopixel
    pip install --pre adafruit-blinka-raspberry-pi5-neopixel
파이 4까지 쓰던 rpi_ws281x 방식은 파이 5에서 동작하지 않습니다.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from drivers.base import ActuatorDriver
from drivers.libcheck import first_line, on_raspberry_pi

logger = logging.getLogger("pi.drivers.neopixel_out")


def parse_color(value: Any, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """'#ff3355' 또는 {"r":..,"g":..,"b":..} 를 (r, g, b)로 바꿉니다."""
    if isinstance(value, dict):
        if "color" in value:
            return parse_color(value["color"], default)
        if {"r", "g", "b"} <= set(value):
            try:
                return tuple(max(0, min(255, int(value[k]))) for k in ("r", "g", "b"))  # type: ignore[return-value]
            except (TypeError, ValueError):
                return default
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 6:
            try:
                return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
            except ValueError:
                return default
        named = {
            "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
            "yellow": (255, 200, 0), "white": (255, 255, 255), "off": (0, 0, 0),
        }
        if text.lower() in named:
            return named[text.lower()]
    return default


class Driver(ActuatorDriver):
    control_type = "rgb"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.count = int(config.get("count", 8))
        self.default_color = parse_color(config.get("default_color", "#ffffff"))
        self.strip = None
        self.simulated = True

        try:
            import board  # type: ignore
            import neopixel  # type: ignore

            pin = getattr(board, f"D{config['pin']}")
            self.strip = neopixel.NeoPixel(pin, self.count, auto_write=False)
            self.simulated = False
        except Exception as exc:
            if on_raspberry_pi():
                logger.warning(
                    f"[{slot_id}] 네오픽셀 라이브러리를 쓸 수 없어 실제 LED 대신 색을 로그로만 표시합니다 "
                    f"— {first_line(exc)}  → 원인·설치 명령 확인: python daemon.py --check"
                )
            else:
                logger.info(
                    f"[{slot_id}] 네오픽셀 라이브러리가 없어 색을 로그로만 표시합니다 (PC에서는 정상)."
                )
        self._state = "off"
        self._color: Optional[Tuple[int, int, int]] = None   # 마지막으로 낸 색 (로그용)

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if self.is_on(state):
            color = parse_color(value, self.default_color)
            brightness = max(0.0, min(100.0, self.number_from(value, "brightness", 100))) / 100.0
            color = tuple(int(c * brightness) for c in color)
        else:
            color = (0, 0, 0)
        result = self.reflected(state)

        if self.strip is not None:
            try:
                self.strip.fill(color)
                self.strip.show()
            except Exception as exc:
                logger.warning(f"[{self.slot_id}] 색 반영 실패: {exc}")
                return self._state

        # 켜짐/꺼짐뿐 아니라 색이 바뀔 때도 남깁니다 (예: 혼잡도 단계마다 색이 바뀜)
        if self._state != result or self._color != color:
            logger.info(f"[{self.slot_id}] {self.label} → {result} RGB{color}")
        self._state = result
        self._color = color
        return result

    def close(self) -> None:
        try:
            if self.strip is not None:
                self.strip.fill((0, 0, 0))
                self.strip.show()
        except Exception:
            pass
