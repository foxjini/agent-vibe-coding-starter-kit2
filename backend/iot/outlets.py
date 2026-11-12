"""현금 배출구 — SG-90 서보 1개가 배출구 덮개 하나를 연다. 출금할 수 있는 금액은 4가지다.

ATM 화면의 금액 버튼 4개(5만·10만·30만·50만 원)와 같은 표다. 어느 금액이든 같은 덮개가
열렸다 닫힌다. Mock과 실기기가 같은 표를 쓴다 — PC에서 잘못된 금액이 잡히면 파이에서도 잡힌다.
"""
import os

# frontend/app/atm/page.tsx의 AMOUNTS와 같다.
WITHDRAW_AMOUNTS: tuple[int, ...] = (50_000, 100_000, 300_000, 500_000)

# 기본 핀: GPIO18(물리 핀 12). 파이 5에서 하드웨어 PWM이 되는 핀이라, 지금은 gpiozero + lgpio의
# 소프트웨어 PWM으로 돌리지만 나중에 하드웨어 PWM으로 바꿔도 배선을 다시 할 필요가 없다.
DEFAULT_SERVO_PIN = 18


def check_amount(amount: int | None) -> int:
    """출금할 수 있는 금액인지 확인한다. 아니면 서보를 움직이기 전에 거절한다."""
    if amount not in WITHDRAW_AMOUNTS:
        allowed = ", ".join(f"{a:,}" for a in WITHDRAW_AMOUNTS)
        raise ValueError(f"출금할 수 없는 금액입니다: {amount} (가능한 금액: {allowed}원)")
    return amount


def servo_pin_from_env() -> int:
    """.env의 SERVO_PIN(배출구 덮개 서보의 GPIO 번호)을 읽는다."""
    raw = os.getenv("SERVO_PIN", "").strip()
    if not raw:
        return DEFAULT_SERVO_PIN
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"SERVO_PIN은 GPIO 번호 하나를 숫자로 적습니다 (예: 18): {raw!r}") from exc
