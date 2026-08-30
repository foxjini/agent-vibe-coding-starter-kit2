---
name: hardware-integration
description: >-
  Mock Provider와 라즈베리파이 5(gpiozero, lgpio) 하드웨어 Provider 전환, desired-state 폴링 통신 및 네트워크 환경 설정을 구현할 때 사용하는 스킬.
---

# hardware-integration

> Mock ↔ 라즈베리파이 5 전환 작업 시 이 스킬을 참고한다.

## Provider 패턴
인터페이스는 **`backend/iot/base.py`에 이미 완성되어 있다.** 새로 정의하지 말고 그대로
상속받는다. 아래 4개 메서드가 전부이며, **모두 `async`다** — 하나라도 빠뜨리면
`TypeError: Can't instantiate abstract class ...`가 난다.

```python
# backend/iot/base.py (이미 있는 파일 — 그대로 사용)
class DeviceProvider(ABC):
    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]: ...
    async def set_actuator_state(self, device_id: str, desired_state: str,
                                 value: Optional[Any] = None,
                                 operator: str = "user") -> Dict[str, Any]: ...
    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]: ...
    async def get_all_statuses(self) -> List[Dict[str, Any]]: ...
```
- `backend/iot/mock_provider.py`: 센서값은 Random Walk로 자연스럽게 변화, 액추에이터는
  메모리 상태로 관리
- `backend/iot/hardware_provider.py`: **GPIO를 직접 만지지 않는다.** 백엔드는 라즈베리파이와
  같은 기기에 있지 않으므로, desired-state를 저장해 두고 파이가 폴링해 가져가도록 중계만
  한다 (실제 GPIO 제어는 `pi/main.py` 담당 —
  `docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 2장)
- `backend/iot/provider_factory.py`: `.env`의 `DEVICE_MODE`(mock/hardware)로 적절한
  Provider를 반환 (이 파일은 학생/AI가 만든다 — 킷에 미리 들어있지 않다)

> `pi/main.py` 안에서 쓰는 클래스는 `backend/iot/base.py`를 `import`할 수 없다(다른 기기).
> 같은 4개 메서드 **이름만** 맞추는 명명 규약이다 — 인터페이스 가이드 2장 참고.

## gpiozero 최소 예시
```python
from gpiozero import LED
led = LED(17)
led.on()   # 켜기
led.off()  # 끄기
```

## 라즈베리파이 5 패키지 설치 (Pi 5 전용 주의)
라즈베리파이 5는 GPIO 칩이 이전 모델과 달라(RP1), 예전 방식(`RPi.GPIO`)이 아니라
`lgpio` 핀 팩토리가 필요하다. `gpiozero`만 설치하면 핀 제어가 실패할 수 있다.
```bash
cd pi
python3 -m venv venv
source venv/bin/activate
pip install gpiozero lgpio requests python-dotenv
```

## desired-state 폴링 패턴
라즈베리파이 쪽 데몬(`pi/main.py`)이 몇 초 주기로 백엔드의
`GET /api/v1/devices/{id}/desired-state`를 호출해 원하는 상태를 받아오고,
`POST /api/v1/devices/{id}/state`로 실제 반영 결과를 보고한다. (백엔드가 파이에
직접 접속하지 않는다 — hardware-rules.md 참고)

## 개발 단계 접속 주소 (백엔드가 아직 학생 PC에서 도는 동안)
클라우드 배포(4주차) 전에는 백엔드가 학생 Windows PC에서 돌고 있으므로,
`pi/.env`의 `BACKEND_URL`은 그 PC의 로컬 IP를 가리켜야 한다(`localhost`는 라즈베리파이
입장에서 자기 자신을 뜻하므로 쓸 수 없다).
```powershell
# Windows PC에서 IP 확인
ipconfig
# → IPv4 주소(예: 192.168.0.25)를 확인
```
```
# pi/.env
BACKEND_URL=http://192.168.0.25:8000
```
