"""
pi 자가 점검 (pi/test_slot_daemon.py)
=============================================================================
GPIO가 없는 PC에서도 돌아갑니다. 백엔드도 켜지 않아도 됩니다(가짜 백엔드를 씁니다).

실행 방법 (pi 폴더에서):
    python test_slot_daemon.py

무엇을 확인하나요?
 1) 기본 드라이버가 모두 만들어지고 apply()/read() 계약을 지키는지
 2) 배치표 오타(슬롯 이름·드라이버·핀 중복)를 실행 전에 잡아내는지
 3) 부품을 **한 줄 추가/삭제**하면 등록·폴링·보고가 따라오는지
 4) 백엔드가 끊겨도 죽지 않고, 돌아오면 자동으로 다시 등록하는지
 5) 종료할 때 부품을 켜 둔 채로 끝내지 않는지
"""
import os
import sys
from typing import Any, Dict, List, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault("DEVICE_MODE", "mock")
os.environ.setdefault("DEVICE_API_KEY", "test_key_for_self_check")

from daemon import SlotDaemon                      # noqa: E402
from drivers import available_drivers, create_driver  # noqa: E402
from drivers.base import ActuatorDriver, SensorDriver  # noqa: E402
from slot_config import validate_slots             # noqa: E402

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return bool(condition)


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * 68)


class FakeBackend:
    """백엔드를 흉내냅니다 — 서버를 켜지 않고 데몬 전체를 돌려 보기 위해."""

    def __init__(self) -> None:
        self.enabled: Dict[str, Dict[str, Any]] = {}
        self.desired: Dict[str, Dict[str, Any]] = {}
        self.reports: List[Dict[str, Any]] = []
        self.register_calls = 0
        self.offline = False
        self.reject_next: Optional[str] = None

    # --- BackendClient와 같은 인터페이스 ---

    def register(self, slots: List[Dict[str, Any]], exclusive: bool = True):
        if self.offline:
            return None
        self.register_calls += 1
        incoming = {s["slot_id"]: s for s in slots}
        disabled = [s for s in self.enabled if exclusive and s not in incoming]
        for slot_id in disabled:
            self.enabled.pop(slot_id)
            self.desired.pop(slot_id, None)
        self.enabled.update(incoming)
        return {"registered": list(incoming), "disabled": disabled, "rejected": []}

    def poll_desired_states(self):
        if self.offline:
            return None
        return {
            slot_id: dict(wanted)
            for slot_id, wanted in self.desired.items()
            if slot_id in self.enabled
        }

    def report_states(self, states: List[Dict[str, Any]]):
        if self.offline:
            return None
        self.reports.extend(states)
        rejected = []
        if self.reject_next:
            rejected.append({"slot_id": self.reject_next, "reason": "SLOT_DISABLED"})
            self.reject_next = None
        return {"accepted": len(states), "rejected": rejected}

    # --- 시나리오 조작용 ---

    def command(self, slot_id: str, state: str, value: Any = None) -> None:
        self.desired[slot_id] = {"slot_id": slot_id, "desired_state": state, "value": value}

    def reported(self, slot_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.reports if r.get("slot_id") == slot_id]


