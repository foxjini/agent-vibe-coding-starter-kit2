"""
집중도 측정 엔진 (vision/detectors/_focus_engine.py) — ★ study 팀 파일
=============================================================================
파일 이름이 `_`로 시작하므로 **검출기가 아닙니다** (로더가 건너뜁니다).
`study_focus.py`가 이 파일의 함수를 가져다 씁니다.

여기가 하는 일은 **재는 것**뿐입니다.
  · 눈이 얼마나 떠 있나 (EAR)
  · 고개를 숙였나
  · 시선이 화면을 벗어났나

"집중하고 있다 / 졸고 있다"는 **판정하지 않습니다.**
판정은 프론트엔드(`frontend/scenarios/studyEngine.ts`)가 합니다 — 그래야 임계값을
TypeScript에서 고칠 수 있고, 카메라 쪽 파이썬을 다시 건드리지 않습니다.

카메라와 좌표
-------------
MediaPipe FaceMesh는 얼굴 점 478개를 돌려줍니다(`refine_landmarks=True`).
이 파일의 함수들은 전부 **픽셀 좌표 배열**만 받습니다 — MediaPipe를 모릅니다.
그래서 웹캠 없이 가짜 좌표로 시험할 수 있습니다 (`vision/test_study_focus.py`).
"""
import math
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

# =============================================================================
# ★ 여기를 고쳐서 맞춥니다 — 교실에서 한 번 조정하세요
# =============================================================================

#: 눈을 "감았다"고 볼 EAR 값. 사람마다 다릅니다. 안경을 쓰면 조금 올리세요.
EAR_CLOSED = 0.15
#: 눈을 "떴다"고 볼 EAR 값. 이 둘 사이를 0.0~1.0으로 폅니다.
EAR_OPEN = 0.30

#: 눈이 이만큼(초) 이어서 감겨 있으면 `eyes_closed` 라벨이 켜집니다.
#: 사람은 0.1~0.4초로 깜빡이므로 그보다 충분히 길어야 합니다.
EYES_CLOSED_SECONDS = 1.2

#: 시선이 좌우로 이만큼 벗어나면 "딴 데 봄". 0.5면 눈 폭의 절반입니다.
GAZE_AWAY = 0.18
#: 고개가 좌우로 이만큼 돌아가면 "딴 데 봄".
YAW_AWAY = 0.16
#: 고개 숙임 — 보정값의 몇 배 아래로 내려가면 "숙였다"로 봅니다.
HEAD_DOWN_RATIO = 0.88

#: 처음 이 시간(초) 동안은 "정면"이 어떤 모양인지 배웁니다 (사람마다 다르므로).
CALIBRATION_SECONDS = 8.0
#: 보정에 필요한 최소 표본 수.
CALIBRATION_MIN_SAMPLES = 30

#: 얼굴 폭이 이 픽셀보다 크면 측정 품질이 좋습니다 (MediaPipe가 192px로 잘라 씁니다).
GOOD_FACE_PX = 192.0

# =============================================================================
# MediaPipe FaceMesh 점 번호 — 고치지 마세요
# =============================================================================

#: 눈 하나를 재는 데 쓰는 여섯 점 (EAR 공식의 p1~p6)
#: 화면 기준 왼쪽 눈 (사람의 오른쪽 눈)
EYE_IMAGE_LEFT = {"outer": 33, "inner": 133, "up": (160, 158), "low": (144, 153)}
#: 화면 기준 오른쪽 눈
EYE_IMAGE_RIGHT = {"outer": 263, "inner": 362, "up": (387, 385), "low": (373, 380)}

#: 눈동자 중심 (refine_landmarks=True 일 때만 있습니다)
IRIS_IMAGE_LEFT = 468
IRIS_IMAGE_RIGHT = 473

NOSE_TIP = 1
CHIN = 152
FOREHEAD = 10
FACE_EDGE_LEFT = 234
FACE_EDGE_RIGHT = 454

#: refine_landmarks=True 로 나오는 점 개수. 이보다 적으면 눈동자가 없습니다.
LANDMARKS_WITH_IRIS = 478


Point = Tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# =============================================================================
# 한 프레임에서 재는 값들
# =============================================================================

