"""
analog_in — 압력·조도·가변저항처럼 연속으로 변하는 센서.

라즈베리파이에는 아날로그 입력 핀이 없습니다. **ADC(MCP3008 등)를 거쳐야** 읽을 수 있습니다.

slot_map.py 예시:
    "sensor_02": {"label": "좌석 압력", "kind": "pressure", "unit": "kg",
                  "driver": "analog_in", "channel": 0,
                  "scale": 120, "interval": 1.0},

옵션
    channel : ADC 채널 번호 (0~7)
    scale   : 0~1 비율에 곱할 값 (예: 최대 120kg이면 scale=120)
    offset  : 더할 값 (영점 보정)
    decimals: 반올림 자리수 (기본 1)

보고 형식: {"value": 47.3}  → 차트가 자동으로 그려집니다 (부록F 3-2절).
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import SensorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.analog_in")


class Driver(SensorDriver):
    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.scale = float(config.get("scale", 100))
        self.offset = float(config.get("offset", 0))
        self.decimals = int(config.get("decimals", 1))
        #: 값이 이만큼 이상 바뀌어야 보고합니다 (노이즈로 차트가 지저분해지지 않게)
        self.deadband = float(config.get("deadband", 0))
        self.device, self.simulated = make_device(
            config.get("adc", "MCP3008"),
            channel=int(config.get("channel", 0)),
        )
        self._last: Optional[float] = None

    def read(self) -> Optional[Any]:
        try:
            ratio = float(self.device.value)
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 값을 읽지 못했습니다: {exc}")
            return None

        measured = round(ratio * self.scale + self.offset, self.decimals)
        if self._last is not None and abs(measured - self._last) < self.deadband:
            return None
        self._last = measured
        return {"value": measured}

    def close(self) -> None:
        try:
            self.device.close()
        except Exception:
            pass
