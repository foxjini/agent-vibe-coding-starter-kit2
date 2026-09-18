"""QR 인식 — opencv-python의 cv2.QRCodeDetector만 사용한다.

qr-recognition-integration 스킬: zbar/pyzbar 같은 별도 시스템 라이브러리를 설치하지
않아도 되도록 OpenCV 내장 디텍터를 쓴다 (Windows/라즈베리파이 설치 부담 최소화).

카메라 없이도 동작을 검증할 수 있게 정지 이미지 디코딩 함수를 함께 둔다
(PRD 5.6 권장: 먼저 정지 이미지/웹캠으로 검증한 뒤 ATM UI와 통합한다).
"""
import logging
import os
import sys
import time
from collections.abc import Callable
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 런타임에는 cv2를 함수 안에서만 import한다 (설치 부담 최소화)
    import cv2

logger = logging.getLogger("qr_scanner")

# 같은 QR을 연속으로 읽어 중복 처리하지 않도록 두는 최소 간격
SAME_CODE_COOLDOWN_SECONDS = 3.0
FRAME_INTERVAL_SECONDS = 0.1

# 카메라 백엔드를 강제할 때 쓰는 환경변수 (.env의 CAMERA_BACKEND)
CAMERA_BACKEND_ENV = "CAMERA_BACKEND"
CAMERA_BACKEND_AUTO = "auto"

# 인식에 쓸 해상도. **카메라 기본값에 맡기지 않는다.**
#
# QR 검출 비용은 화소 수에 거의 비례한다. 실측(같은 CPU, 프레임 한 장 기준):
#     640x480 → 6~12ms,  1280x720 → 24~41ms,  1920x1080 → 52~62ms
# 0.1초마다 한 장을 보므로 640x480이면 한 코어의 10~30% 정도만 쓰지만,
# 1080p로 들어오는 웹캠을 만나면 한 장 처리가 루프 주기에 육박해 인식이 밀린다.
# QR은 화면의 1/3만 차지해도 640x480에서 충분히 읽히므로 굳이 키울 이유가 없다.
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))

# 드라이버가 쌓아 두는 프레임 수. 1로 두면 항상 '가장 최근 화면'을 본다 —
# 우리는 초당 10장만 꺼내 쓰므로, 버퍼가 깊으면 이미 치운 QR을 뒤늦게 읽는다.
CAPTURE_BUFFER_FRAMES = 1

# 어느 번호가 진짜 카메라인지 찾을 때 훑어볼 범위
CAMERA_PROBE_MAX = 6

# '진짜 영상인가'를 확인할 때 연속으로 받아 볼 장 수.
# 한 장만 보면 속는다 — V4L2가 거부한 장치를 다른 백엔드가 억지로 열면 첫 장은
# 그럴듯하게 주고 그 뒤로 아무것도 안 오는 경우가 있다.
CAMERA_TEST_FRAMES = 3


def decode_image_file(path: str) -> str | None:
    """이미지 파일 한 장에서 QR 문자열을 읽는다. 없으면 None."""
    import cv2

    image = cv2.imread(path)
    if image is None:
        raise FileNotFoundError(f"이미지를 열 수 없습니다: {path}")
    data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(image)
    return data or None


