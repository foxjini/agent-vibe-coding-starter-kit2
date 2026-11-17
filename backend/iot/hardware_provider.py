"""라즈베리파이 5 하드웨어 Provider — gpiozero로 MG996R 서보 1개(현금 배출구 덮개)를 제어한다.

hardware-rules.md:
- gpiozero를 우선 사용한다
- Mock과 동일한 DeviceProvider 인터페이스를 구현한다 (전환은 DEVICE_MODE만 바꾼다)

배출구는 1개다. 출금하면 금액(5만·10만·30만·50만 원, outlets.py)과 상관없이 같은 덮개가
열렸다가 닫힌다. 핀 번호는 .env의 SERVO_PIN으로 분리해 두었다(PRD 5.4).
MG996R은 별도 5V(3A 이상) 전원을 쓰고 파이는 신호만 준다.

파이 5에서는 pigpio를 쓸 수 없다. gpiozero가 lgpio로 소프트웨어 PWM을 내보낸다.
MG996R은 펄스가 끊기면 버티는 힘이 없어지므로 기본값은 '자세를 계속 잡는다'이다(아래 SERVO_HOLD).
"""
import asyncio
import logging
import os
import time
from typing import Any, Optional

from .base import DeviceProvider
from .mock_provider import DISPENSER_DISPENSING, DISPENSER_IDLE
from .outlets import check_amount, servo_pin_from_env

logger = logging.getLogger("hardware_provider")

# 덮개 각도 (조립 후 실측으로 조정한다)
SERVO_CLOSED_ANGLE = 0
SERVO_OPEN_ANGLE = 90
# 덮개를 열어 두는 시간 — 손님이 지폐를 집을 만큼
DISPENSE_HOLD_SECONDS = 1.0

# 아래 값들은 .env로 바꿀 수 있다 (servo_settings_from_env).
#
# MG996R 펄스 폭. 흔히 쓰는 0.5~2.5ms로 0~180도를 쓴다. 제품마다 끝 위치가 조금씩
# 달라서, 0도나 180도에서 "드르륵" 버티는 소리가 나면 그쪽 값을 100~200씩 좁힌다.
DEFAULT_MIN_PULSE_US = 500
DEFAULT_MAX_PULSE_US = 2500

# 각도 명령을 준 뒤 서보가 실제로 그 자리에 갈 때까지 기다리는 시간.
# MG996R은 SG-90보다 무겁고 느리다 — 덮개를 단 채로 90도를 돌면 0.4초로는 모자라서,
# 그 전에 펄스를 끊으면 "닫히다 만 자리"에서 멈췄다(0→90→0에서 원위치로 안 오던 문제).
DEFAULT_SETTLE_SECONDS = 1.0

# 자세를 잡은 뒤에도 PWM 펄스를 계속 보낼 것인가 (기본: 계속 보낸다).
#
# 펄스를 끊으면 MG996R은 버티는 힘이 0이 된다. 덮개 무게나 손으로 미는 힘에
# 각도가 그대로 밀려 "각도 유지가 안 되는" 것처럼 보인다. 그래서 MG996R의 기본값은
# '잡고 있는다'(SERVO_HOLD=true)이다. 대신 전류를 조금 더 먹고, 소프트웨어 PWM의
# 흔들림 때문에 가만히 있을 때 "지지직" 소리가 날 수 있다 — 덮개가 밀리지 않는
# 구조라면 false로 바꿔 쉬게 할 수 있다.
DEFAULT_HOLD = True

# 테스트가 기다리는 시간을 0으로 바꿀 수 있게 모듈 값으로 둔다
SERVO_SETTLE_SECONDS = DEFAULT_SETTLE_SECONDS


def servo_settings_from_env() -> dict[str, Any]:
    """서보 펄스 폭·유지 여부·대기 시간을 .env에서 읽는다 (점검 도구도 같은 값을 쓴다)."""
    hold_raw = os.getenv("SERVO_HOLD", "").strip().lower()
    settle_raw = os.getenv("SERVO_SETTLE_SECONDS", "").strip()
    return {
        "min_pulse": int(os.getenv("SERVO_MIN_PULSE_US", str(DEFAULT_MIN_PULSE_US))) / 1_000_000,
        "max_pulse": int(os.getenv("SERVO_MAX_PULSE_US", str(DEFAULT_MAX_PULSE_US))) / 1_000_000,
        "hold": DEFAULT_HOLD if not hold_raw else hold_raw == "true",
        "settle": float(settle_raw) if settle_raw else SERVO_SETTLE_SECONDS,
    }


