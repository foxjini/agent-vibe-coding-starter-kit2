"""
★ subway 팀 검출기 — 객차(칸) 하나의 혼잡도를 점유율(occupancy)로 잽니다.
=============================================================================
**이 파일은 subway 팀이 쓰는 파일입니다.** 다른 팀은 신경 쓰지 않아도 됩니다 —
`SUBWAY_CAR`를 정하지 않으면 아무 일도 하지 않습니다.

웹캠 1대 = 칸 1개
-----------------
비전 프로그램(main.py)은 웹캠을 하나만 엽니다. 그래서 웹캠이 2대면 **비전 프로그램을
2번 따로 켭니다.** 창마다 "이 웹캠은 몇 번 칸인지"를 `SUBWAY_CAR`로 알려 줍니다.

    창 ①  python main.py                                          (.env: CAMERA_INDEX=0, SUBWAY_CAR=car_1)
    창 ②  $env:CAMERA_INDEX="1"; $env:SUBWAY_CAR="car_2"; python main.py

보내는 것 (study_seats.py와 같은 방식 — 라벨은 '어디', extra는 '어떤')

    label = "car_1"                                       ← 몇 번 칸
    count = 5                                             ← 보이는 사람 수 (참고용 — 예전과 같음)
    extra = {"people": 5, "occupancy": 47, "level": 2}    ← 점유율 % · 혼잡 단계 0 여유 · 1 보통 · 2 혼잡 · 3 매우 혼잡

점유율(occupancy)이란
---------------------
**화면(또는 정한 구역)에서 사람이 차지한 넓이의 비율**입니다 (0~100%).
사람끼리 겹쳐 보여도 겹친 부분은 한 번만 셉니다. 사람 수는 가려지면 틀리기 쉽지만
"얼마나 꽉 찼는가"는 덜 흔들립니다. 단계는 사람 수가 아니라 이 점유율로 정합니다.

구역 정하기 (선택) — 천장·벽이 화면에 많이 잡히면 점유율이 낮게 나옵니다.
    SUBWAY_ZONE=0.0,0.3,1.0,1.0     # 왼쪽,위,오른쪽,아래 (0~1 비율). 이 예는 화면 아래 70%만 봄
    SUBWAY_SMOOTH=5                 # 최근 몇 번의 평균으로 부드럽게 (기본 5, 1이면 끔)

**판정은 하지 않습니다.** "어느 칸이 덜 붐비니 그쪽으로 안내하라"는 판단은
프론트엔드 시나리오가 합니다 (docs/부록F 9-2절). main.py도 백엔드도 고치지 않습니다.

고치는 곳은 아래 OCCUPANCY_LEVELS 하나입니다 (칸 크기·카메라 화각에 맞게).
"""
import logging
import os
from collections import deque
from typing import Any, Deque, Dict, List, Sequence, Tuple

import numpy as np

from .base import DetectionEvent, FrameDetector
from .objects import find_people

logger = logging.getLogger("vision.detectors.subway_cars")

#: 두 칸의 라벨. 두 창이 같은 목록을 신고해야 대시보드가 둘 다 압니다.
CARS = ("car_1", "car_2")

# =============================================================================
# ★ 여기만 고치면 됩니다 — 혼잡 단계 기준 (점유율 %)
#   20% 이상이면 1단계(보통), 40% 이상이면 2단계(혼잡), 60% 이상이면 3단계(매우 혼잡)
#   실제 칸에 사람(모형)을 세워 보고, 창 왼쪽 위에 나오는 %를 보며 맞추세요.
# =============================================================================
OCCUPANCY_LEVELS = (20, 40, 60)

#: 점유율을 재는 격자 크기 (가로, 세로). 클수록 정밀하지만 이 정도면 충분합니다.
GRID = (160, 90)
#: 구역을 정하지 않았을 때 = 화면 전체 (왼쪽, 위, 오른쪽, 아래 — 0~1 비율)
FULL_ZONE = (0.0, 0.0, 1.0, 1.0)

#: 사람으로 인정할 최소 확신도. 사람이 아닌 것을 사람으로 세면 올리세요.
MIN_PERSON_CONFIDENCE = 0.5


def crowd_level(occupancy: float) -> int:
    """점유율(%) → 혼잡 단계 0~3."""
    return sum(occupancy >= n for n in OCCUPANCY_LEVELS)