# 팀이 실제로 쓸 만한 배치표 — 기본 드라이버를 고루 덮습니다.
FULL_MAP: Dict[str, Dict[str, Any]] = {
    "actuator_01": {"label": "알람 부저", "kind": "buzzer", "driver": "tonal_buzzer",
                    "pin": 18, "control_type": "tonal", "buzzer_type": "passive"},
    "actuator_02": {"label": "경보 LED", "kind": "led", "driver": "digital_out",
                    "pin": 23, "control_type": "onoff"},
    "actuator_03": {"label": "진동 모터", "kind": "vibration_motor", "driver": "pwm_out",
                    "pin": 13, "control_type": "pwm"},
    "actuator_04": {"label": "자동문", "kind": "servo", "driver": "servo",
                    "pin": 12, "control_type": "servo",
                    "value_schema": {"min": 0, "max": 180, "step": 5}},
    "actuator_05": {"label": "좌석 표시등", "kind": "neopixel", "driver": "neopixel_out",
                    "pin": 21, "control_type": "rgb", "count": 8},
    "actuator_06": {"label": "혼잡도 표시등", "kind": "level_led", "driver": "level_out",
                    "pins": [5, 6, 16], "control_type": "level"},
    "actuator_07": {"label": "스탠드 조명", "kind": "rgb_led", "driver": "rgb_out",
                    "pins": {"r": 25, "g": 8, "b": 7}, "control_type": "rgb"},
    "sensor_01": {"label": "기상 버튼", "kind": "button", "driver": "button_in", "pin": 24},
    "sensor_02": {"label": "좌석 압력", "kind": "pressure", "unit": "kg",
                  "driver": "analog_in", "channel": 0, "scale": 120},
    "sensor_03": {"label": "실내 온도", "kind": "temperature", "unit": "°C",
                  "driver": "dht_in", "pin": 4, "interval": 5.0},
    "sensor_04": {"label": "출입문 거리", "kind": "distance", "unit": "cm",
                  "driver": "distance_in", "trigger_pin": 17, "echo_pin": 27},
}