def _backend_candidates(cv2_module: ModuleType) -> list[tuple[str, int]]:
    """열어 볼 OpenCV 카메라 백엔드를 순서대로 돌려준다.

    Windows 기본 백엔드(MSMF)는 웹캠을 여는 데 5~10초가 걸리거나 아무 메시지 없이
    실패하는 일이 잦다. 그래서 Windows에서는 DSHOW를 먼저 시도하고, 안 되면 OpenCV
    기본값으로 되돌아간다. 라즈베리파이/리눅스는 기본값이 잘 동작하므로 그대로 둔다.

    `.env`에 `CAMERA_BACKEND=dshow`처럼 적으면 그 백엔드 하나만 쓴다.
    """
    named: dict[str, int | None] = {
        "dshow": getattr(cv2_module, "CAP_DSHOW", None),
        "msmf": getattr(cv2_module, "CAP_MSMF", None),
        "v4l2": getattr(cv2_module, "CAP_V4L2", None),
        "any": cv2_module.CAP_ANY,
    }

    requested = os.getenv(CAMERA_BACKEND_ENV, CAMERA_BACKEND_AUTO).strip().lower()
    if requested and requested != CAMERA_BACKEND_AUTO:
        api = named.get(requested)
        if api is None:
            raise ValueError(
                f"{CAMERA_BACKEND_ENV}={requested} 는 이 환경에서 쓸 수 없는 값입니다. "
                f"가능한 값: {', '.join(named)}, {CAMERA_BACKEND_AUTO}"
            )
        return [(requested, api)]

    dshow = named["dshow"]
    if sys.platform == "win32" and dshow is not None:
        return [("dshow", dshow), ("any", cv2_module.CAP_ANY)]

    # 리눅스(라즈베리파이)에서는 V4L2가 정식 경로다. 먼저 이름 붙여 시도하면
    # 로그의 backend= 값만 보고 "제대로 된 영상 장치인가"를 바로 알 수 있다.
    # V4L2가 거부하면 다른 백엔드가 억지로 여는 수가 있는데, 그건 대개 영상
    # 장치가 아니다 (그래서 아래에서 경고를 남긴다).
    v4l2 = named["v4l2"]
    if v4l2 is not None:
        return [("v4l2", v4l2), ("any", cv2_module.CAP_ANY)]
    return [("any", cv2_module.CAP_ANY)]


def _tune_capture(cv2_module: ModuleType, capture: "cv2.VideoCapture") -> tuple[int, int]:
    """해상도와 버퍼 깊이를 지정하고, 카메라가 실제로 준 해상도를 돌려준다.

    지원하지 않는 백엔드/드라이버가 있으므로 실패해도 그냥 넘어간다 —
    인식이 조금 느려질 뿐, 카메라를 못 쓰게 만들 일은 아니다.
    """
    for prop, value in (
        (cv2_module.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH),
        (cv2_module.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT),
        (getattr(cv2_module, "CAP_PROP_BUFFERSIZE", None), CAPTURE_BUFFER_FRAMES),
    ):
        if prop is None:
            continue
        try:
            capture.set(prop, value)
        except Exception as exc:  # noqa: BLE001
            logger.debug("카메라 속성 설정 실패(무시): %s", exc)

    try:
        width = int(capture.get(cv2_module.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2_module.CAP_PROP_FRAME_HEIGHT))
    except Exception:  # noqa: BLE001
        return (0, 0)
    return (width, height)


def grabs_a_frame(capture: "cv2.VideoCapture") -> bool:
    """정말 영상이 들어오는지 연속으로 몇 장 받아 본다.

    **`isOpened()`가 True라고 영상이 오는 것은 아니다.** 리눅스에서 UVC 웹캠 하나를
    꽂으면 장치 노드가 둘 생긴다 — `/dev/video0`(영상)과 `/dev/video1`(메타데이터).
    메타데이터 쪽을 열어도 `isOpened()`는 True가 되고, 그러고는 프레임이 한 장도
    오지 않는다.

    그대로 두면 데몬은 "카메라 열림"이라고 로그를 남긴 채 조용히 돌기만 하고 QR을
    영영 못 읽는다. 오류도 안 나므로 전시장에서 원인을 찾을 길이 없다.

    한 장만 보지 않는 이유: V4L2가 거부한 장치를 FFmpeg 같은 다른 백엔드가 억지로
    열면, 첫 장은 그럴듯하게 돌려주고 그 뒤로는 빈 것만 오는 경우가 있다.
    """
    for _ in range(CAMERA_TEST_FRAMES):
        try:
            ok, frame = capture.read()
        except Exception as exc:  # noqa: BLE001
            logger.debug("테스트 프레임을 읽지 못했습니다: %s", exc)
            return False
        if not ok or frame is None or getattr(frame, "size", 1) == 0:
            return False
    return True


def find_capture_indices(cv2_module: ModuleType, limit: int = CAMERA_PROBE_MAX) -> list[int]:
    """실제로 **영상이 들어오는** 카메라 번호만 골라 돌려준다.

    "몇 번으로 맞춰야 하나"에 답하기 위한 것이다. 번호가 있다고 카메라는 아니므로
    여는 것만으로는 알 수 없고, 한 장 받아 봐야 한다.
    """
    found: list[int] = []
    for index in range(limit):
        capture = cv2_module.VideoCapture(index)
        try:
            if capture.isOpened() and grabs_a_frame(capture):
                found.append(index)
        finally:
            capture.release()
    return found


