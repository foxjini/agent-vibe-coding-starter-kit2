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
(그래야 차트가 각각 그려집니다 — 부록F 3-2절). 두 슬롯에 **같은 pin**을 적으면 센서 하나를
함께 쓰고, 한 번 잰 온도·습도를 나눠 씁니다 (같은 핀을 두 번 잡지 않습니다 — `--check` 경고도 없음).
"""
import logging
import math
import random
import time
from typing import Any, Dict, Optional

from drivers.base import SensorDriver
from drivers.libcheck import first_line, on_raspberry_pi

logger = logging.getLogger("pi.drivers.dht_in")

#: 핀 번호 → 센서 하나와 마지막 측정값. 같은 핀의 슬롯(온도·습도)들이 함께 씁니다.
#:   {"sensor": 객체, "users": 쓰는 슬롯 수, "at": 잰 시각, "temperature": 값, "humidity": 값}
_shared: Dict[int, Dict[str, Any]] = {}
#: DHT는 2초에 한 번보다 자주 잴 수 없습니다 — 이 시간 안에는 잰 값을 나눠 씁니다
SHARE_SECONDS = 2.0


class Driver(SensorDriver):
    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.interval = float(config.get("interval", 5.0))
        self.measure = str(config.get("measure", "temperature")).strip().lower()
        self.decimals = int(config.get("decimals", 1))
        self.pin = config["pin"]
        self.sensor = None
        self.simulated = True
        self._born = time.time()
        self._phase = random.random() * math.tau

        shared = _shared.get(self.pin)
        if shared is not None:
            # 같은 핀의 다른 슬롯(예: 온도)이 이미 센서를 열었으면 그것을 함께 씁니다
            shared["users"] += 1
            self.sensor = shared["sensor"]
            self.simulated = False
            return

        try:
            import adafruit_dht  # type: ignore
            import board  # type: ignore

            pin = getattr(board, f"D{self.pin}")
            model = str(config.get("model", "DHT22")).strip().upper()
            # 파이 5에서 값이 계속 안 읽히면 배치표에 "use_pulseio": False 를 넣어 볼 수 있습니다
            options = {"use_pulseio": bool(config["use_pulseio"])} if "use_pulseio" in config else {}
            self.sensor = (adafruit_dht.DHT11 if model == "DHT11" else adafruit_dht.DHT22)(pin, **options)
            self.simulated = False
            _shared[self.pin] = {"sensor": self.sensor, "users": 1, "at": 0.0,
                                 "temperature": None, "humidity": None}
        except Exception as exc:
            if on_raspberry_pi():
                logger.warning(
                    f"[{slot_id}] 온습도 라이브러리를 쓸 수 없어 실제 센서 대신 흉내낸 값을 보고합니다 "
                    f"— {first_line(exc)}  → 원인·설치 명령 확인: python daemon.py --check"
                )
            else:
                logger.info(
                    f"[{slot_id}] 온습도 라이브러리가 없어 흉내낸 값을 보고합니다 (PC에서는 정상)."
                )

    def read(self) -> Optional[Any]:
        if self.sensor is None:
            # 흉내내기: 온도는 23±2도, 습도는 50±10% 근처에서 천천히 오갑니다.
            wave = math.sin((time.time() - self._born) / 20.0 + self._phase)
            base, swing = (23.0, 2.0) if self.measure == "temperature" else (50.0, 10.0)
            return {"value": round(base + swing * wave, self.decimals)}

        key = "humidity" if self.measure == "humidity" else "temperature"
        shared = _shared.get(self.pin)
        now = time.time()
        if shared is not None and now - shared["at"] < SHARE_SECONDS and shared[key] is not None:
            return {"value": round(float(shared[key]), self.decimals)}   # 방금 잰 값을 나눠 씀

        try:
            # 온도를 읽는 순간 센서가 온도·습도를 함께 잽니다 — 둘 다 받아 둡니다
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity
        except RuntimeError as exc:
            # DHT는 원래 가끔 실패합니다 — 경고만 남기고 다음 회차에 다시 읽습니다.
            logger.debug(f"[{self.slot_id}] 읽기 실패(정상적으로 발생): {exc}")
            return None
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 센서 오류: {exc}")
            return None

        if shared is not None and temperature is not None and humidity is not None:
            shared.update(at=now, temperature=temperature, humidity=humidity)
        raw = humidity if key == "humidity" else temperature
        if raw is None:
            return None
        return {"value": round(float(raw), self.decimals)}

    def close(self) -> None:
        try:
            shared = _shared.get(self.pin)
            if shared is not None and shared["sensor"] is self.sensor:
                shared["users"] -= 1
                if shared["users"] > 0:
                    return          # 같은 핀의 다른 슬롯이 아직 씁니다
                del _shared[self.pin]
            if self.sensor is not None:
                self.sensor.exit()
        except Exception:
            pass
