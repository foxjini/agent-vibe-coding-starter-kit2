"""
★ subway 팀 검출기 — 객차(칸) 하나의 혼잡도를 셉니다.
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

    label = "car_1"                        ← 몇 번 칸
    count = 5                              ← 보이는 사람 수
    extra = {"people": 5, "level": 2}      ← 혼잡 단계 0 여유 · 1 보통 · 2 혼잡 · 3 매우 혼잡

**판정은 하지 않습니다.** "어느 칸이 덜 붐비니 그쪽으로 안내하라"는 판단은
프론트엔드 시나리오가 합니다 (docs/부록F 9-2절). main.py도 백엔드도 고치지 않습니다.

고치는 곳은 아래 LEVELS 하나입니다 (칸 크기·카메라 화각에 맞게).
"""
import logging
import os
from typing import Any, Dict, List

from .base import DetectionEvent, FrameDetector
from .objects import find_people

logger = logging.getLogger("vision.detectors.subway_cars")

#: 두 칸의 라벨. 두 창이 같은 목록을 신고해야 대시보드가 둘 다 압니다.
CARS = ("car_1", "car_2")

# =============================================================================
# ★ 여기만 고치면 됩니다 — 혼잡 단계 기준 (사람 수)
#   사람이 2명 이상이면 1단계(보통), 4명 이상이면 2단계(혼잡), 6명 이상이면 3단계(매우 혼잡)
# =============================================================================
LEVELS = (2, 4, 6)

#: 사람으로 인정할 최소 확신도. 사람이 아닌 것을 사람으로 세면 올리세요.
MIN_PERSON_CONFIDENCE = 0.5


def crowd_level(count: int) -> int:
    """사람 수 → 혼잡 단계 0~3."""
    return sum(count >= n for n in LEVELS)


class Detector(FrameDetector):
    name = "subway_cars"
    labels = CARS
    description = "객차별 사람 수·혼잡 단계 (subway 팀)"

    def __init__(self) -> None:
        super().__init__()
        #: 이 창이 맡은 칸. 정하지 않으면(다른 팀) 아무것도 하지 않습니다.
        self.car = os.getenv("SUBWAY_CAR", "").strip().lower()
        self._count = 0
        if self.car and self.car not in CARS:
            logger.warning(f"SUBWAY_CAR={self.car!r}는 쓸 수 없습니다. {', '.join(CARS)} 중 하나로 적으세요.")
            self.car = ""

    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        if not self.car or frame_bgr is None:
            return []
        self._count = len(find_people(frame_bgr, MIN_PERSON_CONFIDENCE))
        return [DetectionEvent(
            label=self.car,
            detected=True,                      # 칸은 늘 '보이는' 상태 — 바뀌는 것은 사람 수
            count=self._count,
            event_type="car_crowd",
            extra={"people": self._count, "level": crowd_level(self._count)},
        )]

    def status_text(self) -> str:
        if not self.car:
            return ""
        return f"{self.car}: {self._count}명 (혼잡 단계 {crowd_level(self._count)})"
