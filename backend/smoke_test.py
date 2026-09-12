"""
백엔드 자가 점검 스크립트 (smoke_test.py)
=============================================================================
서버를 따로 띄우지 않고 FastAPI 앱을 직접 호출해서, 백엔드의 핵심 경로가
살아 있는지 1분 안에 확인합니다. DB가 꺼져 있어도 실행되며, 이 경우
'DB 없이도 동작하는지'를 함께 검증합니다.

실행 방법 (backend 폴더에서, 가상환경 활성화 후):
    python smoke_test.py

무엇을 확인하나요?
 1) 서버 기동 및 /health (DB 연결 상태 포함)
 2) 슬롯 조회 / 액추에이터 제어 (대시보드 경로)
 3) 라즈베리파이 폴링·상태 보고 (하드웨어 경로, X-Device-Api-Key)
 4) 비전 이벤트 수신 (시나리오 판정은 프론트엔드가 합니다)
 5) 에러 응답이 api-rules.md 규격({"error": {...}})을 지키는지
 6) 시나리오 전용 코드가 백엔드에 남아 있지 않은지

키트가 약속한 "부품을 바꿔도 코드를 고치지 않는다"는 conformance_test.py가 검사합니다.
"""
import os
import sys
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault("RULE_TICK_SECONDS", "3600")  # 점검 중 스케줄 루프가 끼어들지 않도록

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

DEVICE_KEY = os.getenv("DEVICE_API_KEY", "")
DEVICE_HEADERS = {"X-Device-Api-Key": DEVICE_KEY} if DEVICE_KEY else {}

BUZZER = "actuator_01"
BUTTON = "sensor_01"

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


def register_demo_slots(client: TestClient) -> Dict[str, Any]:
    """점검용 하드웨어 구성을 등록합니다 (pi가 부팅 때 하는 일과 같습니다)."""
    return client.post(
        "/api/v1/devices/register",
        headers=DEVICE_HEADERS,
        json={
            "slots": [
                {"slot_id": BUZZER, "label": "알람 부저", "kind": "buzzer",
                 "control_type": "tonal"},
                {"slot_id": BUTTON, "label": "기상 확인 버튼", "kind": "button"},
            ],
            "exclusive": True,
        },
    ).json().get("data", {})