class HardwareDeviceProvider(DeviceProvider):
    """gpiozero 기반 실기기 제어. import 실패 시 즉시 원인을 알린다."""

    def __init__(self) -> None:
        try:
            from gpiozero import AngularServo, Buzzer
        except ImportError as exc:  # 예외를 조용히 삼키지 않는다
            raise RuntimeError(
                "gpiozero를 불러오지 못했습니다.\n"
                "  라즈베리파이 5:  sudo apt install -y python3-gpiozero python3-lgpio\n"
                "  venv를 쓴다면 시스템 패키지를 볼 수 있게 만들어야 합니다 —\n"
                "    rm -rf venv && python3 -m venv --system-site-packages venv\n"
                "  (apt로 깔아 놓고 venv가 못 보는 경우가 파이에서 가장 흔합니다)\n"
                "  자세한 진단:  cd pi && python check_hardware.py"
            ) from exc

        pin = servo_pin_from_env()
        buzzer_pin = os.getenv("BUZZER_PIN", "").strip()
        settings = servo_settings_from_env()
        self._hold = settings["hold"]
        self._settle = settings["settle"]
        min_pulse, max_pulse = settings["min_pulse"], settings["max_pulse"]
        if buzzer_pin and int(buzzer_pin) == pin:
            raise RuntimeError(f"BUZZER_PIN={buzzer_pin}이 배출구 서보 핀(SERVO_PIN={pin})과 겹칩니다.")

        # MG996R 1개: 현금 배출구 덮개
        #
        # 여기서 나는 오류는 import 실패보다 종류가 많다 — 핀 팩토리를 못 고르거나
        # (파이 5에 lgpio가 없다), 권한이 없거나(gpio 그룹), 앞서 띄운 데몬이 같은
        # 핀을 아직 잡고 있거나. 트레이스백만 던지면 부스에서 원인을 못 찾으므로
        # 무엇을 확인해야 하는지까지 적어 준다.
        try:
            self._servo = AngularServo(
                pin, min_angle=0, max_angle=180,
                min_pulse_width=min_pulse, max_pulse_width=max_pulse,
            )
            self._buzzer = Buzzer(int(buzzer_pin)) if buzzer_pin else None
            self._servo.angle = SERVO_CLOSED_ANGLE
            time.sleep(self._settle)
            self._rest(self._servo)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"GPIO를 열지 못했습니다 (배출구 서보=GPIO{pin}, buzzer={buzzer_pin or '없음'}).\n"
                f"  원인: {type(exc).__name__}: {exc}\n"
                "  1) 핀 팩토리 — 파이 5는 lgpio가 필요합니다.\n"
                "     .env에 GPIOZERO_PIN_FACTORY=lgpio 를 넣고, python3-lgpio를 설치하세요.\n"
                "  2) 권한 — sudo usermod -aG gpio $USER  (그 뒤 다시 로그인)\n"
                "  3) 핀 중복 — 앞서 띄운 ATM 데몬이 아직 떠 있으면 같은 핀을 열 수 없습니다.\n"
                "  4) 핀 번호 — .env의 SERVO_PIN이 실제 배선과 같은지.\n"
                "  자세한 진단:  cd pi && python check_hardware.py"
            ) from exc
        self._dispenser_state = DISPENSER_IDLE
        self._buzzer_state = "OFF"
        self.dispense_count = 0

        logger.info(
            "하드웨어 Provider 시작 (배출구 서보=GPIO%d, 펄스 %d~%dµs, 대기 시 펄스=%s, 도착 대기 %.1f초)",
            pin, round(min_pulse * 1e6), round(max_pulse * 1e6), "유지" if self._hold else "끊음", self._settle,
        )

    def _rest(self, servo: Any) -> None:
        """자세를 잡은 뒤 펄스를 끊어 서보를 쉬게 한다 (SERVO_HOLD=true면 잡고 있는다)."""
        if self._hold:
            return
        try:
            servo.detach()
        except Exception as exc:  # noqa: BLE001
            # detach가 없는 구현도 있다. 못 쉬게 하는 것뿐이라 배출은 계속된다.
            logger.debug("서보를 쉬게 하지 못했습니다(무시): %s", exc)

    async def _dispense_once(self, amount: Optional[int]) -> None:
        """배출구 덮개를 열었다가 닫는다."""
        check_amount(amount)  # 출금할 수 없는 금액이면 서보를 움직이기 전에 거절한다
        self._servo.angle = SERVO_OPEN_ANGLE
        # 다 열린 뒤부터 '열어 두는 시간'을 센다 — 무거운 덮개는 여는 데도 시간이 걸린다
        await asyncio.sleep(self._settle + DISPENSE_HOLD_SECONDS)
        self._servo.angle = SERVO_CLOSED_ANGLE
        # 원위치까지 실제로 움직일 시간을 준다. 이 시간이 모자란 채 펄스를 끊으면
        # 닫히다 만 자리에서 멈춘다 (SERVO_HOLD=true면 펄스를 끊지 않으므로 끝까지 간다)
        await asyncio.sleep(self._settle)
        self._rest(self._servo)
        self.dispense_count += 1

    async def get_device_status(self, device_id: str) -> Optional[dict[str, Any]]:
        states = {
            "cash_dispenser_1": self._dispenser_state,
            "buzzer_1": self._buzzer_state,
            "qr_scanner_1": "READY",
        }
        if device_id not in states:
            return None
        return {"device_id": device_id, "state": states[device_id]}

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user",
    ) -> dict[str, Any]:
        if device_id == "cash_dispenser_1":
            if desired_state == DISPENSER_DISPENSING:
                await self._dispense_once(value)
            self._dispenser_state = DISPENSER_IDLE
            return {"device_id": device_id, "state": self._dispenser_state}

        if device_id == "buzzer_1":
            if self._buzzer is None:
                logger.debug("BUZZER_PIN이 없어 부저 명령을 넘깁니다 (선택 기능).")
            elif desired_state == "ON":
                self._buzzer.on()
            else:
                self._buzzer.off()
            self._buzzer_state = desired_state
            return {"device_id": device_id, "state": self._buzzer_state}

        raise KeyError(f"제어할 수 없는 디바이스입니다: {device_id}")

    async def read_sensor_value(self, device_id: str) -> dict[str, Any]:
        return {"device_id": device_id, "value": None, "unit": None}

    async def get_all_statuses(self) -> list[dict[str, Any]]:
        return [
            {"device_id": "cash_dispenser_1", "state": self._dispenser_state},
            {"device_id": "buzzer_1", "state": self._buzzer_state},
            {"device_id": "qr_scanner_1", "state": "READY"},
        ]
