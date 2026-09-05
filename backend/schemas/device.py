from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActuatorControlRequest(BaseModel):
    desired_state: str = Field(..., description="목표 상태 (예: 'ringing', 'off')")
    value: Optional[Any] = Field(default=None, description="주파수, 볼륨 등 추가 제어값")


class DeviceStateReportRequest(BaseModel):
    # 액추에이터 보고 시: state, value
    # 센서 보고 시: value, unit
    state: Optional[str] = Field(default=None, description="반영된 실제 상태")
    value: Optional[Any] = Field(default=None, description="상태 값 또는 센서 측정값")
    unit: Optional[str] = Field(default=None, description="센서 측정 단위")
    reported_at: Optional[str] = Field(default=None, description="보고 시각 (ISO 8601)")


class DeviceResponse(BaseModel):
    id: str
    name: str
    kind: str
    desired_state: Optional[str] = None
    current_state: Optional[str] = None
    desired_value: Optional[Any] = None
    current_value: Optional[Any] = None
    updated_at: Optional[Any] = None
    created_at: Optional[Any] = None


class DesiredStateResponse(BaseModel):
    device_id: str
    kind: str
    desired_state: Optional[str] = None
    value: Optional[Any] = None
    updated_at: Optional[Any] = None