def eye_aspect_ratio(points: Sequence[Point], eye: Dict[str, Any]) -> float:
    """
    눈이 얼마나 떠 있는가 (EAR = eye aspect ratio).

    눈의 **세로 길이를 가로 길이로 나눈** 값입니다. 뜨면 커지고 감으면 0에 가까워집니다.
    얼굴이 가까워도 멀어도 비율이라 값이 비슷하게 유지되는 것이 핵심입니다.

        EAR = (|위1-아래1| + |위2-아래2|) / (2 × |바깥-안쪽|)
    """
    outer, inner = points[eye["outer"]], points[eye["inner"]]
    width = _dist(outer, inner)
    if width <= 0:
        return 0.0
    up1, up2 = points[eye["up"][0]], points[eye["up"][1]]
    low1, low2 = points[eye["low"][0]], points[eye["low"][1]]
    return (_dist(up1, low1) + _dist(up2, low2)) / (2.0 * width)


def eyes_open_ratio(points: Sequence[Point]) -> float:
    """두 눈의 EAR 평균을 0.0(감음)~1.0(뜸)으로 폅니다."""
    ear = (eye_aspect_ratio(points, EYE_IMAGE_LEFT)
           + eye_aspect_ratio(points, EYE_IMAGE_RIGHT)) / 2.0
    span = EAR_OPEN - EAR_CLOSED
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (ear - EAR_CLOSED) / span))


def mean_ear(points: Sequence[Point]) -> float:
    """두 눈 EAR 평균 (펴지 않은 원래 값). 임계값을 맞출 때 봅니다."""
    return (eye_aspect_ratio(points, EYE_IMAGE_LEFT)
            + eye_aspect_ratio(points, EYE_IMAGE_RIGHT)) / 2.0


def gaze_offset(points: Sequence[Point]) -> Optional[float]:
    """
    눈동자가 눈 안에서 좌우로 얼마나 치우쳤나. 0.0이 한가운데입니다.

    눈동자 점(468·473)이 없으면 `None` — `refine_landmarks=True`로 열어야 나옵니다.
    """
    if len(points) < LANDMARKS_WITH_IRIS:
        return None

    offsets: List[float] = []
    for eye, iris in ((EYE_IMAGE_LEFT, IRIS_IMAGE_LEFT),
                      (EYE_IMAGE_RIGHT, IRIS_IMAGE_RIGHT)):
        inner_x = points[eye["inner"]][0]
        outer_x = points[eye["outer"]][0]
        span = outer_x - inner_x
        if abs(span) < 1e-6:
            continue
        # 눈 안쪽 끝을 0, 바깥쪽 끝을 1로 봤을 때 눈동자가 어디 있는가
        t = (points[iris][0] - inner_x) / span
        offsets.append(t - 0.5)

    if not offsets:
        return None
    return sum(offsets) / len(offsets)


def head_yaw(points: Sequence[Point]) -> float:
    """
    고개를 좌우로 얼마나 돌렸나. 0.0이 정면, 부호는 방향입니다.

    코끝이 얼굴 왼쪽 끝과 오른쪽 끝 중 어디에 가까운지로 봅니다.
    """
    nose = points[NOSE_TIP]
    left, right = points[FACE_EDGE_LEFT], points[FACE_EDGE_RIGHT]
    width = _dist(left, right)
    if width <= 0:
        return 0.0
    return (_dist(nose, left) - _dist(nose, right)) / width


def head_pitch_ratio(points: Sequence[Point]) -> float:
    """
    고개를 숙였는지 볼 때 쓰는 비율 — **이 값 자체로는 판단하지 않습니다.**

    눈높이에서 턱까지 / 이마에서 눈높이까지. 고개를 숙이면 턱이 짧아 보여서 값이 줄어듭니다.
    사람마다 얼굴 비율이 달라서, `Calibration`이 처음 몇 초로 "이 사람의 정면"을 배웁니다.
    """
    eye_y = (points[EYE_IMAGE_LEFT["outer"]][1] + points[EYE_IMAGE_RIGHT["outer"]][1]) / 2.0
    upper = abs(eye_y - points[FOREHEAD][1])
    lower = abs(points[CHIN][1] - eye_y)
    if upper <= 0:
        return 0.0
    return lower / upper


def face_width_px(points: Sequence[Point]) -> float:
    """얼굴 폭(픽셀). 설치가 잘 됐는지 보는 값입니다 — 작으면 눈을 못 잽니다."""
    return _dist(points[FACE_EDGE_LEFT], points[FACE_EDGE_RIGHT])


# =============================================================================
# 사람마다 다른 "정면"을 배웁니다
# =============================================================================

