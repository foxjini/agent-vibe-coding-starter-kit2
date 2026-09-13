"""
★ study 팀 검출기 — 좌석 6개를 각각 봅니다.
=============================================================================
**이 파일은 study 팀이 고치는 파일입니다.** 다른 팀은 지우고 자기 검출기를 만드세요.

무엇을 하나
-----------
화면을 좌석 구역으로 나누고, 구역마다 사람이 앉아 있는지 봅니다.
좌석 하나가 라벨 하나(`seat_1` … `seat_6`)이고, 자세한 값은 `extra`에 담습니다.

    label = "seat_3"                                  ← 어디
    extra = {"occupied": True, "focus_score": 0.21}   ← 어떤 상태

**판정은 하지 않습니다.** "3번 자리에 사람이 있고 집중도가 0.21"까지만 말하고,
"집중을 안 하니 알림을 보내라"는 판단은 프론트엔드 시나리오가 합니다(부록F 9-2절).

고치는 곳은 아래 SEATS 하나입니다
---------------------------------
좌석 위치는 **화면 비율(0.0~1.0)** 로 적습니다. 카메라 해상도가 바뀌어도 그대로 맞습니다.
웹캠 화면을 보면서 숫자를 조금씩 바꿔 자리에 맞추세요 (`S` 키로 구역선을 켜고 끕니다).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .base import DetectionEvent, FrameDetector
from .objects import find_people

logger = logging.getLogger("vision.detectors.study_seats")

# =============================================================================
# ★ 여기만 고치면 됩니다 — 좌석 위치 (화면 비율 0.0~1.0)
#
#   (x1, y1, x2, y2)  왼쪽 위 모서리 → 오른쪽 아래 모서리
#   화면을 가로 3칸 × 세로 2칸으로 나눈 기본값입니다. 실제 책상 배치에 맞게 고치세요.
# =============================================================================
SEATS: Dict[str, Tuple[float, float, float, float]] = {
    "seat_1": (0.00, 0.00, 0.33, 0.50),
    "seat_2": (0.33, 0.00, 0.66, 0.50),
    "seat_3": (0.66, 0.00, 1.00, 0.50),
    "seat_4": (0.00, 0.50, 0.33, 1.00),
    "seat_5": (0.33, 0.50, 0.66, 1.00),
    "seat_6": (0.66, 0.50, 1.00, 1.00),
}

#: 사람으로 인정할 최소 확신도. 빈 자리를 사람으로 잘못 보면 올리세요.
MIN_PERSON_CONFIDENCE = 0.5


class Detector(FrameDetector):
    name = "study_seats"
    labels = tuple(SEATS)                      # ("seat_1", … "seat_6")
    description = "좌석별 점유 (study 팀)"

    def __init__(self) -> None:
        super().__init__()
        #: 화면에 구역선을 그릴지 (main.py에서 키로 끄고 켜는 대신 여기서 기본값)
        self.show_regions = True
        self._last: Dict[str, Dict[str, Any]] = {}
        self._focus = FocusMeter()             # 눈 모니터링 (아래 참고)
        if not self._focus.available:
            logger.info(f"집중도 측정은 쉽니다 ({self._focus.reason}). "
                        "좌석 점유는 그대로 동작합니다.")

    # ------------------------------------------------------------------
    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        if frame_bgr is None:
            return []

        height, width = frame_bgr.shape[:2]
        people = find_people(frame_bgr, MIN_PERSON_CONFIDENCE)

        # 사람마다 '발 밑 가운데'가 어느 좌석 구역에 들어가는지 봅니다.
        # 상자 한가운데를 쓰면 앞사람 머리가 뒷자리에 잡히기 쉬워서 아래쪽을 씁니다.
        occupied: Dict[str, Dict[str, Any]] = {}
        for person in people:
            x1, y1, x2, y2 = person["box"]
            point = ((x1 + x2) / 2 / width, (y1 * 0.25 + y2 * 0.75) / height)
            seat = self._seat_at(point)
            if seat is None:
                continue
            # 한 구역에 둘이 잡히면 더 확실한 쪽을 씁니다.
            if person["confidence"] > occupied.get(seat, {}).get("confidence", 0):
                occupied[seat] = {"confidence": person["confidence"], "box": person["box"]}

        events: List[DetectionEvent] = []
        for seat in SEATS:
            here = occupied.get(seat)
            extra: Dict[str, Any] = {"occupied": here is not None}

            if here is not None:
                score = self._focus.score(frame_bgr, here["box"])
                if score is not None:
                    extra["focus_score"] = round(score, 2)
                    extra["state"] = "focused" if score >= 0.5 else "drowsy"

            events.append(DetectionEvent(
                label=seat,
                detected=here is not None,
                confidence=here["confidence"] if here else None,
                count=1 if here else 0,
                event_type="seat_state",
                extra=extra,
            ))

        self._last = {seat: occupied.get(seat, {}) for seat in SEATS}
        return events

    # ------------------------------------------------------------------
    def _seat_at(self, point: Tuple[float, float]) -> Optional[str]:
        """화면 비율 좌표가 어느 좌석 구역에 들어가는지."""
        x, y = point
        for seat, (x1, y1, x2, y2) in SEATS.items():
            if x1 <= x < x2 and y1 <= y < y2:
                return seat
        return None

    def draw(self, frame_bgr, events) -> None:
        """구역선과 자리 상태를 화면에 그립니다 (무엇을 보고 있는지 눈으로 확인)."""
        if not self.show_regions or frame_bgr is None:
            return
        import cv2

        height, width = frame_bgr.shape[:2]
        state = {e.label: e for e in events}
        for seat, (x1, y1, x2, y2) in SEATS.items():
            left, top = int(x1 * width), int(y1 * height)
            right, bottom = int(x2 * width), int(y2 * height)
            event = state.get(seat)
            taken = bool(event and event.detected)
            color = (0, 200, 0) if taken else (120, 120, 120)
            cv2.rectangle(frame_bgr, (left + 2, top + 2), (right - 2, bottom - 2), color, 2)
            cv2.putText(frame_bgr, f"{seat} {'O' if taken else '-'}",
                        (left + 8, top + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
                        cv2.LINE_AA)

    def status_text(self) -> str:
        taken = [seat for seat, info in self._last.items() if info]
        if not taken:
            return f"좌석 {len(SEATS)}칸 — 모두 비어 있음"
        return f"앉은 자리: {', '.join(taken)} ({len(taken)}/{len(SEATS)})"


# =============================================================================
# 집중도 측정 — 눈 모니터링을 여기에 붙입니다
# =============================================================================

class FocusMeter:
    """
    자리에 앉은 사람이 **얼마나 집중하고 있는지**를 0.0~1.0으로 돌려줍니다.

    지금은 MediaPipe가 있으면 얼굴이 보이는지로 아주 거칠게만 봅니다.
    **눈 감김(EAR)·고개 각도로 정교하게 만드는 것이 study 팀의 다음 과제입니다.**

    만드는 방법 (AI에게 물어볼 때 이 구조를 그대로 알려 주세요):
      1. MediaPipe FaceMesh로 눈 주변 랜드마크를 뽑습니다
      2. EAR(eye aspect ratio) = 눈 세로/가로 비율 — 감으면 작아집니다
      3. 몇 초 동안의 평균을 내서 0.0~1.0으로 만듭니다
      4. 여기 `score()`가 그 값을 돌려주면 나머지는 그대로 동작합니다

    ⚠️ 점수를 `confidence`에 넣지 마세요. `confidence`는 "얼마나 확신하는가"이고,
       자동화 규칙이 `min_confidence`로 걸러 냅니다. 점수는 `extra`에 담습니다.
    """

    def __init__(self) -> None:
        self.available = False
        self.reason = ""
        self._mesh = None
        try:
            import mediapipe as mp
            self._mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.4, min_tracking_confidence=0.4,
            )
            self.available = True
        except Exception as exc:
            self.reason = f"MediaPipe를 쓸 수 없습니다: {exc}"

    def score(self, frame_bgr, box: List[int]) -> Optional[float]:
        """자리 하나의 집중도. 잴 수 없으면 None (그 자리는 점수 없이 갑니다)."""
        if not self.available or self._mesh is None:
            return None
        import cv2

        x1, y1, x2, y2 = box
        crop = frame_bgr[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return None
        try:
            result = self._mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        except Exception:
            return None
        if not result.multi_face_landmarks:
            return 0.0                 # 얼굴이 안 보임 = 엎드렸거나 딴 데 봄

        # TODO(study 팀): 여기서 EAR을 계산해 0.0~1.0으로 바꾸세요.
        #   지금은 "얼굴이 정면으로 보인다" 정도만 봅니다.
        return 0.8
