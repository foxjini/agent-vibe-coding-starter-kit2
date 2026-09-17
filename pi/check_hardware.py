"""라즈베리파이 실기기 사전 점검 — `python main.py`가 왜 안 뜨는지 찾아 준다.

실기기에서 나는 오류는 트레이스백만 보면 원인이 잘 안 보인다. 같은
`ModuleNotFoundError`라도 "설치를 안 했다"와 "설치는 했는데 venv가 못 본다"는
고치는 방법이 전혀 다르고, 파이 5에서는 후자가 훨씬 흔하다.

그래서 데몬을 띄우기 전에 한 줄씩 확인한다. **서보는 움직이지 않는다** —
`--servo`를 직접 붙였을 때만 움직이며, 그때도 교사 입회 하에 한다
(`hardware-rules.md` 안전 수칙).

    cd pi
    python check_hardware.py           # 확인만 한다 (안전)
    python check_hardware.py --servo   # 게이트를 한 번 여닫아 본다
"""
import os
import sys
import textwrap
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent / "backend"
for path in (CURRENT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

OK = "  OK  "
FAIL = " 실패 "
WARN = " 주의 "

problems: list[str] = []


def report(status: str, title: str, detail: str = "", fix: str = "") -> None:
    print(f"[{status}] {title}" + (f" — {detail}" if detail else ""))
    if fix:
        for line in textwrap.dedent(fix).strip().splitlines():
            print(f"         {line}")
    if status == FAIL:
        problems.append(title)


def head(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))


# ── 1. 파이썬과 실행 환경 ────────────────────────────────────────────────────
def check_python() -> None:
    head("1. 파이썬 실행 환경")
    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info < (3, 10):
        report(FAIL, f"파이썬 {version}", "3.10 미만",
               fix="이 코드는 `int | None` 문법을 쓰므로 3.10 이상이 필요합니다.\n"
                   "라즈베리파이 OS(Bookworm 3.11 / Trixie 3.13)의 python3로 실행하세요.")
    else:
        report(OK, f"파이썬 {version}", sys.executable)

    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        report(WARN, "가상환경(venv) 밖에서 실행 중", sys.prefix,
               fix="최근 라즈베리파이 OS(Bookworm·Trixie)는 시스템 파이썬에 pip 설치를 막습니다\n"
                   "(externally-managed-environment).")
        return

    # 파이 5에서 가장 흔한 함정: apt로 깐 lgpio를 venv가 못 본다
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    sees_system = False
    if cfg.exists():
        for line in cfg.read_text(errors="ignore").splitlines():
            if line.lower().replace(" ", "").startswith("include-system-site-packages="):
                sees_system = line.strip().lower().endswith("true")
    if sees_system:
        report(OK, "venv가 시스템 패키지를 함께 봄", "--system-site-packages")
    else:
        report(WARN, "venv가 시스템 패키지를 못 봄",
               "include-system-site-packages = false",
               fix="apt로 설치한 python3-lgpio / python3-gpiozero 가 이 venv 안에서는 보이지 않습니다.\n"
                   "파이 5에서는 보통 이렇게 다시 만듭니다:\n"
                   "  rm -rf venv && python3 -m venv --system-site-packages venv")


# ── 2. 저장소 구조 ──────────────────────────────────────────────────────────
def check_layout() -> None:
    head("2. 저장소 구조")
    if not BACKEND_DIR.exists():
        report(FAIL, "backend/ 폴더를 찾을 수 없음", str(BACKEND_DIR),
               fix="pi/ 폴더만 복사하면 안 됩니다. 저장소를 통째로 받으세요.\n"
                   "  git clone <저장소 주소>\n"
                   "backend/ 전체가 부담스러우면 iot/ 하나만 옮겨도 됩니다 —\n"
                   "iot/ 는 표준 라이브러리만 쓰므로 아래 구조면 충분합니다:\n"
                   "  <상위폴더>/pi/ 와 <상위폴더>/backend/iot/")
        return
    try:
        from iot.provider_factory import create_provider  # noqa: F401
        report(OK, "iot 모듈 import 가능", str(BACKEND_DIR))
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "iot 모듈을 불러오지 못함", f"{type(exc).__name__}: {exc}",
               fix="backend/ 와 pi/ 가 같은 상위 폴더에 나란히 있어야 합니다.")


