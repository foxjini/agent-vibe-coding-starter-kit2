"""
★ subway 팀 배치표 예시 — 지하철 혼잡도 시스템

쓰는 방법:  cp examples/slot_map_subway.py slot_map.py
핀 번호는 BCM 기준이며 예시입니다. 실제 배선에 맞게 고치세요.
"""

SLOTS = {
    # --- 액추에이터 ---
    "actuator_01": {
        "label": "혼잡도 안내 LED",
        "kind": "level_led",
        "driver": "level_out",
        # LED를 여러 개 달고 단계로 켭니다. 앞에서부터 차례로 켜집니다.
        "pins": [5, 6, 13],
        "control_type": "level",
        # 0=여유, 1=보통, 2=혼잡, 3=매우혼잡
        "value_schema": {"min": 0, "max": 3, "step": 1},
    },
    "actuator_02": {
        "label": "배경 이동 컨베이어",
        "kind": "motor",
        "driver": "pwm_out",
        "pin": 12,
        "control_type": "pwm",
        "min_level": 25,        # 이보다 약하면 모터가 돌지 않습니다
    },

    # --- 센서 ---
    "sensor_01": {
        "label": "임산부석 압력",
        "kind": "pressure",
        "unit": "kg",
        # 라즈베리파이에는 아날로그 입력이 없어 ADC(MCP3008)를 거칩니다.
        # SPI를 켜 주세요: sudo raspi-config → Interface Options → SPI
        "driver": "analog_in",
        "channel": 0,
        "scale": 120,           # 0~1 비율에 곱할 값 (최대 120kg이면 120)
        "deadband": 0.5,        # 이만큼 변해야 보고 (노이즈로 차트가 지저분해지지 않게)
        "interval": 1.0,
    },

    # --- 필요해지면 주석을 풀어 쓰세요 ---
    # "sensor_02": {
    #     "label": "출입문 거리", "kind": "distance", "unit": "cm",
    #     "driver": "distance_in", "trigger_pin": 17, "echo_pin": 27, "interval": 0.5,
    # },

    # 객차 Pi Camera 3는 슬롯을 쓰지 않습니다 — vision/ 클라이언트가 담당합니다.
}
