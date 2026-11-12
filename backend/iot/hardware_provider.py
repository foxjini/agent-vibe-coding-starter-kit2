"""라즈베리파이 5 하드웨어 Provider — gpiozero로 SG-90 서보 1개(현금 배출구 덮개)를 제어한다.

hardware-rules.md:
- gpiozero를 우선 사용한다
- Mock과 동일한 DeviceProvider 인터페이스를 구현한다 (전환은 DEVICE_MODE만 바꾼다)

배출구는 1개다. 출금하면 금액(5만·10만·30만·50만 원, outlets.py)과 상관없이 같은 덮개가
열렸다가 닫힌다. 핀 번호는 .env의 SERVO_PIN으로 분리해 두었다(PRD 5.4).
SG-90은 별도 5V 전원을 쓰고 파이는 신호만 준다.

파이 5에서는 pigpio를 쓸 수 없다. gpiozero가 lgpio로 소프트웨어 PWM을 내보내는데,
펄스를 계속 내면 SG-90이 떨린다("지지직"). 그래서 자세를 잡은 뒤 펄스를 끊는다(아래 SERVO_HOLD).
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
# 각도 명령을 준 뒤 서보가 실제로 그 자리에 갈 때까지 기다리는 시간
SERVO_SETTLE_SECONDS = 0.4

# SG-90 펄스 폭. gpiozero 기본값(1~2ms)으로는 SG-90이 90도 남짓밖에 돌지 않는다.
# 흔히 쓰는 0.5~2.4ms로 0~180도를 쓴다. 끝에서 "드르륵" 소리가 나면 .env에서 좁힌다.
DEFAULT_MIN_PULSE_US = 500
DEFAULT_MAX_PULSE_US = 2400

# 자세를 잡은 뒤 PWM 펄스를 끊을 것인가.
#
# gpiozero는 각도를 준 뒤에도 펄스를 계속 내보낸다. 서보는 그동안 자세를 유지하느라
# 전류를 계속 먹고, 소프트웨어 PWM의 흔들림 때문에 미세하게 떨린다("지지직" 소리).
# 덮개는 잠깐만 움직이면 되는데 몇 시간짜리 전시 내내 그러고 있으면 발열과
# 전압 강하로 이어진다.
#
# 그래서 기본값은 '쉬게 한다'이다. 다만 덮개가 제 무게로 열린다면
# .env에 SERVO_HOLD=true 를 넣어 잡고 있게 할 수 있다 (전류는 더 먹는다).


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
        self._hold = os.getenv("SERVO_HOLD", "false").strip().lower() == "true"
        min_pulse = int(os.getenv("SERVO_MIN_PULSE_US", str(DEFAULT_MIN_PULSE_US))) / 1_000_000
        max_pulse = int(os.getenv("SERVO_MAX_PULSE_US", str(DEFAULT_MAX_PULSE_US))) / 1_000_000
        if buzzer_pin and int(buzzer_pin) == pin:
            raise RuntimeError(f"BUZZER_PIN={buzzer_pin}이 배출구 서보 핀(SERVO_PIN={pin})과 겹칩니다.")

        # SG-90 1개: 현금 배출구 덮개
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
            time.sleep(SERVO_SETTLE_SECONDS)
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
            "하드웨어 Provider 시작 (배출구 서보=GPIO%d, 대기 시 펄스=%s)",
            pin, "유지" if self._hold else "끊음",
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
        await asyncio.sleep(DISPENSE_HOLD_SECONDS)
        self._servo.angle = SERVO_CLOSED_ANGLE
        # 원위치까지 실제로 움직일 시간을 준 뒤에 펄스를 끊는다 —
        # 바로 끊으면 닫히다 만 자리에서 멈춘다
        await asyncio.sleep(SERVO_SETTLE_SECONDS)
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
