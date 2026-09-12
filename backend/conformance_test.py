"""
플랫폼 키트 적합성 검사 (conformance_test.py)
=============================================================================
"센서·액추에이터를 바꿔도 백엔드·DB·vision을 고치지 않아도 된다"는 약속이
실제로 지켜지는지 검사합니다. 서버를 따로 띄우지 않아도 됩니다.

실행 방법 (backend 폴더에서, 가상환경 활성화 후):
    python conformance_test.py

무엇을 확인하나요? (docs/부록F 11장 체크리스트)
 1) 슬롯 20개가 존재하고 role이 고정되어 있는지
 2) 팀 하드웨어 구성을 등록·변경·제거할 때 코드 수정 없이 반영되는지
 3) 배치 폴링·배치 보고가 동작하는지
 4) 비활성 슬롯은 제어·보고가 거부되는지
 5) 숫자 센서 이력이 차트용으로 적재되는지
 6) 자동화 규칙이 코드 없이 액추에이터를 제어하는지
 7) 백엔드·vision 코드에 팀 고유 디바이스 이름이 없는지
"""
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault("RULE_TICK_SECONDS", "3600")  # 검사 중 스케줄 루프가 끼어들지 않도록

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from db.database import ACTUATOR_SLOTS, SENSOR_SLOTS  # noqa: E402

DEVICE_KEY = os.getenv("DEVICE_API_KEY", "")
HEADERS = {"X-Device-Api-Key": DEVICE_KEY} if DEVICE_KEY else {}

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
    print("-" * 68)


