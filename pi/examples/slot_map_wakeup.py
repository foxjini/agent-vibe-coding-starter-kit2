"""
★ wakeup 팀 배치표 예시 — 스마트 기상 시스템

쓰는 방법:  cp examples/slot_map_wakeup.py slot_map.py
핀 번호는 BCM 기준이며 예시입니다. 실제 배선에 맞게 고치세요.
"""

SLOTS = {
    # --- 액추에이터 ---
    "actuator_01": {
        "label": "알람 부저",
        "kind": "buzzer",
        "driver": "tonal_buzzer",
        "pin": 18,
        "control_type": "tonal",
        # 소리가 안 나면 여기를 바꿔 보세요: passive(수동 피에조) / active(능동 부저)
        "buzzer_type": "passive",
    },
    "actuator_02": {
        "label": "커튼",
        "kind": "servo",
        "driver": "servo",
        "pin": 12,
        "control_type": "servo",
        "value_schema": {"min": 0, "max": 180, "step": 5},
        "min_pulse_ms": 0.5, "max_pulse_ms": 2.4,   # SG90 — 180°까지 돌게
    },
    "actuator_03": {
        "label": "모션 베드",
        "kind": "servo",
        "driver": "servo",
        "pin": 13,
        "control_type": "servo",
        "value_schema": {"min": 0, "max": 180, "step": 5},
        "min_pulse_ms": 0.5, "max_pulse_ms": 2.4,
    },
    "actuator_04": {
        "label": "조명",
        "kind": "neopixel",
        "driver": "neopixel_out",
        "pin": 21,
        "control_type": "rgb",
        "count": 12,            # LED 알 개수 — 8알이 넘으면 별도 5V 전원
    },

    # --- 센서 ---
    "sensor_01": {
        "label": "기상 확인 버튼",
        "kind": "button",
        "driver": "button_in",
        "pin": 24,
        # 일반 푸시버튼은 True, 정전식 터치센서는 False
        "pull_up": True,
    },
    "sensor_02": {
        "label": "침대 압력",
        "kind": "pressure",
        "unit": "%",
        # 압력 센서(FSR)는 아날로그라 MCP3008 CH0을 거칩니다 — SPI를 켜 주세요 (sudo raspi-config)
        "driver": "analog_in",
        "channel": 0,
        "scale": 100,           # 0~1 비율 → 0~100 %
        "deadband": 1,          # 1 % 이상 바뀔 때만 보고
        "interval": 0.5,
    },

    # 기상 감지 웹캠은 슬롯을 쓰지 않습니다 — vision/ 클라이언트가 담당하고
    # 결과는 vision_events로 들어옵니다 (부록F 2-2절).
}
