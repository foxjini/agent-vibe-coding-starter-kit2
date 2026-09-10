"""
백엔드 자가 점검 스크립트 (smoke_test.py)
=============================================================================
서버를 따로 띄우지 않고 FastAPI 앱을 직접 호출해서, 시스템의 핵심 경로가
살아 있는지 1분 안에 확인합니다. DB가 꺼져 있어도 실행되며, 이 경우
'DB 없이도 동작하는지'를 함께 검증합니다.

실행 방법 (backend 폴더에서, 가상환경 활성화 후):
    python smoke_test.py

무엇을 확인하나요?
 1) 서버 기동 및 /health (DB 연결 상태 포함)
 2) 디바이스 목록 조회 / 액추에이터 제어 (대시보드 경로)
 3) 라즈베리파이 폴링·상태 보고 (하드웨어 경로, X-Device-Api-Key)
 4) 알람 발동 → 기상 미션 개시 → 가위바위보 라운드 판정 → 미션 성공
 5) 에러 응답이 api-rules.md 규격({"error": {...}})을 지키는지
"""
import os
import sys
import time
from typing import Any, Dict, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# 미션 판정을 빠르게 확인하기 위해 유예/디바운스를 줄인다 (실제 운영값은 .env로 관리)
os.environ.setdefault("MISSION_ROUND_GRACE_SECONDS", "0")
os.environ.setdefault("MISSION_EVENT_DEBOUNCE_SECONDS", "0")
os.environ.setdefault("WAKEUP_POPUP_DELAY_SECONDS", "2")
os.environ.setdefault("WAKEUP_CONFIRM_TIMEOUT_SECONDS", "2")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

DEVICE_KEY = os.getenv("DEVICE_API_KEY", "")
DEVICE_HEADERS = {"X-Device-Api-Key": DEVICE_KEY} if DEVICE_KEY else {}

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return condition


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * 66)


def mission_status(client: TestClient) -> Dict[str, Any]:
    res = client.get("/api/alarm/status")
    return res.json().get("data", {}).get("mission", {})


def play_round(client: TestClient, hand: Optional[str] = None) -> Dict[str, Any]:
    """현재 라운드에 손동작을 하나 낸다. hand가 None이면 '이기는 손'을 낸다."""
    status = mission_status(client)
    user_hand = hand or status.get("expected_hand")
    client.post(
        "/api/v1/vision/events",
        headers=DEVICE_HEADERS,
        json={
            "event_type": "gesture_detected",
            "detected": True,
            "count": 1,
            "confidence": 0.95,
            "label": user_hand,
        },
    )
    return mission_status(client)


