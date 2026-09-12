"""
드라이버 계약 (pi/drivers/base.py) — 키트 제공, 수정하지 마세요.
=============================================================================
드라이버는 **슬롯 하나에 꽂힌 부품 하나**를 다룹니다.
백엔드가 내려준 목표 상태를 실제 부품에 반영(apply)하고, 센서값을 읽습니다(read).

새 부품을 직접 만들려면 이 파일이 아니라 `drivers/`에 새 파일을 하나 추가하고
아래 두 메서드만 구현하면 됩니다 (부록F 8-3절).

    class MyDriver(ActuatorDriver):
        def apply(self, state, value): ...    # 목표 상태를 부품에 반영
        # (센서라면)
        def read(self): ...                   # 측정값을 돌려줌

**중요 — 상태 계약 (부록A)**
`apply()`는 "실제로 반영된 상태"를 돌려줍니다. 백엔드는 이 값을 current_state로 기록하므로,
반영하지 못했으면 성공한 척하지 말고 그대로 예외를 내거나 이전 상태를 돌려주세요.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("pi.drivers")


class DriverError(Exception):
    """드라이버를 만들거나 쓰는 중 생긴 문제 (핀 충돌, 잘못된 설정 등)."""


class SlotDriver:
    """모든 드라이버의 공통 뼈대."""

    #: 이 드라이버가 액추에이터인지 센서인지 (하위 클래스가 정함)
    role: str = "sensor"
    #: 대시보드 위젯 결정 근거 (부록F 3-1절). 액추에이터만 의미가 있습니다.
    control_type: Optional[str] = None

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        self.slot_id = slot_id
        self.config = config
        self.label = config.get("label") or slot_id
        #: 실기기 대신 흉내만 내고 있는지 (PC 개발 환경). 데몬이 로그에 표시합니다.
        self.simulated = False

    # ------------------------------------------------------------------
    # 하위 클래스가 구현하는 것
    # ------------------------------------------------------------------

    def apply(self, state: Optional[str], value: Any = None) -> str:
        """
        액추에이터에 목표 상태를 반영하고, **실제로 반영된 상태**를 돌려줍니다.
        센서 드라이버는 이 메서드를 쓰지 않습니다.
        """
        raise NotImplementedError(f"{type(self).__name__}은(는) 액추에이터가 아닙니다.")

    def read(self) -> Optional[Any]:
        """
        센서 측정값을 돌려줍니다. 아직 읽을 값이 없으면 None.

        숫자 센서는 반드시 `{"value": 24.5}` 형식으로 돌려주세요 —
        그래야 백엔드가 차트용 이력에 적재합니다 (부록F 3-2절).
        """
        raise NotImplementedError(f"{type(self).__name__}은(는) 센서가 아닙니다.")

    def close(self) -> None:
        """GPIO 자원을 해제합니다 (프로그램 종료 시 데몬이 호출)."""

    # ------------------------------------------------------------------
    # 공통 도우미
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """`POST /api/v1/devices/register`에 올릴 메타데이터를 만듭니다."""
        meta = dict(self.config.get("meta") or {})
        for key in ("pin", "pins", "channel", "driver"):
            if key in self.config:
                meta[key] = self.config[key]
        if self.simulated:
            meta["simulated"] = True

        entry: Dict[str, Any] = {
            "slot_id": self.slot_id,
            "label": self.label,
            "kind": self.config.get("kind") or "unknown",
        }
        if self.role == "actuator":
            entry["control_type"] = self.config.get("control_type") or self.control_type
        if self.config.get("unit"):
            entry["unit"] = self.config["unit"]
        if self.config.get("value_schema"):
            entry["value_schema"] = self.config["value_schema"]
        if meta:
            entry["meta"] = meta
        if self.config.get("display_order") is not None:
            entry["display_order"] = self.config["display_order"]
        return entry

    #: '켜짐'으로 해석하는 desired_state 표현들.
    #: servo는 부록F 3-1절 규약상 "move"를 씁니다.
    ON_STATES = (
        "on", "move", "start", "open", "run", "active", "detected", "true", "1", "high",
    )

    @classmethod
    def is_on(cls, state: Optional[str]) -> bool:
        """백엔드가 내려주는 여러 표현을 '켜기/끄기'로 해석합니다."""
        return str(state or "").strip().lower() in cls.ON_STATES

    @classmethod
    def reflected(cls, state: Optional[str]) -> str:
        """
        반영에 성공했을 때 보고할 상태 문자열.

        백엔드가 내려준 표현을 **그대로** 되돌려 줍니다. servo의 "move"를 "on"으로
        바꿔 보고하면 desired와 current가 영원히 달라 보여서, 대시보드가 계속
        '반영 대기'로 표시됩니다 (부록A 상태 계약).
        """
        text = str(state or "").strip().lower()
        return text if cls.is_on(text) else "off"

    def number_from(self, value: Any, key: str, default: float, *aliases: str) -> float:
        """
        desired_value에서 숫자 하나를 꺼냅니다.

        - {"angle": 90} → number_from(v, "angle", 0) == 90
        - 90            → 90  (값 하나만 보낸 경우)
        - 별칭을 주면 순서대로 찾습니다: number_from(v, "duty", 100, "level")
        """
        raw: Any = None
        if isinstance(value, dict):
            for candidate in (key, *aliases, "value"):
                if candidate in value:
                    raw = value[candidate]
                    break
        elif value is not None:
            raw = value
        if raw is None:
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            logger.warning(
                f"[{self.slot_id}] '{key}' 값이 숫자가 아니라 무시합니다: {raw!r}"
            )
            return default


class ActuatorDriver(SlotDriver):
    role = "actuator"


class SensorDriver(SlotDriver):
    role = "sensor"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        #: 센서를 몇 초마다 읽을지 (온습도처럼 느린 부품은 slot_map에서 늘려 주세요)
        self.interval = float(config.get("interval", 1.0))
        self._last_read_at = 0.0

    def due(self, now: float) -> bool:
        """이번 회차에 이 센서를 읽을 차례인지."""
        return (now - self._last_read_at) >= self.interval

    def mark_read(self, now: float) -> None:
        self._last_read_at = now
