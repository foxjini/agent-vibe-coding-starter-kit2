"""현금 배출구 덮개(SG-90 서보 1개) — 출금하면 덮개가 열렸다 닫히고, 잘못된 금액이면 움직이지 않는가.

라즈베리파이가 없어도 gpiozero의 가짜 핀(MockFactory + MockPWMPin)으로 실기기 Provider
코드를 그대로 돌린다. 핀에 실제로 나간 펄스 기록을 보고 서보가 움직였는지 확인한다.
"""
import asyncio

import pytest

gpiozero = pytest.importorskip("gpiozero")
from gpiozero.pins.mock import MockFactory, MockPWMPin  # noqa: E402

from iot import hardware_provider  # noqa: E402
from iot.mock_provider import MockDeviceProvider  # noqa: E402
from iot.outlets import WITHDRAW_AMOUNTS, servo_pin_from_env  # noqa: E402

PIN = 18
OPEN_DUTY = (0.0005 + 0.0024) / 2 / 0.02  # 90도 ≒ 1.45ms / 20ms
CLOSED_DUTY = 0.0005 / 0.02  # 0도 = 0.5ms / 20ms


@pytest.fixture
def pins(monkeypatch: pytest.MonkeyPatch):
    """가짜 핀 위에서 HardwareDeviceProvider를 만든다 (기다리는 시간은 0으로)."""
    monkeypatch.setenv("SERVO_PIN", str(PIN))
    monkeypatch.delenv("BUZZER_PIN", raising=False)
    monkeypatch.delenv("SERVO_HOLD", raising=False)
    monkeypatch.setattr(hardware_provider, "DISPENSE_HOLD_SECONDS", 0.0)
    monkeypatch.setattr(hardware_provider, "SERVO_SETTLE_SECONDS", 0.0)
    previous = gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    yield gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory.reset()
    gpiozero.Device.pin_factory = previous


def _sent(factory, duty: float) -> bool:
    """서보 핀에 이 각도의 펄스가 한 번이라도 나갔는가."""
    return any(abs(state - duty) < 0.005 for _, state in factory.pin(PIN).states)


@pytest.mark.parametrize("amount", WITHDRAW_AMOUNTS)
def test_cover_opens_then_closes_and_rests(pins, amount: int) -> None:
    provider = hardware_provider.HardwareDeviceProvider()
    pins.pin(PIN).clear_states()
    asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=amount))

    assert _sent(pins, OPEN_DUTY), f"{amount:,}원인데 덮개가 열리지 않음"
    assert _sent(pins, CLOSED_DUTY), "열린 뒤 닫히지 않음"
    # 닫고 나면 펄스를 끊어 쉬게 한다 (SG-90이 떨리지 않게)
    assert pins.pin(PIN).state == 0
    assert provider.dispense_count == 1


def test_unknown_amount_does_not_move_the_servo(pins) -> None:
    provider = hardware_provider.HardwareDeviceProvider()
    pins.pin(PIN).clear_states()
    with pytest.raises(ValueError, match="출금할 수 없는 금액"):
        asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=70_000))
    assert not _sent(pins, OPEN_DUTY)
    assert provider.dispense_count == 0


def test_startup_closes_cover_and_rests(pins) -> None:
    """켤 때 덮개를 닫힌 자세로 맞춘 뒤 펄스를 끊는다."""
    hardware_provider.HardwareDeviceProvider()
    assert _sent(pins, CLOSED_DUTY)
    assert pins.pin(PIN).state == 0


def test_buzzer_on_the_servo_pin_is_refused(pins, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUZZER_PIN", str(PIN))
    with pytest.raises(RuntimeError, match="겹칩니다"):
        hardware_provider.HardwareDeviceProvider()


def test_mock_uses_the_same_amount_table() -> None:
    """PC(Mock)에서도 같은 표로 확인한다 — 잘못된 금액은 PC에서 먼저 잡힌다."""
    provider = MockDeviceProvider()
    asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=300_000))
    with pytest.raises(ValueError):
        asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=None))
    assert provider.dispense_count == 1


def test_bad_pin_setting_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVO_PIN", "12,13")
    with pytest.raises(ValueError, match="GPIO 번호 하나"):
        servo_pin_from_env()
