"""
드라이버 로더 (pi/drivers/__init__.py) — 키트 제공, 수정하지 마세요.

`slot_map.py`의 `"driver": "servo"` 같은 이름을 실제 클래스로 바꿔 줍니다.
새 드라이버를 만들면 이 폴더에 파일을 넣기만 하면 되고, 여기에 등록할 필요는 없습니다.
"""
import importlib
import logging
import pkgutil
from typing import Any, Dict, List

from drivers.base import ActuatorDriver, DriverError, SensorDriver, SlotDriver

logger = logging.getLogger("pi.drivers")

#: 로더가 드라이버로 취급하지 않는 파일들
_NOT_DRIVERS = {"base", "gpio"}


def available_drivers() -> List[str]:
    """`drivers/` 폴더에서 쓸 수 있는 드라이버 이름 목록."""
    names = []
    for module in pkgutil.iter_modules(__path__):
        if not module.name.startswith("_") and module.name not in _NOT_DRIVERS:
            names.append(module.name)
    return sorted(names)


def load_driver_class(name: str):
    """드라이버 이름으로 클래스를 찾아옵니다."""
    try:
        module = importlib.import_module(f"drivers.{name}")
    except ImportError as exc:
        raise DriverError(
            f"드라이버 '{name}'을(를) 찾을 수 없습니다. "
            f"쓸 수 있는 드라이버: {', '.join(available_drivers())}"
        ) from exc

    driver_class = getattr(module, "Driver", None)
    if driver_class is None or not issubclass(driver_class, SlotDriver):
        raise DriverError(
            f"drivers/{name}.py에 SlotDriver를 상속한 'Driver' 클래스가 없습니다."
        )
    return driver_class


def create_driver(slot_id: str, config: Dict[str, Any]) -> SlotDriver:
    """슬롯 설정 한 줄로 드라이버 인스턴스를 만듭니다."""
    name = config.get("driver")
    if not name:
        raise DriverError(f"{slot_id}: 'driver'를 지정해야 합니다.")

    driver_class = load_driver_class(name)
    try:
        return driver_class(slot_id, config)
    except KeyError as exc:
        raise DriverError(
            f"{slot_id}: 드라이버 '{name}'에 필요한 설정 {exc}이(가) 없습니다. "
            f"drivers/{name}.py 맨 위의 예시를 확인하세요."
        ) from exc
    except DriverError:
        raise
    except Exception as exc:
        raise DriverError(f"{slot_id}: 드라이버 '{name}'을(를) 만들지 못했습니다 — {exc}") from exc


__all__ = [
    "ActuatorDriver",
    "DriverError",
    "SensorDriver",
    "SlotDriver",
    "available_drivers",
    "create_driver",
    "load_driver_class",
]
