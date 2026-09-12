"""
hands_rps — 가위바위보 손동작 감지 (**wakeup 팀 게임**).

다른 팀은 이 검출기를 끄고 쓰거나, 이 파일을 본보기로 자기 감지를 만드세요.
끄는 방법: 대시보드 /kit → 영상인식 설정에서 '손동작 인식 사용' 체크 해제.

내보내는 라벨: rock / paper / scissors
**이겼는지 졌는지는 판정하지 않습니다.** 무슨 손인지만 알려 주고,
승패는 프론트엔드 시나리오(`frontend/scenarios/wakeupEngine.ts`)가 정합니다.

새 손동작 감지를 만들려면 이 파일을 복사해 `classify_hand()`만 바꾸면 됩니다.
"""
import logging
from typing import Any, Dict, List, Sequence

from detectors.base import DetectionEvent, FrameDetector

logger = logging.getLogger("vision.detectors.hands_rps")

HAND_KO = {"rock": "주먹", "paper": "보", "scissors": "가위"}


class Detector(FrameDetector):
    name = "hands_rps"
    labels = ("rock", "paper", "scissors")
    description = "가위바위보 손동작 (wakeup 팀)"

    def __init__(self) -> None:
        super().__init__()
        self.last_hand = None
        self._points = None

        try:
            # 손 인식 자체(MediaPipe 로딩·랜드마크 추출)는 옆 파일에 그대로 있습니다.
            from ._hands_rps_engine import RockPaperScissorsDetector

            self._engine = RockPaperScissorsDetector()
            if not self._engine.available:
                self.disable("MediaPipe를 사용할 수 없습니다 (사물 감지는 계속 동작합니다)")
        except Exception as exc:
            self._engine = None
            self.disable(f"손 인식 모듈을 불러오지 못했습니다: {exc}")

    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        if not self.available or self._engine is None:
            return []

        import cv2

        result = self._engine.detect(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        if not result:
            self.last_hand = None
            self._points = None
            return []

        self.last_hand = result["hand"]
        self._points = result.get("points")
        return [DetectionEvent(
            label=result["hand"],
            detected=True,
            confidence=result.get("confidence"),
            count=1,
            event_type="gesture_detected",
        )]

    def draw(self, frame_bgr, events: Sequence[DetectionEvent]) -> None:
        if self._engine is not None and self._points:
            self._engine.draw(frame_bgr, self._points)

    def status_text(self) -> str:
        if not self.available:
            return ""
        if not self.last_hand:
            return ""
        return f"손동작: {HAND_KO.get(self.last_hand, self.last_hand)}"

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.close()
            except Exception:
                pass
