import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from auth import is_admin_pin
from db import database as db
from iot.provider_factory import get_device_provider
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.booth")

# 예약 없이 인증 흐름만 확인하고 싶을 때 쓰는 개발용 만능 PIN.
# 이 값이 열려 있으면 예약하지 않은 사람도 부스에 들어올 수 있으므로
# 기본은 꺼 두고, 로컬 개발에서만 .env로 켠다 (전시 환경에서는 절대 켜지 않는다).
TEST_PIN = "1234"


def _test_pin_allowed() -> bool:
    return os.getenv("ALLOW_TEST_PIN", "false").strip().lower() == "true"


class BoothService:
    """
    학교 노래방 부스 자동화 제어 비즈니스 로직 서비스 (PRD F-01 ~ F-04).
    """

    @staticmethod
    async def verify_and_trigger(pin_code: str) -> Dict[str, Any]:
        """
        4자리 키패드 비밀번호 검증 및 도어락/전원/LED/스피커 자동 제어
        - 관리자 비번(.env의 ADMIN_PIN): 도어락 해제 + LED 점등 (노래방 전원 릴레이는 차단 유지)
        - 예약자 OTP 비번: 도어락 해제 + 릴레이 전원 공급 + LED 점등 + 환영 음성
        """
        provider = get_device_provider()
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # 1. 관리자 고정 비밀번호 처리 (.env의 ADMIN_PIN)
        if is_admin_pin(pin_code):
            logger.info("Admin PIN authenticated. Unlocking door and LED only.")
            await provider.set_actuator_state("door_lock_1", "unlocked", operator="admin")
            await provider.set_actuator_state("led_1", "on", {"mode": "admin", "brightness_pct": 100}, operator="admin")
            await provider.set_actuator_state("relay_1", "off", operator="admin")
            await provider.set_actuator_state(
                "speaker_1", "playing",
                {"track": "admin_welcome", "message": "관리자 모드로 인증되었습니다. 점검을 진행하세요."},
                operator="admin"
            )

            event_msg = {
                "type": "booth_auth",
                "mode": "admin",
                "success": True,
                "message": "관리자 인증 성공 — 도어락 해제 및 LED 점등 (기기 전원 제외)",
                "timestamp": now_str
            }
            await ws_manager.broadcast(event_msg)
            return {
                "success": True,
                "mode": "admin",
                "message": "관리자 모드로 인증되었습니다. (노래방 전원 제외, 도어락 및 LED 작동)"
            }

        # 2. 학생 예약 일회성 비밀번호(OTP 4자리) 검증
        reservation = None
        try:
            reservation = db.get_reservation_by_pin(pin_code)
        except Exception as exc:
            logger.warning(f"DB lookup failed for PIN: {exc}")

        # 예약이 없을 때만 개발용 만능 PIN을 인정한다 (기본은 차단)
        if not reservation and not (_test_pin_allowed() and pin_code == TEST_PIN):
            event_msg = {
                "type": "booth_auth",
                "success": False,
                "message": f"비밀번호 [{pin_code}] 불일치 — 인증에 실패하였습니다.",
                "timestamp": now_str
            }
            await ws_manager.broadcast(event_msg)
            return {
                "success": False,
                "mode": "none",
                "message": "등록되지 않았거나 이미 사용한 비밀번호입니다. (PIN은 1회만 사용할 수 있습니다)"
            }

        user_name = reservation.get("student_name", "학생") if reservation else "테스트 학생"
        logger.info(f"Student reservation authenticated: {user_name}. Activating booth.")

        if reservation and reservation.get("id"):
            try:
                db.update_reservation_status(reservation["id"], "active")
            except Exception as exc:
                logger.warning(f"Failed to update reservation status: {exc}")

        # 일반 사용자 정상 인증: 도어락 해제 + 전원 릴레이 공급 + LED 점등 + 환영음
        await provider.set_actuator_state("door_lock_1", "unlocked", operator="user")
        await provider.set_actuator_state("relay_1", "on", operator="user")
        await provider.set_actuator_state("led_1", "on", {"mode": "normal", "brightness_pct": 100}, operator="user")
        await provider.set_actuator_state(
            "speaker_1", "playing",
            {"track": "welcome", "message": f"{user_name}님 환영합니다! 노래방 전원이 켜졌습니다."},
            operator="user"
        )

        event_msg = {
            "type": "booth_auth",
            "mode": "user",
            "success": True,
            "user_name": user_name,
            "message": f"{user_name}님 인증 성공! 부스 전원 공급 및 도어락이 해제되었습니다.",
            "timestamp": now_str
        }
        await ws_manager.broadcast(event_msg)

        return {
            "success": True,
            "mode": "user",
            "user_name": user_name,
            "reservation": reservation,
            "message": f"{user_name}님 인증 성공! 부스 전원과 도어락이 가동됩니다."
        }

    @staticmethod
    async def trigger_entry() -> Dict[str, Any]:
        """
        사람 입장 감지(PIR 센서 또는 비전 감지) 시 트리거
        환영 안내 문구 및 오디오 출력
        """
        provider = get_device_provider()
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # PIR 센서 상태 갱신
        try:
            db.update_current_state("pir_1", "detected", {"detected": True})
            db.log_sensor_reading("pir_1", value=1.0, unit="detection", value_json={"detected": True})
        except Exception as exc:
            logger.warning(f"DB log failed for entry trigger: {exc}")

        # 스피커 환영 메시지 송출
        await provider.set_actuator_state(
            "speaker_1", "playing",
            {"track": "entry_greeting", "message": "부스에 입장하셨습니다. 즐거운 시간 되세요!"},
            operator="device"
        )

        event_msg = {
            "type": "booth_event",
            "event": "entry_detected",
            "message": "부스 사람 입장 감지 — 환영 안내 음성을 송출합니다.",
            "timestamp": now_str
        }
        await ws_manager.broadcast(event_msg)
        return {"recorded": True, "message": "환영 안내가 출력되었습니다."}

    @staticmethod
    async def trigger_10min_warning() -> Dict[str, Any]:
        """
        이용 종료 10분 전 트리거: LED 깜빡임 알림 및 사전 안내
        """
        provider = get_device_provider()
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # LED 깜빡임 모드로 변경
        await provider.set_actuator_state("led_1", "blink", {"mode": "warning_blink"}, operator="system")
        await provider.set_actuator_state(
            "speaker_1", "playing",
            {"track": "warning_10m", "message": "이용 종료 10분 전입니다. 다음 이용자를 위해 정리를 준비해 주세요."},
            operator="system"
        )

        event_msg = {
            "type": "booth_event",
            "event": "10min_warning",
            "message": "이용 종료 10분 전 — LED 조명이 깜빡이며 종료 알림을 표시합니다.",
            "timestamp": now_str
        }
        await ws_manager.broadcast(event_msg)
        return {"recorded": True, "message": "10분 전 알림이 작동되었습니다."}

    @staticmethod
    async def trigger_session_end() -> Dict[str, Any]:
        """
        이용 종료 트리거:
        1. 지정 종료 음악 ('더윈드 - 다시 만나' 하이라이트 0:58~) 재생
        2. 전원 릴레이 차단, 마이크 차단, 도어락 잠금, LED 소등
        """
        provider = get_device_provider()
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # 1. 종료곡 송출
        await provider.set_actuator_state(
            "speaker_1", "playing",
            {
                "track": "더윈드 - 다시 만나 (0:58~)",
                "message": "이용 시간이 종료되었습니다. 퇴실해 주시기 바랍니다."
            },
            operator="system"
        )

        # 2. 전원 및 마이크 차단, 도어락 잠금, 조명 소등
        await provider.set_actuator_state("relay_1", "off", operator="system")
        await provider.set_actuator_state("door_lock_1", "locked", operator="system")
        await provider.set_actuator_state("led_1", "off", operator="system")

        event_msg = {
            "type": "booth_event",
            "event": "session_ended",
            "message": "이용 종료 — 종료 음악('더윈드 - 다시 만나') 재생 후 전원 및 마이크를 차단했습니다.",
            "timestamp": now_str
        }
        await ws_manager.broadcast(event_msg)
        return {"recorded": True, "message": "이용이 종료되어 기기 전원과 마이크가 차단되었습니다."}