def main_test() -> int:
    print("=" * 66)
    print(" 스마트 기상 시스템 - 백엔드 자가 점검 (smoke test)")
    print("=" * 66)

    with TestClient(main.app) as client:
        # ---------------------------------------------------------------
        section("1. 서버 기동 및 헬스체크")
        res = client.get("/health")
        check("GET /health 200", res.status_code == 200, res.text[:120])
        health = res.json()
        db_connected = bool(health.get("database", {}).get("connected"))
        print(f"       · DB 연결 상태: {'연결됨' if db_connected else '끊김(폴백 모드)'}")
        print(f"       · 디바이스 모드: {health.get('device_mode')}")
        check("헬스체크에 DB 상태 포함", "database" in health)

        # ---------------------------------------------------------------
        section("2. 대시보드 경로 (디바이스 조회 · 제어)")
        res = client.get("/api/devices")
        devices = res.json().get("data", [])
        check("GET /api/devices 200", res.status_code == 200, res.text[:120])
        check("디바이스 3종이 조회됨", len(devices) >= 3, f"count={len(devices)}")

        res = client.post(
            "/api/devices/buzzer_1/control",
            json={"desired_state": "ringing", "value": {"volume": 70, "frequency": 1000}},
        )
        check("POST 부저 제어 200", res.status_code == 200, res.text[:160])
        data = res.json().get("data", {})
        check("desired_state가 ringing으로 반영", data.get("desired_state") == "ringing")

        res = client.get("/api/devices/buzzer_1")
        detail = res.json().get("data", {})
        check(
            "desired_value가 객체(JSON)로 반환 — 문자열이 아님",
            isinstance(detail.get("desired_value"), dict),
            f"type={type(detail.get('desired_value')).__name__}",
        )

        # ---------------------------------------------------------------
        section("3. 하드웨어 경로 (라즈베리파이 폴링 · 상태 보고)")
        res = client.get("/api/v1/devices/buzzer_1/desired-state", headers=DEVICE_HEADERS)
        check("GET desired-state 200 (DB 없어도 성공해야 함)", res.status_code == 200, res.text[:160])
        check(
            "폴링 응답의 desired_state가 ringing",
            res.json().get("data", {}).get("desired_state") == "ringing",
        )

        res = client.post(
            "/api/v1/devices/buzzer_1/state",
            headers=DEVICE_HEADERS,
            json={"state": "ringing", "value": {"volume": 70}},
        )
        check("POST 상태 보고 200", res.status_code == 200, res.text[:160])
        res = client.get("/api/devices/buzzer_1")
        check(
            "보고 후 current_state가 ringing으로 확정",
            res.json().get("data", {}).get("current_state") == "ringing",
        )

        res = client.post(
            "/api/v1/devices/touch_pad_1/state",
            headers=DEVICE_HEADERS,
            json={"value": {"pressed": True, "touch_x": 100, "touch_y": 200, "gesture": "tap"}},
        )
        check("POST 터치 센서 보고 200", res.status_code == 200, res.text[:160])
        res = client.get("/api/devices/touch_pad_1")
        touch = res.json().get("data", {})
        check("터치 보고 후 current_state가 touched", touch.get("current_state") == "touched")
        check(
            "터치 값이 객체(JSON)로 반환",
            isinstance(touch.get("current_value"), dict),
            f"value={touch.get('current_value')!r}",
        )

        # ---------------------------------------------------------------
        section("4. 알람 → 기상 미션 (가위바위보) → 2차 수면 방지")
        client.post("/api/alarm/stop")
        res = client.post("/api/alarm/trigger")
        check("POST /api/alarm/trigger 200", res.status_code == 200, res.text[:160])

        status = mission_status(client)
        check("미션이 시작됨", status.get("active") is True, str(status))
        check("AI 손패가 제시됨", status.get("ai_hand") in ("rock", "paper", "scissors"), str(status))

        res = client.get("/api/devices/buzzer_1")
        check(
            "알람 발동 시 부저 desired_state=ringing",
            res.json().get("data", {}).get("desired_state") == "ringing",
        )

        # 4-1. 지는 손을 내면 라운드가 재시도되어야 한다
        before = mission_status(client)
        losing = {"rock": "scissors", "paper": "rock", "scissors": "paper"}[before["ai_hand"]]
        after = play_round(client, hand=losing)
        check("오답 시 승수가 오르지 않음", after.get("wins", 0) == before.get("wins", 0))
        check(
            "오답 시 다음 라운드로 재시도",
            after.get("round", 0) == before.get("round", 0) + 1,
            f"{before.get('round')} -> {after.get('round')}",
        )

        # 4-2. 이기는 손을 필요한 횟수만큼 내면 미션 성공
        required = after.get("required_wins", 2)
        for _ in range(required):
            after = play_round(client)
        check(
            f"이기는 손 {required}회로 미션 성공",
            after.get("active") is False,
            str(after),
        )

        res = client.get("/api/devices/buzzer_1")
        check(
            "미션 성공 시 부저 desired_state=off",
            res.json().get("data", {}).get("desired_state") == "off",
        )

        status = client.get("/api/alarm/status").json().get("data", {})
        check("2차 수면 방지 감시가 시작됨", status.get("second_sleep_guard_active") is True)

        res = client.post("/api/alarm/confirm-wakeup")
        check("POST 기상 확인 200", res.status_code == 200, res.text[:160])
        time.sleep(0.2)
        status = client.get("/api/alarm/status").json().get("data", {})
        check("기상 확인 후 감시 종료", status.get("second_sleep_guard_active") is False)

        # ---------------------------------------------------------------
        section("5. 알람 예약 (시간대 처리)")
        res = client.post("/api/alarm/schedule", json={"alarm_time": "07:30"})
        check("POST 알람 예약 200", res.status_code == 200, res.text[:160])
        data = res.json().get("data", {})
        check("예약 시각이 저장됨", data.get("alarm_time") == "07:30", str(data))
        check("시간대가 응답에 포함", bool(data.get("timezone")), str(data))
        check(
            "다음 발동 시각이 계산됨",
            isinstance(data.get("remaining_seconds"), int) and data["remaining_seconds"] > 0,
            str(data.get("remaining_seconds")),
        )
        res = client.post("/api/alarm/schedule", json={"alarm_time": "99:99"})
        check("잘못된 시각은 400", res.status_code == 400, res.text[:160])
        client.delete("/api/alarm/schedule")

        # ---------------------------------------------------------------
        section("6. 에러 응답 규격 (api-rules.md)")
        res = client.get("/api/devices/no_such_device")
        body = res.json()
        check("없는 디바이스는 404", res.status_code == 404)
        check("에러 껍데기가 {'error': ...}", "error" in body and "detail" not in body, res.text[:160])
        check(
            "에러 코드 포함",
            body.get("error", {}).get("code") == "DEVICE_NOT_FOUND",
            res.text[:160],
        )

        res = client.post("/api/devices/buzzer_1/control", json={})
        body = res.json()
        check("필수값 누락은 422", res.status_code == 422)
        check(
            "검증 실패도 동일한 껍데기",
            body.get("error", {}).get("code") == "VALIDATION_ERROR",
            res.text[:160],
        )

        res = client.post("/api/devices/touch_pad_1/control", json={"desired_state": "on"})
        check("센서를 제어하려 하면 400", res.status_code == 400, res.text[:160])

        # 정리
        client.post("/api/alarm/stop")

    print("\n" + "=" * 66)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 66)
    if _failed:
        print(" 실패한 항목의 [FAIL] 메시지를 보고 해당 기능을 점검하세요.")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
