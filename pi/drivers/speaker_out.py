"""
speaker_out — 스피커로 알람음 내기 (부저 대신). 파이에 연결한 USB·HDMI 스피커로 소리를 냅니다.

`tonal_buzzer`와 **같은 값**({"frequency": 1000, "volume": 80})을 받으므로, 배치표에서
드라이버만 바꾸면 화면·백엔드·규칙은 그대로 둔 채 부저 대신 스피커가 울립니다.
켜져 있는 동안 소리를 **계속 반복**하고, 끄면 바로 멈춥니다.

slot_map.py 예시:
    "actuator_01": {"label": "알람 스피커", "kind": "speaker",
                    "driver": "speaker_out", "control_type": "tonal"},
                    # 핀이 필요 없습니다 (USB·HDMI 스피커)

옵션 (적지 않으면 기본값)
    "sound_file": "sounds/alarm.wav"   # 재생할 소리 파일 (pi 폴더 기준 경로, wav 권장).
                                       # 없으면 frequency Hz로 '삐-삐-삐' 경보음을 직접 만들어 냅니다.
    "player": "pw-play"                # 재생 프로그램 (기본: pw-play → paplay → aplay 중 있는 것)
    "device": None                     # 특정 스피커로 고정할 때 (보통 비워 둠)

준비 (라즈베리파이 5)
    - 파이 5에는 3.5mm 이어폰 단자가 없습니다 → **USB 스피커**나 HDMI 모니터 스피커를 쓰세요.
    - 바탕화면 오른쪽 위 스피커 아이콘을 우클릭해 출력 장치를 고르고,
      `speaker-test -c2 -t wav -l 1` 로 소리가 나는지 먼저 확인하세요.
    - 데몬은 **바탕화면에 로그인한 사용자와 같은 사용자**로 켜세요 (다른 사용자·sudo로 켜면 소리가 안 납니다).

브라우저(화면)에서 소리를 내지 않고 데몬이 내는 이유: 브라우저는 아무도 화면을 만지지 않으면
소리를 막고, 새로고침·화면 꺼짐에도 끊깁니다. 데몬은 화면과 상관없이 울립니다.
"""
import logging
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from typing import Any, Dict, List, Optional, Tuple

from drivers.base import ActuatorDriver

logger = logging.getLogger("pi.drivers.speaker_out")

DEFAULT_FREQUENCY = 1000
DEFAULT_VOLUME = 80
#: 재생 프로그램 찾는 순서 (파이 OS Bookworm 기본은 PipeWire → pw-play)
PLAYERS = ("pw-play", "paplay", "aplay")
#: 만든 경보음: 삐(0.25초)-쉼(0.15초) ×3, 마지막에 0.6초 쉼 → 약 1.65초 한 묶음을 반복
BEEP_SECONDS, GAP_SECONDS, BEEPS, PAUSE_SECONDS = 0.25, 0.15, 3, 0.6
SAMPLE_RATE = 22050
PI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_alarm_wav(path: str, frequency: float, volume: float) -> None:
    """frequency Hz '삐-삐-삐' 경보음 한 묶음을 16비트 모노 wav로 저장합니다. volume 0~100."""
    amplitude = int(32767 * max(0.0, min(100.0, volume)) / 100 * 0.9)
    frames = bytearray()

    def tone(seconds: float) -> None:
        count = int(SAMPLE_RATE * seconds)
        fade = max(1, int(SAMPLE_RATE * 0.005))       # 끝을 살짝 줄여 '딱' 소리를 없앰
        for i in range(count):
            env = min(1.0, i / fade, (count - 1 - i) / fade)
            frames.extend(struct.pack("<h", int(amplitude * env * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE))))

    def silence(seconds: float) -> None:
        frames.extend(b"\x00\x00" * int(SAMPLE_RATE * seconds))

    for n in range(BEEPS):
        tone(BEEP_SECONDS)
        silence(GAP_SECONDS if n < BEEPS - 1 else PAUSE_SECONDS)
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(bytes(frames))


def find_player(preferred: Optional[str] = None) -> Optional[str]:
    """쓸 수 있는 재생 프로그램 경로 (없으면 None)."""
    for name in ([preferred] if preferred else list(PLAYERS)):
        found = shutil.which(name) if name else None
        if found:
            return found
    return None