class Calibration:
    """
    처음 몇 초 동안 **이 사람이 화면을 볼 때의 모양**을 기록해 기준으로 삼습니다.

    얼굴 비율은 사람마다 다르므로 고정 숫자로 "고개 숙임"을 판단하면 누구는 늘 숙인
    것이 되고 누구는 절대 안 숙인 것이 됩니다. 그래서 기준을 사람에게 맞춥니다.
    """

    def __init__(self, seconds: float = CALIBRATION_SECONDS,
                 min_samples: int = CALIBRATION_MIN_SAMPLES) -> None:
        self.seconds = seconds
        self.min_samples = min_samples
        self._started_at: Optional[float] = None
        self._pitch: List[float] = []
        self._yaw: List[float] = []
        self.pitch_baseline: Optional[float] = None
        self.yaw_baseline: float = 0.0

    @property
    def done(self) -> bool:
        return self.pitch_baseline is not None

    def add(self, pitch: float, yaw: float, now: float) -> None:
        if self.done:
            return
        if self._started_at is None:
            self._started_at = now
        self._pitch.append(pitch)
        self._yaw.append(yaw)

        long_enough = now - self._started_at >= self.seconds
        enough_samples = len(self._pitch) >= self.min_samples
        if long_enough and enough_samples:
            # 평균 대신 중앙값 — 잠깐 고개를 돌린 순간이 기준을 흔들지 않게
            self.pitch_baseline = statistics.median(self._pitch)
            self.yaw_baseline = statistics.median(self._yaw)

    def reset(self) -> None:
        self.__init__(self.seconds, self.min_samples)

    def progress(self, now: float) -> float:
        """보정이 얼마나 됐나 0.0~1.0 (화면에 '보정 중'을 보여 줄 때 씁니다)."""
        if self.done:
            return 1.0
        if self._started_at is None or self.seconds <= 0:
            return 0.0
        by_time = (now - self._started_at) / self.seconds
        by_samples = len(self._pitch) / max(1, self.min_samples)
        return max(0.0, min(1.0, min(by_time, by_samples)))

    def is_head_down(self, pitch: float) -> bool:
        if self.pitch_baseline is None or self.pitch_baseline <= 0:
            return False
        return pitch < self.pitch_baseline * HEAD_DOWN_RATIO

    def is_turned_away(self, yaw: float) -> bool:
        return abs(yaw - self.yaw_baseline) > YAW_AWAY


# =============================================================================
# 한 프레임 측정 결과
# =============================================================================

class Reading:
    """프레임 하나에서 잰 것."""

    __slots__ = ("at", "ear", "open_ratio", "gaze", "yaw", "pitch", "face_px")

    def __init__(self, at: float, ear: float, open_ratio: float,
                 gaze: Optional[float], yaw: float, pitch: float, face_px: float) -> None:
        self.at = at
        self.ear = ear
        self.open_ratio = open_ratio
        self.gaze = gaze
        self.yaw = yaw
        self.pitch = pitch
        self.face_px = face_px


def read_face(points: Sequence[Point], now: float) -> Reading:
    """얼굴 점 배열 하나를 측정값으로 바꿉니다."""
    return Reading(
        at=now,
        ear=mean_ear(points),
        open_ratio=eyes_open_ratio(points),
        gaze=gaze_offset(points),
        yaw=head_yaw(points),
        pitch=head_pitch_ratio(points),
        face_px=face_width_px(points),
    )


# =============================================================================
# 전송 주기에 맞춘 집계 — 여기가 중요합니다
# =============================================================================

