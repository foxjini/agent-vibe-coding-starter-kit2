"""
라즈베리파이 5 하드웨어 데몬 & 윈도우 PC용 Mock-up 시뮬레이터
=============================================================================
1차: 윈도우 PC에서 100% 동작하는 하드웨어 Mock-up (사운드 비프음 + GUI 터치패드)
2차: 라즈베리파이 5(Linux + gpiozero/lgpio) 연동으로 원활하게 전환 가능

- 액추에이터: buzzer_1 (알람 출력 피에조 부저)
- 센서: touch_pad_1 (패드 화면/터치 입력)
- 통신 계약: 부록 A (GET desired-state 폴링 & POST state 보고)
"""

import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HW-Daemon] %(message)s"
)
logger = logging.getLogger("pi.daemon")

# 1. 환경 변수 로드 (.env)
load_dotenv()

# Windows 로컬 개발 시 기본값 fallback
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
# 로컬 테스트 시 localhost로 치환 (Windows PC 단독 실행 대응)
if "192.168." in BACKEND_URL and sys.platform == "win32":
    BACKEND_URL = "http://localhost:8000"

DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "wake_up_2026_09_05_v1_0_0")

POLL_INTERVAL_SECONDS = 1.0  # desired-state 폴링 주기 (초)

# 윈도우 사운드 모듈 지원 확인
HAS_WINSOUND = False
if sys.platform == "win32":
    try:
        import winsound
        HAS_WINSOUND = True
    except ImportError:
        pass


class HardwareMockController:
    """
    라즈베리파이 5 하드웨어(피에조 부저, 터치패드) 시뮬레이션 제어기
    """

    def __init__(self):
        self.current_buzzer_state: str = "off"
        self.is_buzzing: bool = False
        self._sound_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.gui_update_callback = None

    def start_buzzer_sound(self, frequency: int = 1000, volume: int = 80):
        """피에조 부저 알람 소리를 비동기로 재생합니다."""
        if self.is_buzzing:
            return
        self.is_buzzing = True
        self._stop_event.clear()

        def _sound_loop():
            logger.info("피에조 부저 소리 출력 시작 (Beep 1000Hz)...")
            while not self._stop_event.is_set():
                if HAS_WINSOUND:
                    try:
                        winsound.Beep(frequency, 250)
                        time.sleep(0.15)
                    except Exception:
                        time.sleep(0.5)
                else:
                    # 콘솔 비프
                    print("\a", end="", flush=True)
                    time.sleep(0.4)

        self._sound_thread = threading.Thread(target=_sound_loop, daemon=True)
        self._sound_thread.start()

    def stop_buzzer_sound(self):
        """피에조 부저 알람 소리를 멈춥니다."""
        if not self.is_buzzing:
            return
        self.is_buzzing = False
        self._stop_event.set()
        logger.info("피에조 부저 소리 정지 완료.")


hw = HardwareMockController()


# ==============================================================================
# 백엔드 REST API 통신 함수 (부록 A 통신 계약)
# ==============================================================================

def get_auth_headers() -> Dict[str, str]:
    return {
        "X-Device-Api-Key": DEVICE_API_KEY,
        "Content-Type": "application/json",
    }


def poll_desired_state(device_id: str) -> Optional[Dict[str, Any]]:
    """백엔드로부터 액추에이터의 목표 상태(desired-state)를 가져옵니다."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/desired-state"
    try:
        res = requests.get(url, headers=get_auth_headers(), timeout=2.0)
        if res.status_code == 200:
            data = res.json().get("data", {})
            return data
        elif res.status_code == 404:
            logger.warning(f"디바이스 {device_id}를 찾을 수 없습니다 (404).")
        else:
            logger.warning(f"폴링 실패 ({res.status_code}): {res.text}")
    except requests.exceptions.RequestException as exc:
        logger.debug(f"백엔드 연결 대기 중... ({url}): {exc}")
    return None


def report_device_state(device_id: str, state: Optional[str] = None, value: Optional[Any] = None) -> bool:
    """하드웨어가 실제로 반영한 상태 또는 센서 측정값을 백엔드에 보고합니다."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/state"
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "state": state,
        "value": value,
        "reported_at": now_iso,
    }
    try:
        res = requests.post(url, json=payload, headers=get_auth_headers(), timeout=2.0)
        return res.status_code == 200
    except requests.exceptions.RequestException as exc:
        logger.warning(f"상태 보고 실패 ({url}): {exc}")
        return False


