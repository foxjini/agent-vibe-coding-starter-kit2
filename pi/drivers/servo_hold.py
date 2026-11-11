"""
servo_hold — 힘을 유지하는 서보 (MG996R 등 고토크 180도 서보). 문·뚜껑·차단봉·로봇 팔.

`servo`와 같은 각도 서보지만 **멈춘 뒤에도 신호를 계속 보내 그 각도를 힘으로 버팁니다.**
(`servo`의 `detach_after`처럼 신호를 끊지 않습니다 — 적어도 무시합니다.)
SG90처럼 힘이 안 걸리는 곳은 `servo`, 힘이 걸리는 곳은 `servo_hold`를 고르세요.

slot_map.py 예시:
    "actuator_01": {"label": "자동문", "kind": "servo",
                    "driver": "servo_hold", "pin": 12, "control_type": "servo",
                    "value_schema": {"min": 0, "max": 120, "step": 5},
                    "rest_angle": 0,          # 끄면(닫힘) 돌아가 버틸 각도
                    "speed": 90},             # (선택) 1초에 90도씩 천천히 — 순간 전류·충격을 줄임

백엔드에서 내려오는 값: {"angle": 90}   state가 off면 rest_angle로 가서 버팁니다.

옵션 (적지 않으면 기본값)
    "min_pulse_ms": 0.5, "max_pulse_ms": 2.5   # MG996R 기본. 끝에서 '드르륵' 떨면 조금 좁히세요
    "full_range": 180                          # 그 펄스 범위가 덮는 실제 각도
    "speed": 0                                 # 1초에 몇 도씩 움직일지 (0 = 바로 이동)
    "start_angle": (rest_angle)                # 데몬이 켜질 때 잡고 있을 각도. None이면 첫 명령까지 힘 빼고 대기

전원: MG996R은 움직일 때 1~2A 넘게 씁니다. **파이 5V에 꽂지 말고 별도 5~6V(2A 이상) 전원**을
쓰고, 그 전원의 GND를 파이 GND와 이어 주세요. 파이 5V에 꽂으면 파이가 재부팅됩니다.

참고: 라즈베리파이 5는 서보 신호를 소프트웨어로 만들어, 버티는 동안 미세하게 '지잉' 소리가
날 수 있습니다. 힘은 그대로 유지됩니다.
"""
import logging
import threading
import time
from typing import Any, Dict, Optional

from drivers import servo

logger = logging.getLogger("pi.drivers.servo_hold")

#: 천천히 움직일 때 한 걸음 간격 (초) — 서보 신호 주기(20ms)와 같게
STEP_SECONDS = 0.02


class Driver(servo.Driver):
    control_type = "servo"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        config = dict(config)
        if "min_pulse_ms" not in config and "max_pulse_ms" not in config:
            config["min_pulse_ms"], config["max_pulse_ms"] = 0.5, 2.5   # MG996R 기본
        if config.pop("detach_after", None):
            logger.warning(f"[{slot_id}] servo_hold는 힘을 유지하려고 신호를 끊지 않습니다 — detach_after는 무시합니다.")
        super().__init__(slot_id, config)
        self.detach_after = 0.0
        try:
            self.speed = max(0.0, float(config.get("speed", 0) or 0))
        except (TypeError, ValueError):
            logger.warning(f"[{slot_id}] speed는 숫자(초당 각도)여야 합니다 — 바로 이동합니다.")
            self.speed = 0.0
        self._target: Optional[float] = None
        self._mover: Optional[threading.Thread] = None
        self._stop_move = threading.Event()

        start = config.get("start_angle", self.rest_angle)
        if start is not None:
            try:
                start = max(self.min_angle, min(self.max_angle, float(start)))
                self.device.angle = start
                self._angle = self._target = start
            except Exception as exc:
                logger.warning(f"[{slot_id}] 시작 각도 {start}도로 잡지 못했습니다: {exc}")

    # ------------------------------------------------------------------

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if self.speed <= 0:
            result = super().apply(state, value)       # 바로 이동 (detach_after는 0이라 계속 유지)
            self._target = self._angle
            return result

        result = self.reflected(state)
        angle = self.number_from(value, "angle", self.max_angle) if self.is_on(state) else self.rest_angle
        angle = max(self.min_angle, min(self.max_angle, angle))
        if self._target is not None and abs(self._target - angle) < 0.5:
            return result

        self._stop_mover()
        start = self._angle if self._angle is not None else angle
        self._target = angle
        self._stop_move.clear()
        self._mover = threading.Thread(target=self._move, args=(start, angle), daemon=True)
        self._mover.start()
        logger.info(f"[{self.slot_id}] {self.label} → {result} ({start:.0f}도 → {angle:.0f}도, 초당 {self.speed:.0f}도, 유지)")
        return result

    def _move(self, start: float, target: float) -> None:
        """목표 각도까지 STEP_SECONDS마다 조금씩 움직입니다. 새 명령이 오면 멈추고 넘겨줍니다."""
        step = self.speed * STEP_SECONDS
        current = start
        while not self._stop_move.is_set():
            if abs(target - current) <= step:
                current = target
            else:
                current += step if target > current else -step
            with self._lock:
                if self._closed:
                    return
                try:
                    self.device.angle = current
                except Exception as exc:
                    logger.warning(f"[{self.slot_id}] 각도 {current:.0f}도 반영 실패: {exc}")
                    return
                self._angle = current
            if current == target:
                return
            time.sleep(STEP_SECONDS)

    def _stop_mover(self) -> None:
        if self._mover is not None and self._mover.is_alive():
            self._stop_move.set()
            self._mover.join(timeout=1.0)
        self._mover = None

    def close(self) -> None:
        self._stop_mover()
        super().close()
