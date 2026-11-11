"""금액별 배출구 — 5만·10만·30만·50만 원 아울렛 4개, 아울렛마다 SG-90 서보 1개.

ATM 화면의 금액 버튼 4개와 순서가 같다. 출금하면 그 금액의 아울렛 덮개만 열렸다가 닫힌다.
Mock과 실기기가 같은 표를 쓴다 — PC에서 잘못된 금액이 잡히면 파이에서도 잡힌다.
"""
import os

# 금액 → 아울렛 번호(1~4). frontend/app/atm/page.tsx의 AMOUNTS와 같은 순서다.
OUTLET_AMOUNTS: tuple[int, ...] = (50_000, 100_000, 300_000, 500_000)

# 기본 핀: 파이 5에서 하드웨어 PWM이 가능한 GPIO 4개 (물리 핀 32, 33, 12, 35).
# 지금은 gpiozero + lgpio의 소프트웨어 PWM으로 돌리지만, 나중에 하드웨어 PWM으로
# 바꾸더라도 배선을 다시 할 필요가 없다.
DEFAULT_OUTLET_PINS: tuple[int, ...] = (12, 13, 18, 19)


def outlet_number(amount: int | None) -> int:
    """금액에 맞는 아울렛 번호(1~4). 없는 금액이면 어떤 덮개도 열지 않도록 거절한다."""
    if amount not in OUTLET_AMOUNTS:
        allowed = ", ".join(f"{a:,}" for a in OUTLET_AMOUNTS)
        raise ValueError(f"배출구가 없는 금액입니다: {amount} (가능한 금액: {allowed}원)")
    return OUTLET_AMOUNTS.index(amount) + 1


def outlet_pins_from_env() -> tuple[int, ...]:
    """.env의 OUTLET_SERVO_PINS="12,13,18,19"를 읽는다 (5만·10만·30만·50만 원 순서)."""
    raw = os.getenv("OUTLET_SERVO_PINS", "").strip()
    if not raw:
        return DEFAULT_OUTLET_PINS
    try:
        pins = tuple(int(p) for p in raw.replace(" ", "").split(","))
    except ValueError as exc:
        raise ValueError(f"OUTLET_SERVO_PINS는 숫자 4개를 쉼표로 적습니다: {raw!r}") from exc
    if len(pins) != len(OUTLET_AMOUNTS):
        raise ValueError(
            f"OUTLET_SERVO_PINS에는 핀이 {len(OUTLET_AMOUNTS)}개 필요합니다 "
            f"(5만·10만·30만·50만 원 순서): {raw!r}"
        )
    if len(set(pins)) != len(pins):
        raise ValueError(f"OUTLET_SERVO_PINS에 같은 핀이 두 번 있습니다: {raw!r}")
    return pins
