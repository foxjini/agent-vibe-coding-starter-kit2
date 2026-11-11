"""
aht20_in — I2C 온습도 센서 (AHT20 / AHT21 / AHT10, 주소 0x38).

DHT와 달리 **I2C**로 연결합니다 (데이터 핀이 아니라 SDA·SCL 두 줄):
    VIN(VCC) → 3.3V (물리 1번)   GND → GND (물리 6번)
    SDA      → GPIO 2 (물리 3번) SCL → GPIO 3 (물리 5번)
처음 한 번 I2C를 켭니다: sudo raspi-config → Interface Options → I2C → Yes → 재부팅
연결 확인: sudo apt install -y i2c-tools 후 i2cdetect -y 1 → 표에 38이 보이면 성공

slot_map.py 예시 (온도·습도를 슬롯 2개로 — 차트가 각각 그려집니다, 부록F 3-2절):
    "sensor_01": {"label": "교실 온도", "kind": "temperature", "unit": "°C",
                  "driver": "aht20_in", "interval": 2.0},
    "sensor_02": {"label": "교실 습도", "kind": "humidity", "unit": "%",
                  "driver": "aht20_in", "measure": "humidity", "interval": 2.0},

옵션: "measure" temperature(기본)·humidity · "i2c_bus" 1(기본) · "address" 0x38(기본) · "decimals" 1
두 슬롯이 같은 센서를 쓰면 한 번 잰 값을 나눠 씁니다 (1초 안에 다시 재지 않음).
라이브러리: pip install smbus2 (venv에서, sudo 불필요). 없거나 PC면 흉내낸 값을 보고합니다.
"""
import logging
import math
import os
import random
import time
from typing import Any, Dict, Optional, Tuple

from drivers.base import SensorDriver
from drivers.libcheck import first_line, on_raspberry_pi

logger = logging.getLogger("pi.drivers.aht20_in")

DEFAULT_ADDRESS = 0x38
#: 같은 센서를 이 시간 안에는 다시 재지 않습니다 (온도·습도 슬롯 2개가 나눠 씀)
SHARE_SECONDS = 1.0

#: (버스, 주소) → (잰 시각, 온도, 습도)
_shared: Dict[Tuple[int, int], Tuple[float, float, float]] = {}


def crc8(data: bytes) -> int:
    """AHT20 CRC-8 (다항식 0x31, 시작값 0xFF)."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def parse_measurement(data: bytes) -> Tuple[float, float]:
    """측정 결과 6바이트(상태 + 5바이트)를 (온도 °C, 습도 %)로 바꿉니다."""
    raw_humidity = (data[1] << 12) | (data[2] << 4) | (data[3] >> 4)
    raw_temperature = ((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]
    humidity = raw_humidity * 100.0 / (1 << 20)
    temperature = raw_temperature * 200.0 / (1 << 20) - 50.0
    return temperature, humidity


class Driver(SensorDriver):
    #: I2C를 쓰는 부품 — slot_config가 GPIO 2·3을 다른 부품이 쓰는지 확인합니다
    uses_i2c = True

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.interval = float(config.get("interval", 2.0))
        self.measure = str(config.get("measure", "temperature")).strip().lower()
        self.decimals = int(config.get("decimals", 1))
        self.bus_number = int(config.get("i2c_bus", 1))
        address = config.get("address", DEFAULT_ADDRESS)
        self.address = int(address, 16) if isinstance(address, str) else int(address)
        self.bus = None
        self.simulated = True
        self._born = time.time()
        self._phase = random.random() * math.tau
        self._warned = False

        try:
            from smbus2 import SMBus  # type: ignore

            if not os.path.exists(f"/dev/i2c-{self.bus_number}"):
                raise RuntimeError(f"/dev/i2c-{self.bus_number}이 없습니다 (I2C가 꺼져 있음)")
            self.bus = SMBus(self.bus_number)
            self._initialize()
            self.simulated = False
        except Exception as exc:
            self.bus = None
            if on_raspberry_pi():
                logger.warning(
                    f"[{slot_id}] AHT20을 쓸 수 없어 실제 센서 대신 흉내낸 값을 보고합니다 "
                    f"— {first_line(exc)}  → 원인 확인: python daemon.py --check"
                )
            else:
                logger.info(f"[{slot_id}] AHT20 라이브러리·I2C가 없어 흉내낸 값을 보고합니다 (PC에서는 정상).")

    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """전원을 넣은 뒤 보정(calibration) 비트가 없으면 초기화 명령을 보냅니다."""
        status = self.bus.read_byte(self.address)
        if not status & 0x08:
            self.bus.write_i2c_block_data(self.address, 0xBE, [0x08, 0x00])
            time.sleep(0.01)

    def _measure(self) -> Tuple[float, float]:
        from smbus2 import i2c_msg  # type: ignore

        key = (self.bus_number, self.address)
        cached = _shared.get(key)
        now = time.time()
        if cached and now - cached[0] < SHARE_SECONDS:
            return cached[1], cached[2]

        self.bus.write_i2c_block_data(self.address, 0xAC, [0x33, 0x00])   # 측정 시작
        time.sleep(0.08)
        for _ in range(5):
            read = i2c_msg.read(self.address, 7)
            self.bus.i2c_rdwr(read)
            data = bytes(list(read))
            if not data[0] & 0x80:      # 바쁨 비트가 꺼지면 측정 끝
                break
            time.sleep(0.02)
        else:
            raise RuntimeError("측정이 끝나지 않았습니다 (센서가 계속 바쁨)")
        if crc8(data[:6]) != data[6]:
            raise RuntimeError("CRC가 맞지 않습니다 (배선·접촉 확인)")

        temperature, humidity = parse_measurement(data)
        _shared[key] = (now, temperature, humidity)
        return temperature, humidity

    def read(self) -> Optional[Any]:
        if self.bus is None:
            # 흉내내기: 온도는 23±2도, 습도는 50±10% 근처에서 천천히 오갑니다.
            wave = math.sin((time.time() - self._born) / 20.0 + self._phase)
            base, swing = (23.0, 2.0) if self.measure == "temperature" else (50.0, 10.0)
            return {"value": round(base + swing * wave, self.decimals)}

        try:
            temperature, humidity = self._measure()
        except Exception as exc:
            # 한 번 실패는 흔합니다 — 처음 한 번만 경고하고 다음 회차에 다시 잽니다.
            if not self._warned:
                logger.warning(f"[{self.slot_id}] AHT20 읽기 실패 (다음 회차에 다시): {first_line(exc)}")
                self._warned = True
            return None
        self._warned = False
        raw = humidity if self.measure == "humidity" else temperature
        return {"value": round(raw, self.decimals)}

    def close(self) -> None:
        try:
            if self.bus is not None:
                self.bus.close()
        except Exception:
            pass
