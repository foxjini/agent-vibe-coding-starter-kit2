import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

#: `extra`에 담을 수 있는 최대 크기(JSON 문자열 기준). 넘으면 400으로 거절합니다.
#: 영상 프레임이나 좌표 배열을 통째로 실어 보내면 실시간 중계가 느려지므로 막습니다.
MAX_EXTRA_BYTES = 2048
MAX_EXTRA_KEYS = 20


class VisionEventRequest(BaseModel):
    event_type: str = Field(
        ...,
        description="이벤트 종류 (예: 'object_detected', 'gesture_detected', 'person_cleared')",
    )
    detected: bool = Field(..., description="감지 성공 여부")
    count: int = Field(default=0, description="감지된 객체 수")
    confidence: Optional[float] = Field(
        default=None,
        description=(
            "**감지를 얼마나 확신하는가** (0.0~1.0). 점수·측정값을 여기에 넣지 마세요 — "
            "자동화 규칙의 min_confidence가 낮은 값을 걸러내므로 조용히 무시됩니다. "
            "측정값은 `extra`에 담으세요."
        ),
    )
    label: Optional[str] = Field(
        default=None,
        description=(
            "검출기가 내보내는 라벨. 사물 검출기는 COCO 클래스명('person', 'bottle')을 쓰고, "
            "팀이 추가한 검출기는 그 검출기가 선언한 라벨을 씁니다(vision/detectors/ 참고). "
            "백엔드는 라벨 값을 해석하지 않고 그대로 저장·중계합니다. "
            "생략하면 event_type에서 유추합니다(구버전 호환)."
        ),
        examples=["person"],
    )
    extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "라벨 하나로 표현하기 어려운 값을 함께 보냅니다 — 예: 좌석 번호, 측정 점수. "
            "**실시간 중계(WebSocket)로만 전달되고 DB에는 저장되지 않습니다.** "
            "화면 시나리오가 즉시 쓰는 값을 담는 곳이며, 나중에 다시 볼 이력은 담지 마세요. "
            f"JSON으로 {MAX_EXTRA_BYTES}바이트, 키 {MAX_EXTRA_KEYS}개까지."
        ),
        examples=[{"seat": 3, "focus_score": 0.88}],
    )

    @field_validator("extra")
    @classmethod
    def _check_extra_size(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        너무 큰 값을 **조용히 버리지 않고** 분명히 거절합니다.

        조용히 버리면 "보냈는데 화면에 왜 안 오지?"로 학생이 한참 헤맵니다.
        """
        if value is None:
            return None
        if len(value) > MAX_EXTRA_KEYS:
            raise ValueError(
                f"extra의 키가 너무 많습니다({len(value)}개). {MAX_EXTRA_KEYS}개까지만 담으세요."
            )
        try:
            size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"extra는 JSON으로 바꿀 수 있는 값이어야 합니다 ({exc}). "
                "numpy 배열이나 이미지는 담을 수 없습니다."
            ) from exc
        if size > MAX_EXTRA_BYTES:
            raise ValueError(
                f"extra가 너무 큽니다({size}바이트). {MAX_EXTRA_BYTES}바이트까지만 담으세요 — "
                "좌표 배열이나 이미지가 아니라 '요약된 값'을 보내야 실시간 중계가 밀리지 않습니다."
            )
        return value
