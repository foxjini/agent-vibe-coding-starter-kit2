# 하드웨어(라즈베리파이 5) 규칙

## 안전 수칙
1. 새 배선은 반드시 전원을 끈 상태에서만 변경한다
2. LED 등 저전력 소자는 반드시 전류 제한 저항을 거친다
3. 실기기에 처음 연결하기 전에는 반드시 Mock 상태에서 로직을 먼저 검증한다
4. 실기기 첫 연결은 교사 입회 하에 진행한다

## 소프트웨어 설계
- 라즈베리파이 5(RP1 칩셋)에서는 기존 `RPi.GPIO`가 동작하지 않으므로, 반드시 `gpiozero`와 `lgpio` 라이브러리를 사용한다.
- PyPI의 `pip install lgpio` C 컴파일 에러를 방지하기 위해 라즈베리파이 OS 기본 APT 패키지(`python3-gpiozero`, `python3-lgpio`)를 사용하고, 가상환경 생성 시 `--system-site-packages` 옵션을 적용해 시스템 패키지를 재사용한다.
- Mock과 실기기는 `backend/iot/base.py`에 **이미 완성되어 있는** `DeviceProvider`
  인터페이스를 그대로 상속한다 — 메서드를 새로 정의하거나 이름을 바꾸지 않는다
  (`get_device_status` / `set_actuator_state` / `read_sensor_value` /
  `get_all_statuses`, 4개 모두 `async`). 전환 시에는 `backend/iot/provider_factory.py`가
  읽는 `.env`의 `DEVICE_MODE` 값만 바꾼다
- 프론트엔드/백엔드 API 코드는 Mock인지 실기기인지 알지 못하게 만든다 (Provider 뒤로 숨긴다)

## 통신 방식
- 라즈베리파이는 고정 공인 IP가 없을 수 있으므로, 백엔드에 desired-state를 주기적으로
  폴링(pull)하는 방식을 기본으로 한다 (백엔드가 파이에 직접 push하지 않는다)
