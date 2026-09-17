"""카메라 백엔드 선택 로직 검증.

Windows에서 OpenCV 기본 백엔드(MSMF)가 웹캠을 못 여는 사례가 잦아 DSHOW를 먼저
시도한다. 실제 카메라 없이 검증할 수 있도록 cv2 상수만 흉내 낸 가짜 모듈을 쓴다.
"""
from types import SimpleNamespace

import pytest

from qr_scanner import (
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    CAPTURE_BUFFER_FRAMES,
    CAMERA_BACKEND_ENV,
    _backend_candidates,
    _tune_capture,
)

# 실제 OpenCV 상수값 (cv2.CAP_*)
FAKE_CV2 = SimpleNamespace(CAP_ANY=0, CAP_V4L2=200, CAP_DSHOW=700, CAP_MSMF=1400)

# 해상도·버퍼 속성까지 흉내 낸 가짜 cv2 (실제 상수값과 같다)
FAKE_CV2_PROPS = SimpleNamespace(
    CAP_ANY=0, CAP_V4L2=200, CAP_DSHOW=700, CAP_MSMF=1400,
    CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4, CAP_PROP_BUFFERSIZE=38,
)


class FakeCapture:
    """set()을 받아 기억했다가 get()으로 돌려주는 가짜 카메라."""

    def __init__(self, forced: dict[int, float] | None = None) -> None:
        self.props: dict[int, float] = {}
        self._forced = forced or {}      # 요청을 무시하고 제 값을 고집하는 카메라

    def set(self, prop: int, value: float) -> bool:
        self.props[prop] = value
        return True

    def get(self, prop: int) -> float:
        return self._forced.get(prop, self.props.get(prop, 0))


@pytest.fixture(autouse=True)
def _clear_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트마다 CAMERA_BACKEND를 비워 실행 환경의 .env 영향을 없앤다."""
    monkeypatch.delenv(CAMERA_BACKEND_ENV, raising=False)


def test_windows_tries_dshow_first_then_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows에서는 dshow를 먼저 시도하고 기본값으로 되돌아간다."""
    monkeypatch.setattr("qr_scanner.sys.platform", "win32")

    assert _backend_candidates(FAKE_CV2) == [("dshow", 700), ("any", 0)]


def test_linux_keeps_opencv_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """라즈베리파이/리눅스는 기존 동작(기본 백엔드) 그대로 둔다."""
    monkeypatch.setattr("qr_scanner.sys.platform", "linux")

    assert _backend_candidates(FAKE_CV2) == [("any", 0)]


def test_env_forces_single_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """CAMERA_BACKEND를 지정하면 그 백엔드 하나만 쓴다."""
    monkeypatch.setattr("qr_scanner.sys.platform", "win32")
    monkeypatch.setenv(CAMERA_BACKEND_ENV, "MSMF")  # 대소문자/공백은 무시한다

    assert _backend_candidates(FAKE_CV2) == [("msmf", 1400)]


def test_unknown_env_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """오타를 조용히 넘기지 않고 가능한 값을 알려 준다."""
    monkeypatch.setenv(CAMERA_BACKEND_ENV, "dshwo")

    with pytest.raises(ValueError, match="dshwo"):
        _backend_candidates(FAKE_CV2)


# ── 인식 속도를 좌우하는 해상도 (파이에서 중요하다) ──────────────────────────
def test_capture_is_pinned_to_a_cheap_resolution() -> None:
    """카메라 기본값에 맡기지 않는다.

    QR 검출 비용은 화소 수에 거의 비례한다. 1080p로 열리는 웹캠을 만나면 한 장
    처리가 루프 주기(0.1초)에 육박해 인식이 밀린다. QR은 640x480에서도 충분히
    읽히므로 해상도를 고정한다.
    """
    capture = FakeCapture()

    width, height = _tune_capture(FAKE_CV2_PROPS, capture)

    assert capture.props[FAKE_CV2_PROPS.CAP_PROP_FRAME_WIDTH] == CAMERA_WIDTH
    assert capture.props[FAKE_CV2_PROPS.CAP_PROP_FRAME_HEIGHT] == CAMERA_HEIGHT
    assert (width, height) == (CAMERA_WIDTH, CAMERA_HEIGHT)


def test_capture_keeps_only_the_newest_frame() -> None:
    """버퍼가 깊으면 이미 치운 QR을 뒤늦게 읽는다 — 항상 최신 화면만 본다."""
    capture = FakeCapture()

    _tune_capture(FAKE_CV2_PROPS, capture)

    assert capture.props[FAKE_CV2_PROPS.CAP_PROP_BUFFERSIZE] == CAPTURE_BUFFER_FRAMES


def test_tune_reports_what_the_camera_actually_gave() -> None:
    """요청을 무시하는 카메라가 있다. 실제 해상도를 돌려줘야 로그로 알 수 있다."""
    capture = FakeCapture(forced={
        FAKE_CV2_PROPS.CAP_PROP_FRAME_WIDTH: 1920,
        FAKE_CV2_PROPS.CAP_PROP_FRAME_HEIGHT: 1080,
    })

    assert _tune_capture(FAKE_CV2_PROPS, capture) == (1920, 1080)


def test_tune_survives_a_backend_without_these_properties() -> None:
    """속성을 지원하지 않는 백엔드에서도 카메라를 못 쓰게 만들지는 않는다."""

    class StubbornCapture(FakeCapture):
        def set(self, prop: int, value: float) -> bool:
            raise RuntimeError("이 백엔드는 지원하지 않습니다")

    # CAP_PROP_BUFFERSIZE가 아예 없는 옛 cv2도 있다
    old_cv2 = SimpleNamespace(CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4)

    assert _tune_capture(old_cv2, StubbornCapture()) == (0, 0)
