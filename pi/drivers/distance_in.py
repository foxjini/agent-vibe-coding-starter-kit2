"""
distance_in — 초음파 거리센서 (HC-SR04).

배선 주의: ECHO 핀은 5V로 나오므로 **분압저항을 꼭 넣으세요**. 그냥 연결하면 GPIO가 상합니다.

slot_map.py 예시:
    "sensor_05": {"label": "출입문 거리", "kind": "distance", "unit": "cm",
                  "driver": "distance_in", "trigger_pin": 23, "echo_pin": 24,
                  "max_distance_cm": 200, "interval": 0.5},

보고 형식: {"value": 42.7}  (cm)
"""
import logging
import math
import random
import time
from typing import Any, Dict, Optional

from drivers.base import SensorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.distance_in")


class Driver(SensorDriver):
    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.max_cm = float(config.get("max_distance_cm", 200))
        self.decimals = int(config.get("decimals", 1))
        self.deadband = float(config.get("deadband", 1.0))
        self.device, self.simulated = make_device(
            "DistanceSensor",
            echo=config.get("echo_pin", config.get("echo")),
            trigger=config.get("trigger_pin", config.get("trigger")),
            max_distance=self.max_cm / 100.0,
        )
        self._born = time.time()
        self._phase = random.random() * math.tau
        self._last: Optional[float] = None

    def read(self) -> Optional[Any]:
        if self.simulated:
            wave = math.sin((time.time() - self._born) / 8.0 + self._phase)
            measured = round(self.max_cm * (0.5 + 0.4 * wave), self.decimals)
        else:
            try:
                measured = round(float(self.device.distance) * 100.0, self.decimals)
            except Exception as exc:
                logger.warning(f"[{self.slot_id}] 거리를 읽지 못했습니다: {exc}")
                return None

        if self._last is not None and abs(measured - self._last) < self.deadband:
            return None
        self._last = measured
        return {"value": measured}

    def close(self) -> None:
        try:
            self.device.close()
        except Exception:
            pass
