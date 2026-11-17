"""서보 각도 유지 진단 — "90도로 간 뒤 아래로 처진다"의 원인을 가른다.

ATM 데몬이나 hardware_provider.py를 쓰지 않고 gpiozero만으로 서보를 직접 움직인다.
그래서 학생 버전 코드가 어떻게 되어 있든 똑같이 돌려 볼 수 있다.

    cd pi
    source venv/bin/activate
    python servo_hold_test.py            # .env의 SERVO_PIN·펄스 폭을 쓴다
    python servo_hold_test.py --angle 60  # 열림 각도를 바꿔서

3단계로 나눠 보여 준다 (교사 입회, 배출구에 손을 넣지 않는다):

  1단계  0도 → 90도로 간 뒤, 신호를 **계속 보내면서** 10초 버틴다
  2단계  같은 자리에서 신호를 **끊고** 5초 둔다
  3단계  다시 신호를 주고 0도로 돌아간다

  · 1단계에서 이미 처진다  → 코드 문제가 아니다. 전원·토크·기구 문제 (아래 안내)
  · 1단계는 버티고 2단계에서 처진다 → 정상. 신호가 끊기면 서보는 버티지 못한다.
                                    → 실제 코드 어딘가에서 90도에 있는 동안 신호를 끊고 있다
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    try:
        from gpiozero import AngularServo
    except ImportError:
        print("gpiozero가 없습니다 — venv를 --system-site-packages로 만들었는지 확인하세요.")
        return 1

    pin = int(os.getenv("SERVO_PIN", "18"))
    min_us = int(os.getenv("SERVO_MIN_PULSE_US", "500"))
    max_us = int(os.getenv("SERVO_MAX_PULSE_US", "2500"))
    open_angle = 90
    if "--angle" in sys.argv:
        open_angle = int(sys.argv[sys.argv.index("--angle") + 1])

    print(f"GPIO{pin} · 펄스 {min_us}~{max_us}µs · 열림 {open_angle}도")
    print(f"pin factory = {os.getenv('GPIOZERO_PIN_FACTORY', '(기본)')}")
    print("서보 혼(팔)에 덮개를 단 상태로 시작합니다. 배출구에 손을 넣지 마세요.\n")

    # 변수에 꼭 담아 둔다 — 담지 않거나 함수가 끝나 객체가 사라지면 gpiozero가 핀을 닫아
    # 신호가 끊긴다 (그러면 서보는 그 순간부터 버티지 못한다)
    servo = AngularServo(pin, min_angle=0, max_angle=180,
                         min_pulse_width=min_us / 1e6, max_pulse_width=max_us / 1e6)
    try:
        servo.angle = 0
        print("준비: 0도 (2초)")
        time.sleep(2)

        print(f"\n[1단계] {open_angle}도로 이동 — 신호를 계속 보내며 10초 버팁니다")
        servo.angle = open_angle
        for left in range(10, 0, -1):
            print(f"  신호 켜짐 · {left:2d}초 — 지금 각도가 {open_angle}도에서 처지나요?", flush=True)
            time.sleep(1)

        print("\n[2단계] 같은 자리에서 신호를 끊습니다 (5초)")
        servo.detach()
        for left in range(5, 0, -1):
            print(f"  신호 꺼짐 · {left:2d}초 — 처지나요?", flush=True)
            time.sleep(1)

        print("\n[3단계] 다시 신호를 주고 0도로 돌아갑니다 (3초)")
        servo.angle = 0
        time.sleep(3)
    finally:
        servo.close()

    print("""
결과 읽는 법
  1단계에서 이미 처졌다 (신호가 켜져 있는데도)
    → 코드가 아니라 힘이 모자란 것입니다. 차례로 확인하세요.
      ① 서보 전원: 5V 3A 이상 별도 전원인가? (1A 어댑터·파이 5V 핀·건전지 4개는 모자랍니다)
         1단계 중에 서보 전원선(빨강-갈색) 사이 전압을 재 보세요. 4.8V 아래로 떨어지면 전원 문제
      ② GND를 파이와 외부 전원이 함께 쓰는가
      ③ 브레드보드·가는 점퍼선으로 전원을 끌어오지 않았는가 (굵은 선으로 서보에 직접)
      ④ 덮개가 너무 무겁거나 서보 축에서 멀리 매달려 있지 않은가
         → 덮개를 떼고 맨 서보만 돌려 보면, 처지지 않을 때 원인은 무게입니다
      ⑤ MG996R은 위조품이 많습니다. 다른 MG996R로 바꿔 같은 결과인지 확인합니다

  1단계는 버텼고 2단계에서 처졌다
    → 서보·전원은 정상입니다. 실제 ATM 코드가 90도에 있는 동안 신호를 끊고 있습니다.
      hardware_provider.py에서 확인하세요.
      ① 열고 나서 detach() / close() / value = None 을 부르는 곳이 있는가
      ② SERVO_HOLD를 읽는 줄이 .env 값을 실제로 쓰는가
         (예: os.getenv("SERVO_HOLD", "false") — .env가 안 읽히면 false가 됩니다)
      ③ AngularServo 객체를 함수 안 지역 변수로만 만들고 있지 않은가 (함수가 끝나면 핀이 닫힘)
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
