from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceControlRequest(BaseModel):
    """대시보드 사용자가 액추에이터 상태 제어 시 전송하는 스키마"""
    desired_state: str = Field(..., description="목표 상태 (예: 'unlocked', 'on', 'playing')")
    value: Optional[Any] = Field(None, description="추가 제어 파라미터 (밝기, 볼륨 등)")


class DeviceStateReportRequest(BaseModel):
    """라즈베리파이(또는 센서)가 실제 상태 또는 측정값을 보고할 때 전송하는 스키마"""
    state: Optional[str] = Field(None, description="액추에이터 실제 반영 상태")
    value: Optional[Any] = Field(None, description="단일 측정값 또는 서보각도/볼륨 등")
    unit: Optional[str] = Field(None, description="측정 단위 (celsius, detection 등)")
    reported_at: Optional[str] = Field(None, description="측정/보고 시각 (ISO 8601)")


class VisionEventRequest(BaseModel):
    """영상인식(YOLOv8) 클라이언트가 감지 이벤트를 전송할 때 사용하는 스키마"""
    event_type: str = Field(..., description="감지된 이벤트 종류 (예: person_detected, entry)")
    detected: bool = Field(False, description="감지 여부")
    count: int = Field(0, description="감지 객체 수")
    confidence: Optional[float] = Field(None, description="인식 신뢰도 (0.0 ~ 1.0)")


class DeviceResponse(BaseModel):
    """디바이스 단일 응답 모델"""
    id: str
    name: str
    kind: str
    desired_state: Optional[str] = None
    current_state: Optional[str] = None
    desired_value: Optional[Any] = None
    current_value: Optional[Any] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
