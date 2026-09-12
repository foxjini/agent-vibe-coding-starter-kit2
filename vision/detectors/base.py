"""
검출기 계약 (vision/detectors/base.py) — 키트 제공, 수정하지 마세요.
=============================================================================
검출기는 **영상 한 장을 보고 "무엇이 보이는가"만 말합니다.**
그것이 무슨 의미인지(이겼는지, 혼잡한지, 졸고 있는지)는 판정하지 않습니다 —
판정은 프론트엔드 시나리오의 몫입니다 (docs/부록F 9-2절).

새 감지를 추가하려면 이 파일이 아니라 `detectors/`에 새 파일을 하나 넣고
아래 세 가지만 채우면 됩니다. `main.py`도 백엔드도 고치지 않습니다.

    class Detector(FrameDetector):
        name = "pose"                       # 설정에서 이 이름으로 켭니다
        labels = ("my_label_a", "my_label_b")   # 내가 내보낼 라벨 (백엔드에 신고됩니다)

        def detect(self, frame_bgr, config):
            ...
            return [DetectionEvent(label="my_label_a", detected=True, confidence=0.9)]

라벨 이름은 팀이 마음대로 정하면 됩니다. 백엔드도 대시보드도 그 이름을 모르는 상태로
시작해서, 이 `labels` 신고를 받고 배웁니다 — 그래서 공통 코드를 고칠 일이 없습니다.

pi의 `drivers/`와 같은 구조입니다 — 부품을 추가하면 드라이버 파일 하나,
감지를 추가하면 검출기 파일 하나.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("vision.detectors")


@dataclass
class DetectionEvent:
    """
    검출기가 찾아낸 것 하나. 그대로 `POST /api/v1/vision/events`로 전송됩니다.

    label       무엇을 봤는지 (COCO 클래스명, 손동작 이름 등)
    detected    보였는지 / 사라졌는지
    confidence  0~1. 없으면 None
    count       같은 것이 몇 개 보이는지 (혼잡도·인원수 계산에 씁니다)
    event_type  백엔드 기록용 분류. 비우면 검출기 기본값을 씁니다
    """
    label: str
    detected: bool
    confidence: Optional[float] = None
    count: int = 0
    event_type: Optional[str] = None
    #: 화면에 그릴 정보 (검출기가 알아서 그리므로 보통 비워 둡니다)
    extra: Dict[str, Any] = field(default_factory=dict)


class FrameDetector:
    """모든 검출기의 공통 뼈대."""

    #: 설정(`detectors` 목록)에서 이 이름으로 켜고 끕니다
    name: str = "detector"
    #: 이 검출기가 내보낼 수 있는 라벨. 백엔드에 신고되어 규칙 편집기 등에서 쓰입니다.
    #: 빈 튜플이면 "무엇이든 내보낼 수 있다"는 뜻입니다 (예: COCO 80종 전체).
    labels: Tuple[str, ...] = ()
    #: 사람이 읽을 설명 (시작 안내에 출력됩니다)
    description: str = ""

    def __init__(self) -> None:
        #: 준비되지 않았으면(라이브러리 없음 등) 데몬이 건너뜁니다
        self.available: bool = True
        #: 왜 못 쓰는지 (available=False일 때 화면·로그에 표시)
        self.unavailable_reason: str = ""

    # ------------------------------------------------------------------
    # 하위 클래스가 구현하는 것
    # ------------------------------------------------------------------

    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        """
        영상 한 장에서 찾은 것을 돌려줍니다. 아무것도 없으면 빈 목록.

        config는 서버가 내려준 감지 설정입니다
        (`object_labels`, `min_confidence`, `cooldown_seconds` 등).
        """
        raise NotImplementedError

    def draw(self, frame_bgr, events: Sequence[DetectionEvent]) -> None:
        """감지 결과를 영상 위에 그립니다 (선택)."""

    def status_text(self) -> str:
        """화면 상단에 한 줄로 보여 줄 상태 (선택)."""
        return ""

    def close(self) -> None:
        """자원 정리 (선택)."""

    # ------------------------------------------------------------------
    # 공통 도우미
    # ------------------------------------------------------------------

    def disable(self, reason: str) -> None:
        """못 쓰는 상태로 표시합니다 — 프로그램을 죽이지 않습니다."""
        self.available = False
        self.unavailable_reason = reason
        logger.info(f"[{self.name}] 사용할 수 없어 건너뜁니다: {reason}")

    def describe(self) -> Dict[str, Any]:
        """백엔드에 신고할 검출기 정보."""
        return {
            "name": self.name,
            "labels": list(self.labels),
            "description": self.description,
            "available": self.available,
            "reason": self.unavailable_reason,
        }
