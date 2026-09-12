"""
팀별 배치표 예시 자가 점검 (pi/test_team_examples.py)
=============================================================================
`pi/examples/`의 4팀 배치표가 **복사해서 바로 쓸 수 있는 상태인지** 확인합니다.
GPIO도 백엔드도 필요 없습니다.

실행 방법 (pi 폴더에서):
    python test_team_examples.py

확인하는 것:
 1) 4팀 예시가 모두 검사를 통과하는지 (슬롯 이름·드라이버·핀 중복)
 2) 각 부품이 실제로 드라이버로 만들어지고 제어·측정이 되는지
 3) 등록 정보(라벨·종류·control_type·단위)가 대시보드에 쓸 만큼 채워져 있는지
 4) 부록F 워크시트의 팀별 부품 수와 맞는지
"""
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault("DEVICE_MODE", "mock")

from drivers import create_driver                     # noqa: E402
from drivers.base import ActuatorDriver, SensorDriver  # noqa: E402
from slot_config import validate_slots                 # noqa: E402

_passed = 0
_failed = 0

#: 부록F 2-3절 워크시트 기준 (팀, 액추에이터 수, 센서 수)
EXPECTED = {
    "wakeup": (1, 1),
    "classroom": (5, 0),
    "study": (4, 1),
    "subway": (2, 1),
}

#: control_type별로 보낼 값 (부록F 3-1절)
SAMPLE_VALUE: Dict[str, Any] = {
    "tonal": ("on", {"frequency": 880, "volume": 70}),
    "onoff": ("on", None),
    "pulse": ("on", {"on_time": 0.3, "off_time": 0.3}),
    "pwm": ("on", {"duty": 60}),
    "servo": ("move", {"angle": 60}),
    "rgb": ("on", {"r": 255, "g": 0, "b": 0}),
    "level": ("on", {"level": 2}),
}


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return condition


def load_example(team: str) -> Dict[str, Dict[str, Any]]:
    path = Path(CURRENT_DIR, "examples", f"slot_map_{team}.py")
    spec = importlib.util.spec_from_file_location(f"example_{team}", path)
    module = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
    spec.loader.exec_module(module)                          # type: ignore[union-attr]
    return module.SLOTS


def main_test() -> int:
    print("=" * 68)
    print(" 팀별 배치표 예시 — 자가 점검")
    print("=" * 68)

    for team, (want_actuators, want_sensors) in EXPECTED.items():
        print(f"\n[{team}]\n{'-' * 68}")

        slots = load_example(team)
        usable, problems = validate_slots(slots)
        if not check(f"배치표가 검사를 통과 (슬롯 {len(slots)}개)", not problems, str(problems)):
            continue
        check("빠짐없이 쓸 수 있는 상태", len(usable) == len(slots),
              f"{len(usable)}/{len(slots)}")

        drivers = {}
        errors = []
        for slot_id, config in usable.items():
            try:
                drivers[slot_id] = create_driver(slot_id, config)
            except Exception as exc:
                errors.append(f"{slot_id}: {exc}")
        check("모든 부품이 드라이버로 만들어짐", not errors, str(errors[:2]))

        actuators = [d for d in drivers.values() if isinstance(d, ActuatorDriver)]
        sensors = [d for d in drivers.values() if isinstance(d, SensorDriver)]
        check(f"액추에이터 {want_actuators}개 (부록F 워크시트 기준)",
              len(actuators) == want_actuators, f"실제 {len(actuators)}개")
        check(f"센서 {want_sensors}개 (부록F 워크시트 기준)",
              len(sensors) == want_sensors, f"실제 {len(sensors)}개")

        # control_type에 맞는 값을 보내 반영 결과가 명령과 같은지 (부록A 상태 계약)
        mismatched = []
        for slot_id, driver in drivers.items():
            if not isinstance(driver, ActuatorDriver):
                continue
            control_type = driver.config.get("control_type") or driver.control_type or "onoff"
            state, value = SAMPLE_VALUE.get(control_type, ("on", None))
            if driver.apply(state, value) != state or driver.apply("off") != "off":
                mismatched.append(f"{slot_id}({control_type})")
        check("액추에이터가 내린 명령을 그대로 반영 보고", not mismatched, str(mismatched))

        # 등록 정보가 대시보드에 쓸 만큼 채워져 있는지
        missing = []
        for slot_id, driver in drivers.items():
            entry = driver.describe()
            if not entry.get("label"):
                missing.append(f"{slot_id}:label")
            if not entry.get("kind") or entry["kind"] == "unknown":
                missing.append(f"{slot_id}:kind")
            if isinstance(driver, ActuatorDriver) and not entry.get("control_type"):
                missing.append(f"{slot_id}:control_type")
        check("등록 정보(라벨·종류·제어방식)가 모두 채워짐", not missing, str(missing))

        numeric_without_unit = [
            slot_id for slot_id, driver in drivers.items()
            if isinstance(driver, SensorDriver)
            and driver.config.get("kind") in ("temperature", "humidity", "distance",
                                              "pressure", "light")
            and not driver.config.get("unit")
        ]
        check("숫자 센서에 단위가 적혀 있음 (차트 축 표시용)",
              not numeric_without_unit, str(numeric_without_unit))

        for driver in drivers.values():
            driver.close()

    print("\n" + "=" * 68)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 68)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
