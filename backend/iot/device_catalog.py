"""
디바이스 기본 정의 — Mock/Hardware Provider가 공유하는 단일 출처.

DB가 비어 있거나 연결되지 않았을 때 사용하는 메모리 폴백 상태이며,
`devices` 테이블의 id/kind와 100% 일치해야 합니다 (db/init.sql 시드 참고).
"""
from datetime import datetime, timezone
from typing import Any, Dict


def build_default_devices(simulated: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    기본 디바이스 상태 사전을 생성합니다.

    simulated=True (Mock 모드)면 시연용 초기 측정값을 채워 넣고,
    simulated=False (실기기 모드)면 '아직 보고받지 않음'을 뜻하는 빈 값으로 둡니다.
    실기기 모드에서 그럴듯한 가짜 값을 넣으면 배선이 빠져도 대시보드가 정상으로 보입니다.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "buzzer_1": {
            "id": "buzzer_1",
            "name": "알람 출력 장치(피에조 부저)",
            "kind": "buzzer",
            "is_actuator": True,
            "desired_state": "off",
            "current_state": "off" if simulated else None,
            "desired_value": {"volume": 80, "frequency": 1000},
            "current_value": {"volume": 80, "frequency": 1000} if simulated else None,
            "updated_at": now_iso,
        },
        "touch_pad_1": {
            "id": "touch_pad_1",
            "name": "패드 화면/터치 입력",
            "kind": "touch_pad",
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
            "name": "기상 감지 카메라",
            "kind": "camera",
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
    }