def open_camera(camera_index: int = 0) -> "cv2.VideoCapture":
    """웹캠을 연다. 백엔드를 순서대로 시도하고 모두 실패하면 RuntimeError."""
    import cv2

    tried: list[str] = []
    for name, api in _backend_candidates(cv2):
        capture = cv2.VideoCapture(camera_index, api)
        if not capture.isOpened():
            capture.release()
            tried.append(name)
            continue

        width, height = _tune_capture(cv2, capture)
        if not grabs_a_frame(capture):
            # 열리기는 했는데 영상이 안 온다 — 영상 장치가 아니다
            capture.release()
            tried.append(f"{name}(영상 없음)")
            continue

        logger.info(
            "카메라 열림 (index=%d, backend=%s, %dx%d)", camera_index, name, width, height
        )
        if sys.platform != "win32" and name != "v4l2":
            # V4L2로는 안 열렸다는 뜻이다. 영상이 오긴 왔지만 정식 영상 장치가
            # 아닐 수 있으므로, QR이 안 읽히면 여기부터 의심한다.
            logger.warning(
                "V4L2로 열리지 않아 %s 백엔드로 열었습니다 (index=%d). 정식 영상 장치가 "
                "아닐 수 있습니다 — QR이 안 읽히면 python check_hardware.py 로 "
                "쓸 수 있는 번호를 확인하세요.", name, camera_index,
            )
        if width * height > CAMERA_WIDTH * CAMERA_HEIGHT * 2:
            # 요청을 무시하는 카메라가 있다. 느려지는 이유를 로그에 남겨 둔다.
            logger.warning(
                "카메라가 요청한 %dx%d 대신 %dx%d로 열렸습니다 — QR 인식이 느려질 수 있습니다.",
                CAMERA_WIDTH, CAMERA_HEIGHT, width, height,
            )
        return capture

    working = find_capture_indices(cv2)
    found = (
        f"지금 영상이 들어오는 번호: {', '.join(str(i) for i in working)}"
        if working
        else "영상이 들어오는 장치를 하나도 찾지 못했습니다 (웹캠이 꽂혀 있나요?)"
    )
    raise RuntimeError(
        f"카메라를 열 수 없습니다 (index={camera_index}, 시도: {', '.join(tried)}).\n"
        f"  {found}\n"
        "  → .env의 CAMERA_INDEX를 위 번호로 맞추고 데몬을 다시 켜세요.\n"
        "  라즈베리파이에 USB 웹캠 하나만 꽂았다면 보통 0입니다. /dev/video1이 보여도\n"
        "  그건 같은 웹캠의 메타데이터 장치라 영상이 오지 않습니다.\n"
        "  (윈도우라면 Zoom·Teams·브라우저 등 웹캠을 쓰는 프로그램을 모두 끄세요)"
    )


def scan_loop(
    on_qr: Callable[[str], None],
    camera_index: int = 0,
    stop_flag: Callable[[], bool] | None = None,
) -> None:
    """카메라를 열고 QR이 보일 때마다 on_qr(문자열)을 호출한다.

    별도 스레드에서 돌린다. 예외는 로그로 남기고 루프를 멈추지 않는다 —
    인식 실패로 ATM 전체가 죽으면 안 된다.
    """
    import cv2

    capture = open_camera(camera_index)
    detector = cv2.QRCodeDetector()
    last_data: str | None = None
    last_time = 0.0
    logger.info("QR 스캔 시작 (camera_index=%d)", camera_index)

    try:
        while not (stop_flag and stop_flag()):
            ok, frame = capture.read()
            if not ok:
                time.sleep(FRAME_INTERVAL_SECONDS)
                continue

            try:
                data, _points, _straight = detector.detectAndDecode(frame)
            except Exception as exc:  # noqa: BLE001
                logger.warning("QR 디코딩 오류(무시하고 계속): %s", exc)
                continue

            now = time.monotonic()
            if data and (data != last_data or now - last_time > SAME_CODE_COOLDOWN_SECONDS):
                last_data, last_time = data, now
                try:
                    on_qr(data)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("QR 처리 중 오류: %s", exc)

            time.sleep(FRAME_INTERVAL_SECONDS)
    finally:
        capture.release()
        logger.info("QR 스캔 종료")
