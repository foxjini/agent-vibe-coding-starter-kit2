import os
from typing import Optional

from .base import DeviceProvider
from .mock_provider import MockDeviceProvider

_provider_instance: Optional[DeviceProvider] = None


def get_device_provider() -> DeviceProvider:
    """
    .env의 DEVICE_MODE 설정('mock' 또는 'hardware')에 따라
    적절한 DeviceProvider 싱글톤 인스턴스를 반환합니다.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    mode = os.getenv("DEVICE_MODE", "mock").lower()

    if mode == "hardware":
        try:
            from .hardware_provider import HardwareDeviceProvider
            _provider_instance = HardwareDeviceProvider()
        except ImportError:
            # 아직 hardware_provider가 구현되지 않은 개발 전반부에는 Mock으로 폴백
            _provider_instance = MockDeviceProvider()
    else:
        _provider_instance = MockDeviceProvider()

    return _provider_instance
