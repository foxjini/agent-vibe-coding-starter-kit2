"""
라즈베리파이 5 초보자를 위한 1분 백엔드 통신 검증 스크립트 (test_connection.py)
=============================================================================
[ELI5 설명]
이 스크립트는 실제 부저나 버튼 부품을 전선으로 연결하기 전에,
라즈베리파이가 백엔드(식당 주방)와 쪽지를 잘 주고받는지 '글자(print)'로 먼저 확인하는 도구입니다!

실행 방법:
    python test_connection.py
"""

import os
import sys
import time
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

# 1. 환경 설정 불러오기
load_dotenv()

# 백엔드 주소 (라즈베리파이에서 실행할 때는 백엔드가 켜진 PC의 IP를 적어주세요!)
# 예: BACKEND_URL = "http://192.168.0.100:8000"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "wake_up_2026_09_05_v1_0_0")

HEADERS = {
    "X-Device-Api-Key": DEVICE_API_KEY,
    "Content-Type": "application/json",
}

print("=" * 65)
print("🚀 [ELI5] 라즈베리파이 5 ↔ 백엔드 통신 첫걸음 테스트기")
print("=" * 65)
print(f"📍 연결할 백엔드 주소: {BACKEND_URL}")
print(f"🔑 우리 팀 비밀 암호: {DEVICE_API_KEY[:6]}****")
print("=" * 65)
print("💡 [안내] 실제 하드웨어 핀 연결 없이, 화면 글자(print)로 성공을 확인합니다.\n")


def check_backend_connection() -> bool:
    """백엔드가 켜져 있는지 확인하는 헬스체크"""
    print("🔍 1단계: 백엔드 우체국이 문을 열었는지 확인 중...")
    try:
        res = requests.get(f"{BACKEND_URL}/health", timeout=3.0)
        if res.status_code == 200:
            print("  ✅ [성공!] 백엔드 서버와 연결되었습니다! (상태 코드: 200 OK)")
            return True
        else:
            print(f"  ⚠️ [응답 받음] 백엔드가 응답했으나 상태 코드가 {res.status_code} 입니다.")
            return True
    except requests.exceptions.ConnectionError:
        print("\n❌ [연결 실패!] 백엔드 컴퓨터를 찾을 수 없습니다.")
        print("  👉 처방전:")
        print("     1) 백엔드 담당 친구의 컴퓨터에서 백엔드 서버가 켜져 있는지 확인하세요.")
        print(f"     2) 라즈베리파이 .env 파일의 BACKEND_URL({BACKEND_URL})에 친구 PC의 실제 IP가 적혀 있는지 확인하세요.")
        print("     3) 두 컴퓨터가 같은 와이파이(Wi-Fi)에 연결되어 있는지 확인하세요.\n")
        return False
    except Exception as e:
        print(f"\n❌ [오류 발생]: {e}\n")
        return False


def get_buzzer_command():
    """백엔드에 '지금 부저 울려야 하나요?' 물어보기 (GET desired-state)"""
    url = f"{BACKEND_URL}/api/v1/devices/buzzer_1/desired-state"
    try:
        res = requests.get(url, headers=HEADERS, timeout=3.0)
        if res.status_code == 200:
            data = res.json().get("data", {})
            desired_state = data.get("desired_state", "off")
            return desired_state
        elif res.status_code == 404:
            print("  ⚠️ [404] 백엔드 DB에 'buzzer_1'이라는 디바이스가 등록되지 않았습니다.")
        elif res.status_code in (401, 403):
            print("  ⚠️ [인증 오류] DEVICE_API_KEY 비밀 암호가 백엔드와 일치하지 않습니다.")
    except Exception as e:
        print(f"  ⚠️ 통신 실패: {e}")
    return None


def report_buzzer_done(state: str):
    """백엔드에 '부저 상태를 반영했습니다!' 보고하기 (POST state)"""
    url = f"{BACKEND_URL}/api/v1/devices/buzzer_1/state"
    payload = {
        "state": state,
        "value": {"sound": "beep_beep", "volume": 80},
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = requests.post(url, json=payload, headers=HEADERS, timeout=3.0)
        return res.status_code == 200
    except Exception:
        return False


def simulate_touch_button():
    """터치패드 센서 터치 이벤트 시뮬레이션 (POST state)"""
    url = f"{BACKEND_URL}/api/v1/devices/touch_pad_1/state"
    payload = {
        "value": {
            "pressed": True,
            "touch_x": 320,
            "touch_y": 240,
            "gesture": "tap",
        },
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = requests.post(url, json=payload, headers=HEADERS, timeout=3.0)
        if res.status_code == 200:
            print("  👉 📱 [센서 보고 성공] '기상 확인 터치패드가 눌렸습니다!' 백엔드 전송 완료!")
            return True
    except Exception as e:
        print(f"  ❌ 터치 전송 실패: {e}")
    return False


def start_polling_loop():
    """1초마다 우체통 확인하기 루프"""
    print("\n📬 2단계: 1초마다 백엔드 우체통 열어보기 시작 (Ctrl+C를 누르면 멈춥니다)")
    print("-" * 65)

    last_state = None
    count = 0

    try:
        while True:
            count += 1
            current_state = get_buzzer_command()

            if current_state is not None:
                # 상태 변경이 감지되었을 때 특별히 크게 출력
                if current_state != last_state:
                    print(f"\n🔔 [상태 변화 감지!] 부저 명령이 바뀌었습니다: {last_state} ➡️ {current_state}")
                    last_state = current_state

                    if current_state in ("ringing", "on"):
                        print("  🔊 [피에조 부저 흉내내기] 삐- 삐- 삐-! 알람이 시끄럽게 울리고 있습니다!")
                        report_buzzer_done("ringing")
                        print("  📤 [보고 완료] 백엔드에 '부저가 실제로 울리고 있어요'라고 보고했습니다.\n")
                    else:
                        print("  🔇 [피에조 부저 흉내내기] 알람 소리가 꺼졌습니다. 조용~")
                        report_buzzer_done("off")
                        print("  📤 [보고 완료] 백엔드에 '부저가 꺼졌어요'라고 보고했습니다.\n")
                else:
                    # 1초마다 정상 동작 중임을 간결하게 표시
                    print(f"[{count:03d}초] 백엔드 확인 중... 현재 buzzer_1 명령 상태: '{current_state}'")

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n🛑 [테스트 종료] 라즈베리파이 통신 테스트를 정상적으로 마쳤습니다.")
        print("💡 [보너스 테스트] 기상 확인 터치패드 신호를 1회 전송해볼까요? (y/n): ", end="")
        try:
            choice = input().strip().lower()
            if choice == "y":
                simulate_touch_button()
        except Exception:
            pass
        print("🎉 수고하셨습니다! 백엔드와의 통신 기초를 완벽하게 통과했습니다.\n")


if __name__ == "__main__":
    # 1단계 헬스체크 통과 시 폴링 시작
    if check_backend_connection():
        start_polling_loop()
    else:
        print("💡 백엔드를 켠 후 다시 `python test_connection.py`를 실행해 보세요!")
