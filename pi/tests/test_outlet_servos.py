"""금액별 배출구(SG-90 서보 4개) — 그 금액의 덮개만 열리는가.

라즈베리파이가 없어도 gpiozero의 가짜 핀(MockFactory + MockPWMPin)으로 실기기 Provider
코드를 그대로 돌린다. 핀에 실제로 나간 펄스 기록을 보고 어느 서보가 움직였는지 확인한다.
"""
import asyncio

import pytest

gpiozero = pytest.importorskip("gpiozero")
from gpiozero.pins.mock import MockFactory, MockPWMPin  # noqa: E402

from iot import hardware_provider  # noqa: E402
from iot.mock_provider import MockDeviceProvider  # noqa: E402
from iot.outlets import OUTLET_AMOUNTS, outlet_number, outlet_pins_from_env  # noqa: E402

PINS = (12, 13, 18, 19)


@pytest.fixture
def pins(monkeypatch: pytest.MonkeyPatch):
    """가짜 핀 위에서 HardwareDeviceProvider를 만든다 (기다리는 시간은 0으로)."""
    monkeypatch.setenv("OUTLET_SERVO_PINS", ",".join(map(str, PINS)))
    monkeypatch.delenv("BUZZER_PIN", raising=False)
    monkeypatch.delenv("SERVO_HOLD", raising=False)
    monkeypatch.setattr(hardware_provider, "DISPENSE_HOLD_SECONDS", 0.0)
    monkeypatch.setattr(hardware_provider, "SERVO_SETTLE_SECONDS", 0.0)
    previous = gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    yield gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory.reset()
    gpiozero.Device.pin_factory = previous


def _opened(factory, pin: int) -> bool:
    """이 핀에 '열림' 각도의 펄스가 한 번이라도 나갔는가."""
    # 50Hz(20ms 주기)에서 90도 ≒ (0.5ms + 2.4ms) / 2 = 1.45ms → 듀티 약 0.0725
    open_duty = (0.0005 + 0.0024) / 2 / 0.02
    return any(abs(state - open_duty) < 0.005 for _, state in factory.pin(pin).states)


def _clear(factory) -> None:
    for pin in PINS:
        factory.pin(pin).clear_states()


@pytest.mark.parametrize("amount", OUTLET_AMOUNTS)
def test_only_the_matching_outlet_opens(pins, amount: int) -> None:
    provider = hardware_provider.HardwareDeviceProvider()
    _clear(pins)
    result = asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=amount))

    number = outlet_number(amount)
    assert result["outlet"] == number
    opened = [p for p in PINS if _opened(pins, p)]
    assert opened == [PINS[number - 1]], f"{amount:,}원인데 열린 핀: {opened}"
    # 닫고 나면 펄스를 끊어 쉬게 한다 (SG-90이 떨리지 않게)
    assert all(pins.pin(p).state == 0 for p in PINS)


def test_unknown_amount_moves_no_servo(pins) -> None:
    provider = hardware_provider.HardwareDeviceProvider()
    _clear(pins)
    with pytest.raises(ValueError, match="배출구가 없는 금액"):
        asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=70_000))
    assert not any(_opened(pins, p) for p in PINS)
    assert provider.dispense_count == 0


def test_startup_closes_covers_and_rests(pins) -> None:
    """켤 때 덮개 4개를 닫힌 자세로 맞춘 뒤 펄스를 끊는다."""
    hardware_provider.HardwareDeviceProvider()
    closed_duty = 0.0005 / 0.02
    for p in PINS:
        states = [s for _, s in pins.pin(p).states]
        assert any(abs(s - closed_duty) < 0.005 for s in states), f"GPIO{p}이 닫힌 자세를 받지 못함"
        assert pins.pin(p).state == 0


def test_buzzer_on_an_outlet_pin_is_refused(pins, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUZZER_PIN", "18")
    with pytest.raises(RuntimeError, match="겹칩니다"):
        hardware_provider.HardwareDeviceProvider()


def test_mock_uses_the_same_outlet_table() -> None:
    """PC(Mock)에서도 같은 표로 확인한다 — 잘못된 금액은 PC에서 먼저 잡힌다."""
    provider = MockDeviceProvider()
    result = asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=300_000))
    assert result["outlet"] == 3
    assert provider.outlet_counts == {1: 0, 2: 0, 3: 1, 4: 0}
    with pytest.raises(ValueError):
        asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=None))
    assert provider.dispense_count == 1


@pytest.mark.parametrize(
    "raw, problem",
    [("12,13,18", "4개"), ("12,13,18,18", "두 번"), ("12,13,a,19", "숫자")],
)
def test_bad_pin_setting_is_explained(monkeypatch: pytest.MonkeyPatch, raw: str, problem: str) -> None:
    monkeypatch.setenv("OUTLET_SERVO_PINS", raw)
    with pytest.raises(ValueError, match=problem):
        outlet_pins_from_env()
