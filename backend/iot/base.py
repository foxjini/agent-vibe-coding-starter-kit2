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

    @staticmethod
    def is_actuator(device: Dict[str, Any]) -> bool:
        """
        액추에이터인지 판정합니다.
        DB 행에는 is_actuator 컬럼이 없으므로 role로 판단하고, 메모리 캐시는 둘 다 가집니다.
        """
        if device.get("role"):
            return device["role"] == "actuator"
        return bool(device.get("is_actuator"))

    @staticmethod
    def is_disabled_slot(device: Dict[str, Any]) -> bool:
        """슬롯(slot_index>=1)인데 팀이 사용하지 않도록 꺼 둔 상태인지."""
        return bool(device.get("slot_index")) and not device.get("enabled")

    def visible_cached_devices(self) -> List[Dict[str, Any]]:
        """DB가 없을 때 대시보드에 보여줄 디바이스 (비활성 슬롯은 숨긴다)."""
        return [dict(d) for d in self._devices.values() if not self.is_disabled_slot(d)]

    def cached_slots(
        self,
        role: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        DB가 없을 때 '하드웨어 구성' 화면에 보여줄 슬롯 목록 (레거시 행은 제외).
        DB의 get_slots()와 같은 순서(센서 먼저, 슬롯 번호 순)로 돌려줍니다.
        """
        slots = [
            dict(dev)
            for dev in self._devices.values()
            if dev.get("slot_index")
            and (role is None or dev.get("role") == role)
            and (not enabled_only or dev.get("enabled"))
        ]
        slots.sort(key=lambda dev: (dev.get("role") != "sensor", dev.get("slot_index") or 0))
        return slots

    def apply_slot_registration(
        self,
        slots: List[Dict[str, Any]],
        exclusive: bool = True,
    ) -> Dict[str, List[str]]:
        """
        pi가 등록한 슬롯 매핑을 메모리 캐시에도 반영합니다.
        (DB가 꺼져 있어도 그 세션 동안은 키트가 동작하도록)

        DB의 register_slots()와 같은 모양({registered, disabled, rejected})을 돌려주므로,
        DB 장애 중에도 파이에게 '무엇이 실제로 반영됐는지' 정직하게 알려줄 수 있습니다.
        """
        registered: List[str] = []
        rejected: List[str] = []
        disabled: List[str] = []

        for entry in slots:
            slot_id = entry.get("slot_id")
            dev = self._devices.get(slot_id)
            if not dev or not dev.get("slot_index"):
                rejected.append(str(slot_id))
                continue
            dev["enabled"] = True
            for key in ("label", "kind", "unit", "control_type", "value_schema", "meta", "display_order"):
                if key in entry and entry[key] is not None:
                    dev[key] = entry[key]
            dev["updated_at"] = datetime.now(timezone.utc).isoformat()
            registered.append(slot_id)

        if exclusive:
            keep = set(registered)
            for slot_id, dev in self._devices.items():
                if not dev.get("slot_index") or slot_id in keep:
                    continue
                if dev.get("enabled"):
                    disabled.append(slot_id)
                dev["enabled"] = False

        return {"registered": registered, "disabled": disabled, "rejected": rejected}

    def update_cached_metadata(self, device_id: str, fields: Dict[str, Any]) -> None:
        """슬롯 메타데이터 수정(PATCH)을 메모리 캐시에도 반영합니다."""
        dev = self._devices.get(device_id)
        if not dev:
            return
        for key, value in fields.items():
            if key in ("enabled", "label", "kind", "unit", "control_type",
                       "value_schema", "meta", "display_order"):
                dev[key] = value
        dev["updated_at"] = datetime.now(timezone.utc).isoformat()

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
