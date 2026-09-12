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
            "검출기가 내보내는 라벨. 사물 검출기는 COCO 클래스명('person', 'bottle')을 쓰고, "
            "팀이 추가한 검출기는 그 검출기가 선언한 라벨을 씁니다(vision/detectors/ 참고). "
            "백엔드는 라벨 값을 해석하지 않고 그대로 저장·중계합니다. "
            "생략하면 event_type에서 유추합니다(구버전 호환)."
        ),
        examples=["person"],
    )