class WindowAccumulator:
    """
    **한 프레임의 값을 그대로 보내면 안 됩니다.**

    백엔드로는 몇 초에 한 번만 전송되는데(`cooldown_seconds`, 기본 2.5초),
    그 순간이 하필 눈을 깜빡인 프레임이면 "졸고 있음"이 됩니다.
    그래서 창(window) 동안 모은 다음 **요약해서** 보냅니다.

    `longest_closed`가 졸음 판단의 핵심입니다 — 깜빡임(0.1~0.4초)과
    조는 것(1초 이상)을 길이로 가릅니다.
    """

    def __init__(self, calibration: Optional[Calibration] = None) -> None:
        self.calibration = calibration or Calibration()
        self._readings: List[Reading] = []
        self._no_face = 0
        self._closed_since: Optional[float] = None
        self._longest_closed = 0.0

    # ------------------------------------------------------------------
    def add(self, reading: Reading) -> None:
        self._readings.append(reading)
        self.calibration.add(reading.pitch, reading.yaw, reading.at)

        # 눈을 감고 있는 구간의 길이를 잽니다 (창을 넘어가도 이어서)
        closed = reading.ear < EAR_CLOSED
        if closed:
            if self._closed_since is None:
                self._closed_since = reading.at
            self._longest_closed = max(self._longest_closed,
                                       reading.at - self._closed_since)
        else:
            self._closed_since = None

    def add_no_face(self) -> None:
        """얼굴이 안 보인 프레임."""
        self._no_face += 1
        self._closed_since = None

    # ------------------------------------------------------------------
    @property
    def closed_run_seconds(self) -> float:
        """지금까지 이어서 눈을 감고 있는 시간 (창을 비워도 이어집니다)."""
        return self._longest_closed

    def summarize(self, now: float) -> Dict[str, Any]:
        """
        지금까지 모은 것을 요약합니다. **값은 그대로 `extra`에 담깁니다.**

        키를 늘릴 때는 백엔드 제한(키 20개·JSON 2KB)을 넘지 않게 하세요.
        """
        total = len(self._readings) + self._no_face
        if total == 0:
            return {
                "samples": 0,
                "face": False,
                "calibrated": self.calibration.done,
            }

        if not self._readings:
            return {
                "samples": total,
                "face": False,
                "no_face": 1.0,
                "calibrated": self.calibration.done,
            }

        seen = len(self._readings)
        closed = sum(1 for r in self._readings if r.ear < EAR_CLOSED)
        head_down = sum(1 for r in self._readings if self.calibration.is_head_down(r.pitch))
        away = sum(
            1 for r in self._readings
            if self.calibration.is_turned_away(r.yaw)
            or (r.gaze is not None and abs(r.gaze) > GAZE_AWAY)
        )

        return {
            "samples": total,
            "face": True,
            # 눈이 얼마나 떠 있었나 (0.0 감음 ~ 1.0 뜸)
            "eyes_open": round(sum(r.open_ratio for r in self._readings) / seen, 3),
            # 창에서 눈을 감고 있던 프레임 비율
            "closed_ratio": round(closed / seen, 3),
            # 가장 길게 이어서 감고 있던 시간(초) — 깜빡임과 졸음을 가르는 값
            "closed_run": round(self._longest_closed, 2),
            # 고개를 숙이고 있던 프레임 비율
            "head_down": round(head_down / seen, 3),
            # 시선·고개가 화면을 벗어난 프레임 비율
            "look_away": round(away / seen, 3),
            # 얼굴이 안 보인 프레임 비율
            "no_face": round(self._no_face / total, 3),
            # 얼굴 폭(px) — 설치 품질. 작으면 눈 측정이 부정확합니다
            "face_px": int(sum(r.face_px for r in self._readings) / seen),
            # 이 사람의 '정면'을 다 배웠는가
            "calibrated": self.calibration.done,
        }

    def drain(self, now: float) -> Dict[str, Any]:
        """요약을 돌려주고 창을 비웁니다. 보정 결과와 감은 구간은 유지됩니다."""
        summary = self.summarize(now)
        self._readings.clear()
        self._no_face = 0
        # 눈을 계속 감고 있는 중이면 그 구간은 이어서 세야 합니다
        if self._closed_since is None:
            self._longest_closed = 0.0
        return summary

    def reset(self) -> None:
        """사람이 바뀌었을 때 (자리를 비웠다 돌아왔을 때) 처음부터 다시."""
        self._readings.clear()
        self._no_face = 0
        self._closed_since = None
        self._longest_closed = 0.0
        self.calibration.reset()


def reading_confidence(summary: Dict[str, Any],
                       expected_samples: int = 20) -> float:
    """
    **이 측정을 얼마나 믿을 수 있는가** (0.0~1.0).

    자동화 규칙의 `min_confidence`가 이 값으로 거릅니다. 집중도 점수가 아닙니다 —
    점수는 `extra`에 있고, 이것은 "표본이 충분하고 얼굴이 크게 잡혔는가"입니다.
    """
    samples = int(summary.get("samples") or 0)
    if samples <= 0:
        return 0.0
    by_samples = min(1.0, samples / max(1, expected_samples))
    face_px = float(summary.get("face_px") or 0)
    if not summary.get("face"):
        # 얼굴이 없다는 것은 표본만 충분하면 확실합니다
        return round(by_samples, 3)
    by_size = min(1.0, face_px / GOOD_FACE_PX) if face_px else 0.3
    return round(by_samples * by_size, 3)
