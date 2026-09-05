import os
from typing import Optional

from .base import DeviceProvider
from .mock_provider import MockDeviceProvider

_provider_instance: Optional[DeviceProvider] = None


def get_device_provider() -> DeviceProvider:
    """
    .env의 DEVICE_MODE 설정('mock' 또는 'hardware')에 따라
    싱글톤 DeviceProvider 인스턴스를 반환합니다.
    """
    global _provider_instance
    if _provider_instance is None:
        device_mode = os.getenv("DEVICE_MODE", "mock").lower()
        if device_mode == "hardware":
            try:
                from .hardware_provider import HardwareDeviceProvider  # type: ignore
                _provider_instance = HardwareDeviceProvider()
            except (ImportError, AttributeError):
                # 하드웨어 프로바이더가 아직 구현되지 않았거나 로컬 환경인 경우 Mock으로 fallback
                _provider_instance = MockDeviceProvider()
        else:
            _provider_instance = MockDeviceProvider()

    return _provider_instance
