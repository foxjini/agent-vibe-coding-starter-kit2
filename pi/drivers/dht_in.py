"""
dht_in — 온습도 센서 (DHT11 / DHT22).

이 센서는 느리고 잘 실패합니다. `interval`을 5초 이상으로 두세요 (2초 미만이면 읽기 실패).
읽기에 실패해도 프로그램은 죽지 않고 다음 회차에 다시 시도합니다.

slot_map.py 예시:
    "sensor_03": {"label": "실내 온도", "kind": "temperature", "unit": "°C",
                  "driver": "dht_in", "pin": 4, "interval": 5.0},
    "sensor_04": {"label": "실내 습도", "kind": "humidity", "unit": "%",
                  "driver": "dht_in", "pin": 4, "measure": "humidity", "interval": 5.0},

한 부품에서 온도와 습도를 둘 다 쓰려면 **슬롯 2개**로 나누고 `measure`로 구분합니다
(그래야 차트가 각각 그려집니다 — 부록F 3-2절).
"""
import logging
import math
import random
import time
from typing import Any, Dict, Optional

from drivers.base import SensorDriver

logger = logging.getLogger("pi.drivers.dht_in")


class Driver(SensorDriver):
    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.interval = float(config.get("interval", 5.0))
        self.measure = str(config.get("measure", "temperature")).strip().lower()
        self.decimals = int(config.get("decimals", 1))
        self.sensor = None
        self.simulated = True
        self._born = time.time()
        self._phase = random.random() * math.tau

        try:
            import adafruit_dht  # type: ignore
            import board  # type: ignore

            pin = getattr(board, f"D{config['pin']}")
            model = str(config.get("model", "DHT22")).strip().upper()
            self.sensor = (adafruit_dht.DHT11 if model == "DHT11" else adafruit_dht.DHT22)(pin)
            self.simulated = False
        except Exception as exc:
            logger.info(
                f"[{slot_id}] 온습도 라이브러리를 쓸 수 없어 흉내낸 값을 보고합니다 "
                f"({type(exc).__name__}). 실기기에서는 "
                "`pip install adafruit-circuitpython-dht`를 설치하세요."
            )

    def read(self) -> Optional[Any]:
        if self.sensor is None:
            # 흉내내기: 온도는 23±2도, 습도는 50±10% 근처에서 천천히 오갑니다.
            wave = math.sin((time.time() - self._born) / 20.0 + self._phase)
            base, swing = (23.0, 2.0) if self.measure == "temperature" else (50.0, 10.0)
            return {"value": round(base + swing * wave, self.decimals)}

        try:
            raw = self.sensor.temperature if self.measure == "temperature" else self.sensor.humidity
        except RuntimeError as exc:
            # DHT는 원래 가끔 실패합니다 — 경고만 남기고 다음 회차에 다시 읽습니다.
            logger.debug(f"[{self.slot_id}] 읽기 실패(정상적으로 발생): {exc}")
            return None
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 센서 오류: {exc}")
            return None

        if raw is None:
            return None
        return {"value": round(float(raw), self.decimals)}

    def close(self) -> None:
        try:
            if self.sensor is not None:
                self.sensor.exit()
        except Exception:
            pass
