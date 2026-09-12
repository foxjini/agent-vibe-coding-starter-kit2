"""
★ study 팀 배치표 예시 — 스마트 학습 공간

쓰는 방법:  cp examples/slot_map_study.py slot_map.py
핀 번호는 BCM 기준이며 예시입니다. 실제 배선에 맞게 고치세요.
"""

SLOTS = {
    # --- 액추에이터 ---
    "actuator_01": {
        "label": "스탠드 RGB 조명",
        "kind": "rgb_led",
        # 핀이 3개(R·G·B)인 모듈이면 rgb_out,
        # 데이터선 하나로 여러 알을 제어하는 네오픽셀이면 neopixel_out을 쓰세요.
        "driver": "rgb_out",
        "pins": {"r": 17, "g": 27, "b": 22},
        "control_type": "rgb",
        # 색이 반대로 나오면(빨강을 켰는데 청록) 공통 양극 모듈입니다 → True
        "common_anode": False,
    },
    "actuator_02": {
        "label": "등받이 진동 모터",
        "kind": "vibrator",
        "driver": "pwm_out",
        "pin": 13,
        "control_type": "pwm",
        # 너무 약하면 안 돌아가는 모터가 있습니다 — 최소 세기를 올려 주세요
        "min_level": 30,
    },
    "actuator_03": {
        "label": "방석 진동 모터",
        "kind": "vibrator",
        "driver": "pwm_out",
        "pin": 19,
        "control_type": "pwm",
        "min_level": 30,
    },
    "actuator_04": {
        "label": "스탠드 전원 릴레이",
        "kind": "relay",
        "driver": "digital_out",
        "pin": 16,
        "control_type": "onoff",
    },

    # --- 센서 ---
    "sensor_01": {
        "label": "터치 입력",
        "kind": "touch",
        "driver": "button_in",
        "pin": 24,
        # 정전식 터치센서는 감지하면 HIGH를 내므로 False입니다
        "pull_up": False,
    },

    # 정면 USB 웹캠은 슬롯을 쓰지 않습니다 — vision/ 클라이언트가 담당합니다.
}
