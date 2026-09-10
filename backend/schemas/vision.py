from typing import Optional
from pydantic import BaseModel, Field


class VisionEventRequest(BaseModel):
    event_type: str = Field(
        ...,
        description="이벤트 종류 (예: 'object_detected', 'gesture_detected', 'person_cleared')",
    )
    detected: bool = Field(..., description="감지 성공 여부")
    count: int = Field(default=0, description="감지된 객체 수")
    confidence: Optional[float] = Field(default=None, description="신뢰도 (0.0~1.0)")
    label: Optional[str] = Field(
        default=None,
        description=(
            "감지 대상 이름. 사물이면 COCO 클래스명('person', 'bottle'), "
            "손동작이면 'rock' / 'paper' / 'scissors'. "
            "생략하면 백엔드가 event_type에서 유추합니다(구버전 호환)."
        ),
        examples=["person", "rock"],
    )
