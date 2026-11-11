"""
servo360 — 360도 연속 회전 서보 (MG-90 360°, FS90R, SG90 360° 등).

180도 서보(`servo` 드라이버)와 다릅니다. 연속 회전 서보는 펄스로 **각도가 아니라 속도·방향**을
받습니다. 그래서 `servo` 드라이버로 쓰면 각도 0도(=가장 짧은 펄스)가 "한쪽으로 최고 속도"가 되어
**멈추지 않고 계속 돕니다.** 이 드라이버는 속도로 다룹니다.

    속도  100 → 정방향 최고 속도
    속도    0 → 정지
    속도 -100 → 역방향 최고 속도
    끄기       → 정지 (펄스를 끊습니다 — 가장 확실하게 멈춤)

slot_map.py 예시:
    "actuator_02": {"label": "회전 진열대", "kind": "servo360",
                    "driver": "servo360", "pin": 13,
                    "control_type": "pwm",           # 대시보드에 '세기' 슬라이더로 나옵니다
                    "value_schema": {"min": -100, "max": 100, "step": 10}},

대시보드·규칙에서 보내는 값: {"duty": 50}  (또는 {"speed": 50}) — -100~100
    켜기만 보내고 값이 없으면 `default_speed`(기본 50)로 돕니다.

옵션 (적지 않으면 기본값)
    "stop_pulse_ms": 1.5    # 서보가 멈추는 펄스 폭. 속도 0에서 조금씩 기어가면 1.45~1.55 사이로 맞추세요
    "pulse_span_ms": 0.5    # 최고 속도까지 더하고 빼는 폭 (1.5±0.5 → 1.0~2.0ms)
    "reverse": False        # True면 방향을 반대로 (정방향이 거꾸로 돌면)
    "deadband": 5           # 이 값보다 작은 속도는 정지로 봅니다
    "hold_stop": False      # True면 정지할 때 펄스를 끊지 않고 stop_pulse_ms를 계속 보냄
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.servo360")

#: 멈춤 펄스로 받아들이는 범위 (ms). 이 밖은 오타로 보고 기본값을 씁니다.
STOP_PULSE_RANGE = (1.2, 1.8)
SPAN_RANGE = (0.1, 0.8)


def speed_to_value(speed: float, reverse: bool = False, deadband: float = 5.0) -> Optional[float]:
    """속도(-100~100)를 gpiozero Servo 값(-1~1)으로. 정지면 None."""
    speed = max(-100.0, min(100.0, float(speed)))
    if abs(speed) < deadband:
        return None
    value = speed / 100.0
    return -value if reverse else value


class Driver(ActuatorDriver):
    control_type = "pwm"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        stop = self._number(config, "stop_pulse_ms", 1.5, STOP_PULSE_RANGE)
        span = self._number(config, "pulse_span_ms", 0.5, SPAN_RANGE)
        self.reverse = bool(config.get("reverse", False))
        self.deadband = max(0.0, float(config.get("deadband", 5)))
        self.default_speed = float(config.get("default_speed", 50))
        self.hold_stop = bool(config.get("hold_stop", False))
        self.device, self.simulated = make_device(
            "Servo", config["pin"], initial_value=None,
            min_pulse_width=(stop - span) / 1000.0,
            max_pulse_width=(stop + span) / 1000.0,
        )
        self._speed: Optional[float] = None   # 마지막으로 낸 속도 (None = 아직 없음)

    def _number(self, config: Dict[str, Any], key: str, default: float, allowed) -> float:
        try:
            number = float(config.get(key, default))
        except (TypeError, ValueError):
            number = float("nan")
        if not (allowed[0] <= number <= allowed[1]):
            if key in config:
                logger.warning(
                    f"[{self.slot_id}] {key}={config.get(key)!r}는 쓸 수 없습니다 "
                    f"({allowed[0]}~{allowed[1]}) — 기본값 {default}로 동작합니다."
                )
            return default
        return number

    def apply(self, state: Optional[str], value: Any = None) -> str:
        result = self.reflected(state)
        speed = self.number_from(value, "duty", self.default_speed, "speed") if self.is_on(state) else 0.0
        speed = max(-100.0, min(100.0, speed))
        target = speed_to_value(speed, self.reverse, self.deadband)
        if target is None:
            speed = 0.0

        if self._speed is not None and abs(self._speed - speed) < 0.5:
            return result
        try:
            if target is None:
                # 정지: 펄스를 끊으면(detach) 대부분의 연속 회전 서보가 확실히 멈춥니다
                self.device.value = 0.0 if self.hold_stop else None
            else:
                self.device.value = target
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 속도 {speed:.0f} 반영 실패: {exc}")
            return "off" if self._speed is None else result
        self._speed = speed
        if speed == 0:
            logger.info(f"[{self.slot_id}] {self.label} → {result} (정지)")
        else:
            way = "정방향" if speed > 0 else "역방향"
            logger.info(f"[{self.slot_id}] {self.label} → {result} (속도 {abs(speed):.0f}%, {way})")
        return result

    def close(self) -> None:
        try:
            self.device.value = None   # 끌 때 반드시 멈춥니다
            self.device.close()
        except Exception:
            pass
