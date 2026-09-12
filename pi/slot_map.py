"""
★ 팀 하드웨어 배치표 (pi/slot_map.py) — **이 파일만 고치면 됩니다.**
=============================================================================
이 파일은 "어느 슬롯에 어떤 부품을 어느 핀으로 꽂았는가"만 적는 곳입니다.

  부품을 추가하고 싶다 → SLOTS에 한 줄 추가
  부품을 떼고 싶다     → SLOTS에서 그 줄을 삭제 (대시보드에서도 자동으로 사라집니다)
  핀을 바꿨다          → pin 값만 수정
  부저 종류를 바꿨다    → driver를 tonal_buzzer ↔ digital_out 으로 교체

백엔드·DB·vision·프론트엔드는 **한 줄도 고치지 않습니다.** (docs/부록F 8장)

-----------------------------------------------------------------------------
슬롯 이름은 정해져 있습니다 (바꿀 수 없습니다)
    센서       sensor_01 ~ sensor_10
    액추에이터  actuator_01 ~ actuator_10
쓰지 않는 슬롯은 그냥 적지 않으면 됩니다.

한 줄에 적는 것
    label        대시보드에 표시할 이름 (한글로 쓰세요)
    kind         부품 종류 (buzzer, led, servo, temperature …)
    driver       drivers/ 폴더의 파일 이름 (아래 표 참고)
    pin          GPIO 번호 (BCM 기준 — 보드의 물리 핀 번호가 아닙니다)
    control_type 대시보드 위젯 모양 (액추에이터만. 생략하면 드라이버 기본값)
    unit         단위 (센서만. °C, kg, cm …)
    interval     센서를 몇 초마다 읽을지 (기본 1초. 온습도는 5초 이상)

쓸 수 있는 드라이버
    [액추에이터] digital_out(on/off)  pwm_out(세기)  tonal_buzzer(주파수)
                 servo(각도)  neopixel_out(RGB)  level_out(단계)
    [센서]       button_in(버튼·터치·PIR)  analog_in(압력·조도)
                 dht_in(온습도)  distance_in(거리)
    확인 방법: python -c "import drivers; print(drivers.available_drivers())"
"""

SLOTS = {
    # =========================================================================
    # 액추에이터 (actuator_01 ~ actuator_10)
    # =========================================================================
    "actuator_01": {
        "label": "알람 부저",
        "kind": "buzzer",
        "driver": "tonal_buzzer",
        "pin": 18,
        "control_type": "tonal",
        # 소리가 안 나면 여기를 바꿔 보세요: passive(수동 피에조) / active(능동 부저)
        "buzzer_type": "passive",
    },

    # =========================================================================
    # 센서 (sensor_01 ~ sensor_10)
    # =========================================================================
    "sensor_01": {
        "label": "기상 확인 버튼",
        "kind": "button",
        "driver": "button_in",
        "pin": 24,
        # 일반 푸시버튼은 True, 정전식 터치센서·PIR은 False
        "pull_up": True,
    },

    # -------------------------------------------------------------------------
    # 아래는 2차 개발에서 부품을 추가할 때 쓰는 예시입니다.
    # 실제로 부품을 달았다면 앞의 # 를 지우고 핀 번호를 맞춰 주세요.
    # -------------------------------------------------------------------------
    # "actuator_02": {
    #     "label": "경보 LED", "kind": "led",
    #     "driver": "digital_out", "pin": 23, "control_type": "onoff",
    #     "blink": True,
    # },
    # "actuator_03": {
    #     "label": "자동문", "kind": "servo",
    #     "driver": "servo", "pin": 12, "control_type": "servo",
    #     "value_schema": {"min": 0, "max": 180, "step": 5},
    # },
    # "actuator_04": {
    #     "label": "좌석 표시등", "kind": "neopixel",
    #     "driver": "neopixel_out", "pin": 21, "control_type": "rgb", "count": 8,
    # },
    # "actuator_05": {
    #     "label": "혼잡도 표시등", "kind": "level_led",
    #     "driver": "level_out", "pins": [5, 6, 13], "control_type": "level",
    #     "value_schema": {"min": 0, "max": 3, "step": 1},
    # },
    # "sensor_02": {
    #     "label": "실내 온도", "kind": "temperature", "unit": "°C",
    #     "driver": "dht_in", "pin": 4, "interval": 5.0,
    # },
    # "sensor_03": {
    #     "label": "좌석 압력", "kind": "pressure", "unit": "kg",
    #     "driver": "analog_in", "channel": 0, "scale": 120, "deadband": 0.5,
    # },
    # "sensor_04": {
    #     "label": "출입문 거리", "kind": "distance", "unit": "cm",
    #     "driver": "distance_in", "trigger_pin": 23, "echo_pin": 27, "interval": 0.5,
    # },
}