# ── 3. .env 설정 ────────────────────────────────────────────────────────────
def check_env() -> None:
    head("3. pi/.env 설정")
    env_path = CURRENT_DIR / ".env"
    if not env_path.exists():
        report(FAIL, ".env 파일이 없음", str(env_path),
               fix="cp .env.example .env 로 만들고 값을 채우세요.")
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        report(OK, ".env 읽음", str(env_path))
    except ImportError:
        report(FAIL, "python-dotenv 미설치", fix="pip install python-dotenv")
        return

    mode = os.getenv("DEVICE_MODE", "mock").strip().lower()
    report(OK if mode in ("mock", "hardware") else FAIL, f"DEVICE_MODE={mode or '(비어 있음)'}",
           "실기기" if mode == "hardware" else "시뮬레이터",
           fix="" if mode in ("mock", "hardware") else "mock 또는 hardware 여야 합니다.")

    url = os.getenv("BACKEND_URL", "").strip()
    if not url:
        report(FAIL, "BACKEND_URL이 비어 있음", fix="BACKEND_URL=http://<백엔드 PC의 IP>:8000")
    elif "localhost" in url or "127.0.0.1" in url:
        report(WARN, f"BACKEND_URL={url}", "파이에서 localhost는 파이 자신을 뜻합니다",
               fix="백엔드가 다른 PC에 있다면 그 PC의 실제 IP로 바꾸세요.")
    else:
        report(OK, f"BACKEND_URL={url}")

    key = os.getenv("DEVICE_API_KEY", "").strip()
    report(OK if key else FAIL, "DEVICE_API_KEY", f"{len(key)}자" if key else "비어 있음",
           fix="" if key else "backend/.env의 DEVICE_API_KEY와 **같은 값**을 넣으세요.")

    if mode == "hardware":
        factory = os.getenv("GPIOZERO_PIN_FACTORY", "").strip()
        report(OK if factory == "lgpio" else WARN, f"GPIOZERO_PIN_FACTORY={factory or '(없음)'}",
               fix="" if factory == "lgpio" else "파이 5(RP1 칩)에서는 lgpio가 필요합니다.")


