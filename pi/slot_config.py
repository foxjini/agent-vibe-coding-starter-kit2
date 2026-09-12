"""
배치표 검사기 (pi/slot_config.py) — 키트 제공, 수정하지 마세요.

`slot_map.py`를 실제로 쓰기 전에 먼저 읽고 확인합니다.
오타 하나로 GPIO를 건드린 뒤에 죽는 대신, **무엇이 왜 틀렸는지** 먼저 알려 줍니다.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from drivers import available_drivers, load_driver_class
from drivers.base import DriverError

logger = logging.getLogger("pi.slot_config")

SLOT_COUNT = 10
SENSOR_SLOTS = tuple(f"sensor_{i:02d}" for i in range(1, SLOT_COUNT + 1))
ACTUATOR_SLOTS = tuple(f"actuator_{i:02d}" for i in range(1, SLOT_COUNT + 1))
ALL_SLOTS = SENSOR_SLOTS + ACTUATOR_SLOTS


def slot_role(slot_id: str) -> Optional[str]:
    """슬롯 이름으로 역할을 판정합니다. 슬롯이 아니면 None."""
    if slot_id in SENSOR_SLOTS:
        return "sensor"
    if slot_id in ACTUATOR_SLOTS:
        return "actuator"
    return None


def validate_slots(slots: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    배치표를 검사합니다.

    돌려주는 값: (쓸 수 있는 슬롯만 남긴 사전, 사람이 읽을 문제 목록)
    문제가 있는 줄은 **그 줄만 빼고** 나머지는 그대로 동작시킵니다 —
    한 줄 오타 때문에 전체 시스템이 멈추면 수업이 진행되지 않습니다.
    """
    problems: List[str] = []
    usable: Dict[str, Dict[str, Any]] = {}

    if not isinstance(slots, dict):
        return {}, ["slot_map.py의 SLOTS는 딕셔너리여야 합니다."]

    pins_in_use: Dict[Any, str] = {}

    for slot_id, config in slots.items():
        role = slot_role(slot_id)
        if role is None:
            problems.append(
                f"'{slot_id}'는 슬롯 이름이 아닙니다. "
                f"sensor_01~sensor_{SLOT_COUNT:02d} 또는 "
                f"actuator_01~actuator_{SLOT_COUNT:02d} 중에서 쓰세요."
            )
            continue

        if not isinstance(config, dict):
            problems.append(f"{slot_id}: 설정이 딕셔너리가 아닙니다 ({type(config).__name__}).")
            continue

        driver_name = config.get("driver")
        if not driver_name:
            problems.append(f"{slot_id}: 'driver'를 적어야 합니다 (쓸 수 있는 드라이버: "
                            f"{', '.join(available_drivers())}).")
            continue

        try:
            driver_class = load_driver_class(driver_name)
        except DriverError as exc:
            problems.append(f"{slot_id}: {exc}")
            continue

        # 센서 슬롯에 액추에이터 드라이버를 꽂는 실수를 먼저 잡습니다.
        if driver_class.role != role:
            problems.append(
                f"{slot_id}는 {role} 슬롯인데 드라이버 '{driver_name}'은(는) "
                f"{driver_class.role}용입니다. 슬롯 번호를 "
                f"{'actuator_NN' if driver_class.role == 'actuator' else 'sensor_NN'}으로 바꾸세요."
            )
            continue

        # 같은 핀을 두 슬롯이 쓰면 한쪽이 조용히 동작하지 않습니다.
        def claim(pin: Any, where: str) -> None:
            """핀 번호 하나를 이 슬롯 것으로 찜합니다 (겹치면 문제로 적습니다)."""
            if not isinstance(pin, int) or isinstance(pin, bool):
                problems.append(
                    f"{slot_id}: {where}에 적은 핀 번호가 숫자가 아닙니다 ({pin!r}). "
                    "GPIO 번호를 숫자로 적으세요 — 예: \"pin\": 17"
                )
                return
            owner = pins_in_use.get(pin)
            if owner and owner != slot_id:
                problems.append(
                    f"GPIO {pin}번을 {owner}와 {slot_id}가 같이 쓰고 있습니다. "
                    "핀 하나에 부품 하나만 연결하세요."
                )
            pins_in_use[pin] = slot_id

        for key in ("pin", "trigger_pin", "echo_pin"):
            pin = config.get(key)
            if pin is None:
                continue
            if isinstance(pin, (list, tuple, dict)):
                # 여러 핀을 쓰는 부품(level_out·rgb_out)은 'pins'에 적습니다.
                problems.append(
                    f"{slot_id}: '{key}'에는 핀 번호 하나만 적습니다. 핀을 여러 개 쓰는 "
                    '부품은 \'pins\'에 적으세요 — 예: "pins": [5, 6, 13] 또는 '
                    '"pins": {"r": 17, "g": 27, "b": 22}'
                )
                continue
            claim(pin, f"'{key}'")

        # pins는 목록([5, 6, 13])일 수도, 딕셔너리({"r":17,"g":27,"b":22})일 수도 있습니다
        declared = config.get("pins") or []
        if isinstance(declared, dict):
            pin_list = list(declared.values())
        elif isinstance(declared, (list, tuple)):
            pin_list = list(declared)
        else:
            problems.append(
                f"{slot_id}: 'pins'는 목록이나 딕셔너리여야 합니다 ({type(declared).__name__})."
            )
            pin_list = []
        for pin in pin_list:
            claim(pin, "'pins'")

        usable[slot_id] = dict(config)

    return usable, problems


def load_slot_map(module_name: str = "slot_map") -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """`slot_map.py`를 읽어 검사까지 마친 결과를 돌려줍니다."""
    import importlib

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return {}, [f"{module_name}.py를 읽지 못했습니다: {exc}"]

    slots = getattr(module, "SLOTS", None)
    if slots is None:
        return {}, [f"{module_name}.py에 SLOTS 딕셔너리가 없습니다."]
    return validate_slots(slots)
