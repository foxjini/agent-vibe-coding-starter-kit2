# DB 규칙 (MySQL → 추후 Supabase 마이그레이션 고려)

## 네이밍
- 테이블/컬럼: snake_case
- 최소 테이블 4개
  - `devices(id, name, kind, desired_state, current_state, updated_at, created_at)` —
    `id`는 `led_1`처럼 짧고 읽기 쉬운 슬러그를 기본키로 쓴다(라즈베리파이가 URL에
    그대로 넣어 폴링하므로 사람이 읽을 수 있는 슬러그를 권장한다). 다른 테이블은 전부
    이 `id`를 `device_id`로 참조한다
    - `desired_state`: 대시보드/트리거가 "이렇게 되어야 한다"고 지정한 목표 상태
    - `current_state`: 라즈베리파이(또는 Mock)가 "실제로 이렇게 됐다"고 보고한 상태
    - **이 두 컬럼은 메모리 변수가 아니라 반드시 DB에 저장한다** — 백엔드를
      `--reload`로 재시작할 때마다 desired-state가 초기화되면 폴링 계약이 깨진다
      (`docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 3장·11장)
    - `desired_value` / `current_value`(JSON, NULL 허용): on/off로 표현되지 않는
      값을 담는다. **서보 각도, LED 밝기, 네오픽셀 색, 부저 주파수를 쓰는 팀은
      필수다** — `VARCHAR`인 state 컬럼만으로는 각도 90도를 표현할 수 없다
      (`docs/부록D-iot-test-system-연동-가이드.md` 3장)
  - `sensor_readings(id, device_id, value, unit, value_json, created_at)` —
    값이 1개인 센서는 `value`+`unit`을, 온습도센서(DHT11)처럼 한 번에 2개 이상을
    보고하는 센서는 `value_json`에 `{"temperature_c": 24.5, "humidity_pct": 55.0}`
    형태로 담는다 (둘 중 쓰는 쪽만 채우고 나머지는 NULL)
  - `control_log(id, device_id, action, value, actor, created_at)` — actor는 `'user'` 또는 `'device'`
  - `vision_events(id, event_type, detected, count, confidence, created_at)`

## 경보성 디바이스 원칙
`devices.kind`가 경보성(예: 침입감지)인 디바이스는 트리거 로직이 절대 자동으로 원래
상태로 되돌리지 않는다 — 대시보드에서 사람이 수동으로 해제해야 한다
(`dashboard-ui-design` 스킬의 AlertCard 참고).

## 마이그레이션 호환성
- MySQL 전용 문법(`AUTO_INCREMENT`, `ENUM(...)` 등)을 쓸 때는 주석으로 `-- MySQL-only`
  표시해둔다 (db-migration 스킬에서 Supabase 전환 시 이 주석을 기준으로 변환한다)
- 날짜/시간은 UTC로 저장하고, 타임존 변환은 애플리케이션 레이어에서 처리한다

## 쓰기 경로
- 개발 단계(MySQL): 백엔드가 직접 커넥션을 통해 쓴다
- 배포 단계(Supabase): 백엔드는 `service_role` 키로 RLS를 우회해서 쓴다.
  프론트엔드는 절대 DB에 직접 쓰지 않는다 — 항상 백엔드 API를 거친다
