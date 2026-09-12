"""
비전 클라이언트 자가 점검 (vision/test_vision_config.py)
=============================================================================
웹캠도 백엔드도 없이 실행됩니다. 확인하는 것:

 1) 감지 대상이 코드에 하드코딩되어 있지 않은지 (부록F 10장)
 2) 서버 설정을 받아 라벨 → COCO 클래스 번호로 바꾸는지
 3) 서버가 없거나 이상한 값을 줘도 기본값으로 계속 동작하는지
 4) 삭제된 엔드포인트를 부르지 않는지

실행 방법 (vision 폴더에서):
    python test_vision_config.py
"""
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import main as vision  # noqa: E402

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
    print(f"\n{title}\n{'-' * 66}")


class FakeResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Dict[str, Any]:
        return self._payload


class FakeSession:
    """서버를 흉내냅니다 — 실제 백엔드 없이 설정 폴링을 시험합니다."""

    def __init__(self, payload: Dict[str, Any], status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.requested_urls = []

    def get(self, url, **kwargs):
        self.requested_urls.append(url)
        if self.status_code == 0:
            raise vision.requests.exceptions.ConnectionError("연결 실패")
        return FakeResponse(self.status_code, {"data": self.payload})

    def post(self, url, **kwargs):
        self.requested_urls.append(url)
        return FakeResponse(200, {"data": {}})


def make_client(session: FakeSession) -> "vision.BackendClient":
    """설정 폴링만 한 번 돌린 클라이언트를 만듭니다."""
    client = vision.BackendClient.__new__(vision.BackendClient)
    client.backend_url = "http://test"
    client.headers = {"X-Device-Api-Key": "k", "Content-Type": "application/json"}
    client._session = session          # type: ignore[attr-defined]
    client._running = True             # type: ignore[attr-defined]
    client.last_send_ok = None
    client.config = dict(vision.FALLBACK_CONFIG)
    client.config_source = "기본값(서버 연결 전)"

    # 한 회차만 돌리고 멈춘다
    original_sleep = vision.time.sleep

    def stop_after_one(_seconds):
        client._running = False        # type: ignore[attr-defined]

    vision.time.sleep = stop_after_one
    try:
        client._config_loop()          # type: ignore[attr-defined]
    finally:
        vision.time.sleep = original_sleep
    return client


def main_test() -> int:
    print("=" * 66)
    print(" 영상인식 클라이언트 — 자가 점검")
    print("=" * 66)

    vision.CLASS_INDEX.update({name: index for index, name in enumerate(vision.COCO_CLASSES)})

    # ------------------------------------------------------------------
    section("1. 감지 대상이 코드에 박혀 있지 않은가 (부록F 10장)")
    source = Path(CURRENT_DIR, "main.py").read_text(encoding="utf-8")
    check("MISSION_TARGETS 같은 고정 대상표가 없음", "MISSION_TARGETS" not in source)
    check("설정 엔드포인트를 호출함", "/api/v1/vision/config" in source)
    check("삭제된 알람 API를 부르지 않음", "/api/alarm" not in source,
          "P3.5에서 제거된 엔드포인트입니다")
    check("팀 고유 디바이스 이름이 없음",
          not re.search(r"\b(buzzer_1|touch_pad_1|camera_1)\b", source))

    # ------------------------------------------------------------------
    section("2. 서버 설정을 받아 적용하는가")
    session = FakeSession({
        "object_labels": ["dog", "Cup", "laptop"],
        "gesture_enabled": False,
        "min_confidence": 0.8,
        "cooldown_seconds": 4.0,
        "source": "saved",
    })
    client = make_client(session)
    check("설정 엔드포인트로 요청함",
          any("/api/v1/vision/config" in url for url in session.requested_urls),
          str(session.requested_urls))
    check("대상 목록을 소문자로 받아 적용", client.config["object_labels"] == ["dog", "cup", "laptop"],
          str(client.config["object_labels"]))
    check("손동작 사용 여부가 반영됨", client.config["gesture_enabled"] is False)
    check("신뢰도 기준이 반영됨", client.config["min_confidence"] == 0.8)
    check("쿨다운이 반영됨", client.config["cooldown_seconds"] == 4.0)
    check("설정 출처를 표시함", client.config_source == "서버 설정", client.config_source)

    indexes = [vision.CLASS_INDEX[label] for label in client.config["object_labels"]
               if label in vision.CLASS_INDEX]
    check("라벨이 COCO 클래스 번호로 변환됨", indexes == [16, 41, 63], str(indexes))

    # ------------------------------------------------------------------
    section("3. 서버가 없거나 이상해도 계속 동작하는가")
    offline = make_client(FakeSession({}, status_code=0))
    check("서버에 연결되지 않으면 기본값 유지",
          offline.config["object_labels"] == vision.FALLBACK_CONFIG["object_labels"],
          str(offline.config["object_labels"]))

    empty = make_client(FakeSession({"object_labels": [], "source": "default"}))
    check("대상이 빈 목록이면 기본값으로 되돌림",
          empty.config["object_labels"] == vision.FALLBACK_CONFIG["object_labels"],
          str(empty.config["object_labels"]))

    broken = make_client(FakeSession({"object_labels": ["cup"], "min_confidence": None,
                                      "cooldown_seconds": None}))
    check("빠진 값은 기본값으로 채움",
          broken.config["min_confidence"] == 0.6 and broken.config["cooldown_seconds"] == 2.5,
          str(broken.config))

    denied = make_client(FakeSession({}, status_code=403))
    check("인증 실패해도 죽지 않고 기본값 유지",
          denied.config["object_labels"] == vision.FALLBACK_CONFIG["object_labels"])

    # ------------------------------------------------------------------
    section("4. 모르는 라벨을 줘도 화면이 깨지지 않는가")
    unknown = make_client(FakeSession({"object_labels": ["cup", "우주선", "zebra"]}))
    labels = unknown.config["object_labels"]
    usable = [vision.CLASS_INDEX[label] for label in labels if label in vision.CLASS_INDEX]
    check("COCO에 없는 라벨은 감지 대상에서 조용히 빠짐", usable == [41, 22], str(usable))
    check("한글 이름이 없는 라벨은 영문 그대로 표시", vision.label_ko("zebra") == "zebra")
    check("한글 이름이 있으면 한글로 표시", vision.label_ko("cup") == "컵")

    print("\n" + "=" * 66)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 66)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