# ── 4. GPIO ─────────────────────────────────────────────────────────────────
def check_gpio(move_servo: bool) -> None:
    head("4. GPIO (DEVICE_MODE=hardware일 때만 필요)")
    if os.getenv("DEVICE_MODE", "mock").strip().lower() != "hardware":
        report(OK, "mock 모드 — GPIO 점검 건너뜀")
        return

    try:
        import gpiozero
        report(OK, f"gpiozero {gpiozero.__version__}")
    except ImportError as exc:
        report(FAIL, "gpiozero 미설치", str(exc),
               fix="라즈베리파이 OS 데스크톱 이미지에는 보통 이미 깔려 있습니다.\n"
                   "먼저 venv 밖에서 보이는지 확인하세요:\n"
                   "  /usr/bin/python3 -c 'import gpiozero, lgpio; print(\"있음\")'\n"
                   "→ '있음'이 나오면 설치 문제가 아니라 venv가 못 보는 것입니다:\n"
                   "  rm -rf venv && python3 -m venv --system-site-packages venv\n"
                   "→ 거기서도 안 되면 그때 설치합니다:\n"
                   "  sudo apt install -y python3-gpiozero python3-lgpio")
        return

    try:
        import lgpio  # noqa: F401
        report(OK, "lgpio 사용 가능")
    except ImportError as exc:
        report(FAIL, "lgpio 미설치", str(exc),
               fix="위와 같습니다 — venv가 시스템 패키지를 보는지 먼저 확인하세요.\n"
                   "정말 없을 때만:  sudo apt install -y python3-lgpio\n"
                   "파이 5는 GPIO 칩이 달라(RP1) 예전 RPi.GPIO로는 동작하지 않습니다.")

    try:
        from gpiozero import Device
        factory = Device._default_pin_factory()
        report(OK, "핀 팩토리 준비됨", type(factory).__name__)
        close = getattr(factory, "close", None)
        if callable(close):
            close()
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "핀 팩토리를 열지 못함", f"{type(exc).__name__}: {exc}",
               fix="1) lgpio 설치 여부 (위 줄)\n"
                   "2) 권한 — 사용자가 gpio 그룹에 있어야 합니다:\n"
                   "     sudo usermod -aG gpio $USER   (그 뒤 다시 로그인)\n"
                   "3) 이미 떠 있는 ATM 데몬이 같은 핀을 잡고 있지는 않은지")
        return

    if not move_servo:
        gate = os.getenv("SERVO_GATE_PIN", "18")
        pusher = os.getenv("SERVO_PUSHER_PIN", "19")
        report(OK, f"서보 핀 설정 확인 (gate=GPIO{gate}, pusher=GPIO{pusher})",
               "실제 동작은 --servo 를 붙였을 때만 합니다")
        return

    try:
        from gpiozero import AngularServo
        gate_pin = int(os.getenv("SERVO_GATE_PIN", "18"))
        servo = AngularServo(gate_pin, min_angle=0, max_angle=180)
        print(f"         GPIO{gate_pin} 게이트를 90도로 엽니다...")
        servo.angle = 90
        import time
        time.sleep(1.0)
        servo.angle = 0
        time.sleep(0.5)
        servo.close()
        report(OK, f"서보 동작 확인 (GPIO{gate_pin})", "실제로 움직였는지 눈으로 확인하세요")
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "서보를 움직이지 못함", f"{type(exc).__name__}: {exc}",
               fix="MG996R은 별도 5V 전원이 필요합니다. 파이 5V 핀으로 직접 구동하면\n"
                   "전압이 떨어져 파이가 재부팅되거나 서보가 떨리기만 합니다.\n"
                   "접지(GND)를 파이와 외부 전원이 **함께** 쓰는지도 확인하세요.")


# ── 5. 카메라 ───────────────────────────────────────────────────────────────
def check_camera() -> None:
    head("5. 카메라 (ENABLE_CAMERA=true일 때만 필요)")
    if os.getenv("ENABLE_CAMERA", "true").strip().lower() == "false":
        report(OK, "ENABLE_CAMERA=false — 카메라 점검 건너뜀", "POST /qr 로 시연합니다")
        return

    try:
        import cv2
        report(OK, f"opencv {cv2.__version__}")
    except ImportError as exc:
        report(FAIL, "cv2를 불러오지 못함", str(exc),
               fix="libGL.so.1 같은 시스템 라이브러리가 없을 때 자주 납니다:\n"
                   "  sudo apt install -y libgl1 libglib2.0-0\n"
                   "그래도 안 되면 데스크톱 라이브러리가 필요 없는 쪽으로 바꿉니다:\n"
                   "  pip uninstall -y opencv-python && pip install opencv-python-headless")
        return

    devices = sorted(str(p) for p in Path("/dev").glob("video*"))
    if devices:
        report(OK, "비디오 장치 발견", ", ".join(devices))
    else:
        report(WARN, "/dev/video* 장치가 없음",
               fix="파이 카메라 모듈(CSI)은 최근 라즈베리파이 OS에서 cv2.VideoCapture로 열리지 않습니다.\n"
                   "USB 웹캠을 쓰거나, 카메라 없이 시연하려면 .env에 ENABLE_CAMERA=false")

    no_device_fix = (
        "USB 웹캠이 꽂혀 있는지 확인하세요 (lsusb 로 보입니다).\n"
        "파이 카메라 모듈(CSI)은 cv2.VideoCapture로 열리지 않습니다.\n"
        "카메라 없이 먼저 시연하려면 .env에 ENABLE_CAMERA=false 를 넣고 POST /qr 로 진행합니다."
    )
    index_fix = "CAMERA_INDEX를 1, 2로 바꿔 보세요. 위 장치 목록의 번호와 맞춥니다."

    index = int(os.getenv("CAMERA_INDEX", "0"))
    try:
        capture = cv2.VideoCapture(index)
        if not capture.isOpened():
            capture.release()
            report(FAIL, f"카메라를 열지 못함 (CAMERA_INDEX={index})",
                   fix=index_fix if devices else no_device_fix)
            return
        ok, frame = capture.read()
        capture.release()
        if ok and frame is not None:
            report(OK, f"카메라 영상 읽기 성공 (CAMERA_INDEX={index})", f"{frame.shape[1]}x{frame.shape[0]}")
        else:
            report(FAIL, "카메라는 열렸지만 영상이 안 들어옴",
                   fix="다른 프로그램이 카메라를 쓰고 있는지 확인하세요.")
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "카메라 점검 중 오류", f"{type(exc).__name__}: {exc}")


