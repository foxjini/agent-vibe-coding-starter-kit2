"""
플랫폼 키트 슬롯 API 스키마 (docs/부록F-IoT-개발-플랫폼-키트-규약.md 5장)

슬롯 ID는 sensor_01~sensor_10 / actuator_01~actuator_10 으로 고정되어 있고,
부품의 '의미'는 아래 메타데이터로만 표현됩니다 — 백엔드 코드는 의미를 모릅니다.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SlotMetadataUpdate(BaseModel):
    """PATCH /api/slots/{slot_id} — 팀이 슬롯에 의미를 부여합니다."""
    enabled: Optional[bool] = Field(default=None, description="사용 여부 (제거 = false)")
    label: Optional[str] = Field(default=None, max_length=100, description="화면에 보이는 이름")
    kind: Optional[str] = Field(
        default=None, max_length=30,
        description="분류 (buzzer/servo/led/relay/temperature/button …)",
    )
    unit: Optional[str] = Field(default=None, max_length=20, description="센서 단위 (°C, kg, cm)")
    control_type: Optional[str] = Field(
        default=None, max_length=20,
        description="액추에이터 제어 방식: onoff/pulse/tonal/pwm/servo/rgb/level",
    )
    value_schema: Optional[Dict[str, Any]] = Field(
        default=None, description='위젯 범위. 예: {"min":0,"max":180,"step":1}'
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None, description='팀 자유 확장. 예: {"pin":18,"note":"교실 앞문"}'
    )
    display_order: Optional[int] = Field(default=None, ge=0, le=99, description="대시보드 정렬 순서")


class SlotRegistration(SlotMetadataUpdate):
    """POST /api/v1/devices/register 의 슬롯 1개 항목."""
    slot_id: str = Field(..., description="sensor_01 … actuator_10", examples=["actuator_01"])


class SlotRegisterRequest(BaseModel):
    """
    라즈베리파이가 부팅 시 자기 배선을 일괄 등록합니다.

    exclusive=True(기본)면 목록에 없는 슬롯은 자동으로 enabled=false가 됩니다
    → pi/slot_map.py에서 한 줄을 지우면 대시보드에서도 사라집니다.
    """
    slots: List[SlotRegistration] = Field(..., min_length=0, max_length=20)
    exclusive: bool = Field(default=True, description="목록에 없는 슬롯을 자동 비활성화")


class StateReport(BaseModel):
    """
    배치 보고 1건.

    - state가 있으면 **액추에이터 반영 결과**로 처리합니다.
    - state가 없으면 **센서 측정값**으로 처리합니다.
    """
    slot_id: str = Field(..., description="sensor_01 … actuator_10 (레거시 디바이스 ID도 허용)")
    state: Optional[str] = Field(default=None, description="액추에이터가 실제로 반영한 상태")
    value: Optional[Any] = Field(
        default=None,
        description='액추에이터 값 또는 센서 측정값. 숫자 센서는 {"value": 24.5} 형식',
    )
    unit: Optional[str] = Field(default=None, max_length=20)


class StateReportRequest(BaseModel):
    """POST /api/v1/devices/states — 여러 슬롯을 한 번에 보고합니다."""
    states: List[StateReport] = Field(..., min_length=1, max_length=40)
    reported_at: Optional[str] = Field(default=None, description="보고 시각 (ISO 8601)")


class RuleUpsertRequest(BaseModel):
    """자동화 규칙 생성/수정 (부록F 7장)."""
    name: str = Field(..., max_length=100)
    definition: Dict[str, Any] = Field(
        ...,
        description='{"when": {...}, "then": [...], "otherwise": [...], "cooldown_seconds": 30}',
    )
    enabled: bool = Field(default=True)
    priority: int = Field(default=0, ge=0, le=99)