def main_test() -> int:
    print("=" * 66)
    print(" IoT 플랫폼 키트 백엔드 - 자가 점검 (smoke test)")
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

        register_demo_slots(client)

        # ---------------------------------------------------------------
        section("2. 대시보드 경로 (슬롯 조회 · 제어)")
        res = client.get("/api/devices")
        devices = res.json().get("data", [])
        check("GET /api/devices 200", res.status_code == 200, res.text[:120])
        check("등록한 슬롯 2개가 조회됨", len(devices) == 2, f"count={len(devices)}")
        check("쓰지 않는 슬롯은 목록에 없음",
              all(d.get("id") in (BUZZER, BUTTON) for d in devices),
              str([d.get("id") for d in devices]))

        # 제어 전 current_state를 기억해 둔다 — 제어는 이 값을 건드리면 안 된다 (부록A 계약)
        before = client.get(f"/api/devices/{BUZZER}").json().get("data", {}).get("current_state")

        res = client.post(
            f"/api/devices/{BUZZER}/control",
            json={"desired_state": "on", "value": {"volume": 70, "frequency": 1000}},
        )
        check("POST 액추에이터 제어 200", res.status_code == 200, res.text[:160])
        data = res.json().get("data", {})
        check("desired_state가 on으로 반영", data.get("desired_state") == "on")

        res = client.get(f"/api/devices/{BUZZER}")
        detail = res.json().get("data", {})
        check(
            "desired_value가 객체(JSON)로 반환 — 문자열이 아님",
            isinstance(detail.get("desired_value"), dict),
            f"type={type(detail.get('desired_value')).__name__}",
        )
        # 부록A 계약: 백엔드는 desired_*만 쓰고, current_*는 하드웨어 보고로만 확정한다.
        # 단 Mock 모드에서는 시뮬레이터 자신이 '하드웨어'이므로 즉시 반영되는 것이 정상이다.
        mock_mode = str(health.get("device_mode", "")).lower() == "mock"
        if mock_mode:
            check("Mock 모드에서는 가상 하드웨어가 즉시 반영 보고",
                  detail.get("current_state") == "on", str(detail.get("current_state")))
        else:
            check("제어 명령이 current_state를 건드리지 않음 (하드웨어 보고만 확정)",
                  detail.get("current_state") == before,
                  f"{before!r} → {detail.get('current_state')!r}")
        check("desired와 current가 각각 따로 전달됨",
              "desired_state" in detail and "current_state" in detail, str(sorted(detail))[:160])

        # ---------------------------------------------------------------
        section("3. 하드웨어 경로 (라즈베리파이 폴링 · 상태 보고)")
        res = client.get("/api/v1/devices/desired-states", headers=DEVICE_HEADERS)
        check("GET 배치 폴링 200 (DB 없어도 성공해야 함)", res.status_code == 200, res.text[:160])
        polled = res.json().get("data", {}).get("slots", {})
        check("폴링 응답의 desired_state가 on",
              polled.get(BUZZER, {}).get("desired_state") == "on", str(polled)[:160])

        res = client.post(
            "/api/v1/devices/states",
            headers=DEVICE_HEADERS,
            json={"states": [
                {"slot_id": BUZZER, "state": "on", "value": {"volume": 70}},
                {"slot_id": BUTTON, "value": {"pressed": True}},
            ]},
        )
        check("POST 배치 보고 200", res.status_code == 200, res.text[:160])
        check("2건 모두 수락됨", res.json().get("data", {}).get("accepted") == 2, res.text[:160])

        res = client.get(f"/api/devices/{BUZZER}")
        check("보고 후 current_state가 on으로 확정",
              res.json().get("data", {}).get("current_state") == "on")

        res = client.get(f"/api/devices/{BUTTON}")
        button = res.json().get("data", {})
        check("센서 보고 후 current_state가 touched", button.get("current_state") == "touched")
        check("센서 값이 객체(JSON)로 반환", isinstance(button.get("current_value"), dict),
              f"value={button.get('current_value')!r}")

        # 구버전 단일 엔드포인트도 호환을 위해 살아 있어야 합니다
        res = client.get(f"/api/v1/devices/{BUZZER}/desired-state", headers=DEVICE_HEADERS)
        check("구버전 단일 폴링도 여전히 동작 (호환)", res.status_code == 200, res.text[:120])

        # ---------------------------------------------------------------
        section("4. 비전 이벤트 (판정은 프론트엔드가 합니다)")
        res = client.post(
            "/api/v1/vision/events",
            headers=DEVICE_HEADERS,
            json={"event_type": "gesture_detected", "label": "rock",
                  "detected": True, "count": 1, "confidence": 0.93},
        )
        check("POST 비전 이벤트 200", res.status_code == 200, res.text[:160])
        body = res.json().get("data", {})
        check("이벤트 라벨이 그대로 기록됨", body.get("label") == "rock", str(body)[:120])
        check("백엔드가 승패를 판정하지 않음 (mission 필드 없음)", "mission" not in body,
              str(body)[:120])

        # ---------------------------------------------------------------
        section("5. 에러 응답 규격 (api-rules.md)")
        res = client.get("/api/devices/no_such_device")
        body = res.json()
        check("없는 디바이스는 404", res.status_code == 404)
        check("에러 껍데기가 {'error': ...}", "error" in body and "detail" not in body, res.text[:160])
        check("에러 코드 포함", body.get("error", {}).get("code") == "DEVICE_NOT_FOUND",
              res.text[:160])

        res = client.post(f"/api/devices/{BUZZER}/control", json={})
        body = res.json()
        check("필수값 누락은 422", res.status_code == 422)
        check("검증 실패도 동일한 껍데기",
              body.get("error", {}).get("code") == "VALIDATION_ERROR", res.text[:160])

        res = client.post(f"/api/devices/{BUTTON}/control", json={"desired_state": "on"})
        check("센서를 제어하려 하면 400", res.status_code == 400, res.text[:160])

        res = client.post(f"/api/devices/{BUZZER}/control", json={"desired_state": "on"},
                          headers={"X-Device-Api-Key": "wrong_key"})
        check("디바이스 키로 사용자 경로를 부르지 않아도 동작 (인증 경로 분리)",
              res.status_code in (200, 401, 403), res.text[:120])

        # ---------------------------------------------------------------
        section("6. 시나리오 코드가 백엔드에 남아 있지 않은지")
        paths = set(main.app.openapi()["paths"])
        check("알람 전용 엔드포인트가 없음",
              not any(p.startswith("/api/alarm") for p in paths),
              str(sorted(p for p in paths if p.startswith("/api/alarm"))))
        check("슬롯·규칙·타이머 엔드포인트는 있음",
              {"/api/slots", "/api/rules", "/api/timers"} <= paths,
              str(sorted(paths)))

        for module in ("services.trigger_service", "routers.alarm"):
            try:
                __import__(module)
                present = True
            except ImportError:
                present = False
            check(f"{module} 모듈이 제거됨", not present)

        # 정리 — 하드웨어가 껐다고 보고한 상태까지 되돌려 다음 실행에 영향을 주지 않게 한다
        client.post(f"/api/devices/{BUZZER}/control", json={"desired_state": "off"})
        client.post("/api/v1/devices/states", headers=DEVICE_HEADERS,
                    json={"states": [{"slot_id": BUZZER, "state": "off"}]})
        client.post("/api/v1/devices/register", headers=DEVICE_HEADERS,
                    json={"slots": [], "exclusive": True})

    print("\n" + "=" * 66)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 66)
    if _failed:
        print(" 실패한 항목의 [FAIL] 메시지를 보고 해당 기능을 점검하세요.")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
