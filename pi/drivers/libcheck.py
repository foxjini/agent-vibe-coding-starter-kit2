"""
부품 라이브러리 점검 (pi/drivers/libcheck.py) — 키트 제공, 수정하지 마세요.
=============================================================================
네오픽셀(neopixel_out)·온습도(dht_in)는 gpiozero가 아니라 Adafruit 라이브러리(Blinka)로,
AHT20 온습도(aht20_in)는 smbus2(I2C)로 움직입니다. 라이브러리가 없으면 데몬은 멈추지 않고 그 슬롯만 '흉내내기'로 돌아가는데,
실제 파이에서는 "대시보드는 동작 중인데 부품은 가만히 있는" 헷갈리는 상태가 됩니다.

그래서 실제 라즈베리파이에서는 시작할 때(그리고 `--check`에서) 미리 확인하고,
무엇이 없는지와 **그대로 복사해 쓸 설치 명령**을 "고쳐야 할 것"에 보여 줍니다.
PC(흉내내기)에서는 확인하지 않습니다.
"""
import importlib
import importlib.util
import os
import shlex
from typing import Any, Dict, List

# Blinka 최신판은 `import board` 순간 빠진 라이브러리를 "설치할까요? [Y/n]" 하고 묻습니다.
# SSH 창에서 데몬을 켜면 그 질문에서 멈추므로 끄고, 대신 아래 점검이 설치 명령을 알려 줍니다.
os.environ.setdefault("BLINKA_SKIP_DEPENDENCY_CHECK", "1")

#: 드라이버 → (부품 이름, 불러올 모듈, pip 패키지)
NEEDS = {
    "neopixel_out": ("네오픽셀", "neopixel", "adafruit-circuitpython-neopixel"),
    "dht_in": ("온습도", "adafruit_dht", "adafruit-circuitpython-dht"),
    "aht20_in": ("온습도(AHT20)", "smbus2", "smbus2"),
}
#: Blinka(adafruit) 라이브러리를 쓰는 드라이버 — 이것을 쓸 때만 Blinka 의존성을 봅니다
BLINKA_DRIVERS = ("neopixel_out", "dht_in")
#: I2C를 쓰는 드라이버 — 파이에서 I2C가 켜져 있는지 봅니다
I2C_DRIVERS = ("aht20_in",)

#: Blinka가 함께 권하지만 이 키트의 드라이버에는 필요 없는 것 (파이에서 컴파일이 필요할 수 있음)
_NOT_NEEDED = ("adafruit-blinka-raspberry-pi-pwm", "rpi_ws281x", "rpi-ws281x")
#: 파이 5 네오픽셀 라이브러리 (아직 정식판이 없어 --pre로 설치)
_PI5_NEOPIXEL = "Adafruit-Blinka-Raspberry-Pi5-Neopixel"


def _model() -> str:
    """보드 이름 (예: "Raspberry Pi 5 Model B Rev 1.0"). 파이가 아니면 빈 문자열."""
    # /proc/device-tree는 /sys/firmware/devicetree/base를 가리키는 링크입니다
    for path in ("/sys/firmware/devicetree/base/model", "/proc/device-tree/model"):
        try:
            with open(path, "rb") as f:
                return f.read().decode(errors="ignore").strip("\x00 \n")
        except OSError:
            continue
    return ""


def on_raspberry_pi() -> bool:
    """이 컴퓨터가 라즈베리파이인지 (PC에서는 False)."""
    return "Raspberry Pi" in _model()


def is_pi5() -> bool:
    """라즈베리파이 5 / 500 인지."""
    return "Raspberry Pi 5" in _model()


def first_line(exc: BaseException) -> str:
    """예외 메시지의 첫 줄 (없으면 예외 이름)."""
    lines = str(exc).strip().splitlines()
    return lines[0] if lines else type(exc).__name__


def _blinka_missing() -> List[str]:
    """Blinka가 '이 파이에 필요한데 없거나 오래됐다'고 보는 pip 요구사항 목록."""
    try:
        from adafruit_blinka.agnostic import detector
        from adafruit_blinka.platform_dependencies import get_missing_platform_dependencies
    except Exception:
        return []          # Blinka가 없거나 옛 버전 — 아래 import 점검이 대신 알려 줍니다
    try:
        return list(get_missing_platform_dependencies(detector))
    except Exception:
        return []


