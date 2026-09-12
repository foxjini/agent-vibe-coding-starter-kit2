"""
카메라 열기 (vision/camera.py) — 키트 제공, 수정하지 마세요.
=============================================================================
팀마다 카메라가 다릅니다.

  USB 웹캠 (PC)            cv2.VideoCapture  ← wakeup · classroom · study
  Pi Camera (라즈베리파이)   picamera2         ← subway (객차 Pi Camera 3)

라즈베리파이 OS Bookworm부터는 CSI 카메라(Pi Camera)가 `cv2.VideoCapture(0)`으로
열리지 않는 경우가 많습니다. 예전 카메라 스택이 빠지고 libcamera로 바뀌었기 때문입니다.
그래서 **picamera2가 설치되어 있으면 먼저 그쪽을 시도**합니다.

  .env의 CAMERA_SOURCE로 직접 고를 수도 있습니다:
      auto (기본) / usb / picamera
"""
import logging
import os
from typing import Any, Optional, Tuple

import cv2

logger = logging.getLogger("vision.camera")

DEFAULT_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
DEFAULT_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))


class Camera:
    """카메라 한 대. `read()`가 (성공여부, 프레임)을 돌려줍니다."""

    def __init__(self, backend: str, handle: Any, description: str):
        self.backend = backend          # "usb" | "picamera"
        self._handle = handle
        self.description = description

    def read(self) -> Tuple[bool, Any]:
        if self.backend == "picamera":
            try:
                frame = self._handle.capture_array()
            except Exception as exc:
                logger.warning(f"Pi Camera 프레임을 읽지 못했습니다: {exc}")
                return False, None
            # picamera2는 RGB로 주고 OpenCV는 BGR을 씁니다
            return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return self._handle.read()

    def release(self) -> None:
        try:
            if self.backend == "picamera":
                self._handle.stop()
                self._handle.close()
            else:
                self._handle.release()
        except Exception:
            pass


def _try_picamera(width: int, height: int) -> Optional[Camera]:
    try:
        from picamera2 import Picamera2
    except Exception:
        return None    # 라즈베리파이가 아니거나 설치되지 않음 — 조용히 넘어갑니다

    try:
        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        ))
        camera.start()
        logger.info(f"Pi Camera로 열었습니다 ({width}x{height}).")
        return Camera("picamera", camera, f"Pi Camera {width}x{height}")
    except Exception as exc:
        logger.warning(f"picamera2가 있지만 카메라를 열지 못했습니다: {exc}")
        return None


def _try_usb(index: int, width: int, height: int) -> Optional[Camera]:
    # 윈도우에서는 DirectShow 백엔드로 열어야 안정적입니다
    capture = None
    if os.name == "nt":
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            logger.warning("CAP_DSHOW로 열기 실패, 기본 백엔드로 재시도합니다.")
            capture.release()
            capture = cv2.VideoCapture(index)
    else:
        capture = cv2.VideoCapture(index)

    if not capture or not capture.isOpened():
        if capture:
            capture.release()
        return None

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    logger.info(f"USB 웹캠(인덱스 {index})으로 열었습니다.")
    return Camera("usb", capture, f"USB 웹캠 #{index}")


def open_camera(
    index: int = 0,
    source: str = "auto",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> Optional[Camera]:
    """
    카메라를 엽니다. 열지 못하면 None과 함께 원인별 안내를 로그로 남깁니다.

    source: auto(기본) — picamera2가 있으면 먼저 시도하고, 없으면 USB 웹캠
            usb       — USB 웹캠만
            picamera  — Pi Camera만
    """
    source = (source or "auto").strip().lower()

    if source in ("auto", "picamera"):
        camera = _try_picamera(width, height)
        if camera:
            return camera
        if source == "picamera":
            logger.error(
                "Pi Camera를 열지 못했습니다. 라즈베리파이에서 아래를 확인하세요.\n"
                "  1) 리본 케이블이 제대로 꽂혔는지 (파란 면 방향 주의)\n"
                "  2) picamera2 설치: sudo apt install -y python3-picamera2\n"
                "  3) 인식 확인: rpicam-hello --list-cameras\n"
                "  4) 가상환경이면 --system-site-packages로 만들어야 picamera2가 보입니다"
            )
            return None

    if source in ("auto", "usb"):
        camera = _try_usb(index, width, height)
        if camera:
            return camera

    logger.error(
        f"카메라를 열지 못했습니다 (source={source}, index={index}).\n"
        "  · USB 웹캠이면: 연결을 확인하고, 다른 프로그램이 쓰고 있지 않은지 보세요.\n"
        "    카메라가 여러 대면 .env의 CAMERA_INDEX를 1, 2로 바꿔 보세요.\n"
        "  · 라즈베리파이의 Pi Camera면: .env에 CAMERA_SOURCE=picamera를 넣고\n"
        "    sudo apt install -y python3-picamera2 를 설치하세요."
    )
    return None
