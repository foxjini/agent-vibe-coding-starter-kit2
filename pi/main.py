"""
라즈베리파이 5 실기기 데몬 & 하이브리드 Mock 시뮬레이터 (pi/main.py)
=============================================================================
스마트 기상 시스템 (Smart Wake-up System) 하드웨어 제어 프로그램

[동작 모드]
1. 실기기 모드 (라즈베리파이 5):
   - GPIO 18: 알람 출력 피에조 부저 (gpiozero.Buzzer, lgpio 핀 팩토리)
   - GPIO 24: 기상 확인 물리 버튼 / 정전식 터치센서 (gpiozero.Button)
2. Mock 모드 (윈도우 PC / 가상 환경):
   - winsound 비프음 / 콘솔 비프 + Tkinter GUI 터치패드 시뮬레이터

[통신 계약 - 부록 A 규약 준수]
- 1초 주기 백엔드 desired-state 폴링: GET /api/v1/devices/{id}/desired-state
- 실기기 반영 상태 보고: POST /api/v1/devices/{id}/state
- 기상 확인 터치/버튼 입력: POST /api/v1/devices/touch_pad_1/state
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import requests
from dotenv import load_dotenv

# 윈도우 콘솔 UTF-8 호환성 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HW-Daemon] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pi.daemon")

# 1. 환경 설정 로드 (.env)
load_dotenv()

# 라즈베리파이 5 RP1 칩셋 호환용 lgpio 핀 팩토리 설정
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "wake_up_2026_09_05_v1_0_0")
DEVICE_MODE = os.getenv("DEVICE_MODE", "auto").lower()  # auto, hardware, mock
BUZZER_PIN = int(os.getenv("BUZZER_PIN", "18"))
BUTTON_PIN = int(os.getenv("BUTTON_PIN", "24"))
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))

# 윈도우 사운드 모듈 지원 확인
HAS_WINSOUND = False
if sys.platform == "win32":
    try:
        import winsound
        HAS_WINSOUND = True
    except ImportError:
        pass


# ==============================================================================
# 백엔드 REST API 통신 함수 (부록 A 통신 계약)
# ==============================================================================

def get_auth_headers() -> Dict[str, str]:
    """부록 A 제4장: X-Device-Api-Key 인증 헤더"""
    return {
        "X-Device-Api-Key": DEVICE_API_KEY,
        "Content-Type": "application/json",
    }


def poll_desired_state(device_id: str) -> Optional[Dict[str, Any]]:
    """백엔드로부터 액추에이터의 목표 상태(desired-state)를 조회합니다."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/desired-state"
    try:
        res = requests.get(url, headers=get_auth_headers(), timeout=2.5)
        if res.status_code == 200:
            return res.json().get("data", {})
        elif res.status_code == 404:
            logger.warning(f"디바이스 '{device_id}'를 찾을 수 없습니다 (404 Not Found).")
        elif res.status_code in (401, 403):
            logger.error("인증 실패! .env의 DEVICE_API_KEY가 백엔드와 일치하는지 확인하세요.")
        else:
            logger.warning(f"폴링 실패 ({res.status_code}): {res.text}")
    except requests.exceptions.RequestException as exc:
        logger.debug(f"백엔드 연결 대기 중... ({url}): {exc}")
    return None


