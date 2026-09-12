"""
디바이스 기본 정의 — Mock/Hardware Provider가 공유하는 단일 출처.

DB가 비어 있거나 연결되지 않았을 때 사용하는 메모리 폴백 상태이며,
`devices` 테이블의 id/role과 100% 일치해야 합니다 (db/init.sql 시드 참고).

두 종류의 행이 들어 있습니다.
1) 플랫폼 키트 슬롯 20개 (sensor_01~10 / actuator_01~10)
   - 기본값은 enabled=False. 팀이 pi의 register 또는 대시보드 설정으로 켭니다.
   - 백엔드는 슬롯에 무엇이 꽂혀 있는지 모릅니다 (부록F 2장).
2) 레거시 디바이스 (buzzer_1 / touch_pad_1 / camera_1)
   - wakeup 팀 1차 시스템 호환용. P3.5에서 슬롯으로 교체됩니다.
"""
from datetime import datetime, timezone
from typing import Any, Dict

SLOT_COUNT = 10
UNASSIGNED_KIND = "unassigned"


def _slot_entry(slot_id: str, role: str, index: int, now_iso: str) -> Dict[str, Any]:
    """빈 슬롯 한 칸. 팀이 등록하기 전까지는 라벨도 종류도 없습니다."""
    return {
        "id": slot_id,
        "slot_id": slot_id,
        "name": slot_id,
        "label": None,
        "kind": UNASSIGNED_KIND,
        "role": role,
        "slot_index": index,
        "enabled": False,
        "is_actuator": role == "actuator",
        "unit": None,
        "control_type": None,
        "value_schema": None,
        "meta": None,
        "display_order": 0,
        "desired_state": "off" if role == "actuator" else None,
        "current_state": None,
        "desired_value": None,
        "current_value": None,
        "updated_at": now_iso,
    }


def build_slot_registry(now_iso: str = None) -> Dict[str, Dict[str, Any]]:
    """플랫폼 키트 슬롯 20개를 만듭니다 (전부 enabled=False)."""
    now_iso = now_iso or datetime.now(timezone.utc).isoformat()
    registry: Dict[str, Dict[str, Any]] = {}
    for index in range(1, SLOT_COUNT + 1):
        sensor_id = f"sensor_{index:02d}"
        actuator_id = f"actuator_{index:02d}"
        registry[sensor_id] = _slot_entry(sensor_id, "sensor", index, now_iso)
        registry[actuator_id] = _slot_entry(actuator_id, "actuator", index, now_iso)
    return registry


def build_default_devices(simulated: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    기본 디바이스 상태 사전을 생성합니다 (슬롯 20개 + 레거시 3개).

    simulated=True (Mock 모드)면 시연용 초기 측정값을 채워 넣고,
    simulated=False (실기기 모드)면 '아직 보고받지 않음'을 뜻하는 빈 값으로 둡니다.
    실기기 모드에서 그럴듯한 가짜 값을 넣으면 배선이 빠져도 대시보드가 정상으로 보입니다.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    devices = build_slot_registry(now_iso)

    # --- 레거시 디바이스 (wakeup 1차 시스템 호환, P3.5에서 제거 예정) ---
    devices.update({
        "buzzer_1": {
            "id": "buzzer_1",
            "slot_id": "buzzer_1",
            "name": "알람 출력 장치(피에조 부저)",
            "label": "알람 출력 장치(피에조 부저)",
            "kind": "buzzer",
            "role": "actuator",
            "slot_index": 0,
            "enabled": True,
            "is_actuator": True,
            "control_type": "tonal",
            "desired_state": "off",
            "current_state": "off" if simulated else None,
            "desired_value": {"volume": 80, "frequency": 1000},
            "current_value": {"volume": 80, "frequency": 1000} if simulated else None,
            "updated_at": now_iso,
        },
        "touch_pad_1": {
            "id": "touch_pad_1",
            "slot_id": "touch_pad_1",
            "name": "패드 화면/터치 입력",
            "label": "패드 화면/터치 입력",
            "kind": "touch_pad",
            "role": "sensor",
            "slot_index": 0,
            "enabled": True,
            "is_actuator": False,
            "desired_state": None,
            "current_state": "idle" if simulated else None,
            "desired_value": None,
            "current_value": {
                "pressed": False,
                "touch_x": 0,
                "touch_y": 0,
                "gesture": "none",
            } if simulated else None,
            "updated_at": now_iso,
        },
        "camera_1": {
            "id": "camera_1",
            "slot_id": "camera_1",
            "name": "기상 감지 카메라",
            "label": "기상 감지 카메라",
            "kind": "camera",
            "role": "sensor",
            "slot_index": 0,
            "enabled": True,
            "is_actuator": False,
            "desired_state": None,
            "current_state": "idle" if simulated else None,
            "desired_value": None,
            "current_value": {
                "person_detected": False,
                "confidence": 0.0,
                "gesture": "none",
                "motion_detected": False,
            } if simulated else None,
            "updated_at": now_iso,
        },
    })
    return devices
