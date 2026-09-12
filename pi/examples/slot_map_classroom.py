"""
★ classroom 팀 배치표 예시 — 스마트 교실

쓰는 방법:  cp examples/slot_map_classroom.py slot_map.py
핀 번호는 BCM 기준이며 예시입니다. 실제 배선에 맞게 고치세요.
"""

SLOTS = {
    # --- 액추에이터 5개 ---
    "actuator_01": {
        "label": "자동문 서보",
        "kind": "servo",
        "driver": "servo",
        "pin": 12,
        "control_type": "servo",
        # 문이 열리는 각도 범위. 대시보드 슬라이더 범위가 이 값으로 정해집니다.
        "value_schema": {"min": 0, "max": 120, "step": 5},
        "rest_angle": 0,        # 평소(닫힘) 각도
    },
    "actuator_02": {
        "label": "좌석 안내 LED",
        "kind": "led",
        "driver": "digital_out",
        "pin": 23,
        "control_type": "onoff",
    },
    "actuator_03": {
        "label": "교실 분위기 조명(네오픽셀)",
        "kind": "neopixel",
        "driver": "neopixel_out",
        "pin": 21,
        "control_type": "rgb",
        "count": 12,            # LED 알 개수
    },
    "actuator_04": {
        "label": "수업 알림 부저",
        "kind": "buzzer",
        "driver": "tonal_buzzer",
        "pin": 18,
        "control_type": "tonal",
        "buzzer_type": "passive",
    },
    "actuator_05": {
        "label": "교실 조명 릴레이",
        "kind": "relay",
        "driver": "digital_out",
        "pin": 16,
        "control_type": "onoff",
        # LOW에서 켜지는 릴레이 모듈이면 False로 바꾸세요 (반대로 동작하면 이것입니다)
        "active_high": True,
    },

    # --- 센서 (필요해지면 주석을 풀어 쓰세요) ---
    # "sensor_01": {
    #     "label": "교실 온도", "kind": "temperature", "unit": "°C",
    #     "driver": "dht_in", "pin": 4, "interval": 5.0,
    # },
    # "sensor_02": {
    #     "label": "출입문 거리", "kind": "distance", "unit": "cm",
    #     "driver": "distance_in", "trigger_pin": 17, "echo_pin": 27, "interval": 0.5,
    # },

    # FHD 출입 웹캠은 슬롯을 쓰지 않습니다 — vision/ 클라이언트가 담당합니다.
}
