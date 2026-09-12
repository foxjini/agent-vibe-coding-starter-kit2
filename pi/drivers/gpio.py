"""
GPIO 접근 계층 (pi/drivers/gpio.py) — 키트 제공, 수정하지 마세요.
=============================================================================
라즈베리파이에서는 gpiozero를 쓰고, **GPIO가 없는 PC에서는 흉내내기 부품**으로
자동 대체합니다. 그래서 학생들은 윈도우 노트북에서도 데몬을 그대로 실행해 볼 수 있습니다.

왜 드라이버마다 mock 파일을 따로 두지 않았나요?
  드라이버 로직(각도 제한, 볼륨→듀티비 환산 등)은 실기기와 흉내내기가 똑같아야 합니다.
  파일을 둘로 나누면 한쪽만 고쳐져서 "PC에서는 되는데 파이에서는 안 되는" 일이 생깁니다.
  그래서 **부품을 흉내내는 계층만** 여기서 바꾸고, 드라이버는 한 벌만 유지합니다.
"""
import logging
import math
import os
import random
import time
from typing import Any, Optional

logger = logging.getLogger("pi.drivers.gpio")

# 라즈베리파이 5(RP1 칩셋)는 lgpio 핀 팩토리가 필요합니다.
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

_gpiozero: Any = None
_probe_done = False
_probe_error: Optional[str] = None


def gpio_available() -> bool:
    """이 컴퓨터에서 진짜 GPIO를 쓸 수 있는지 한 번만 확인합니다."""
    global _gpiozero, _probe_done, _probe_error
    if _probe_done:
        return _gpiozero is not None

    _probe_done = True
    mode = os.getenv("DEVICE_MODE", "auto").strip().lower()
    if mode == "mock":
        _probe_error = "DEVICE_MODE=mock 설정"
        return False

    try:
        import gpiozero  # noqa: F401
        from gpiozero import Device

        # import만으로는 부족합니다 — 핀 팩토리가 실제로 열리는지 확인해야
        # PC에서 gpiozero만 설치된 경우를 걸러낼 수 있습니다.
        Device.ensure_pin_factory()
        _gpiozero = gpiozero
        return True
    except Exception as exc:
        _probe_error = f"{type(exc).__name__}: {exc}"
        if mode == "hardware":
            logger.error(
                "DEVICE_MODE=hardware인데 GPIO를 열지 못했습니다. 배선·권한을 확인하세요. "
                f"원인: {_probe_error}"
            )
        return False


def gpio_unavailable_reason() -> str:
    gpio_available()
    return _probe_error or ""


def _gz():
    if not gpio_available():
        raise RuntimeError("GPIO를 사용할 수 없습니다.")
    return _gpiozero


# ==============================================================================
# 흉내내기 부품 (GPIO가 없을 때 자동으로 대신 쓰입니다)
# ==============================================================================

class _SimDevice:
    """gpiozero 부품 중 드라이버가 실제로 쓰는 부분만 흉내냅니다."""

    def __init__(self, pin: Any = None, **kwargs: Any) -> None:
        self.pin = pin
        self.value = 0.0
        self.frequency = kwargs.get("frequency", 0)
        self.closed = False

    def on(self) -> None:
        self.value = 1.0

    def off(self) -> None:
        self.value = 0.0

    def beep(self, on_time: float = 0.25, off_time: float = 0.15, **kwargs: Any) -> None:
        self.value = 1.0

    def close(self) -> None:
        self.closed = True


class _SimButton(_SimDevice):
    """PC에서는 눌리지 않은 상태로 둡니다 (테스트에서 직접 바꿀 수 있습니다)."""

    def __init__(self, pin: Any = None, **kwargs: Any) -> None:
        super().__init__(pin, **kwargs)
        self.is_pressed = False
        self.when_pressed = None
        self.when_released = None

    def press(self) -> None:
        """테스트·시연용: 버튼을 눌린 것으로 만듭니다."""
        self.is_pressed = True
        if callable(self.when_pressed):
            self.when_pressed()


class _SimAnalog(_SimDevice):
    """조도·압력처럼 연속으로 변하는 값을 그럴듯한 파형으로 흉내냅니다."""

    def __init__(self, pin: Any = None, **kwargs: Any) -> None:
        super().__init__(pin, **kwargs)
        self._born = time.time()
        self._phase = random.random() * math.tau

    @property  # type: ignore[override]
    def value(self) -> float:
        elapsed = time.time() - self._born
        return round(0.5 + 0.35 * math.sin(elapsed / 6.0 + self._phase), 4)

    @value.setter
    def value(self, _new: float) -> None:
        pass  # 입력 부품이라 값을 쓰지 않습니다


def make_device(kind: str, *args: Any, **kwargs: Any):
    """
    gpiozero 부품을 만듭니다. GPIO가 없으면 흉내내기 부품을 돌려줍니다.

    돌려주는 값: (부품, 흉내내기인지 여부)
    """
    if gpio_available():
        try:
            return getattr(_gz(), kind)(*args, **kwargs), False
        except Exception as exc:
            # 핀 충돌·배선 문제는 프로그램을 죽이지 않고 흉내내기로 이어 갑니다.
            logger.warning(
                f"GPIO 부품 {kind}{args}를 만들지 못해 흉내내기로 대체합니다: {exc}"
            )

    if kind == "Button":
        return _SimButton(*args, **kwargs), True
    if kind in ("MCP3008", "MCP3208", "AnalogInputDevice"):
        return _SimAnalog(*args, **kwargs), True
    return _SimDevice(*args, **kwargs), True
