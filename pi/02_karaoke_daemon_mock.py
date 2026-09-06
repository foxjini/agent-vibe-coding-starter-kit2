"""
02_karaoke_daemon_mock.py
--------------------------------------------------------------------------------
[라즈베리파이 5 담당자를 위한 2단계 실습: 노래방 부스 폴링 데몬 (Mock 모드)]

* 목적:
    - 카운터(백엔드)에 3초마다 "지금 할 일 있나요?" 하고 물어봅니다(GET desired-state).
    - 아직 실제 솔레노이드/릴레이를 꽂지 않았으므로, print() 문으로 화면에 동작을 시뮬레이션합니다.
    - 지시를 수행한 후 카운터에 "지시대로 완료했습니다!" 하고 보고(POST state)합니다.
    - 웹 대시보드 화면에 내 보고가 실시간으로 반영되는 것을 눈으로 확인합니다.

* 실행 방법:
    cd pi
    python 02_karaoke_daemon_mock.py
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# 1. 환경변수 불러오기
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "KARAOKE_2026_09_05_v1_0_0")

HEADERS = {
    "X-Device-Api-Key": DEVICE_API_KEY,
    "Content-Type": "application/json",
}

# 우리가 감시하고 제어할 부스 액추에이터 4종 목록
ACTUATORS = [
    {"id": "door_lock_1", "name": "솔레노이드 도어락", "emoji": "🚪"},
    {"id": "relay_1",     "name": "기기 전원 릴레이", "emoji": "⚡"},
    {"id": "led_1",       "name": "부스 조명 LED",   "emoji": "💡"},
    {"id": "speaker_1",   "name": "스피커 모듈",      "emoji": "🔊"},
]

# 현재 내가 기억하고 있는 각 부품의 실제 상태 (초기값)
my_current_states = {
    "door_lock_1": "locked",
    "relay_1": "off",
    "led_1": "off",
    "speaker_1": "idle",
}

print("=" * 70)
print("🎤 [라즈베리파이 5] 학교 노래방 부스 제어 데몬 시작 (Mock 모드)")
print(f"📍 카운터(백엔드) 주소: {BACKEND_URL}")
print(f"🔑 출입증(API 키): {DEVICE_API_KEY[:8]}********")
print(f"🏷️ 감시 대상 디바이스: {[a['id'] for a in ACTUATORS]}")
print("⏱️ 폴링 주기: 3초 (종료하려면 터미널에서 Ctrl + C 를 누르세요)")
print("=" * 70)


def poll_and_execute(actuator):
    """카운터의 지시서를 확인하고, 변경사항이 있으면 print() 출력 후 보고합니다."""
    device_id = actuator["id"]
    name = actuator["name"]
    emoji = actuator["emoji"]

    desired_url = f"{BACKEND_URL}/api/v1/devices/{device_id}/desired-state"

    try:
        # 1. 지시서 확인 (GET)
        res = requests.get(desired_url, headers=HEADERS, timeout=3)

        if res.status_code == 401:
            print(f"🚨 [인증 실패 401] {device_id}: 출입증(DEVICE_API_KEY)이 틀렸습니다! .env를 확인하세요.")
            return
        elif res.status_code == 404:
            print(f"🔍 [부품 없음 404] {device_id}: 카운터 장부에 이 이름이 등록되어 있지 않습니다.")
            return
        elif res.status_code != 200:
            print(f"⚠️ [응답 이상 {res.status_code}] {device_id}: {res.text}")
            return

        data = res.json().get("data", {})
        desired_state = data.get("desired_state")
        desired_value = data.get("value")

        # 2. 카운터의 지시와 내 현재 상태가 다르면 행동(모의 print) 개시!
        if desired_state and desired_state != my_current_states.get(device_id):
            print("\n" + "-" * 60)
            print(f"📬 [지시서 도착] {emoji} {name} ({device_id})")
            print(f"   카운터의 목표 상태: {desired_state} (기존: {my_current_states.get(device_id)})")

            # --- [하드웨어 시뮬레이션 print 출력] ---
            if device_id == "door_lock_1":
                if desired_state == "unlocked":
                    print("   🚪 [모의 동작] 철컥! 솔레노이드 도어락이 '해제'되었습니다! (부스 입장 가능)")
                else:
                    print("   🚪 [모의 동작] 딸깍! 솔레노이드 도어락이 '잠금'되었습니다!")

            elif device_id == "relay_1":
                if desired_state == "on":
                    print("   ⚡ [모의 동작] 릴레이 작동! 노래방 반주기에 220V 전원이 켜졌습니다!")
                else:
                    print("   ⚡ [모의 동작] 릴레이 차단! 노래방 반주기 전원이 꺼졌습니다.")

            elif device_id == "led_1":
                print(f"   💡 [모의 동작] 부스 조명이 '{desired_state}' 상태로 전환되었습니다. (설정값: {desired_value})")

            elif device_id == "speaker_1":
                print(f"   🔊 [모의 동작] 스피커에서 오디오가 출력됩니다: '{desired_state}' (설정값: {desired_value})")
            # --------------------------------------

            # 3. 내 로컬 상태 갱신
            my_current_states[device_id] = desired_state

            # 4. 카운터에 완료 보고서 전송 (POST)
            report_url = f"{BACKEND_URL}/api/v1/devices/{device_id}/state"
            report_body = {
                "state": desired_state,
                "value": desired_value,
            }
            rep_res = requests.post(report_url, headers=HEADERS, json=report_body, timeout=3)
            if rep_res.status_code == 200:
                print(f"   📤 [보고 완료] 카운터에 '{desired_state}' 보고 성공! (대시보드 실시간 반영)")
            else:
                print(f"   ⚠️ [보고 실패] 상태 보고 실패 코드: {rep_res.status_code}")
            print("-" * 60 + "\n")

    except requests.exceptions.ConnectionError:
        print(f"❌ [카운터 연결 불가] 백엔드 컴퓨터({BACKEND_URL})에 닿지 않습니다. 서버가 켜져 있는지 확인하세요.")
    except requests.exceptions.Timeout:
        print(f"⏳ [타임아웃] 응답 지연 (3초 초과)")
    except Exception as exc:
        print(f"⚠️ 처리 중 오류: {exc}")


def main():
    loop_count = 0
    while True:
        try:
            loop_count += 1
            # 4개 액추에이터 순차 폴링
            for actuator in ACTUATORS:
                poll_and_execute(actuator)

            # 콘솔에 생존 하트비트 점(dot) 표시
            sys.stdout.write(f"\r💓 폴링 루프 작동 중... (#{loop_count}회차) [Ctrl+C 종료]")
            sys.stdout.flush()

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다. 수고하셨습니다!")
            break


if __name__ == "__main__":
    main()