def report_device_state(
    device_id: str,
    state: Optional[str] = None,
    value: Optional[Any] = None,
) -> bool:
    """하드웨어가 실제로 반영한 상태 또는 센서 측정값을 백엔드에 보고합니다."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/state"
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "state": state,
        "value": value,
        "reported_at": now_iso,
    }
    try:
        res = requests.post(url, json=payload, headers=get_auth_headers(), timeout=2.5)
        return res.status_code == 200
    except requests.exceptions.RequestException as exc:
        logger.warning(f"상태 보고 실패 ({url}): {exc}")
        return False


def send_touch_pad_input(x: int = 320, y: int = 240, gesture: str = "tap") -> bool:
    """
    기상 확인 물리 버튼 누름 또는 터치패드 터치 입력을 백엔드로 전송합니다.
    (부록 A 센서 보고 엔드포인트 및 2차 수면 방지 팝업 해제 연동)
    """
    logger.info(f"📱 [기상 확인 입력 발생] 터치패드/버튼 신호 감지! (X={x}, Y={y}, gesture={gesture})")
    reading = {
        "pressed": True,
        "touch_x": x,
        "touch_y": y,
        "gesture": gesture,
    }

    # 1. 부록 A 공식 센서 상태 보고 (POST /api/v1/devices/touch_pad_1/state)
    success = report_device_state(device_id="touch_pad_1", state=None, value=reading)

    # 2. 알람 기상 확인 직접 호출 (POST /api/alarm/confirm-wakeup 백업)
    try:
        alarm_url = f"{BACKEND_URL}/api/alarm/confirm-wakeup"
        requests.post(
            alarm_url,
            json={"actor": "touch_pad"},
            headers=get_auth_headers(),
            timeout=2.0,
        )
    except Exception:
        pass

    return success


# ==============================================================================
# 하드웨어 제어기 추상화 (Real Pi 5 vs Mock)
# ==============================================================================

class BaseHardwareController:
    def __init__(self):
        self.current_buzzer_state: str = "off"
        self.is_buzzing: bool = False
        self.gui_update_callback: Optional[Callable[[str], None]] = None

    def start_buzzer(self) -> None:
        raise NotImplementedError

    def stop_buzzer(self) -> None:
        raise NotImplementedError

    def cleanup(self) -> None:
        pass


class RaspberryPi5HardwareController(BaseHardwareController):
    """
    실제 라즈베리파이 5 전용 하드웨어 제어기
    - GPIO 18: 피에조 부저 (gpiozero.Buzzer)
    - GPIO 24: 기상 확인 물리 버튼 / 정전식 터치센서 (gpiozero.Button)
    """

    def __init__(self, buzzer_pin: int = 18, button_pin: int = 24):
        super().__init__()
        self.buzzer_pin = buzzer_pin
        self.button_pin = button_pin

        from gpiozero import Button, Buzzer

        logger.info(f"🔌 [RPi 5 실기기 초기화] 부저: GPIO {buzzer_pin}, 버튼/센서: GPIO {button_pin}")

        # 피에조 부저 초기화
        self.buzzer = Buzzer(self.buzzer_pin)
        self.buzzer.off()

        # 기상 확인 버튼/터치센서 초기화 (풀업 저항 활성화, 채터링 방지 0.05초)
        self.button = Button(self.button_pin, pull_up=True, bounce_time=0.05)
        self.button.when_pressed = self._on_physical_button_pressed

        logger.info("✅ 라즈베리파이 5 GPIO 핀 설정 완료 (Buzzer=Ready, Button=Ready)")

    def _on_physical_button_pressed(self):
        """GPIO 24번 물리 버튼이나 터치센서가 감지되었을 때 자동 호출"""
        logger.info("🔔 [GPIO 이벤트] 실기기 버튼/터치센서 눌림 감지! 백엔드로 기상 확인 전송...")
        send_touch_pad_input(x=320, y=240, gesture="physical_button")
        if self.gui_update_callback:
            self.gui_update_callback("button_pressed")

    def start_buzzer(self):
        if self.is_buzzing:
            return
        self.is_buzzing = True
        logger.info(f"🚨 [부저 작동] GPIO {self.buzzer_pin}번 피에조 부저 비프음 시작 (Beeping)...")
        # 0.25초 울리고 0.15초 쉬는 경보 패턴 반복
        self.buzzer.beep(on_time=0.25, off_time=0.15)

    def stop_buzzer(self):
        if not self.is_buzzing:
            return
        self.is_buzzing = False
        logger.info(f"🔇 [부저 정지] GPIO {self.buzzer_pin}번 피에조 부저 소리 정지.")
        self.buzzer.off()

    def cleanup(self):
        logger.info("🧹 라즈베리파이 GPIO 자원 해제 중...")
        try:
            self.buzzer.off()
            self.buzzer.close()
            self.button.close()
        except Exception as e:
            logger.debug(f"GPIO 정리 중 예외: {e}")


class HardwareMockController(BaseHardwareController):
    """
    윈도우 PC 및 개발 환경용 Mock 시뮬레이션 제어기
    - 사운드: winsound.Beep (1000Hz) 또는 콘솔 Beep
    """

    def __init__(self):
        super().__init__()
        self._sound_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        logger.info("🖥️ [Mock 모드 활성화] 사운드 비프음 및 소프트웨어 시뮬레이터로 동작합니다.")

    def start_buzzer(self, frequency: int = 1000):
        if self.is_buzzing:
            return
        self.is_buzzing = True
        self._stop_event.clear()

        def _sound_loop():
            logger.info("🚨 [Mock 부저] 가상 피에조 부저 소리 출력 시작 (1000Hz Beep)...")
            while not self._stop_event.is_set():
                if HAS_WINSOUND:
                    try:
                        winsound.Beep(frequency, 250)
                        time.sleep(0.15)
                    except Exception:
                        time.sleep(0.4)
                else:
                    print("\a", end="", flush=True)
                    time.sleep(0.4)

        self._sound_thread = threading.Thread(target=_sound_loop, daemon=True)
        self._sound_thread.start()

    def stop_buzzer(self):
        if not self.is_buzzing:
            return
        self.is_buzzing = False
        self._stop_event.set()
        logger.info("🔇 [Mock 부저] 가상 피에조 부저 소리 정지 완료.")

    def cleanup(self):
        self.stop_buzzer()


def create_hardware_controller() -> BaseHardwareController:
    """실행 환경(라즈베리파이 5 vs PC) 및 설정에 따라 적절한 컨트롤러를 생성합니다."""
    # 1. 강제 모드 지정 확인
    if DEVICE_MODE == "mock":
        logger.info("설정에 따라 Mock 모드로 실행합니다. (DEVICE_MODE=mock)")
        return HardwareMockController()

    if DEVICE_MODE == "hardware":
        logger.info("설정에 따라 실기기 모드로 실행합니다. (DEVICE_MODE=hardware)")
        try:
            return RaspberryPi5HardwareController(buzzer_pin=BUZZER_PIN, button_pin=BUTTON_PIN)
        except Exception as exc:
            logger.error(f"❌ 라즈베리파이 실기기 초기화 실패: {exc}")
            logger.warning("Mock 모드로 안전하게 폴백합니다.")
            return HardwareMockController()

    # 2. 'auto' 자동 감지 모드
    if sys.platform != "win32":
        try:
            logger.info("Linux 환경 감지: 라즈베리파이 5 실기기 GPIO 연결 시도 중...")
            return RaspberryPi5HardwareController(buzzer_pin=BUZZER_PIN, button_pin=BUTTON_PIN)
        except Exception as exc:
            logger.warning(f"실기기 GPIO 연결 불가 ({exc}) -> Mock 모드로 전환합니다.")
            return HardwareMockController()
    else:
        logger.info("Windows PC 환경 감지: Mock 모드로 실행합니다.")
        return HardwareMockController()


# 컨트롤러 인스턴스 생성
controller = create_hardware_controller()


# ==============================================================================
# 백그라운드 폴링 데몬 워커
# ==============================================================================

_daemon_running = True


def background_polling_loop():
    """1초 주기로 백엔드의 buzzer_1 desired-state를 폴링하고 실제 반영합니다."""
    logger.info("🔄 [폴링 데몬] 백엔드 desired-state 폴링 루프 가동 시작 (주기: 1.0초)...")

    while _daemon_running:
        try:
            desired_info = poll_desired_state("buzzer_1")
            if desired_info:
                desired_state = desired_info.get("desired_state") or "off"

                # 상태 변경 감지
                if desired_state != controller.current_buzzer_state:
                    logger.info(
                        f"🔔 [상태 전환] 부저 목표 상태 변경 감지: "
                        f"'{controller.current_buzzer_state}' ➡️ '{desired_state}'"
                    )
                    controller.current_buzzer_state = desired_state

                    if desired_state in ("ringing", "on"):
                        controller.start_buzzer()
                        report_device_state("buzzer_1", state="ringing")
                    else:
                        controller.stop_buzzer()
                        report_device_state("buzzer_1", state="off")

                    if controller.gui_update_callback:
                        controller.gui_update_callback(desired_state)

        except Exception as e:
            logger.error(f"폴링 루프 중 예외 발생: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


# ==============================================================================
# GUI Mock-up 인터페이스 (Tkinter - 데스크톱 환경)
# ==============================================================================

def run_gui():
    """데스크톱 디스플레이가 있을 때 GUI 제어창을 표시합니다."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Raspberry Pi 5 Daemon (Smart Wakeup)")
    root.geometry("460x530")
    root.configure(bg="#1e293b")
    root.resizable(False, False)

    is_hw = isinstance(controller, RaspberryPi5HardwareController)
    mode_badge = "🟢 라즈베리파이 5 실기기 연결됨" if is_hw else "🟡 PC Mock 시뮬레이터 동작 중"

    # 헤더
    header = tk.Label(
        root,
        text="스마트 기상 시스템 하드웨어 데몬",
        font=("Malgun Gothic", 14, "bold"),
        bg="#1e293b",
        fg="#f8fafc",
        pady=10,
    )
    header.pack()

    sub_header = tk.Label(
        root,
        text=f"{mode_badge}\n백엔드: {BACKEND_URL} | 핀: 부저({BUZZER_PIN}), 버튼({BUTTON_PIN})",
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
    buzzer_frame.pack(fill="x", padx=20, pady=12)

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
        text=f"백엔드 desired-state를 {POLL_INTERVAL_SECONDS}초마다 폴링 중",
        font=("Malgun Gothic", 8),
        bg="#0f172a",
        fg="#94a3b8",
    )
    buzzer_desc.pack()

    # 2. 터치패드 / 물리 버튼 센서 영역
    touch_frame = tk.LabelFrame(
        root,
        text=" 2. 기상 확인 입력 (터치패드 / 물리 버튼: touch_pad_1) ",
        font=("Malgun Gothic", 10, "bold"),
        bg="#0f172a",
        fg="#e2e8f0",
        padx=15,
        pady=15,
    )
    touch_frame.pack(fill="x", padx=20, pady=10)

    touch_info = tk.Label(
        touch_frame,
        text="실제 기기 버튼을 누르거나 아래 화면을 클릭하면 기상 확인 신호가 전송됩니다.\n(2차 수면 방지 팝업 자동 해제 연동)",
        font=("Malgun Gothic", 8),
        bg="#0f172a",
        fg="#94a3b8",
    )
    touch_info.pack(pady=4)

    canvas = tk.Canvas(touch_frame, width=380, height=90, bg="#334155", highlightthickness=0, cursor="hand2")
    canvas.pack(pady=6)
    canvas.create_text(
        190, 45,
        text="[ 📱 화면을 터치하거나 물리 버튼을 누르세요 ]",
        fill="#f8fafc",
        font=("Malgun Gothic", 11, "bold"),
    )

    touch_feedback_lbl = tk.Label(
        touch_frame,
        text="마지막 입력: 대기 중",
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
                text=f"터치 성공 ({event.x}, {event.y}) - 기상 확인 전송 완료 ({now_time})",
                fg="#4ade80",
            )
        else:
            touch_feedback_lbl.config(
                text=f"전송 실패 (백엔드 확인 필요) ({now_time})",
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
        elif state == "button_pressed":
            now_time = datetime.now().strftime("%H:%M:%S")
            touch_feedback_lbl.config(
                text=f"물리 버튼 눌림 감지! 기상 확인 완료 ({now_time})",
                fg="#4ade80",
            )
        else:
            buzzer_status_lbl.config(
                text="● 부저 대기 (OFF)",
                fg="#64748b",
            )
            buzzer_frame.config(bg="#0f172a")

    controller.gui_update_callback = lambda s: root.after(0, update_gui_state, s)

    # 종료 버튼
    quit_btn = tk.Button(
        root,
        text="데몬 종료",
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


# ==============================================================================
# 메인 함수 및 종료 핸들러
# ==============================================================================

def shutdown(signum=None, frame=None):
    """안전한 데몬 종료 및 GPIO 정리"""
    global _daemon_running
    print("\n🛑 데몬 종료 신호를 수신했습니다. 정리 중...")
    _daemon_running = False
    controller.cleanup()
    print("👋 안전하게 종료되었습니다.")
    sys.exit(0)


def run_cli_interactive():
    """터미널 환경에서 백그라운드로 실행하며 터치 입력을 시뮬레이션할 수 있는 CLI 모드"""
    print("💡 [안내] 터미널 CLI 모드로 작동 중입니다.")
    print("   - 기상 확인 버튼 테스트: [Enter] 키를 누르세요.")
    print("   - 데몬 종료: Ctrl + C 를 누르세요.\n")

    try:
        while _daemon_running:
            line = sys.stdin.readline()
            if not line:
                time.sleep(1)
                continue
            # Enter 입력 시 터치 입력 이벤트 발송
            send_touch_pad_input(x=320, y=240, gesture="cli_button")
    except (KeyboardInterrupt, Exception):
        pass


def main():
    # SIGINT(Ctrl+C) 및 SIGTERM 안전 종료 바인딩
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    is_hw = isinstance(controller, RaspberryPi5HardwareController)
    mode_text = "라즈베리파이 5 실기기 (RP1 GPIO)" if is_hw else "PC Mock 시뮬레이터 (Sound/GUI)"

    print("\n" + "=" * 65)
    print(" [스마트 기상 시스템 - 라즈베리파이 5 하드웨어 데몬]")
    print("=" * 65)
    print(f" * 백엔드 URL: {BACKEND_URL}")
    print(f" * 디바이스 인증키: {DEVICE_API_KEY[:6]}****")
    print(f" * 현재 동작 모드: {mode_text}")
    print(f" * 핀 설정: 피에조 부저=GPIO {BUZZER_PIN}, 기상 버튼/터치센서=GPIO {BUTTON_PIN}")
    print(f" * 폴링 주기: {POLL_INTERVAL_SECONDS}초")
    print("=" * 65 + "\n")

    # 1. 백그라운드 폴링 스레드 시작
    poll_thread = threading.Thread(target=background_polling_loop, daemon=True)
    poll_thread.start()

    # 2. GUI 실행 시도 (데스크톱 X11/Wayland 디스플레이가 없으면 CLI 모드로 폴백)
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY") or sys.platform == "win32")
    gui_started = False

    if has_display:
        try:
            run_gui()
            gui_started = True
        except Exception as e:
            logger.info(f"GUI 실행 생략 (CLI 모드로 전환): {e}")

    if not gui_started:
        run_cli_interactive()

    shutdown()


if __name__ == "__main__":
    main()