def main_test() -> int:
    print("=" * 68)
    print(" 라즈베리파이 슬롯 데몬 — 자가 점검")
    print("=" * 68)

    # ------------------------------------------------------------------
    section("1. 드라이버 계약 (apply / read)")
    names = available_drivers()
    # 드라이버는 파일을 넣으면 늘어납니다. 개수를 고정하지 말고 '있어야 할 것'만 확인합니다.
    required = {
        "digital_out", "pwm_out", "tonal_buzzer", "servo", "neopixel_out", "rgb_out",
        "level_out", "button_in", "analog_in", "dht_in", "distance_in", "servo360", "aht20_in", "servo_hold",
    }
    check(f"기본 드라이버가 모두 있음 (현재 {len(names)}종)", required <= set(names),
          f"빠진 것: {sorted(required - set(names))}")

    usable, problems = validate_slots(FULL_MAP)
    check("여러 드라이버를 쓰는 배치표가 검사를 통과", not problems, str(problems))

    drivers = {slot_id: create_driver(slot_id, config) for slot_id, config in usable.items()}
    check("배치표 10줄이 모두 드라이버로 만들어짐", len(drivers) == len(FULL_MAP))
    check("PC에서는 모두 흉내내기로 대체됨 (죽지 않음)",
          all(d.simulated for d in drivers.values()),
          str([s for s, d in drivers.items() if not d.simulated]))

    actuators = [d for d in drivers.values() if isinstance(d, ActuatorDriver)]
    check("액추에이터 apply()가 반영된 상태를 돌려줌",
          all(d.apply("on", {"angle": 90, "duty": 50, "frequency": 880,
                             "volume": 70, "color": "#ff0000"}) == "on" for d in actuators))
    check("액추에이터 apply('off')가 off를 돌려줌",
          all(d.apply("off") == "off" for d in actuators))

    # 부록F 3-1절: control_type마다 desired_state와 value 형식이 정해져 있습니다.
    # 반영 결과(current_state)가 desired_state와 다르면 대시보드가 영원히 '반영 대기'로 보입니다.
    contract = [
        ("servo", {"driver": "servo", "pin": 12, "control_type": "servo"}, "move", {"angle": 90}),
        ("onoff", {"driver": "digital_out", "pin": 23, "control_type": "onoff"}, "on", None),
        ("pulse", {"driver": "digital_out", "pin": 26, "control_type": "pulse"}, "on",
         {"on_time": 0.25, "off_time": 0.15}),
        ("tonal", {"driver": "tonal_buzzer", "pin": 18, "control_type": "tonal"}, "on",
         {"frequency": 880, "volume": 70}),
        ("pwm", {"driver": "pwm_out", "pin": 13, "control_type": "pwm"}, "on", {"duty": 70}),
        ("rgb", {"driver": "neopixel_out", "pin": 21, "control_type": "rgb"}, "on",
         {"r": 255, "g": 0, "b": 0}),
        ("level", {"driver": "level_out", "pins": [5, 6, 16], "control_type": "level"}, "on",
         {"level": 2}),
    ]
    mismatches = []
    for index, (control_type, config, state, value) in enumerate(contract):
        driver = create_driver(f"actuator_{index + 1:02d}", {**config, "label": control_type})
        if driver.apply(state, value) != state:
            mismatches.append(control_type)
        driver.close()
    check("control_type 7종이 desired_state를 그대로 반영 보고 (부록F 3-1절)",
          not mismatches, f"어긋난 것: {mismatches}")

    servo = create_driver("actuator_01", {"driver": "servo", "pin": 12, "control_type": "servo"})
    servo.apply("move", {"angle": 90})
    check("servo의 'move' 상태를 켜짐으로 인식 (각도 반영)", servo._angle == 90.0, str(servo._angle))
    servo.close()

    pwm = create_driver("actuator_02", {"driver": "pwm_out", "pin": 13, "control_type": "pwm"})
    pwm.apply("on", {"duty": 70})
    check("pwm이 {'duty': 70}을 세기 70%로 반영", abs(pwm.device.value - 0.7) < 0.001,
          str(pwm.device.value))
    pwm.close()

    # 360도 연속 회전 서보 (MG-90 360° 등) — 각도가 아니라 속도, 끄면 확실히 멈춤
    spin = create_driver("actuator_05", {"driver": "servo360", "pin": 13, "control_type": "pwm",
                                         "value_schema": {"min": -100, "max": 100, "step": 10}})
    check("servo360 켜기(속도 60)는 'on'으로 보고", spin.apply("on", {"duty": 60}) == "on")
    check("servo360 속도 60 → 정방향 0.6", spin.device.value == 0.6, str(spin.device.value))
    spin.apply("on", {"duty": -40})
    check("servo360 속도 -40 → 역방향 -0.4", spin.device.value == -0.4, str(spin.device.value))
    spin.apply("on", {"duty": 3})
    check("servo360 아주 작은 속도(3)는 정지 — 펄스를 끊음", spin.device.value is None,
          str(spin.device.value))
    spin.apply("on", {"duty": 80})
    check("servo360 끄기 → 정지 (펄스를 끊음)",
          spin.apply("off") == "off" and spin.device.value is None, str(spin.device.value))
    spin.close()
    reverse = create_driver("actuator_06", {"driver": "servo360", "pin": 12, "reverse": True,
                                            "control_type": "pwm"})
    reverse.apply("on", {"speed": 50})
    check("servo360 reverse: True면 방향 반대 ({'speed': 50} → -0.5)",
          reverse.device.value == -0.5, str(reverse.device.value))
    reverse.close()

    # AHT20 (I2C 온습도) — 변환식은 데이터시트 계산과 같아야 합니다
    from drivers.aht20_in import crc8, parse_measurement
    sample = bytes([0x1C, 0x66, 0x66, 0x65, 0x99, 0x9A])   # 습도 40% · 온도 20℃가 되도록 만든 값
    temperature, humidity = parse_measurement(sample)
    check("AHT20 측정값 변환 (습도 40% · 온도 20℃)",
          abs(humidity - 40.0) < 0.01 and abs(temperature - 20.0) < 0.01,
          f"temperature={temperature:.3f}, humidity={humidity:.3f}")
    check("AHT20 CRC-8 (데이터시트 예: 0xBE·0xEF → 0x92)", crc8(bytes([0xBE, 0xEF])) == 0x92,
          hex(crc8(bytes([0xBE, 0xEF]))))
    aht_t = create_driver("sensor_05", {"driver": "aht20_in", "label": "교실 온도", "unit": "°C"})
    aht_h = create_driver("sensor_06", {"driver": "aht20_in", "label": "교실 습도", "unit": "%",
                                        "measure": "humidity"})
    t_read, h_read = aht_t.read(), aht_h.read()
    check("AHT20 온도·습도 슬롯 2개가 PC에서도 숫자를 보고 (흉내내기)",
          isinstance(t_read, dict) and isinstance(h_read, dict) and 15 < t_read["value"] < 30
          and 30 < h_read["value"] < 70, f"{t_read} {h_read}")
    aht_t.close()
    aht_h.close()
    _, problems = validate_slots({
        "sensor_05": {"driver": "aht20_in", "kind": "temperature", "unit": "°C"},
        "sensor_06": {"driver": "aht20_in", "kind": "humidity", "unit": "%", "measure": "humidity"},
    })
    check("AHT20 온도·습도 두 슬롯은 핀 충돌 없이 통과", not problems, str(problems))
    _, problems = validate_slots({
        "sensor_05": {"driver": "aht20_in", "kind": "temperature", "unit": "°C"},
        "actuator_01": {"driver": "digital_out", "pin": 2, "control_type": "onoff"},
    })
    check("I2C 핀(GPIO 2)을 다른 부품이 쓰면 알려 줌",
          len(problems) == 1 and "I2C" in problems[0], str(problems))

    # 서보 떨림 — detach_after를 적으면 움직인 뒤 신호를 끊음 (안 적으면 예전처럼 계속 잡음)
    import time as _time
    hold = create_driver("actuator_07", {"driver": "servo", "pin": 19, "control_type": "servo"})
    hold.apply("move", {"angle": 45})
    _time.sleep(0.15)
    check("servo 기본: 움직인 뒤에도 신호를 유지 (예전과 같음)",
          hold.device.value is not None and hold._detach_timer is None, f"value={hold.device.value}")
    hold.close()
    calm = create_driver("actuator_07", {"driver": "servo", "pin": 19, "control_type": "servo",
                                         "detach_after": 0.1})
    calm.apply("move", {"angle": 45})
    _time.sleep(0.3)
    check("servo detach_after 0.1 → 움직이고 0.1초 뒤 신호 끊음 (떨림 방지)",
          calm.device.value is None and calm._angle == 45.0, f"value={calm.device.value}")
    calm.apply("move", {"angle": 90})
    check("신호를 끊은 뒤에도 다음 명령으로 다시 움직임", calm._angle == 90.0, str(calm._angle))
    calm.close()

    # 힘을 유지하는 서보 (MG996R) — detach_after를 적어도 신호를 끊지 않음, 천천히 이동
    strong = create_driver("actuator_08", {"driver": "servo_hold", "pin": 18, "control_type": "servo",
                                           "detach_after": 0.1, "rest_angle": 0})
    check("servo_hold는 시작할 때 rest_angle(0도)로 잡고 버팀", strong._angle == 0.0, str(strong._angle))
    check("servo_hold 'move'를 그대로 보고", strong.apply("move", {"angle": 90}) == "move")
    _time.sleep(0.3)
    check("servo_hold는 detach_after를 적어도 신호를 유지 (힘 유지)",
          strong.device.value is not None and strong._angle == 90.0, f"value={strong.device.value}")
    strong.apply("off")
    check("servo_hold 끄기 → rest_angle로 가서 버팀", strong._angle == 0.0, str(strong._angle))
    strong.close()
    slow = create_driver("actuator_08", {"driver": "servo_hold", "pin": 18, "control_type": "servo",
                                         "speed": 300, "rest_angle": 0})
    slow.apply("move", {"angle": 120})
    _time.sleep(0.15)
    middle = slow._angle
    check("servo_hold speed 300 → 0.15초 뒤 아직 가는 중 (한 번에 휙 돌지 않음)",
          middle is not None and 0 < middle < 120, str(middle))
    slow.apply("move", {"angle": 0})
    _time.sleep(0.7)
    check("이동 중 새 명령 → 그 자리에서 방향을 바꿔 새 목표(0도)에 도착", slow._angle == 0.0, str(slow._angle))
    slow.apply("move", {"angle": 60})
    _time.sleep(0.5)
    check("servo_hold 천천히 이동해 목표(60도)에 정확히 도착", slow._angle == 60.0, str(slow._angle))
    slow.close()

    # DHT 하나로 온도·습도 슬롯 2개 — 센서를 한 번만 열고, 한 번 잰 값을 나눠 써야 합니다
    import types as _types
    opened, measured = [], []

    class _FakeDHT:
        def __init__(self, pin, **kwargs):
            opened.append(pin)
            self.exited = False

        @property
        def temperature(self):
            measured.append("t")
            return 21.5

        @property
        def humidity(self):
            return 44.0

        def exit(self):
            self.exited = True

    saved = {name: sys.modules.get(name) for name in ("adafruit_dht", "board")}
    sys.modules["adafruit_dht"] = _types.SimpleNamespace(DHT11=_FakeDHT, DHT22=_FakeDHT)
    sys.modules["board"] = _types.SimpleNamespace(D4="D4")
    try:
        dht_t = create_driver("sensor_07", {"driver": "dht_in", "pin": 4, "model": "DHT11",
                                            "label": "온도", "unit": "°C"})
        dht_h = create_driver("sensor_08", {"driver": "dht_in", "pin": 4, "model": "DHT11",
                                            "measure": "humidity", "label": "습도", "unit": "%"})
        check("DHT 같은 핀 두 슬롯 → 센서는 한 번만 엶", opened == ["D4"] and not dht_h.simulated,
              str(opened))
        t_val, h_val = dht_t.read(), dht_h.read()
        check("DHT 온도·습도가 한 번 잰 값을 나눠 씀 (21.5℃ · 44%)",
              t_val == {"value": 21.5} and h_val == {"value": 44.0} and measured == ["t"],
              f"{t_val} {h_val} 측정 {len(measured)}번")
        sensor = dht_t.sensor
        dht_t.close()
        check("한 슬롯을 닫아도 다른 슬롯이 쓰는 동안 센서를 닫지 않음", not sensor.exited)
        dht_h.close()
        check("마지막 슬롯을 닫으면 센서를 닫음", sensor.exited)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    _, problems = validate_slots({
        "sensor_07": {"driver": "dht_in", "pin": 4, "kind": "temperature", "unit": "°C"},
        "sensor_08": {"driver": "dht_in", "pin": 4, "measure": "humidity", "kind": "humidity", "unit": "%"},
    })
    check("DHT 온도·습도 두 슬롯의 같은 핀은 경고하지 않음", not problems, str(problems))
    _, problems = validate_slots({
        "sensor_07": {"driver": "dht_in", "pin": 4, "kind": "temperature", "unit": "°C"},
        "actuator_01": {"driver": "digital_out", "pin": 4, "control_type": "onoff"},
    })
    check("DHT 핀을 다른 부품이 쓰면 여전히 알려 줌", len(problems) == 1, str(problems))

    pulse = create_driver("actuator_03", {"driver": "digital_out", "pin": 26,
                                          "control_type": "pulse"})
    pulse.apply("on", {"on_time": 0.25, "off_time": 0.15})
    check("pulse가 점멸 주기를 반영", pulse._timing == (0.25, 0.15), str(pulse._timing))
    pulse.apply("on", {"on_time": 1.0, "off_time": 1.0})
    check("켜져 있어도 점멸 주기가 바뀌면 다시 반영", pulse._timing == (1.0, 1.0), str(pulse._timing))
    pulse.close()

    sensors = [d for d in drivers.values() if isinstance(d, SensorDriver)]
    numeric_ok = True
    for driver in sensors:
        measured = driver.read()
        if measured is None:
            continue
        if not isinstance(measured, dict):
            numeric_ok = False
        elif driver.config.get("unit") and "value" not in measured:
            numeric_ok = False   # 단위가 있는 센서는 차트용 숫자를 내야 합니다
    check("단위가 있는 센서는 {'value': 숫자} 형식으로 보고 (차트 자동 동작 조건)", numeric_ok)

    for driver in drivers.values():
        driver.close()

    # ------------------------------------------------------------------
    section("2. 배치표 오타를 실행 전에 잡아내는가")
    _, problems = validate_slots({"sensor_99": {"driver": "button_in", "pin": 5}})
    check("슬롯 이름이 틀리면 알려 줌", len(problems) == 1 and "슬롯 이름이 아닙니다" in problems[0])

    _, problems = validate_slots({"actuator_01": {"driver": "buttn_in", "pin": 5}})
    check("드라이버 이름 오타를 알려 줌", problems and "찾을 수 없습니다" in problems[0])

    _, problems = validate_slots({"sensor_01": {"driver": "servo", "pin": 5}})
    check("센서 슬롯에 액추에이터 드라이버를 꽂으면 알려 줌",
          problems and "actuator_NN" in problems[0], str(problems))

    _, problems = validate_slots({
        "actuator_01": {"driver": "digital_out", "pin": 18},
        "actuator_02": {"driver": "digital_out", "pin": 18},
    })
    check("두 슬롯이 같은 핀을 쓰면 알려 줌", problems and "같이 쓰고" in problems[0], str(problems))

    usable, problems = validate_slots({
        "actuator_01": {"driver": "tonal_buzzer", "pin": 18},
        "sensor_99": {"driver": "button_in", "pin": 5},
    })
    check("오타가 있는 줄만 빼고 나머지는 살린다", list(usable) == ["actuator_01"], str(list(usable)))

    # 핀을 여러 개 쓰는 부품은 pins에 적습니다. pin에 목록·딕셔너리를 적는 실수가 흔합니다.
    _, problems = validate_slots({
        "actuator_01": {"driver": "level_out", "pin": {"low": 5, "mid": 6, "high": 13}},
    })
    check("pin에 여러 핀을 적으면 pins를 쓰라고 알려 줌 (죽지 않음)",
          problems and "'pins'에 적으세요" in problems[0], str(problems))

    _, problems = validate_slots({"actuator_01": {"driver": "level_out", "pins": [5, 6, 13]}})
    check("pins에 목록을 적으면 통과", not problems, str(problems))

    _, problems = validate_slots({
        "actuator_01": {"driver": "rgb_out", "pins": {"r": 17, "g": 27, "b": 22}},
    })
    check("pins에 딕셔너리를 적으면 통과", not problems, str(problems))

    _, problems = validate_slots({"actuator_01": {"driver": "digital_out", "pin": "열일곱"}})
    check("핀 번호에 글자를 적으면 알려 줌",
          problems and "숫자가 아닙니다" in problems[0], str(problems))

    _, problems = validate_slots({"actuator_01": {"driver": "level_out", "pins": "5,6,13"}})
    check("pins에 문자열을 적으면 알려 줌",
          problems and "목록이나 딕셔너리" in problems[0], str(problems))

    _, problems = validate_slots({
        "actuator_01": {"driver": "level_out", "pins": [5, 6]},
        "actuator_02": {"driver": "digital_out", "pin": 6},
    })
    check("pins와 pin이 같은 핀을 쓰면 알려 줌",
          problems and "같이 쓰고" in problems[0], str(problems))

    # ------------------------------------------------------------------
    section("3. 부품 추가 — slot_map.py에 한 줄 추가")
    backend = FakeBackend()
    base_map = {
        "actuator_01": {"label": "알람 부저", "kind": "buzzer", "driver": "tonal_buzzer",
                        "pin": 18, "control_type": "tonal"},
        "sensor_01": {"label": "기상 버튼", "kind": "button", "driver": "button_in", "pin": 24},
    }
    daemon = SlotDaemon(backend, base_map)       # type: ignore[arg-type]
    check("드라이버 생성 실패 없음", daemon.build_drivers() == [])
    daemon.tick(now=1000.0)
    check("부팅 시 배치표가 등록됨", backend.register_calls == 1 and len(backend.enabled) == 2,
          str(list(backend.enabled)))
    check("등록 내용에 위젯 결정 근거(control_type)가 포함됨",
          backend.enabled["actuator_01"].get("control_type") == "tonal")
    check("등록 내용에 단위·핀 정보가 포함됨",
          backend.enabled["sensor_01"].get("meta", {}).get("pin") == 24)

    backend.command("actuator_01", "on", {"frequency": 880, "volume": 70})
    daemon.tick(now=1001.0)
    buzzer_reports = backend.reported("actuator_01")
    check("대시보드 명령이 부저에 반영되고 결과가 보고됨",
          buzzer_reports and buzzer_reports[-1].get("state") == "on", str(buzzer_reports))

    # 여기가 '한 줄 추가'입니다 — 코드는 고치지 않습니다.
    added_map = dict(base_map)
    added_map["actuator_02"] = {"label": "경보 LED", "kind": "led",
                               "driver": "digital_out", "pin": 23, "control_type": "onoff"}
    daemon2 = SlotDaemon(backend, added_map)     # type: ignore[arg-type]
    daemon2.build_drivers()
    daemon2.tick(now=2000.0)
    check("추가한 LED가 백엔드에 등록됨", "actuator_02" in backend.enabled,
          str(list(backend.enabled)))

    backend.command("actuator_02", "on")
    daemon2.tick(now=2001.0)
    led_reports = backend.reported("actuator_02")
    check("추가한 LED를 코드 수정 없이 제어 가능",
          led_reports and led_reports[-1].get("state") == "on", str(led_reports))

    # ------------------------------------------------------------------
    section("4. 부품 제거 — slot_map.py에서 한 줄 삭제")
    removed_map = {k: v for k, v in added_map.items() if k != "actuator_02"}
    daemon3 = SlotDaemon(backend, removed_map)   # type: ignore[arg-type]
    daemon3.build_drivers()
    daemon3.tick(now=3000.0)
    check("삭제한 줄의 슬롯이 백엔드에서 자동으로 꺼짐", "actuator_02" not in backend.enabled,
          str(list(backend.enabled)))
    check("꺼진 슬롯은 폴링 대상에서도 빠짐", "actuator_02" not in (backend.poll_desired_states() or {}))

    # ------------------------------------------------------------------
    section("5. 백엔드가 끊겼을 때")
    backend.offline = True
    before = len(backend.reports)
    daemon3.tick(now=4000.0)     # 예외 없이 지나가야 합니다
    check("백엔드가 끊겨도 데몬이 죽지 않음", len(backend.reports) == before)

    backend.offline = False
    daemon3.tick(now=4001.0)
    check("백엔드가 돌아오면 자동으로 다시 등록함", backend.register_calls >= 3,
          f"register_calls={backend.register_calls}")

    backend.reject_next = "actuator_01"
    daemon3._applied.clear()
    backend.command("actuator_01", "off")
    daemon3.tick(now=4002.0)
    check("보고를 거부당하면 다음 회차에 배치표를 다시 등록함", daemon3._registered is False)

    # ------------------------------------------------------------------
    section("6. 재동기화 · 종료 정리")
    daemon4 = SlotDaemon(backend, base_map)      # type: ignore[arg-type]
    daemon4.build_drivers()
    backend.command("actuator_01", "on", {"frequency": 1000})
    daemon4.tick(now=5000.0)
    backend.reports.clear()
    daemon4.tick(now=5001.0)
    check("상태가 그대로면 같은 명령을 다시 쓰지 않음 (GPIO 낭비 방지)",
          not backend.reported("actuator_01"), str(backend.reports))

    daemon4.tick(now=5001.0 + 31)     # 재동기화 주기(30초)를 넘김
    check("30초마다 현재 상태를 다시 보고해 백엔드와 맞춤",
          bool(backend.reported("actuator_01")), str(backend.reports))

    buzzer = daemon4.drivers["actuator_01"]
    check("종료 전에는 부저가 켜져 있음", buzzer._state == "on")
    daemon4.close()
    check("종료할 때 부품을 끄고 정리함", buzzer.device.value == 0 and buzzer.device.closed,
          f"value={buzzer.device.value}, closed={buzzer.device.closed}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 68)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 68)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
