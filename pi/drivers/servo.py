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

멈춰 있을 때 '지지직' 떨면 — 움직인 뒤 신호 끊기 (적지 않으면 예전과 똑같이 계속 잡고 있음)
    라즈베리파이 5는 서보 신호를 소프트웨어로 만들어서, 각도를 유지하는 동안 신호가 조금씩
    흔들리고 서보가 그때마다 떨립니다.
    "detach_after": 0.5     # 움직이고 0.5초 뒤 신호를 끊음 → 떨림 없음 (다음 명령 때 다시 움직임)
    신호를 끊으면 서보가 그 각도를 **힘으로 버티지는 않습니다.** 커튼·표시판처럼 힘이 안 걸리면 OK,
    무거운 문처럼 밀리면 안 되는 곳은 적지 마세요.
"""
import logging
import threading
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
        #: 움직인 뒤 몇 초 뒤에 신호를 끊을지 (0이면 끊지 않음 — 예전과 같음)
        try:
            self.detach_after = max(0.0, float(config.get("detach_after", 0) or 0))
        except (TypeError, ValueError):
            logger.warning(f"[{slot_id}] detach_after는 숫자(초)여야 합니다 — 끊지 않고 동작합니다.")
            self.detach_after = 0.0
        self._lock = threading.Lock()
        self._detach_timer: Optional[threading.Timer] = None
        self._closed = False

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

        with self._lock:
            self._cancel_detach()
            try:
                self.device.angle = angle
            except Exception as exc:
                logger.warning(f"[{self.slot_id}] 각도 {angle}도 반영 실패: {exc}")
                return "off" if self._angle is None else result
            self._angle = angle
            if self.detach_after > 0:
                self._detach_timer = threading.Timer(self.detach_after, self._detach)
                self._detach_timer.daemon = True
                self._detach_timer.start()
        logger.info(f"[{self.slot_id}] {self.label} → {result} ({angle:.0f}도)")
        return result

    def _cancel_detach(self) -> None:
        if self._detach_timer is not None:
            self._detach_timer.cancel()
            self._detach_timer = None

    def _detach(self) -> None:
        """움직임이 끝났을 시간 뒤 신호를 끊어 정지 상태의 떨림을 없앱니다."""
        with self._lock:
            self._detach_timer = None
            if self._closed:
                return
            try:
                if hasattr(self.device, "detach"):
                    self.device.detach()
                else:
                    self.device.value = None   # 흉내내기 부품
            except Exception as exc:
                logger.debug(f"[{self.slot_id}] 신호 끊기 실패: {exc}")

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._cancel_detach()
        try:
            # 서보는 끌 때 힘을 빼 줘야 떨림(지터)과 발열이 없습니다.
            self.device.detach() if hasattr(self.device, "detach") else None
            self.device.close()
        except Exception:
            pass