def parse_zone(text: str) -> Tuple[float, float, float, float]:
    """`SUBWAY_ZONE=0,0.3,1,1` 을 (왼쪽, 위, 오른쪽, 아래)로 읽습니다. 잘못 적었으면 화면 전체."""
    if not text.strip():
        return FULL_ZONE
    try:
        x1, y1, x2, y2 = (float(v) for v in text.split(","))
    except ValueError:
        logger.warning(f"SUBWAY_ZONE={text!r}을 읽지 못했습니다. 숫자 4개를 쉼표로 적으세요 (예: 0,0.3,1,1) — 화면 전체를 봅니다.")
        return FULL_ZONE
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        logger.warning(f"SUBWAY_ZONE={text!r}의 범위가 이상합니다 (0~1, 왼쪽<오른쪽, 위<아래) — 화면 전체를 봅니다.")
        return FULL_ZONE
    return x1, y1, x2, y2


def occupancy_percent(boxes: Sequence[Sequence[float]], frame_w: int, frame_h: int,
                      zone: Tuple[float, float, float, float] = FULL_ZONE) -> float:
    """
    사람 상자들이 구역에서 차지한 넓이의 비율(0~100)을 돌려줍니다.

    상자를 작은 격자에 색칠해서 셉니다 — 겹친 부분은 한 번만 칠해지므로 두 번 세지 않습니다.
    boxes: [[x1, y1, x2, y2], ...] (화면 픽셀)
    """
    if frame_w <= 0 or frame_h <= 0:
        return 0.0
    gw, gh = GRID
    mask = np.zeros((gh, gw), dtype=bool)
    for x1, y1, x2, y2 in boxes:
        left = max(0, min(gw, int(np.floor(x1 / frame_w * gw))))
        right = max(0, min(gw, int(np.ceil(x2 / frame_w * gw))))
        top = max(0, min(gh, int(np.floor(y1 / frame_h * gh))))
        bottom = max(0, min(gh, int(np.ceil(y2 / frame_h * gh))))
        mask[top:bottom, left:right] = True
    zx1, zy1, zx2, zy2 = zone
    area = mask[int(round(zy1 * gh)):int(round(zy2 * gh)), int(round(zx1 * gw)):int(round(zx2 * gw))]
    return float(area.mean() * 100) if area.size else 0.0


class Detector(FrameDetector):
    name = "subway_cars"
    labels = CARS
    description = "객차별 점유율·혼잡 단계 (subway 팀)"

    def __init__(self) -> None:
        super().__init__()
        #: 이 창이 맡은 칸. 정하지 않으면(다른 팀) 아무것도 하지 않습니다.
        self.car = os.getenv("SUBWAY_CAR", "").strip().lower()
        self._count = 0
        self._occupancy = 0
        self.zone = parse_zone(os.getenv("SUBWAY_ZONE", ""))
        try:
            smooth = max(1, int(os.getenv("SUBWAY_SMOOTH", "5")))
        except ValueError:
            smooth = 5
        #: 최근 점유율 몇 개 — 평균을 내서 숫자가 덜 흔들리게 합니다
        self._recent: Deque[float] = deque(maxlen=smooth)
        if self.car and self.car not in CARS:
            logger.warning(f"SUBWAY_CAR={self.car!r}는 쓸 수 없습니다. {', '.join(CARS)} 중 하나로 적으세요.")
            self.car = ""

    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        if not self.car or frame_bgr is None:
            return []
        people = find_people(frame_bgr, MIN_PERSON_CONFIDENCE)
        height, width = frame_bgr.shape[:2]
        self._count = len(people)
        self._recent.append(occupancy_percent([p["box"] for p in people], width, height, self.zone))
        self._occupancy = int(round(sum(self._recent) / len(self._recent)))
        return [DetectionEvent(
            label=self.car,
            detected=True,                      # 칸은 늘 '보이는' 상태 — 바뀌는 것은 사람 수
            count=self._count,
            event_type="car_crowd",
            extra={"people": self._count, "occupancy": self._occupancy,
                   "level": crowd_level(self._occupancy)},
        )]

    def status_text(self) -> str:
        if not self.car:
            return ""
        return f"{self.car}: 점유율 {self._occupancy}% · {self._count}명 (혼잡 단계 {crowd_level(self._occupancy)})"
