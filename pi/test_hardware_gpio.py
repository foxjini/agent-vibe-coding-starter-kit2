"""
라즈베리파이 5 실기기 하드웨어(GPIO 18 피에조 부저 & GPIO 24 버튼/터치센서) 1분 단독 테스트 스크립트
=============================================================================
이 스크립트는 백엔드 서버와 통신하기 전에,
라즈베리파이 5의 40핀 헤더에 연결된 부품들이 올바르게 작동하는지 직접 확인하는 도구입니다.

테스트 항목:
1. GPIO 18 피에조 부저: 짧게 2회 삐- 삐- 소리 출력
2. GPIO 24 기상 확인 버튼/터치센서: 10초간 버튼 누름 이벤트 감지 대기

실행 방법 (라즈베리파이 터미널):
    python test_hardware_gpio.py
"""

import os
import sys
import time
from dotenv import load_dotenv

# 윈도우 콘솔 UTF-8 출력 호환성 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

# 라즈베리파이 5 RP1 칩셋용 lgpio 핀 팩토리 환경변수 설정
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

BUZZER_PIN = int(os.getenv("BUZZER_PIN", "18"))
BUTTON_PIN = int(os.getenv("BUTTON_PIN", "24"))

print("=" * 65)
print("[*] [라즈베리파이 5] 하드웨어 GPIO 핀 배선 단독 테스트기")
print("=" * 65)
print(f"[*] 피에조 부저 핀: GPIO {BUZZER_PIN}")
print(f"[*] 기상 확인 버튼/터치센서 핀: GPIO {BUTTON_PIN}")
print("=" * 65 + "\n")

# gpiozero 임포트 시도
try:
    from gpiozero import Buzzer, Button
    from gpiozero.pins.lgpio import LGPIOFactory
except ImportError as e:
    print("[!] [패키지 안내] gpiozero 또는 lgpio 라이브러리를 찾을 수 없습니다.")
    print("    라즈베리파이 5(Bookworm/Trixie)에서는 APT 패키지를 연동해야 C 빌드 에러가 나지 않습니다:")
    print("    1) sudo apt install -y python3-gpiozero python3-lgpio")
    print("    2) python3 -m venv --system-site-packages venv")
    print("    3) source venv/bin/activate && pip install -r requirements.txt\n")
    if sys.platform == "win32":
        print("💡 (안내: 현재 윈도우 PC 환경입니다. 실기기 GPIO 배선 테스트는 실제 라즈베리파이 5에서 실행됩니다.)")
    sys.exit(0)


def test_buzzer(pin: int) -> bool:
    """피에조 부저 2회 비프음 테스트"""
    print(f"[*] [1단계] GPIO {pin}번 피에조 부저 소리 테스트 시작...")
    try:
        buzzer = Buzzer(pin)
        print("  ▶ 삐- (1회)")
        buzzer.on()
        time.sleep(0.3)
        buzzer.off()
        time.sleep(0.2)

        print("  ▶ 삐- (2회)")
        buzzer.on()
        time.sleep(0.3)
        buzzer.off()

        buzzer.close()
        print("  [OK] 피에조 부저 테스트 완료! 소리가 정상적으로 들렸나요?\n")
        return True
    except Exception as exc:
        print(f"  [X] 피에조 부저 테스트 실패: {exc}")
        print("  👉 점검 사항: 배선(GND 및 GPIO 18) 연결 상태와 능동/수동 부저 여부를 확인하세요.\n")
        return False


def test_button(pin: int) -> bool:
    """기상 확인 물리 버튼 / 터치 센서 입력 테스트"""
    print(f"[*] [2단계] GPIO {pin}번 기상 확인 버튼/터치센서 입력 감지 테스트 (10초 대기)...")
    print("  👉 지금 버튼을 누르거나 터치센서에 손을 대보세요!")

    detected = False

    def on_pressed():
        nonlocal detected
        detected = True
        print(f"\n  [감지 성공!] GPIO {pin}번 신호 감지! (버튼 누름 / 터치 확인)")

    try:
        # 풀업 저항 기본 적용 (푸시 버튼 GND 연결 또는 터치센서 모듈 지원)
        button = Button(pin, pull_up=True, bounce_time=0.05)
        button.when_pressed = on_pressed

        start_time = time.time()
        while time.time() - start_time < 10:
            if detected:
                break
            remain = int(10 - (time.time() - start_time))
            print(f"\r  대기 중... 남은 시간: {remain:02d}초", end="", flush=True)
            time.sleep(0.2)

        print("")
        button.close()

        if detected:
            print("  [OK] 버튼/터치센서가 정상적으로 작동합니다!\n")
            return True
        else:
            print("  [!] 10초 동안 버튼 입력이 감지되지 않았습니다.")
            print("  👉 점검 사항: 핀 번호가 맞는지, 접지(GND) 배선이 잘 꽂혀 있는지 확인하세요.\n")
            return False
    except Exception as exc:
        print(f"  [X] 버튼 테스트 실패: {exc}\n")
        return False


def main():
    print("▶ 하드웨어 테스트를 시작합니다...\n")
    buzzer_ok = test_buzzer(BUZZER_PIN)
    button_ok = test_button(BUTTON_PIN)

    print("=" * 65)
    print("📋 [최종 하드웨어 점검 결과 요약]")
    print(f" * 피에조 부저 (GPIO {BUZZER_PIN}): {'[정상]' if buzzer_ok else '[점검 필요]'}")
    print(f" * 기상 버튼 (GPIO {BUTTON_PIN}): {'[정상]' if button_ok else '[점검 필요]'}")
    print("=" * 65)

    if buzzer_ok:
        print("\n🚀 이제 'python main.py'를 실행하여 스마트 기상 시스템 연동을 시작할 수 있습니다!")
    else:
        print("\n💡 배선을 점검한 후 다시 'python test_hardware_gpio.py'를 실행해 보세요.")


if __name__ == "__main__":
    main()