# ── 6. 백엔드 연결 ──────────────────────────────────────────────────────────
def check_backend() -> None:
    head("6. 백엔드 연결")
    try:
        import requests
    except ImportError:
        report(FAIL, "requests 미설치", fix="pip install requests")
        return

    url = os.getenv("BACKEND_URL", "").strip().rstrip("/")
    if not url:
        report(FAIL, "BACKEND_URL이 없어 확인할 수 없음")
        return

    try:
        health = requests.get(f"{url}/health", timeout=5)
        report(OK if health.ok else FAIL, f"GET {url}/health", f"HTTP {health.status_code}")
    except Exception as exc:  # noqa: BLE001
        report(FAIL, f"백엔드에 닿지 못함 ({url})", f"{type(exc).__name__}",
               fix="1) 백엔드가 0.0.0.0으로 떠 있는지:\n"
                   "     uvicorn main:app --host 0.0.0.0 --port 8000\n"
                   "2) 파이에서 핑이 되는지: ping <백엔드 IP>\n"
                   "3) PC 방화벽이 8000 포트를 막고 있지는 않은지")
        return

    # 키가 맞는지는 ATM 전용 엔드포인트로만 알 수 있다 (401이면 키, 404면 키는 맞음)
    try:
        probe = requests.get(
            f"{url}/api/v1/atm/verify/CHECK-0000",
            headers={"X-Device-Api-Key": os.getenv("DEVICE_API_KEY", "")},
            timeout=5,
        )
        if probe.status_code in (401, 403):
            report(FAIL, "디바이스 키를 서버가 거부함", f"HTTP {probe.status_code}",
                   fix="pi/.env와 backend/.env의 DEVICE_API_KEY를 **같은 값**으로 맞추고\n"
                       "백엔드와 데몬을 모두 다시 켜세요 (시작할 때 한 번만 읽습니다).")
        else:
            report(OK, "디바이스 키 통과", f"HTTP {probe.status_code} (없는 세션이므로 404가 정상)")
    except Exception as exc:  # noqa: BLE001
        report(FAIL, "디바이스 키 확인 실패", f"{type(exc).__name__}: {exc}")


def main() -> int:
    move_servo = "--servo" in sys.argv
    print("=" * 64)
    print(" 스마트 금융 보안 ATM — 라즈베리파이 사전 점검")
    if move_servo:
        print(" ⚠ --servo: 서보를 실제로 움직입니다. 교사 입회 하에 진행하세요.")
    print("=" * 64)

    check_python()
    check_layout()
    check_env()
    check_gpio(move_servo)
    check_camera()
    check_backend()

    print("\n" + "=" * 64)
    if problems:
        print(f"실패 {len(problems)}건: " + ", ".join(problems))
        print("위 [실패] 줄 아래의 안내를 위에서부터 차례로 고치세요.")
        return 1
    print("전부 통과 — python main.py 로 ATM 데몬을 켜도 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
