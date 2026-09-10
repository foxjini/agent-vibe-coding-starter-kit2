from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DeviceProvider(ABC):
    """
    모든 IoT 디바이스(센서 및 액추에이터) 제어 제공자의 공통 인터페이스 추상 클래스.
    MockDeviceProvider(개발 전반부)와 HardwareDeviceProvider(라즈베리파이 5)가
    이 클래스를 상속받아 동일한 메서드를 구현합니다.

    `self._devices`는 DB가 없을 때 쓰는 메모리 폴백 캐시입니다.
    기본 저장소는 언제나 DB이며, 캐시는 DB 장애 시 시스템이 멈추지 않게 하는 보조 수단입니다.
    """

    def __init__(self, devices: Dict[str, Dict[str, Any]]) -> None:
        self._devices: Dict[str, Dict[str, Any]] = devices

    # --------------------------------------------------------------------
    # 공통 헬퍼
    # --------------------------------------------------------------------

    def update_cached_state(
        self,
        device_id: str,
        state: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        """
        하드웨어가 보고한 실제 상태를 메모리 캐시에도 반영합니다.
        (DB 장애 중에도 대시보드가 마지막 보고값을 볼 수 있게 합니다.)
        """
        dev = self._devices.get(device_id)
        if not dev:
            return
        if state is not None:
            dev["current_state"] = state
        if value is not None:
            dev["current_value"] = value
        dev["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_cached_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        dev = self._devices.get(device_id)
        return dict(dev) if dev else None

    # --------------------------------------------------------------------
    # 하위 클래스가 구현해야 하는 인터페이스
    # --------------------------------------------------------------------

    @abstractmethod
    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 디바이스의 현재 상태 및 측정값을 반환합니다.
        """
        pass

    @abstractmethod
    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user"
    ) -> Dict[str, Any]:
        """
        액추에이터의 desired-state를 갱신하거나 제어 명령을 전달합니다.
        """
        pass

    @abstractmethod
    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        센서의 최신 측정값을 읽어옵니다.
        """
        pass

    @abstractmethod
    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """
        등록된 모든 디바이스의 현재 상태 목록을 반환합니다.
        """
        pass