def wait_for_ws_message(ws, message_type: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """
    WebSocket에서 원하는 종류의 메시지를 기다립니다.

    메시지가 오지 않아도 검사가 멈추지 않도록 별도 스레드에서 읽고 시간 제한을 둡니다.
    (기대한 메시지가 없으면 None을 돌려주고, 해당 항목만 실패로 기록됩니다.)
    """
    found: Dict[str, Any] = {}

    def drain() -> None:
        try:
            for _ in range(20):
                message = ws.receive_json()
                if message.get("type") == message_type:
                    found.update(message)
                    return
        except Exception:
            pass  # 연결이 닫히면 조용히 끝낸다

    worker = threading.Thread(target=drain, daemon=True)
    worker.start()
    worker.join(timeout=timeout)
    return found or None


def register(client: TestClient, slots: List[Dict[str, Any]], exclusive: bool = True):
    return client.post(
        "/api/v1/devices/register",
        headers=HEADERS,
        json={"slots": slots, "exclusive": exclusive},
    )


def main_test() -> int:
    print("=" * 68)
    print(" IoT 개발 플랫폼 키트 — 적합성 검사")
    print("=" * 68)

    with TestClient(main.app) as client:
        db_on = bool(client.get("/health").json().get("database", {}).get("connected"))
        print(
            " DB 연결: " + ("정상 (전체 검사)" if db_on
                           else "끊김 (DB가 필요한 검사는 '건너뜀'으로 표시됩니다)")
        )

        # ---------------------------------------------------------------
        section("1. 슬롯 레지스트리 (부록F 2장)")
        res = client.get("/api/slots")
        check("GET /api/slots 200", res.status_code == 200, res.text[:120])
        slots = res.json().get("data", [])
        check(
            f"슬롯 {len(SENSOR_SLOTS) + len(ACTUATOR_SLOTS)}개가 존재",
            len(slots) == len(SENSOR_SLOTS) + len(ACTUATOR_SLOTS),
            f"count={len(slots)}",
        )
        ids = {s["slot_id"] for s in slots}
        check("sensor_01 ~ sensor_10 이 모두 있음", set(SENSOR_SLOTS) <= ids)
        check("actuator_01 ~ actuator_10 이 모두 있음", set(ACTUATOR_SLOTS) <= ids)
        roles = {s["slot_id"]: s["role"] for s in slots}
        check(
            "role이 슬롯 이름과 일치 (불변 규칙)",
            all(roles.get(s) == "sensor" for s in SENSOR_SLOTS)
            and all(roles.get(s) == "actuator" for s in ACTUATOR_SLOTS),
        )

        # ---------------------------------------------------------------
        section("2. 팀 하드웨어 구성 등록 (pi/slot_map.py 역할)")
        res = register(client, [
            {"slot_id": "actuator_01", "label": "자동문 서보", "kind": "servo",
             "control_type": "servo", "value_schema": {"min": 0, "max": 180}, "meta": {"pin": 12}},
            {"slot_id": "actuator_02", "label": "조명 릴레이", "kind": "relay", "control_type": "onoff"},
            {"slot_id": "sensor_01", "label": "실내 온도", "kind": "temperature", "unit": "°C"},
        ])
        check("POST /api/v1/devices/register 200", res.status_code == 200, res.text[:160])
        data = res.json().get("data", {})
        check("3개 슬롯이 등록됨", len(data.get("registered", [])) == 3, str(data))
        if not db_on:
            check("DB 미연결이면 persisted=false로 알려 줌", data.get("persisted") is False, str(data))

        res = client.get("/api/devices")
        active = {d["id"] for d in res.json().get("data", [])}
        check("등록한 슬롯이 대시보드 목록에 나타남",
              {"actuator_01", "actuator_02", "sensor_01"} <= active, str(sorted(active)))
        check("등록하지 않은 빈 슬롯은 대시보드에 없음", "actuator_09" not in active)

        # ---------------------------------------------------------------
        section("3. 배치 폴링 · 배치 보고 (부록F 5-2절)")
        res = client.get("/api/v1/devices/desired-states", headers=HEADERS)
        check("GET desired-states 200", res.status_code == 200, res.text[:160])
        polled = res.json().get("data", {}).get("slots", {})
        check("활성 액추에이터 2개만 폴링 대상", set(polled) == {"actuator_01", "actuator_02"},
              str(sorted(polled)))
        check("control_type이 함께 전달됨 (위젯 자동 결정 근거)",
              polled.get("actuator_01", {}).get("control_type") == "servo")

        res = client.post("/api/devices/actuator_01/control",
                          json={"desired_state": "move", "value": {"angle": 90}})
        check("서보 슬롯 제어 200", res.status_code == 200, res.text[:200])

        res = client.post("/api/v1/devices/states", headers=HEADERS, json={"states": [
            {"slot_id": "actuator_01", "state": "move", "value": {"angle": 90}},
            {"slot_id": "sensor_01", "value": {"value": 28.6}, "unit": "°C"},
        ]})
        check("POST states 배치 보고 200", res.status_code == 200, res.text[:160])
        body = res.json().get("data", {})
        check("2건 모두 수락", body.get("accepted") == 2 and not body.get("rejected"), str(body))

        res = client.get("/api/devices/actuator_01")
        dev = res.json().get("data", {})
        check("보고 후 current_state가 확정됨", dev.get("current_state") == "move", str(dev.get("current_state")))
        check("desired/current가 분리되어 보관됨",
              dev.get("desired_state") == "move" and isinstance(dev.get("desired_value"), dict))

        # ---------------------------------------------------------------
        section("4. 부품 제거 (pi/slot_map.py에서 한 줄 삭제)")
        res = register(client, [
            {"slot_id": "actuator_01", "label": "자동문 서보", "kind": "servo", "control_type": "servo"},
            {"slot_id": "sensor_01", "label": "실내 온도", "kind": "temperature", "unit": "°C"},
        ])
        check("제거 반영 200", res.status_code == 200, res.text[:160])
        check("빠진 슬롯이 자동 비활성화됨",
              "actuator_02" in res.json().get("data", {}).get("disabled", []),
              str(res.json().get("data")))

        polled = client.get("/api/v1/devices/desired-states", headers=HEADERS).json()["data"]["slots"]
        check("폴링 대상에서 제외됨", "actuator_02" not in polled, str(sorted(polled)))

        res = client.post("/api/devices/actuator_02/control", json={"desired_state": "on"})
        check("비활성 슬롯 제어는 400으로 거부", res.status_code == 400, res.text[:160])

        res = client.post("/api/v1/devices/states", headers=HEADERS,
                          json={"states": [{"slot_id": "actuator_02", "state": "on"}]})
        rejected = res.json().get("data", {}).get("rejected", [])
        check("비활성 슬롯 보고는 거부되지만 배치 전체는 실패하지 않음",
              res.status_code == 200 and rejected and rejected[0]["reason"] == "SLOT_DISABLED",
              res.text[:160])

        res = client.post("/api/v1/devices/states", headers=HEADERS,
                          json={"states": [{"slot_id": "sensor_99", "value": {"value": 1}}]})
        rejected = res.json().get("data", {}).get("rejected", [])
        check("존재하지 않는 슬롯은 UNKNOWN_SLOT으로 거부",
              rejected and rejected[0]["reason"] == "UNKNOWN_SLOT", res.text[:160])

        # ---------------------------------------------------------------
        section("4-2. 부품 교체 (같은 슬롯에 다른 부품을 꽂음)")
        # 서보를 떼고 부저를 꽂았는데 서보의 value_schema(0~180도)가 남아 있으면
        # 대시보드에 주파수 슬라이더가 0~180Hz로 그려집니다.
        register(client, [
            {"slot_id": "actuator_01", "label": "서보 시절", "kind": "servo",
             "control_type": "servo", "value_schema": {"min": 0, "max": 180}, "unit": "도"},
        ])
        register(client, [
            {"slot_id": "actuator_01", "label": "부저로 교체", "kind": "buzzer",
             "control_type": "tonal"},
        ])
        res = client.get("/api/slots")
        swapped = next(
            (s for s in res.json().get("data", []) if s.get("slot_id") == "actuator_01"), {}
        )
        check("교체한 부품의 종류·라벨이 반영됨",
              swapped.get("kind") == "buzzer" and swapped.get("label") == "부저로 교체",
              str(swapped)[:160])
        check("이전 부품의 value_schema가 남지 않음", swapped.get("value_schema") is None,
              str(swapped.get("value_schema")))
        check("이전 부품의 unit이 남지 않음", swapped.get("unit") is None, str(swapped.get("unit")))
        check("이전 부품의 control_type이 새 값으로 바뀜",
              swapped.get("control_type") == "tonal", str(swapped.get("control_type")))

        # 뒤 검사들이 쓰는 구성(서보 + 온도센서)으로 되돌린다
        register(client, [
            {"slot_id": "actuator_01", "label": "자동문 서보", "kind": "servo",
             "control_type": "servo", "value_schema": {"min": 0, "max": 180}, "meta": {"pin": 12}},
            {"slot_id": "sensor_01", "label": "실내 온도", "kind": "temperature", "unit": "°C"},
        ])

        # ---------------------------------------------------------------
        section("5. 메타데이터 수정 (대시보드 하드웨어 구성 화면)")
        res = client.patch("/api/slots/sensor_02",
                           json={"enabled": True, "label": "출입 감지", "kind": "presence"})
        check("PATCH /api/slots/{slot_id} 200", res.status_code == 200, res.text[:160])
        check("라벨이 반영됨", res.json().get("data", {}).get("label") == "출입 감지")
        res = client.patch("/api/slots/not_a_slot", json={"enabled": True})
        check("슬롯이 아닌 ID는 404", res.status_code == 404, res.text[:120])
        client.patch("/api/slots/sensor_02", json={"enabled": False})

        # ---------------------------------------------------------------
        section("6. 센서 이력 (차트 자동 동작 조건)")
        for temp in (26.1, 27.3, 29.8):
            client.post("/api/v1/devices/states", headers=HEADERS,
                        json={"states": [{"slot_id": "sensor_01", "value": {"value": temp}, "unit": "°C"}]})
        res = client.get("/api/devices/sensor_01/readings?limit=10")
        readings = res.json().get("data", [])
        numeric = [r for r in readings if r.get("value") is not None]
        if db_on:
            check("숫자 센서 이력이 value 컬럼에 적재됨", len(numeric) >= 3, f"rows={len(readings)}")
        else:
            check("DB 미연결 시 이력은 빈 목록 (500이 아님)", readings == [], str(readings)[:80])

        # ---------------------------------------------------------------
        section("7. 자동화 규칙 (코드 없이 제어)")
        rule = {
            "name": "적합성 검사용 규칙",
            "definition": {
                "when": {"type": "sensor_threshold", "slot_id": "sensor_01", "op": ">", "value": 28},
                "then": [{"action": "set_actuator", "slot_id": "actuator_01",
                          "state": "move", "value": {"angle": 180}}],
                "otherwise": [{"action": "set_actuator", "slot_id": "actuator_01",
                               "state": "move", "value": {"angle": 0}}],
            },
        }
        res = client.post("/api/rules", json=rule)
        if db_on:
            check("POST /api/rules 200", res.status_code == 200, res.text[:200])
        else:
            check("DB 미연결 시 규칙 저장은 503으로 분명히 거부", res.status_code == 503, res.text[:200])
        rule_id = res.json().get("data", {}).get("id") if res.status_code == 200 else None

        res = client.post("/api/rules", json={"name": "잘못된 규칙", "definition": {"when": {"type": "nope"}}})
        check("지원하지 않는 트리거는 400", res.status_code == 400, res.text[:160])

        if db_on and rule_id:
            client.post("/api/v1/devices/states", headers=HEADERS,
                        json={"states": [{"slot_id": "sensor_01", "value": {"value": 31.0}}]})
            dev = client.get("/api/devices/actuator_01").json()["data"]
            check("임계값 초과 → 규칙이 액추에이터를 제어", dev.get("desired_value", {}).get("angle") == 180,
                  str(dev.get("desired_value")))
            client.post("/api/v1/devices/states", headers=HEADERS,
                        json={"states": [{"slot_id": "sensor_01", "value": {"value": 20.0}}]})
            dev = client.get("/api/devices/actuator_01").json()["data"]
            check("임계값 이하 → otherwise 분기로 복귀", dev.get("desired_value", {}).get("angle") == 0,
                  str(dev.get("desired_value")))
        else:
            print("       · DB 미연결이라 규칙 발동 검사는 건너뜁니다.")

        if rule_id:
            check("DELETE /api/rules/{id} 200", client.delete(f"/api/rules/{rule_id}").status_code == 200)

        # 트리거 3종·액션 2종이 모두 쓸 수 있는지 (부록F 7장)
        vision_rule = {
            "name": "적합성 검사용 비전 규칙",
            "definition": {
                # actuator_02는 4번 검사에서 '떼어낸' 슬롯이므로 살아 있는 슬롯을 쓴다
                "when": {"type": "vision_label", "label": "person", "min_confidence": 0.5},
                "then": [
                    {"action": "set_actuator", "slot_id": "actuator_01",
                     "state": "move", "value": {"angle": 45}},
                    {"action": "notify", "level": "warn", "message": "사람이 감지되었습니다."},
                ],
            },
        }
        res = client.post("/api/rules", json=vision_rule)
        vision_rule_id = res.json().get("data", {}).get("id") if res.status_code == 200 else None
        sched_rule = {
            "name": "적합성 검사용 스케줄 규칙",
            "definition": {
                "when": {"type": "schedule", "at": "07:30"},
                "then": [{"action": "notify", "message": "기상 시간입니다.", "after_seconds": 1}],
            },
        }
        res_sched = client.post("/api/rules", json=sched_rule)
        res_bad_sched = client.post("/api/rules", json={
            "name": "시각 형식이 틀린 규칙",
            "definition": {"when": {"type": "schedule", "at": "아침"},
                           "then": [{"action": "notify", "message": "x"}]},
        })
        if db_on:
            check("vision_label 트리거 규칙 생성 200", vision_rule_id is not None, res.text[:160])
            check("schedule 트리거 규칙 생성 200", res_sched.status_code == 200, res_sched.text[:160])
            check("schedule의 잘못된 시각 형식은 400", res_bad_sched.status_code == 400,
                  res_bad_sched.text[:160])
        else:
            check("DB 미연결 시 규칙 정의 검증은 그대로 동작 (400)", res_bad_sched.status_code == 400,
                  res_bad_sched.text[:160])

        if db_on and vision_rule_id:
            # 비전 클라이언트가 보내는 것과 같은 경로로 이벤트를 흘려 넣고,
            # 대시보드가 실제로 받는 WebSocket 알림까지 함께 확인한다
            with client.websocket_connect("/ws") as ws:
                client.post("/api/v1/vision/events", headers=HEADERS, json={
                    "event_type": "person_detected", "label": "person",
                    "detected": True, "confidence": 0.91, "count": 1,
                })
                notified = wait_for_ws_message(ws, "notify")
            dev = client.get("/api/devices/actuator_01").json()["data"]
            check("비전 라벨 감지 → 규칙이 액추에이터를 제어",
                  dev.get("desired_value", {}).get("angle") == 45, str(dev.get("desired_value")))
            check("notify 액션이 대시보드로 전달됨",
                  bool(notified) and notified.get("level") == "warn", str(notified))

        for rid in (vision_rule_id, res_sched.json().get("data", {}).get("id")
                    if res_sched.status_code == 200 else None):
            if rid:
                client.delete(f"/api/rules/{rid}")

        # ---------------------------------------------------------------
        section("7-2. 1차 완성본 마이그레이션 (레거시 디바이스 → 슬롯)")
        if db_on:
            import pymysql  # noqa: E402

            from db.database import _get_connection_params, init_db  # noqa: E402

            conn = pymysql.connect(**_get_connection_params(include_db=True))
            try:
                with conn.cursor() as cursor:
                    # 1차 완성본만 올린 팀의 DB 상태를 흉내낸다
                    cursor.execute(
                        "INSERT INTO devices (id, name, kind, role, slot_index, enabled) "
                        "VALUES ('buzzer_1','알람 출력 장치(피에조 부저)','buzzer','actuator',0,TRUE) "
                        "ON DUPLICATE KEY UPDATE enabled = TRUE"
                    )
                    cursor.execute(
                        "UPDATE devices SET enabled=FALSE, label=NULL, kind='unassigned' "
                        "WHERE id='actuator_01'"
                    )
                conn.commit()
            finally:
                conn.close()

            init_db()   # 서버가 켜질 때 하는 일과 같다
            slots = client.get("/api/slots").json().get("data", [])
            migrated = next((s for s in slots if s.get("slot_id") == "actuator_01"), {})
            check("레거시 부저의 이름이 슬롯으로 옮겨짐",
                  migrated.get("label") == "알람 출력 장치(피에조 부저)", str(migrated)[:160])
            check("쓰고 있던 부품이라 슬롯이 켜진 채로 넘어옴", bool(migrated.get("enabled")))

            devices = client.get("/api/devices").json().get("data", [])
            check("레거시 디바이스는 대시보드에서 사라짐",
                  all(d.get("id") != "buzzer_1" for d in devices),
                  str([d.get("id") for d in devices]))
            check("이력을 잃지 않도록 행 자체는 남아 있음",
                  any(s.get("slot_id") == "actuator_01" for s in slots))
        else:
            print("       · DB 미연결이라 마이그레이션 검사는 건너뜁니다.")

        # ---------------------------------------------------------------
        section("7-3. 감지 대상을 코드 없이 바꾸기 (부록F 10장)")
        res = client.get("/api/v1/vision/config", headers=HEADERS)
        check("GET /api/v1/vision/config 200", res.status_code == 200, res.text[:160])
        config = res.json().get("data", {})
        check("감지 대상 목록이 내려옴", isinstance(config.get("object_labels"), list),
              str(config)[:160])
        check("신뢰도·쿨다운 기준이 함께 내려옴",
              isinstance(config.get("min_confidence"), (int, float))
              and isinstance(config.get("cooldown_seconds"), (int, float)), str(config)[:160])

        res = client.put("/api/vision/config", json={
            "object_labels": ["Dog", "cup", "cup", "rock"], "min_confidence": 0.8,
        })
        if db_on:
            check("PUT /api/vision/config 200", res.status_code == 200, res.text[:160])
            saved = res.json().get("data", {})
            check("대상이 소문자·중복 제거되어 저장됨",
                  saved.get("object_labels") == ["dog", "cup"], str(saved.get("object_labels")))
            check("손동작 라벨은 사물 대상에서 제외됨 (MediaPipe가 판정)",
                  "rock" not in (saved.get("object_labels") or []))
            check("신뢰도 기준이 저장됨", saved.get("min_confidence") == 0.8)

            # 규칙에 쓴 라벨은 설정에 없어도 자동으로 포함되어야 한다
            rule_res = client.post("/api/rules", json={
                "name": "비전 설정 검사용 규칙",
                "definition": {
                    "when": {"type": "vision_label", "label": "person"},
                    "then": [{"action": "notify", "message": "사람 감지"}],
                },
            })
            rule_id = rule_res.json().get("data", {}).get("id")
            merged = client.get("/api/v1/vision/config", headers=HEADERS).json().get("data", {})
            check("규칙에 쓴 라벨이 감지 대상에 자동 포함됨",
                  "person" in (merged.get("object_labels") or []),
                  str(merged.get("object_labels")))
            if rule_id:
                client.delete(f"/api/rules/{rule_id}")

            # 원상 복구
            client.put("/api/vision/config", json={
                "object_labels": ["person", "bottle", "cup", "book", "cell phone"],
                "min_confidence": 0.6,
            })
        else:
            check("DB 미연결 시에도 기본 감지 대상을 내려줌",
                  bool(config.get("object_labels")), str(config)[:120])

        # ---------------------------------------------------------------
        section("8. 코드 격리 (팀 고유 이름이 고정층에 없어야 함)")
        root = Path(CURRENT_DIR).parent
        team_names = [
            "servo_door", "seat_led", "neopixel_seat", "relay_light",
            "rgb_led", "vibration_motor", "relay_power", "touch_display",
            "led_congestion", "motor_conveyor", "sensor_seat_pressure",
            # wakeup 1차 완성본 이름 (P3.5에서 제거됨)
            "buzzer_1", "touch_pad_1", "camera_1",
        ]
        # 마이그레이션 대응표는 옛 이름을 알아야 하므로 여기서만 예외입니다.
        MIGRATION_FILE = "db/database.py"

        targets = [p for p in (root / "backend").rglob("*.py")] + \
                  [p for p in (root / "vision").rglob("*.py")]
        # 자가 점검 스크립트는 "이 이름이 없어야 한다"를 검사하느라 그 이름을 적고 있습니다.
        targets = [p for p in targets
                   if not (p.name.startswith("test_") or p.name.endswith("_test.py"))]
        leaked = []
        for path in targets:
            relative = str(path.relative_to(root / "backend")) if "backend" in path.parts else ""
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in team_names:
                if not re.search(rf"\b{re.escape(name)}", text):
                    continue
                if relative == MIGRATION_FILE and name in ("buzzer_1", "touch_pad_1", "camera_1"):
                    continue    # 1차 완성본 이관용 대응표
                leaked.append(f"{path.relative_to(root)}:{name}")
        check("팀 고유 디바이스 이름이 backend/vision에 없음", not leaked, str(leaked[:5]))

        # 마이그레이션 대응표는 살아 있어야 합니다 (1차 완성본을 올린 팀이 그대로 올라오도록)
        migration_text = (root / "backend" / MIGRATION_FILE).read_text(encoding="utf-8")
        check("1차 완성본 이관 대응표는 남아 있음",
              "LEGACY_DEVICE_MIGRATION" in migration_text)

        # vision은 '무엇을 감지할지'를 코드에 두면 안 됩니다 (부록F 10장)
        vision_text = (root / "vision" / "main.py").read_text(encoding="utf-8")
        check("vision이 감지 대상을 코드에 고정하지 않음",
              "MISSION_TARGETS" not in vision_text)
        check("vision이 서버 설정을 받아 씀",
              "/api/v1/vision/config" in vision_text)

        # 정리
        register(client, [], exclusive=True)

    print("\n" + "=" * 68)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 68)
    if _failed:
        print(" 실패 항목은 부록F 규약과 어긋난 부분입니다. 키트 코드를 점검하세요.")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
