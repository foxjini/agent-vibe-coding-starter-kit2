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

    # --- 센서 ---
    "sensor_01": {
        "label": "기상 확인 버튼",
        "kind": "button",
        "driver": "button_in",
        "pin": 24,
        # 일반 푸시버튼은 True, 정전식 터치센서는 False
        "pull_up": True,
    },

    # 기상 감지 웹캠은 슬롯을 쓰지 않습니다 — vision/ 클라이언트가 담당하고
    # 결과는 vision_events로 들어옵니다 (부록F 2-2절).
}
