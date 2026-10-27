"""
servo — 각도를 지정하는 서보모터 (자동문, 커튼, 급식 배급구).

slot_map.py 예시:
    "actuator_01": {"label": "자동문", "kind": "servo",
                    "driver": "servo", "pin": 12, "control_type": "servo",
                    "value_schema": {"min": 0, "max": 180, "step": 5}},

백엔드에서 내려오는 값: {"angle": 90}
state가 off면 `rest_angle`(기본 0도)로 돌아갑니다.

SG90처럼 180도를 다 못 돌 때 — 펄스 폭 옵션 (적지 않으면 예전과 똑같이 동작)
    gpiozero 기본 펄스는 1.0~2.0ms라 SG90(보통 0.5~2.4ms)은 절반 정도만 돕니다.
    "min_pulse_ms": 0.5, "max_pulse_ms": 2.4   # 서보 설명서의 값. 끝에서 '드르륵' 떨면 조금 좁히세요
    "full_range": 180                          # 그 펄스 범위가 덮는 실제 각도 (기본 180)
    이 옵션을 적으면 **보낸 각도 = 실제 각도**가 되고, value_schema는 움직일 수 있는 범위만 정합니다.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from drivers.base import ActuatorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.servo")

#: 펄스 폭으로 받아들이는 범위 (ms). 이 밖은 오타로 보고 무시합니다.
PULSE_MS_RANGE = (0.3, 3.0)
#: 한쪽만 적었을 때 쓰는 gpiozero 기본값 (ms)
DEFAULT_PULSE_MS = (1.0, 2.0)


class Driver(ActuatorDriver):
    control_type = "servo"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        schema = config.get("value_schema") or {}
        self.min_angle = float(schema.get("min", config.get("min_angle", 0)))
        self.max_angle = float(schema.get("max", config.get("max_angle", 180)))
        self.rest_angle = float(config.get("rest_angle", self.min_angle))

        pulse = self._pulse_widths(config)
        if pulse is None:
            # 예전 방식: value_schema 범위를 gpiozero 기본 펄스(1~2ms)에 대응시킵니다.
            device_args: Dict[str, Any] = {"min_angle": self.min_angle, "max_angle": self.max_angle}
        else:
            # 펄스 범위 = 실제 0도~full_range도. 보낸 각도가 곧 실제 각도입니다.
            full_range = float(config.get("full_range", 180))
            device_args = {
                "min_angle": 0.0,
                "max_angle": full_range,
                "min_pulse_width": pulse[0] / 1000.0,
                "max_pulse_width": pulse[1] / 1000.0,
            }
            self.min_angle = max(0.0, self.min_angle)
            self.max_angle = min(full_range, self.max_angle)
        self.device, self.simulated = make_device("AngularServo", config["pin"],
                                                  initial_angle=None, **device_args)
        self._angle: Optional[float] = None

    def _pulse_widths(self, config: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """min_pulse_ms·max_pulse_ms를 읽습니다. 둘 다 없거나 잘못됐으면 None(예전 방식)."""
        if "min_pulse_ms" not in config and "max_pulse_ms" not in config:
            return None
        try:
            low = float(config.get("min_pulse_ms", DEFAULT_PULSE_MS[0]))
            high = float(config.get("max_pulse_ms", DEFAULT_PULSE_MS[1]))
        except (TypeError, ValueError):
            logger.warning(f"[{self.slot_id}] min_pulse_ms·max_pulse_ms는 숫자여야 합니다 — 기본 펄스로 동작합니다.")
            return None
        lo_ok, hi_ok = PULSE_MS_RANGE
        if not (lo_ok <= low < high <= hi_ok):
            logger.warning(
                f"[{self.slot_id}] 펄스 폭이 이상합니다 (min {low}ms, max {high}ms). "
                f"{lo_ok}~{hi_ok}ms 사이에서 min < max로 적으세요 — 기본 펄스로 동작합니다."
            )
            return None
        return low, high

    def apply(self, state: Optional[str], value: Any = None) -> str:
        result = self.reflected(state)     # servo는 보통 "move"
        if self.is_on(state):
            angle = self.number_from(value, "angle", self.max_angle)
        else:
            angle = self.rest_angle

        angle = max(self.min_angle, min(self.max_angle, angle))
        if self._angle is not None and abs(self._angle - angle) < 0.5:
            return result

        try:
            self.device.angle = angle
        except Exception as exc:
            logger.warning(f"[{self.slot_id}] 각도 {angle}도 반영 실패: {exc}")
            return "off" if self._angle is None else result
        self._angle = angle
        logger.info(f"[{self.slot_id}] {self.label} → {result} ({angle:.0f}도)")
        return result

    def close(self) -> None:
        try:
            # 서보는 끌 때 힘을 빼 줘야 떨림(지터)과 발열이 없습니다.
            self.device.detach() if hasattr(self.device, "detach") else None
            self.device.close()
        except Exception:
            pass