def player_command(player: str, path: str, volume: Optional[float], device: Optional[str]) -> List[str]:
    """재생 프로그램별 명령줄. volume은 파일 재생일 때만 (0~100, None이면 원래 크기)."""
    name = os.path.basename(player)
    cmd = [player]
    if name == "pw-play":
        if device:
            cmd += ["--target", str(device)]
        if volume is not None:
            cmd += ["--volume", f"{max(0.0, min(100.0, volume)) / 100:.2f}"]
    elif name == "paplay":
        if device:
            cmd += ["--device", str(device)]
        if volume is not None:
            cmd += ["--volume", str(int(65536 * max(0.0, min(100.0, volume)) / 100))]
    elif name == "aplay":
        cmd += ["-q"] + (["-D", str(device)] if device else [])
    return cmd + [path]


class Driver(ActuatorDriver):
    control_type = "tonal"

    def __init__(self, slot_id: str, config: Dict[str, Any]) -> None:
        super().__init__(slot_id, config)
        self.device_name = config.get("device") or None
        self.player = find_player(config.get("player"))
        if self.player is None:
            self.simulated = True     # 재생 프로그램이 없으면(PC 등) 로그만 남깁니다
            wanted = config.get("player") or " / ".join(PLAYERS)
            logger.warning(f"[{slot_id}] 재생 프로그램({wanted})이 없어 소리 없이 흉내만 냅니다.")
        self.sound_file: Optional[str] = None
        if config.get("sound_file"):
            path = str(config["sound_file"])
            path = path if os.path.isabs(path) else os.path.join(PI_DIR, path)
            if os.path.isfile(path):
                self.sound_file = path
            else:
                logger.warning(f"[{slot_id}] 소리 파일 {path}이 없어 경보음을 만들어 냅니다.")
        if os.path.basename(self.player or "") == "aplay" and self.sound_file:
            logger.info(f"[{slot_id}] aplay는 볼륨을 못 바꿉니다 — 소리 크기는 파일·시스템 볼륨을 따릅니다.")
        self._tone_path = os.path.join(tempfile.gettempdir(), f"speaker_out_{slot_id}.wav")
        self._playing: Optional[Tuple[float, float]] = None   # (frequency, volume) — 같은 값이면 다시 시작 안 함
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def apply(self, state: Optional[str], value: Any = None) -> str:
        if not self.is_on(state):
            if self._playing is not None:
                self._stop_playing()
                logger.info(f"[{self.slot_id}] {self.label} → off")
            return "off"

        frequency = max(50.0, min(8000.0, self.number_from(value, "frequency", DEFAULT_FREQUENCY)))
        volume = max(0.0, min(100.0, self.number_from(value, "volume", DEFAULT_VOLUME)))
        wanted = (frequency, volume) if not self.sound_file else (0.0, volume)
        if self._playing == wanted:      # 이미 같은 소리를 내는 중 (데몬은 매번 같은 값을 다시 보냅니다)
            return "on"

        self._stop_playing()
        if self.sound_file:
            path, player_volume, what = self.sound_file, volume, os.path.basename(self.sound_file)
        else:
            make_alarm_wav(self._tone_path, frequency, volume)
            path, player_volume, what = self._tone_path, None, f"{frequency:.0f}Hz 경보음"
        self._playing = wanted
        if not self.simulated:
            cmd = player_command(self.player, path, player_volume, self.device_name)
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, args=(cmd,), daemon=True)
            self._thread.start()
        logger.info(f"[{self.slot_id}] {self.label} → on (스피커, {what}, 볼륨 {volume:.0f})"
                    + (" — 흉내내기" if self.simulated else ""))
        return "on"

    def _loop(self, cmd: List[str]) -> None:
        """끌 때까지 소리를 반복 재생합니다."""
        failures = 0
        while not self._stop.is_set():
            try:
                with self._lock:
                    if self._stop.is_set():
                        return
                    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    self._proc = proc
                _, err = proc.communicate()
                code = proc.returncode
            except Exception as exc:
                logger.warning(f"[{self.slot_id}] 재생을 시작하지 못했습니다: {exc}")
                return
            if self._stop.is_set():
                return
            if code != 0:
                failures += 1
                message = (err or b"").decode(errors="ignore").strip().splitlines()
                if failures >= 3:
                    logger.warning(
                        f"[{self.slot_id}] 소리 재생이 계속 실패합니다 ({message[-1] if message else f'종료 코드 {code}'}). "
                        "스피커 연결·출력 장치 선택과, 데몬을 바탕화면 사용자로 켰는지 확인하세요."
                    )
                    return
                self._stop.wait(0.5)
            else:
                failures = 0

    def _stop_playing(self) -> None:
        self._playing = None
        self._stop.set()
        with self._lock:
            proc = self._proc
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self._proc = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def close(self) -> None:
        self._stop_playing()
        try:
            os.remove(self._tone_path)
        except OSError:
            pass
