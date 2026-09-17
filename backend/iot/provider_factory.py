import logging
import os
from typing import Optional

from .base import DeviceProvider
from .mock_provider import MockDeviceProvider

logger = logging.getLogger("backend.iot.factory")

_provider_instance: Optional[DeviceProvider] = None


def get_device_provider() -> DeviceProvider:
    """
    .env의 DEVICE_MODE 설정('mock' 또는 'hardware')에 따라
    싱글톤 DeviceProvider 인스턴스를 반환합니다.
    """
    global _provider_instance
    if _provider_instance is None:
        device_mode = os.getenv("DEVICE_MODE", "mock").strip().lower()
        if device_mode == "hardware":
            try:
                from .hardware_provider import HardwareDeviceProvider  # type: ignore
                _provider_instance = HardwareDeviceProvider()
                logger.info("DEVICE_MODE=hardware — 실기기 연동 모드로 기동합니다.")
            except (ImportError, AttributeError) as exc:
                # 예전에는 이 폴백이 조용히 일어나서, DEVICE_MODE=hardware로 바꾸고
                # 재시작해도 화면상 아무 차이가 없어 학생이 원인을 찾지 못했다.
                # 이제는 경고로 분명히 남긴다.
                logger.warning(
                    "DEVICE_MODE=hardware 이지만 HardwareDeviceProvider를 불러오지 "
                    f"못했습니다({exc}). Mock으로 대체합니다 — 대시보드가 실기기 "
                    "반영 여부와 무관하게 '완료'로 보일 수 있습니다."
                )
                _provider_instance = MockDeviceProvider()
        else:
            _provider_instance = MockDeviceProvider()
            logger.info(f"DEVICE_MODE={device_mode or 'mock'} — Mock 시뮬레이터 모드로 기동합니다.")

    return _provider_instance