def _pip(packages: List[str], pre: bool = False) -> str:
    args = ["pip", "install"] + (["--pre"] if pre else []) + packages
    return " ".join(shlex.quote(a) for a in args)


def check_libraries(slot_configs: Dict[str, Dict[str, Any]]) -> List[str]:
    """배치표에 적은 부품의 라이브러리를 실제 파이에서 쓸 수 있는지 확인합니다.

    돌려주는 것: 사람이 읽는 문제 줄 목록 (문제가 없거나 PC면 빈 목록)
    """
    used: Dict[str, List[str]] = {}
    for slot_id, config in slot_configs.items():
        driver = config.get("driver")
        if driver in NEEDS:
            used.setdefault(driver, []).append(slot_id)
    if not on_raspberry_pi():
        return []

    problems: List[str] = []
    install: List[str] = []
    install_pre: List[str] = []

    for driver, slot_ids in used.items():
        name, module, package = NEEDS[driver]
        try:
            importlib.import_module(module)
        except Exception as exc:
            problems.append(
                f"{', '.join(slot_ids)} {name}: 라이브러리를 쓸 수 없어 실제 부품 대신 흉내내기로 돕니다 "
                f"— {first_line(exc)}"
            )
            if importlib.util.find_spec(module) is None:
                install.append(package)

    speaker_slots = [sid for sid, cfg in slot_configs.items() if cfg.get("driver") == "speaker_out"]
    if speaker_slots:
        import shutil
        wanted = {cfg.get("player") for sid, cfg in slot_configs.items() if sid in speaker_slots} - {None}
        names = sorted(wanted) if wanted else ["pw-play", "paplay", "aplay"]
        if not any(shutil.which(name) for name in names):
            problems.append(
                f"{', '.join(speaker_slots)} 스피커: 재생 프로그램({' / '.join(names)})이 없어 소리 없이 흉내만 냅니다 → "
                "sudo apt install -y pipewire-bin alsa-utils"
            )

    if any(driver in used for driver in I2C_DRIVERS):
        buses = {int(cfg.get("i2c_bus", 1)) for cfg in slot_configs.values() if cfg.get("driver") in I2C_DRIVERS}
        for bus in sorted(buses):
            if not os.path.exists(f"/dev/i2c-{bus}"):
                problems.append(
                    f"I2C: /dev/i2c-{bus}이 없습니다 (I2C가 꺼져 있음) → "
                    "sudo raspi-config → Interface Options → I2C → Yes → sudo reboot"
                )

    blinka_missing = _blinka_missing() if any(d in used for d in BLINKA_DRIVERS) else []
    for requirement in blinka_missing:
        low = requirement.lower()
        if low.startswith(_NOT_NEEDED):
            continue
        if low.startswith(_PI5_NEOPIXEL.lower()):
            if "neopixel_out" in used:
                install_pre.append(_PI5_NEOPIXEL)
            continue
        install.append(requirement)

    if "neopixel_out" in used and is_pi5():
        if importlib.util.find_spec("adafruit_raspberry_pi5_neopixel_write") is None \
                and _PI5_NEOPIXEL not in install_pre:
            install_pre.append(_PI5_NEOPIXEL)
        if not os.path.exists("/dev/pio0"):
            problems.append(
                "네오픽셀: /dev/pio0이 없습니다 (파이 5 펌웨어가 오래됨) → "
                "sudo apt update && sudo apt full-upgrade -y && sudo rpi-eeprom-update -a 후 sudo reboot"
            )
        elif not os.access("/dev/pio0", os.R_OK | os.W_OK):
            problems.append(
                "네오픽셀: /dev/pio0을 쓸 권한이 없습니다 → "
                "/etc/udev/rules.d/99-pio.rules에 SUBSYSTEM==\"*-pio\", GROUP=\"gpio\", MODE=\"0660\" 한 줄을 넣고 sudo reboot"
            )

    install = list(dict.fromkeys(install))
    if (install or install_pre) and not problems:
        problems.append("네오픽셀·온습도(DHT·AHT20) 라이브러리 중 없거나 오래된 것이 있습니다 (아래 명령으로 설치)")
    if install:
        problems.append(f"설치 — (venv)가 켜진 파이 터미널에서: {_pip(install)}")
    if install_pre:
        problems.append(f"설치 — 이어서: {_pip(install_pre, pre=True)}")
    if install or install_pre:
        problems.append("설치한 뒤: python daemon.py --check 로 이 줄들이 사라졌는지 확인 → 데몬 다시 켜기")
    return problems
