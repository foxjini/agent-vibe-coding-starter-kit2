"""현금 배출구 덮개(MG996R 서보 1개) — 출금하면 덮개가 열렸다 닫히고, 잘못된 금액이면 움직이지 않는가.

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
OPEN_DUTY = (0.0005 + 0.0025) / 2 / 0.02  # 90도 = 1.5ms / 20ms (펄스 500~2500µs 기준)
CLOSED_DUTY = 0.0005 / 0.02  # 0도 = 0.5ms / 20ms


@pytest.fixture
def pins(monkeypatch: pytest.MonkeyPatch):
    """가짜 핀 위에서 HardwareDeviceProvider를 만든다 (기다리는 시간은 0으로)."""
    monkeypatch.setenv("SERVO_PIN", str(PIN))
    for key in ("BUZZER_PIN", "SERVO_HOLD", "SERVO_SETTLE_SECONDS", "SERVO_MIN_PULSE_US", "SERVO_MAX_PULSE_US"):
        monkeypatch.delenv(key, raising=False)
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


def _now(factory) -> float:
    """서보 핀에 지금 나가고 있는 펄스 (0이면 펄스를 끊은 것)."""
    return factory.pin(PIN).state


def test_defaults_suit_mg996r(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("SERVO_HOLD", "SERVO_SETTLE_SECONDS", "SERVO_MIN_PULSE_US", "SERVO_MAX_PULSE_US"):
        monkeypatch.delenv(key, raising=False)
    cfg = hardware_provider.servo_settings_from_env()
    assert cfg["hold"] is True, "MG996R은 펄스를 끊으면 각도를 못 버틴다 — 기본은 잡고 있기"
    assert cfg["settle"] >= 1.0, "0.4초로는 덮개를 단 MG996R이 원위치까지 못 온다"
    assert (cfg["min_pulse"], cfg["max_pulse"]) == (0.0005, 0.0025)


@pytest.mark.parametrize("amount", WITHDRAW_AMOUNTS)
def test_cover_opens_then_returns_and_keeps_holding(pins, amount: int) -> None:
    """기본(SERVO_HOLD=true): 열었다가 0도로 돌아온 뒤에도 0도 펄스를 계속 보낸다."""
    provider = hardware_provider.HardwareDeviceProvider()
    pins.pin(PIN).clear_states()
    asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=amount))

    assert _sent(pins, OPEN_DUTY), f"{amount:,}원인데 덮개가 열리지 않음"
    assert abs(_now(pins) - CLOSED_DUTY) < 0.005, "원위치(0도)를 잡고 있어야 덮개가 밀리지 않는다"
    assert provider.dispense_count == 1


def test_rest_mode_cuts_pulse_only_after_reaching_closed(pins, monkeypatch: pytest.MonkeyPatch) -> None:
    """SERVO_HOLD=false: 0도 명령 → 도착 대기 시간을 다 기다린 뒤에야 펄스를 끊는다."""
    monkeypatch.setenv("SERVO_HOLD", "false")
    monkeypatch.setenv("SERVO_SETTLE_SECONDS", "1.5")
    monkeypatch.setattr(hardware_provider.time, "sleep", lambda s: None)
    provider = hardware_provider.HardwareDeviceProvider()
    pins.pin(PIN).clear_states()

    waits: list[tuple[float, float]] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append((seconds, _now(pins)))  # 기다리기 시작할 때 무슨 펄스가 나가고 있었나

    monkeypatch.setattr(hardware_provider.asyncio, "sleep", fake_sleep)
    asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=50_000))

    (open_wait, open_duty), (close_wait, close_duty) = waits
    assert abs(open_duty - OPEN_DUTY) < 0.005 and open_wait == pytest.approx(1.5)
    # 예전 버그: 0도 명령 뒤 0.4초만 기다리고 끊어서, 닫히다 만 자리에서 멈췄다
    assert abs(close_duty - CLOSED_DUTY) < 0.005 and close_wait == pytest.approx(1.5)
    assert _now(pins) == 0


def test_unknown_amount_does_not_move_the_servo(pins) -> None:
    provider = hardware_provider.HardwareDeviceProvider()
    pins.pin(PIN).clear_states()
    with pytest.raises(ValueError, match="출금할 수 없는 금액"):
        asyncio.run(provider.set_actuator_state("cash_dispenser_1", "DISPENSING", value=70_000))
    assert not _sent(pins, OPEN_DUTY)
    assert provider.dispense_count == 0


def test_startup_closes_cover_and_holds(pins) -> None:
    """켤 때 덮개를 닫힌 자세로 맞추고, 기본값이면 그 자세를 잡고 있는다."""
    provider = hardware_provider.HardwareDeviceProvider()  # 변수에 두지 않으면 바로 치워져 핀이 닫힌다
    assert abs(_now(pins) - CLOSED_DUTY) < 0.005
    assert provider.dispense_count == 0



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