def send_touch_pad_input(x: int = 320, y: int = 240, gesture: str = "tap") -> bool:
    """터치패드 센서 입력(기상 확인용)을 백엔드로 전송합니다."""
    logger.info(f"[센서 입력] 터치패드 터치 발생! (X={x}, Y={y}, gesture={gesture})")
    reading = {
        "pressed": True,
        "touch_x": x,
        "touch_y": y,
        "gesture": gesture,
    }
    return report_device_state(device_id="touch_pad_1", value=reading)


# ==============================================================================
# 백그라운드 폴링 데몬 워커
# ==============================================================================

def background_polling_loop():
    """1초 주기로 백엔드의 buzzer_1 desired-state를 폴링하고 실제 반영합니다."""
    logger.info("라즈베리파이 하드웨어 폴링 루프 가동 시작...")

    while True:
        try:
            desired_info = poll_desired_state("buzzer_1")
            if desired_info:
                desired_state = desired_info.get("desired_state") or "off"

                # 상태 변경 감지
                if desired_state != hw.current_buzzer_state:
                    logger.info(
                        f"[상태 전환] 부저 상태 변경 감지: {hw.current_buzzer_state} -> {desired_state}"
                    )
                    hw.current_buzzer_state = desired_state

                    if desired_state in ("ringing", "on"):
                        # 부저 알람 울리기
                        hw.start_buzzer_sound()
                        report_device_state("buzzer_1", state="ringing")
                    else:
                        # 부저 끄기
                        hw.stop_buzzer_sound()
                        report_device_state("buzzer_1", state="off")

                    if hw.gui_update_callback:
                        hw.gui_update_callback(desired_state)

        except Exception as e:
            logger.error(f"폴링 루프 오류: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


# ==============================================================================
# GUI Mock-up 인터페이스 (Tkinter)
# ==============================================================================

def run_gui():
    """윈도우 화면에 실제 하드웨어 느낌의 피에조 부저 & 터치패드 시뮬레이터 창을 띄웁니다."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("Raspberry Pi 5 Mock-up (Smart Wakeup Hardware)")
    root.geometry("460x520")
    root.configure(bg="#1e293b")
    root.resizable(False, False)

    # 헤더
    header = tk.Label(
        root,
        text="라즈베리파이 5 하드웨어 Mock-up",
        font=("Malgun Gothic", 14, "bold"),
        bg="#1e293b",
        fg="#f8fafc",
        pady=10,
    )
    header.pack()

    sub_header = tk.Label(
        root,
        text=f"백엔드 연결: {BACKEND_URL}\n피에조 부저(buzzer_1) & 터치패드(touch_pad_1)",
        font=("Malgun Gothic", 9),
        bg="#1e293b",
        fg="#94a3b8",
    )
    sub_header.pack()

    # 1. 피에조 부저 상태 표시 영역
    buzzer_frame = tk.LabelFrame(
        root,
        text=" 1. 알람 출력 장치 (피에조 부저: buzzer_1) ",
        font=("Malgun Gothic", 10, "bold"),
        bg="#0f172a",
        fg="#e2e8f0",
        padx=15,
        pady=15,
    )
    buzzer_frame.pack(fill="x", padx=20, pady=15)

    buzzer_status_lbl = tk.Label(
        buzzer_frame,
        text="● 부저 정지 (OFF)",
        font=("Malgun Gothic", 13, "bold"),
        bg="#0f172a",
        fg="#64748b",
    )
    buzzer_status_lbl.pack(pady=5)

    buzzer_desc = tk.Label(
        buzzer_frame,
        text="백엔드 desired-state를 1초마다 폴링 중\n(알람 시작 시 실제 비프음과 함께 빨간색으로 점멸합니다)",
        font=("Malgun Gothic", 8),
        bg="#0f172a",
        fg="#94a3b8",
    )
    buzzer_desc.pack()

    # 2. 터치패드 센서 시뮬레이터 영역
    touch_frame = tk.LabelFrame(
        root,
        text=" 2. 패드 화면/터치 입력 센서 (touch_pad_1) ",
        font=("Malgun Gothic", 10, "bold"),
        bg="#0f172a",
        fg="#e2e8f0",
        padx=15,
        pady=15,
    )
    touch_frame.pack(fill="x", padx=20, pady=10)

    touch_info = tk.Label(
        touch_frame,
        text="아래 패드 영역을 클릭하면 백엔드로 기상 확인 터치 이벤트가 전송됩니다.\n(2차 수면 방지 팝업 자동 해제 연동)",
        font=("Malgun Gothic", 8),
        bg="#0f172a",
        fg="#94a3b8",
    )
    touch_info.pack(pady=4)

    # 터치 입력 캔버스
    canvas = tk.Canvas(touch_frame, width=380, height=100, bg="#334155", highlightthickness=0, cursor="hand2")
    canvas.pack(pady=8)
    canvas.create_text(
        190, 50,
        text="[ 📱 화면을 터치하세요 (기상 확인) ]",
        fill="#f8fafc",
        font=("Malgun Gothic", 11, "bold"),
    )

    touch_feedback_lbl = tk.Label(
        touch_frame,
        text="마지막 터치: 대기 중",
        font=("Malgun Gothic", 9),
        bg="#0f172a",
        fg="#38bdf8",
    )
    touch_feedback_lbl.pack()

    def on_canvas_click(event):
        success = send_touch_pad_input(x=event.x, y=event.y, gesture="tap")
        now_time = datetime.now().strftime("%H:%M:%S")
        if success:
            touch_feedback_lbl.config(
                text=f"마지막 터치: ({event.x}, {event.y}) - 기상 확인 전송 완료 ({now_time})",
                fg="#4ade80",
            )
        else:
            touch_feedback_lbl.config(
                text=f"마지막 터치: 전송 실패 (백엔드 확인 필요) ({now_time})",
                fg="#f87171",
            )

    canvas.bind("<Button-1>", on_canvas_click)

    # GUI 상태 업데이트 콜백
    def update_gui_state(state: str):
        if state in ("ringing", "on"):
            buzzer_status_lbl.config(
                text="🚨 부저 알람 동작 중! (RINGING) 🚨",
                fg="#ef4444",
            )
            buzzer_frame.config(bg="#450a0a")
        else:
            buzzer_status_lbl.config(
                text="● 부저 대기 (OFF)",
                fg="#64748b",
            )
            buzzer_frame.config(bg="#0f172a")

    hw.gui_update_callback = lambda s: root.after(0, update_gui_state, s)

    # 하단 종료 안내
    quit_btn = tk.Button(
        root,
        text="Mock-up 데몬 종료",
        command=root.destroy,
        bg="#334155",
        fg="#f1f5f9",
        font=("Malgun Gothic", 9),
        relief="flat",
        padx=15,
        pady=5,
        cursor="hand2",
    )
    quit_btn.pack(pady=12)

    root.mainloop()


def main():
    print("\n" + "=" * 65)
    print(" [스마트 기상 시스템 - 라즈베리파이 5 Mock-up 프로그램]")
    print(f" * 백엔드 URL: {BACKEND_URL}")
    print(f" * 디바이스 키: {DEVICE_API_KEY}")
    print(" * 모드: 윈도우 PC 100% Mock-up (사운드 비프 + GUI 터치패드)")
    print("=" * 65 + "\n")

    # 1. 백그라운드 폴링 스레드 시작
    poll_thread = threading.Thread(target=background_polling_loop, daemon=True)
    poll_thread.start()

    # 2. GUI 실행 (Tkinter 미지원 환경 시 CLI 폴백)
    try:
        run_gui()
    except Exception as e:
        logger.warning(f"GUI 실행 불가 (CLI 모드로 지속 실행): {e}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("사용자에 의해 Mock 데몬이 종료되었습니다.")


if __name__ == "__main__":
    main()
