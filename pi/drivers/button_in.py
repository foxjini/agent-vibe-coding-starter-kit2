"""
button_in — 버튼 · 정전식 터치센서 · 인체감지(PIR) 센서.

극성이 반대라서 이것만 틀려도 "항상 눌림" 또는 "절대 안 눌림"이 됩니다.
    일반 푸시버튼 (핀 ↔ GND)      : pull_up=True   ← 기본값
    정전식 터치센서 (감지 시 HIGH) : pull_up=False
    PIR 인체감지 센서              : pull_up=False

slot_map.py 예시:
    "sensor_01": {"label": "기상 버튼", "kind": "button",
                  "driver": "button_in", "pin": 24, "pull_up": True},

보고 형식: {"pressed": true}  → 백엔드가 1/0 이력으로도 쌓아 줍니다.
"""
import logging
from typing import Any, Dict, Optional

from drivers.base import SensorDriver
from drivers.gpio import make_device

logger = logging.getLogger("pi.drivers.button_in")


class Driver(SensorDriver):
    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.device, self.simulated = make_device(
            "Button",
            config["pin"],
            pull_up=bool(config.get("pull_up", True)),
            bounce_time=float(config.get("bounce_time", 0.05)),
        )
        #: 눌렸다 떼어져도 한 번은 꼭 보고하도록 잡아 둡니다 (짧은 터치를 놓치지 않게)
        self._latched = False
        self._last_reported: Optional[bool] = None
        try:
            self.device.when_pressed = self._on_pressed
        except Exception:
            pass

    def _on_pressed(self) -> None:
        self._latched = True

    def read(self) -> Optional[Any]:
        pressed = bool(self._latched or getattr(self.device, "is_pressed", False))
        self._latched = False

        # 상태가 바뀌었을 때만 보고합니다 (1초마다 같은 값을 쌓지 않도록)
        if pressed == self._last_reported:
            return None
        self._last_reported = pressed
        if pressed:
            logger.info(f"[{self.slot_id}] {self.label} 눌림 감지")
        return {"pressed": pressed}

    def close(self) -> None:
        try:
            self.device.close()
        except Exception:
            pass
