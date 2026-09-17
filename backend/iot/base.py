from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DeviceProvider(ABC):
    """
    모든 IoT 디바이스(센서 및 액추에이터) 제어 제공자의 공통 인터페이스 추상 클래스.
    MockDeviceProvider(개발 전반부)와 HardwareDeviceProvider(라즈베리파이 5)가
    이 클래스를 상속받아 동일한 메서드를 구현합니다.
    """

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

    async def apply_reported_state(
        self,
        device_id: str,
        state: Optional[str],
        value: Optional[Any] = None
    ) -> None:
        """
        라즈베리파이가 보고한 실제 반영 결과를 메모리 상태에 반영합니다.

        DB가 살아 있으면 DB가 유일한 진실이므로 이 메서드는 사실상 거들 뿐이지만,
        DB가 잠깐 끊긴 동안에도 파이의 보고가 사라지지 않게 하려면 필요합니다.
        (추상 메서드가 아니라 기본 동작이 없는 구상 메서드입니다.)
        """
        return None
