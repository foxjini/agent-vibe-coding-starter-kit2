from typing import Optional
from pydantic import BaseModel, Field


class VisionEventRequest(BaseModel):
    event_type: str = Field(..., description="이벤트 종류 (예: 'gesture_detected', 'person_detected')")
    detected: bool = Field(..., description="감지 성공 여부")
    count: int = Field(default=0, description="감지된 객체 수")
    confidence: Optional[float] = Field(default=None, description="신뢰도 (0.0~1.0)")
