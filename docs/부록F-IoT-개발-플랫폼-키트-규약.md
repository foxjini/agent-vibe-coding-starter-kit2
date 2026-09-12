# 부록F — IoT 개발 플랫폼 키트 규약 (P0 설계 확정안)

> 📂 **4개 팀(wakeup · classroom · study · subway) 공통 / 전 담당자 필수** · 전체 목록 [docs/README.md](README.md)
>
> **이 문서의 목적**: 팀이 2차 개발에서 **센서·액추에이터의 종류나 개수를 바꿀 때
> 백엔드·DB·vision을 한 줄도 고치지 않아도 되도록** 하는 공통 규약을 정의합니다.
> 팀이 고치는 것은 **`frontend/`와 `pi/` 두 곳뿐**입니다.
>
> 이 문서는 구현 전 **계약서(P0)** 입니다. 여기 적힌 슬롯 규약·DB 스키마·API 형식은
> 한 번 확정하면 바꾸지 않습니다(바꾸면 4팀이 모두 영향을 받습니다).
>
> 🌿 **키트 코드는 `platform` 브랜치에서 개발합니다.** 브랜치 운영 방법과 진행 상황은
> 저장소 루트의 [`PLATFORM.md`](../PLATFORM.md)를 보세요.

---

## 1. 왜 이 키트가 필요한가

지금은 디바이스 이름이 코드에 직접 박혀 있습니다. 실제로 세어 보면 **10개 파일 20곳**입니다.

| 파일 | 하드코딩 개수 |
|---|---|
| `pi/main.py` | 7 |
| `backend/iot/device_catalog.py` | 6 |
| `backend/db/init.sql`, `backend/db/database.py` | 각 3 |
| `frontend/app/page.tsx` | 2 |
| `backend/services/*`, `backend/routers/*` | 각 1 |

그래서 부품 하나만 바꿔도 백엔드·DB까지 손대야 하고, 팀마다 이름이 전부 달라
**4팀이 코드를 공유할 수 없습니다**(실제로 현재 4팀의 디바이스 ID는 겹치는 것이 하나도 없습니다).

### 해결 방식: 이름을 코드에서 빼고 "슬롯 + 라벨"로 분리

```
[고정층]  백엔드 · DB · vision
          슬롯 20개만 안다. 무엇이 꽂혀 있는지는 모른다. → 4팀 코드 100% 동일, 영구 불변
              sensor_01 … sensor_10      (센서 최대 10개)
              actuator_01 … actuator_10  (액추에이터 최대 10개)

[매핑층]  DB의 메타데이터 (코드 아님, 데이터)
          "actuator_01 = 알람 부저, 주파수 제어" ← 팀이 API·대시보드로 지정

[팀층]    frontend (화면·시나리오) + pi (배선·드라이버)
          팀이 자유롭게 수정
```

---

## 2. 슬롯 규약 (불변)

### 2-1. 슬롯 ID

| 역할 | 슬롯 ID | 개수 | 비고 |
|---|---|---|---|
| 센서 | `sensor_01` ~ `sensor_10` | 10 | 두 자리 0 채움(`sensor_1` ❌) |
| 액추에이터 | `actuator_01` ~ `actuator_10` | 10 | 동일 |

- 20개 슬롯은 **DB에 처음부터 모두 생성**되어 있습니다. 팀이 추가·삭제하지 않습니다.
- **사용하지 않는 슬롯은 `enabled = false`** 로 둡니다(삭제가 아니라 비활성).
- 슬롯의 `role`(sensor/actuator)은 **절대 바뀌지 않습니다**. 센서가 부족하다고
  `actuator_07`을 센서로 쓰지 않습니다.
- 슬롯 ID를 코드에 직접 쓰는 것은 `pi/slot_map.py`와 프론트 시나리오 코드에서만 허용합니다.
  백엔드·DB·vision에는 특정 슬롯 번호가 등장하지 않습니다.

### 2-2. 카메라는 슬롯을 쓰지 않습니다

웹캠·Pi Camera는 `vision/` 클라이언트가 담당하고, 결과는 `vision_events`로 들어옵니다
(기존 계약 그대로). 대시보드에 "카메라 연결 상태"를 표시하고 싶을 때만
센서 슬롯 하나에 `kind: "camera"`로 등록해 상태 표시용으로 씁니다.

### 2-3. 4팀 슬롯 할당 워크시트 (현재 부품 기준)

> 각 팀은 아래 표를 자기 브랜치의 `AGENTS.md`에 복사해 채우고, 같은 내용을
> `pi/slot_map.py`에 반영합니다. 이 표와 `slot_map.py`가 **유일한 진실**입니다.

**wakeup — 스마트 기상 시스템**

| 슬롯 | 부품 | kind | control_type / 단위 |
|---|---|---|---|
| `actuator_01` | 알람 피에조 부저 | `buzzer` | `tonal` |
| `sensor_01` | 기상 확인 버튼/터치센서 | `button` | — |
| (vision) | 기상 감지 웹캠 | — | `vision_events` |
| 미사용 | `actuator_02~10`, `sensor_02~10` | | `enabled=false` |

**classroom — 스마트 교실 (액추에이터 5개, 가장 많음)**

| 슬롯 | 부품 | kind | control_type |
|---|---|---|---|
| `actuator_01` | MG90S 서보모터(자동문) | `servo` | `servo` |
| `actuator_02` | 좌석 LED | `led` | `onoff` |
| `actuator_03` | 네오픽셀 | `neopixel` | `rgb` |
| `actuator_04` | 부저 | `buzzer` | `tonal` |
| `actuator_05` | 릴레이(교실 조명) | `relay` | `onoff` |
| (vision) | FHD 출입 웹캠 | — | `vision_events` |

**study — 스마트 학습 공간**

| 슬롯 | 부품 | kind | control_type |
|---|---|---|---|
| `actuator_01` | RGB LED 바(스탠드) | `led` | `rgb` |
| `actuator_02` | 진동 모터 A(등받이) | `vibrator` | `pwm` |
| `actuator_03` | 진동 모터 B(방석) | `vibrator` | `pwm` |
| `actuator_04` | 릴레이/MOSFET 모듈 | `relay` | `onoff` |
| `sensor_01` | 매립형 터치 디스플레이 | `touch` | — |
| (vision) | 정면 USB 웹캠 | — | `vision_events` |

**subway — 지하철 혼잡도 시스템**

| 슬롯 | 부품 | kind | control_type |
|---|---|---|---|
| `actuator_01` | 혼잡도 안내 LED | `led` | `level` (단계 표시) |
| `actuator_02` | 배경 이동 컨베이어 | `motor` | `pwm` |
| `sensor_01` | 임산부석 압력센서 | `pressure` | 단위 `kg` |
| (vision) | 객차 Pi Camera 3 | — | `vision_events` |

---

## 3. 디바이스 메타데이터 (팀이 지정하는 값)

슬롯에 "의미"를 붙이는 값입니다. **코드가 아니라 데이터**이므로 API나 대시보드 설정 화면에서 바꿉니다.

| 필드 | 예시 | 설명 |
|---|---|---|
| `label` | `"알람 부저"` | 화면에 보이는 이름. 팀이 자유롭게 |
| `kind` | `"buzzer"` | 아이콘·표시 방식 결정용 분류 |
| `unit` | `"°C"`, `"kg"` | 센서 단위 (액추에이터는 비움) |
| `control_type` | `"tonal"` | 액추에이터 제어 방식 → **프론트 위젯이 자동 결정됨** |
| `value_schema` | `{"min":0,"max":180}` | 슬라이더·다이얼 범위 |
| `enabled` | `true` / `false` | 사용 여부 (제거 = false) |
| `display_order` | `1` | 대시보드 정렬 순서 |
| `meta` | `{"pin":18,"note":"교실 앞문"}` | 팀 자유 확장 (핀 번호·설치 위치 등) |

### 3-1. `control_type` 규약 — 이 값이 위젯과 값 형식을 결정합니다

| control_type | `desired_state` | `value` 형식 | 프론트 위젯 | 쓰는 팀 |
|---|---|---|---|---|
| `onoff` | `"on"` / `"off"` | `null` | 토글 스위치 | classroom, study |
| `pulse` | `"on"` / `"off"` | `{"on_time":0.25,"off_time":0.15}` | 토글 + 점멸 주기 | 경보등 |
| `tonal` | `"on"` / `"off"` | `{"frequency":1000,"volume":80}` | 토글 + 주파수/볼륨 | wakeup, classroom |
| `pwm` | `"on"` / `"off"` | `{"duty":0~100}` | 슬라이더 | study, subway |
| `servo` | `"move"` / `"off"` | `{"angle":0~180}` | 각도 다이얼 | classroom |
| `rgb` | `"on"` / `"off"` | `{"r":0-255,"g":0-255,"b":0-255}` | 컬러 피커 | classroom, study |
| `level` | `"on"` / `"off"` | `{"level":0~N}` | 단계 선택 버튼 | subway |

> `desired_state`는 **항상 문자열**이고, 세부 값은 **항상 `value` 객체**에 담습니다.
> 이 규칙 덕분에 백엔드는 값의 의미를 몰라도 저장·중계할 수 있습니다.

### 3-2. 센서 `kind`별 보고 값 형식

| kind | `value` 형식 | 비고 |
|---|---|---|
| `button`, `touch` | `{"pressed": true}` | 눌림 이벤트 |
| `presence`, `motion` | `{"detected": true}` | 재실·동작 감지 |
| `temperature`, `humidity`, `distance`, `pressure`, `light` | `{"value": 24.5}` | **숫자는 반드시 `value` 키** |
| `camera` | `{"connected": true, "fps": 15}` | 상태 표시용 |
| 그 외 | 자유 JSON | 차트는 안 그려짐 |

> ⚠️ **숫자 센서는 반드시 `{"value": 숫자}` 형태로 보고하세요.**
> 백엔드가 이 키를 보고 `sensor_readings.value`(FLOAT)에 넣기 때문에,
> 이것만 지키면 **차트·통계가 코드 수정 없이 자동으로** 동작합니다.
> 복합 센서(온습도 동시)는 슬롯 2개로 나누는 것을 권장합니다.

---

## 4. DB 스키마 (확정 — 이후 변경하지 않습니다)

> **실제 구현 메모 (P1)** — 1차 완성본을 이미 올린 팀의 DB를 **지우지 않고** 올라오도록,
> `devices` 테이블을 새로 만들지 않고 **부족한 컬럼만 자동으로 추가**했습니다
> (`db/database.py`의 `_ensure_column`). 그래서 두 가지가 아래 설계도와 다릅니다.
>
> | 설계도 | 실제 | 이유 |
> |---|---|---|
> | 기본키 `slot_id` | 기본키는 기존 이름 그대로 **`id`** | 기존 행·외래 관계를 깨지 않기 위해 |
> | `kind NULL` | `kind NOT NULL`, 빈 슬롯은 `'unassigned'` | 기존 컬럼이 NOT NULL이라서 |
>
> **API·WebSocket에서는 언제나 `slot_id`로 주고받습니다** — 프론트엔드와 pi는 `id`를 몰라도
> 됩니다. SQL을 직접 쓸 때만 `WHERE id = 'sensor_01'`로 적으세요.

```sql
-- 1. 디바이스 슬롯 (20행 고정 시드. 추가·삭제 없음)
CREATE TABLE IF NOT EXISTS devices (
  id            VARCHAR(20) PRIMARY KEY,   -- 'sensor_01' … 'actuator_10' (API에서는 slot_id)
  role          VARCHAR(10) NOT NULL,      -- 'sensor' | 'actuator'  (불변)
  slot_index    TINYINT     NOT NULL,      -- 1~10, 레거시 행은 0
  enabled       BOOLEAN     DEFAULT FALSE, -- 팀이 사용 여부 토글
  label         VARCHAR(100) NULL,         -- 팀이 지정하는 표시 이름
  kind          VARCHAR(30)  NOT NULL,     -- 'buzzer','servo','temperature' … (빈 슬롯은 'unassigned')
  unit          VARCHAR(20)  NULL,         -- '°C','kg','cm'
  control_type  VARCHAR(20)  NULL,         -- 3-1절 표 참고 (액추에이터만)
  value_schema  JSON         NULL,         -- {"min":0,"max":180,"step":1}
  meta          JSON         NULL,         -- 팀 자유 확장 (핀 번호 등)
  display_order TINYINT      DEFAULT 0,
  desired_state VARCHAR(30)  NULL,         -- 백엔드가 내린 명령
  current_state VARCHAR(30)  NULL,         -- pi가 보고한 실제 상태
  desired_value JSON         NULL,
  current_value JSON         NULL,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2~4. 기존과 동일 (이미 범용). device_id가 slot_id를 가리킨다
--   sensor_readings (device_id, value FLOAT, unit, value_json, created_at)
--   control_log     (device_id, action, value JSON, actor, created_at)
--   vision_events   (event_type, detected, count, confidence, label, created_at)

-- 5. 앱 설정 (기존)
--   app_settings (setting_key, setting_value JSON, updated_at)

-- 6. 자동화 규칙 (신규)
CREATE TABLE IF NOT EXISTS rules (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(100) NOT NULL,
  enabled    BOOLEAN DEFAULT TRUE,
  priority   TINYINT DEFAULT 0,
  definition JSON NOT NULL,        -- 7장의 규칙 JSON
  last_fired_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**확장 여유**: `meta`·`value_schema`·`definition`이 JSON이므로, 나중에 필드가 더 필요해도
**스키마 변경 없이** 담을 수 있습니다. 이것이 "DB를 고치지 않는다"를 지키는 장치입니다.

---

## 5. API 계약

### 5-1. 전체 목록

| 메서드/경로 | 호출 주체 | 인증 | 용도 | 상태 |
|---|---|---|---|---|
| `GET /api/slots` | 대시보드 | 사용자 | **슬롯 20개 전체 + 메타데이터** (`?role=`, `?enabled_only=`) | ✅ P1 |
| `PATCH /api/slots/{slot_id}` | 대시보드 | 사용자 | **메타데이터 수정** (label·kind·unit·control_type·enabled…) | ✅ P1 |
| `GET /api/devices` | 대시보드 | 사용자 | 팀이 **실제로 쓰는** 디바이스 목록 (비활성 슬롯은 숨김) | ✅ 기존 |
| `GET /api/devices/{slot_id}` | 대시보드 | 사용자 | 슬롯 1개 상세 | ✅ 기존 |
| `POST /api/devices/{slot_id}/control` | 대시보드 | 사용자 | 액추에이터 목표 상태 지정 (비활성 슬롯은 400) | ✅ 기존 |
| `GET /api/devices/{slot_id}/readings` | 대시보드 | 사용자 | 센서 이력 (차트용, 최대 500) | ✅ 기존 |
| `GET /api/v1/devices/desired-states` | **pi** | 디바이스 키 | **전체 액추에이터 목표 상태 일괄 조회** | ✅ P1 |
| `POST /api/v1/devices/states` | **pi** | 디바이스 키 | **센서값·반영상태 일괄 보고** | ✅ P1 |
| `POST /api/v1/devices/register` | **pi** | 디바이스 키 | 부팅 시 슬롯 매핑 일괄 등록 | ✅ P1 |
| `GET/POST /api/rules`, `PUT/DELETE /api/rules/{id}` | 대시보드 | 사용자 | 자동화 규칙 CRUD | ✅ P1 |
| `POST /api/timers` | 대시보드 | 사용자 | N초 뒤 액션 1회 실행 (시나리오 SDK의 serverTimer) | ✅ P3 |
| `POST /api/v1/vision/events` | vision | 디바이스 키 | 감지 이벤트 (기존 계약 유지) | ✅ 기존 |
| `GET /api/logs/control`, `GET /api/events/vision`, `GET /health` | 대시보드 | 사용자 | 기존 그대로 | ✅ 기존 |
| `GET /api/v1/vision/config` | vision | 디바이스 키 | 감지 대상 목록 | ✅ P4 |
| `GET/PUT /api/vision/config` | 대시보드 | 사용자 | 감지 대상 설정 화면 | ✅ P4 |

**목록 두 개의 차이** — `GET /api/slots`는 빈 슬롯까지 20개를 모두 돌려주므로 '하드웨어 구성'
설정 화면용이고, `GET /api/devices`는 활성 슬롯만 돌려주므로 대시보드 본화면용입니다.

**타이머** — `POST /api/timers`는 "지금부터 N초 뒤에 딱 한 번"을 위한 것입니다.
반복되는 자동화는 규칙(`/api/rules`)으로 만드세요. 규칙 액션의 `after_seconds`는
트리거가 발동한 뒤의 지연이라, 트리거 없이 지금 재는 시간은 표현할 수 없습니다.

기존 단일 폴링(`GET /api/v1/devices/{slot_id}/desired-state`)과 단일 보고(`POST .../state`)도
**호환을 위해 유지**합니다. 다만 pi는 배치 API를 쓰는 것을 기본으로 합니다.

### 5-1-1. DB가 꺼져 있을 때 (수업 중 실제로 자주 생기는 상황)

XAMPP를 켜지 않아도 키트는 멈추지 않습니다. 슬롯 목록·배치 폴링·배치 보고·제어는
메모리 캐시로 동작하고, **기록이 필요한 것만** 솔직하게 거부합니다.

| 상황 | 응답 |
|---|---|
| `GET /api/slots`, `GET /api/v1/devices/desired-states` | 메모리 캐시로 정상 응답 (빈 목록이 아님) |
| `POST /api/v1/devices/register` | 200 + `"persisted": false` (그 세션 동안만 유효) |
| `GET /api/devices/{slot_id}/readings` | 빈 목록 `[]` (500이 아님) |
| `POST /api/rules` 등 규칙 저장 | **503 `DB_UNAVAILABLE`** — 규칙은 DB에만 저장되므로 |

현재 DB 상태는 `GET /health`의 `database.connected`로 확인합니다.

### 5-2. 배치 API가 필수인 이유

슬롯이 20개로 늘어나므로, 기존처럼 디바이스마다 1초 주기로 따로 호출하면
**팀당 초당 20요청**이 됩니다. 배치로 묶으면 **초당 1요청**입니다.

**`GET /api/v1/devices/desired-states`** — 활성 액추에이터만 돌려줍니다.
```json
{
  "data": {
    "server_time": "2026-09-12T07:30:00+09:00",
    "slots": {
      "actuator_01": { "desired_state": "on", "value": {"frequency":1000,"volume":85},
                       "control_type": "tonal", "updated_at": "..." },
      "actuator_02": { "desired_state": "off", "value": null,
                       "control_type": "onoff", "updated_at": "..." }
    }
  }
}
```

**`POST /api/v1/devices/states`** — 액추에이터 반영 결과와 센서값을 한 번에 보고합니다.
```json
{
  "reported_at": "2026-09-12T07:30:01+09:00",
  "states": [
    { "slot_id": "actuator_01", "state": "on",  "value": {"frequency":1000} },
    { "slot_id": "sensor_01",   "value": {"pressed": true} },
    { "slot_id": "sensor_02",   "value": {"value": 24.6}, "unit": "°C" }
  ]
}
```
- `state`가 있으면 **액추에이터 반영 결과**, 없으면 **센서 측정값**으로 처리합니다(기존 규칙과 동일).
- 응답은 `{"data":{"accepted": 3, "rejected": []}}` 형식이며, 모르는 슬롯은 `rejected`에 담고
  나머지는 정상 처리합니다(하나 틀렸다고 전체가 실패하지 않음).

**`POST /api/v1/devices/register`** — 배선을 아는 pi가 메타데이터를 올립니다.

> **등록은 그 슬롯의 메타데이터 전체를 덮어씁니다.** 보내지 않은 항목은 지워집니다.
> 서보를 떼고 부저를 꽂았는데 서보의 `value_schema`(0~180도)가 남아 있으면
> 대시보드에 주파수 슬라이더가 0~180Hz로 그려지기 때문입니다.
```json
{
  "exclusive": true,
  "slots": [
    { "slot_id": "actuator_01", "label": "알람 부저", "kind": "buzzer",
      "control_type": "tonal", "value_schema": {"frequency":{"min":200,"max":4000}},
      "meta": {"pin": 18} },
    { "slot_id": "sensor_01", "label": "기상 버튼", "kind": "button", "meta": {"pin": 24} }
  ]
}
```
`exclusive: true`면 목록에 없는 슬롯은 자동으로 `enabled=false`가 됩니다
→ **부품을 떼면 pi의 `slot_map.py`에서 지우기만 하면 대시보드에서도 사라집니다.**

### 5-3. 응답·에러 형식 (기존 유지)

성공 `{"data": ...}` / 실패 `{"error": {"code": "...", "message": "..."}}`

---

## 6. WebSocket 이벤트 계약

| 이벤트 | 언제 | 주요 필드 |
|---|---|---|
| `device_state` | 액추에이터 명령/반영 | `slot_id`, `desired_state`, `current_state`, `desired_value`, `current_value`, `actor` |
| `sensor_reading` | 센서 보고 | `slot_id`, `value`, `unit`, `current_state` |
| `slot_config` | 메타데이터 변경(등록·수정) | `slot_id`, 변경된 메타데이터 |
| `vision_event` | 비전 감지 | `label`, `detected`, `confidence`, `count` |
| `rule_fired` | 규칙 발동 | `rule_id`, `name`, `actions` |
| `notify` | 규칙/시나리오 알림 | `level`, `message` |

> `desired_state`와 `current_state`는 **항상 따로 보냅니다**(부록A 계약).
> 둘이 다르면 대시보드는 "하드웨어 반영 대기"로 표시합니다 —
> 배선이 빠졌는데 화면만 정상으로 보이는 사고를 막는 장치입니다.

---

## 7. 자동화 규칙 (최소 스펙)

> **목적**: 반복적인 자동화(임계값·스케줄)를 **코드 없이** 처리해, 프론트 담당 학생이
> 시나리오의 재미있는 부분에만 집중하게 합니다. 규칙은 **선택**이며,
> 프론트에서 직접 제어해도 똑같이 동작합니다.

### 7-1. 규칙 JSON

```json
{
  "name": "더우면 조명 릴레이 끄기",
  "enabled": true,
  "when": { "type": "sensor_threshold", "slot_id": "sensor_02",
            "op": ">", "value": 28, "for_seconds": 5 },
  "then": [ { "action": "set_actuator", "slot_id": "actuator_05", "state": "off" } ],
  "otherwise": [ { "action": "set_actuator", "slot_id": "actuator_05", "state": "on" } ],
  "cooldown_seconds": 30
}
```

### 7-2. 트리거 3종 (이것만 지원합니다)

| type | 필드 | 예시 용도 |
|---|---|---|
| `schedule` | `at: "07:30"` 또는 `in_seconds: 5` | 알람 시각, 수업 시작 시각 |
| `sensor_threshold` | `slot_id`, `field`(기본 `value`), `op`(`>` `>=` `<` `<=` `==` `!=`), `value`, `for_seconds` | 온도·압력·거리 자동 제어 |
| `vision_label` | `label`, `min_confidence`, `count_at_least` | 사람 감지 시 조명 on |

### 7-3. 액션 2종 + 지연 옵션

| action | 필드 |
|---|---|
| `set_actuator` | `slot_id`, `state`, `value`(선택), `after_seconds`(선택 — N초 후 실행) |
| `notify` | `level`(`info`/`warn`/`alert`), `message` |

`after_seconds`가 **타이머 프리미티브** 역할을 합니다.
예) wakeup의 2차 수면 방지: 미션 성공 후 `after_seconds: 60`으로 알림 → 미응답 시 부저 재동작.

### 7-4. 규칙으로 하지 않는 것

라운드·승수·AI 손패가 있는 **가위바위보 미션 같은 게임 로직은 규칙으로 표현하지 않습니다.**
이런 시나리오는 다음 장의 프론트엔드 시나리오 SDK로 작성합니다.

---

## 8. pi 계약 — 팀이 고치는 파일은 `slot_map.py` 하나

```
pi/
├── slot_map.py        ← ★ 팀이 편집하는 유일한 파일
├── drivers/           ← 키트 제공 (필요 시 팀이 새 드라이버 추가)
│   ├── base.py            드라이버 계약 (apply / read 2개 메서드)
│   ├── gpio.py            GPIO 접근 + PC용 흉내내기 부품 자동 대체
│   ├── digital_out.py     on/off 출력 (LED, 릴레이, 액티브 부저)
│   ├── pwm_out.py         PWM (진동모터 세기, LED 밝기, 모터 속도)
│   ├── tonal_buzzer.py    주파수 지정 부저 (passive/active 선택)
│   ├── servo.py           서보모터 각도
│   ├── neopixel_out.py    RGB 스트립 (데이터선 1개로 여러 알)
│   ├── rgb_out.py         3핀 RGB LED (R·G·B 각각 PWM)
│   ├── level_out.py       단계 표시 (LED 여러 개를 단계로)
│   ├── button_in.py       버튼·터치센서·PIR (극성 설정)
│   ├── analog_in.py       압력·조도 (ADC 경유)
│   ├── dht_in.py          온습도
│   └── distance_in.py     초음파 거리
├── examples/          ← 팀별 배치표 예시 (복사해서 slot_map.py로 쓰세요)
├── slot_config.py     ← 키트 제공 배치표 검사기 (오타를 실행 전에 잡아냄)
├── backend_client.py  ← 키트 제공 배치 통신 (등록·폴링·보고)
├── daemon.py          ← 키트 제공 공통 루프 (수정 불필요)
└── test_slot_daemon.py ← 키트 제공 자가 점검 (GPIO·백엔드 없이 실행)
```

> **구현 메모** — 설계 단계에서는 드라이버마다 `mock_*.py`를 따로 두기로 했지만,
> 실제로는 **`drivers/gpio.py` 한 곳에서 부품만 흉내내도록** 바꿨습니다.
> 파일을 둘로 나누면 각도 제한·볼륨 환산 같은 로직이 한쪽만 고쳐져서
> "PC에서는 되는데 파이에서는 안 되는" 일이 생기기 때문입니다.
> 드라이버는 한 벌만 유지하고, 실기기/흉내내기는 부품 계층에서만 갈립니다.

**배선 확인 먼저** — 부품을 건드리기 전에 배치표만 점검할 수 있습니다.

```bash
cd pi
python daemon.py --check     # 백엔드·GPIO·슬롯 목록·오타를 보여주고 종료
python test_slot_daemon.py   # GPIO도 백엔드도 없이 28개 항목 자가 점검
```

### 8-1. `slot_map.py` 형식

```python
# 이 파일만 팀 하드웨어에 맞게 고칩니다.
# 부품을 떼면 줄을 지우고, 붙이면 줄을 추가합니다. 그게 전부입니다.
SLOTS = {
    # --- 액추에이터 ---
    "actuator_01": {
        "label": "알람 부저", "kind": "buzzer",
        "driver": "tonal_buzzer", "pin": 18,
        "control_type": "tonal",
    },
    "actuator_02": {
        "label": "경보 LED", "kind": "led",
        "driver": "digital_out", "pin": 23,
        "control_type": "onoff",
    },
    # --- 센서 ---
    "sensor_01": {
        "label": "기상 버튼", "kind": "button",
        "driver": "button_in", "pin": 24, "pull_up": True,
    },
    "sensor_02": {
        "label": "실내 온도", "kind": "temperature", "unit": "°C",
        "driver": "dht_in", "pin": 4, "interval": 5.0,
    },
}
```

### 8-2. 데몬 동작 (키트 제공, 수정 불필요)

1. 부팅 시 `SLOTS`를 `POST /api/v1/devices/register`로 등록 (`exclusive: true`)
2. 1초 주기로 `GET /api/v1/devices/desired-states` → 드라이버에 반영
3. 센서값·반영상태를 `POST /api/v1/devices/states`로 일괄 보고
4. 보고 실패 시 다음 회차 재시도, 30초마다 재동기화
5. GPIO·라이브러리를 쓸 수 없으면(PC 환경 등) 그 부품만 흉내내기로 대체 —
   **프로그램이 죽지 않습니다.** 배치표 한 줄에 오타가 있어도 그 줄만 빼고 나머지는 동작합니다.

### 8-3. pi 담당 학생의 작업 범위

| 하고 싶은 것 | 해야 하는 일 |
|---|---|
| 우리 팀 배치표 시작 | `cp examples/slot_map_<우리팀>.py slot_map.py` 후 핀 번호만 수정 |
| 부품 추가 | `SLOTS`에 한 줄 추가 |
| 부품 제거 | `SLOTS`에서 한 줄 삭제 |
| 핀 변경 | `pin` 값 수정 |
| 부저 종류 변경 | `driver`를 `digital_out` ↔ `tonal_buzzer`로 |
| 키트에 없는 부품 | `drivers/`에 클래스 1개 추가 (`apply()`/`read()` 2개 메서드) |

---

## 9. frontend 계약 — 카드 자동 생성 + 시나리오 SDK

```
frontend/
├── lib/
│   ├── api.ts          기존 (apiFetch, parseJsonValue)
│   ├── slots.ts        슬롯 메타데이터 → 위젯 결정 (키트 제공)
│   └── scenario.ts     ★ 시나리오 SDK useScenario() (키트 제공)
├── components/kit/     키트 제공 범용 컴포넌트 (디자인은 팀이 수정)
│   ├── SlotGrid.tsx         활성 슬롯 자동 배치
│   ├── SensorSlotCard.tsx   kind·unit에 맞는 값 표시
│   ├── ActuatorSlotCard.tsx control_type에 맞는 위젯 자동 선택
│   ├── SlotIcon.tsx         kind에 맞는 아이콘
│   ├── HardwareSetup.tsx    슬롯 20칸 설정 화면 (라벨·종류·사용여부)
│   └── RuleEditor.tsx       규칙 편집기 (7장 스펙)
├── app/kit/page.tsx    ★ 키트 대시보드 (팀이 자유롭게 고쳐 쓰는 출발점)
└── app/page.tsx        wakeup 1차 대시보드 (P3.5에서 정리 예정)
```

**두 화면이 공존합니다** — `/`는 1차 완성본(기상 시스템) 화면 그대로이고,
`/kit`이 플랫폼 키트 화면입니다. 2차 개발은 `/kit`에서 시작하세요.

### 9-1. 카드 자동 생성

`GET /api/devices`의 `control_type`만 보고 위젯이 결정됩니다(3-1절 표).
**슬롯 구성을 바꿔도 화면 코드는 그대로**이고, 팀은 디자인만 손봅니다.

### 9-2. 시나리오 SDK — 프론트가 "두뇌"를 맡는 방식

WebSocket 배선·재연결·상태 동기화는 SDK가 처리합니다. 팀은 규칙을 쓰기만 합니다.

```tsx
const {
  slots,                      // 현재 슬롯 상태 (실시간 갱신)
  slotOf,                     // slotOf("actuator_01") — 슬롯 하나 찾기
  connected,                  // 백엔드 WebSocket 연결 여부
  setActuator,                // setActuator("actuator_01", "on", {frequency: 1000})
  onSensor,                   // onSensor("sensor_01", e => { if (e.pressed) ... })
  onVision,                   // onVision(["rock","paper"], e => { ... })
  onSlotChange,               // onSlotChange("actuator_01", s => { ... })
  after, cancel,              // after(60, cb) — 지연 실행 (취소 가능)
  notify, notices,            // 화면 알림 (규칙의 notify 액션도 여기로 들어옵니다)
  serverTimer,                // 브라우저를 닫아도 살아있는 타이머 (POST /api/timers)
  refresh,                    // 슬롯 목록 다시 읽기
} = useScenario();
```

`onSensor`·`onVision`·`onSlotChange`는 **구독 해지 함수**를 돌려줍니다.
`useEffect`에서 등록했다면 정리 함수로 꼭 해지하세요.

```tsx
useEffect(() => onSensor("sensor_01", (e) => {
  if (e.pressed) setActuator("actuator_01", "off");
}), [onSensor, setActuator]);
```

예) wakeup의 가위바위보 미션을 프론트에서 작성하면 이런 모양이 됩니다:

```tsx
// 알람이 울리면 미션 시작
onSlotChange("actuator_01", (s) => {
  if (s.desired_state === "on") startRound();
});

// 손동작이 들어오면 승패 판정
onVision(["rock", "paper", "scissors"], (e) => {
  const result = judge(aiHand, e.label);
  if (result === "win" && ++wins >= 2) {
    setActuator("actuator_01", "off");          // 알람 해제
    serverTimer(60, () => notify("기상 확인!")); // 2차 수면 방지
  } else {
    startRound();                                // 오답 → 재시도
  }
});
```

### 9-3. 브라우저를 닫으면?

프론트가 두뇌이므로 **대시보드 탭이 닫히면 시나리오가 멈춥니다.** 전시회·시연에서는
화면이 항상 열려 있으므로 문제가 없지만, 꼭 브라우저 없이 동작해야 하는 동작은
백엔드에 맡기세요. 이 경계를 팀이 알고 있어야 합니다.

| 상황 | 어디에 맡기나 |
|---|---|
| 화면이 열려 있는 동안의 게임·미션 로직 | 시나리오 SDK (`onVision`, `after`) |
| "지금부터 60초 뒤에 한 번" | `serverTimer(60, …)` → `POST /api/timers` |
| "온도가 28도를 넘으면 항상" 같은 반복 자동화 | 규칙 (7장, RuleEditor 화면) |

> 타이머는 저장되지 않습니다 — 백엔드를 재시작하면 사라집니다.
> 수업이 끝나도 살아 있어야 하는 자동화는 규칙으로 만드세요.

---

## 10. vision 계약 — 감지 "대상"은 설정으로, 감지 "방법"은 플러그인으로

팀마다 보는 것이 다릅니다. 손동작·사람 수·자세·혼잡도 — 그래서 vision은
**통째로 공통이 아니고, 공통 루프 + 검출기 플러그인**으로 나뉩니다.

```
vision/
  main.py                  공통 — 카메라를 열고, 검출기를 돌리고, 보내고, 보여 줌
  camera.py                공통 — USB 웹캠 / Pi Camera 자동 선택
  detectors/
    base.py                공통 — 검출기 계약 (이 파일은 고치지 않습니다)
    __init__.py            공통 — 폴더를 훑어 검출기를 자동으로 찾는 로더
    objects.py             공통 — 사물 탐지(YOLO). 4팀이 같이 씁니다
    <팀 이름>.py            ★ 팀 고유 — 파일 하나 = 검출기 하나
    _<보조 모듈>.py          `_`로 시작하면 로더가 검출기로 세지 않습니다
```

### 10-1. 검출기 계약 (`detectors/base.py`)

파일 하나에 `FrameDetector`를 상속한 `Detector` 클래스를 두면 끝입니다.
**등록은 하지 않습니다** — `detectors/` 폴더를 넣으면 자동으로 인식됩니다(pi의 `drivers/`와 같은 방식).

```python
class Detector(FrameDetector):
    name = "pose"                          # 설정에서 이 이름으로 켭니다
    labels = ("my_label_a", "my_label_b")  # 내가 내보낼 라벨 (백엔드에 신고됩니다)
    description = "자세 감지"

    def detect(self, frame_bgr, config):   # 한 프레임을 보고 무엇이 보이는지만 말합니다
        return [DetectionEvent(label="my_label_a", detected=True, confidence=0.9)]
```

- 라이브러리가 없으면 `self.disable("이유")`를 부르면 됩니다. 그 검출기만 빠지고
  **나머지는 그대로 동작합니다** — MediaPipe가 없다고 사물 감지까지 멈추면 수업이 멈춥니다.
- 검출기는 **판정하지 않습니다.** 이겼는지·혼잡한지·졸고 있는지는 프론트엔드 시나리오의 몫입니다(9-2절).

### 10-2. 검출기 신고 — 백엔드는 라벨 이름을 모릅니다

비전 클라이언트는 부팅할 때 자기 검출기를 한 번 신고합니다.

```
POST /api/v1/vision/detectors     (디바이스 키)
{ "detectors": [
    {"name": "objects",  "labels": [],                      "description": "사물 탐지"},
    {"name": "my_pose",  "labels": ["my_label_a"],           "description": "자세 감지"},
    {"name": "broken",   "labels": [], "available": false,   "reason": "라이브러리 없음"}
] }
```

**이 신고가 규약의 핵심입니다.** 백엔드 코드에는 어느 팀의 라벨 이름도 없습니다.
신고를 받고 나면 백엔드는 그 라벨이 "사물 탐지 대상이 아니다"라는 것을 알게 되고,
대시보드의 영상인식 설정 화면과 규칙 편집기도 그 목록을 보고 채워집니다.
그래서 팀이 검출기를 추가해도 **백엔드 0줄 · 대시보드 0줄**입니다.

DB가 꺼져 있으면 응답에 `"persisted": false`가 들어옵니다(감지는 계속 동작합니다).
저장된 척하지 않는 이유: "설정은 바꿨는데 왜 안 먹지?"로 한참 헤매게 됩니다.

### 10-3. 감지 설정 (`GET /api/v1/vision/config`)

```json
{ "data": {
    "object_labels": ["person", "bottle", "cup"],
    "detectors": [],
    "min_confidence": 0.6,
    "cooldown_seconds": 2.5,
    "source": "saved",
    "known_detectors": [{"name": "objects", "labels": [], "available": true}],
    "gesture_enabled": true
} }
```

- `object_labels` — **사물 탐지 검출기에만** 주는 값입니다(COCO 클래스명).
  규칙(`vision_label` 트리거)과 대시보드 설정에서 자동으로 산출됩니다.
  **규칙에 쓴 라벨은 설정에 적지 않아도 자동으로 포함됩니다** — 규칙을 만들었는데
  감지가 안 되면 원인을 찾기 어렵기 때문입니다.
- `detectors` — 돌릴 검출기 이름 목록. **비어 있으면 "가진 것 전부"**입니다.
  그래서 팀이 나중에 검출기를 추가해도 설정을 다시 만지지 않아도 돌아갑니다.
- `known_detectors` — 10-2의 신고 내용. 대시보드가 이것을 보고 체크박스를 그립니다.
- `gesture_enabled` — 구버전 화면·클라이언트 호환용 불린입니다(신규 코드는 `detectors`를 씁니다).
- 사물 탐지가 아닌 검출기의 라벨은 `object_labels`에서 **자동으로 제외**됩니다.
  제외 목록은 코드가 아니라 **신고**에서 나옵니다.
- COCO에 없는 라벨을 넣으면 조용히 건너뜁니다 (화면이 깨지지 않습니다).
- vision은 5초마다 설정을 다시 받아오므로 **프로그램을 다시 켜지 않아도** 반영됩니다.
- 서버에 연결되지 않으면 마지막 설정(없으면 기본 대상 5종)으로 계속 동작합니다.
- 바꾸는 곳: 대시보드 `/kit` → **영상인식 설정** 탭. `PUT /api/vision/config`는
  DB가 꺼져 있으면 200이 아니라 **503 `DB_UNAVAILABLE`**로 거절합니다.
- 이벤트 전송 형식은 기존 그대로: `{"event_type","detected","count","confidence","label"}`
  백엔드는 `label` 값을 해석하지 않고 그대로 저장·중계합니다.

### 10-4. 카메라 (`camera.py`)

`CAMERA_SOURCE=auto|usb|picamera`(기본 `auto`)로 고릅니다. `auto`는 picamera2를 먼저
시도하고 없으면 USB 웹캠으로 넘어갑니다. 실패하면 원인별 한국어 안내를 출력합니다
(리본 케이블, `sudo apt install -y python3-picamera2`, `rpicam-hello --list-cameras`).

**vision 화면은 판정하지 않습니다.** 무엇을 봤는지만 보여 주고, 승패·라운드 같은 시나리오
판정은 프론트엔드가 합니다(9-2절). 그래서 미리보기 창에는 감지 대상과 인식 결과만 나옵니다.

---

## 11. 적합성 체크리스트 (키트를 제대로 쓰고 있는가)

`backend/conformance_test.py`가 자동으로 검사합니다. 서버를 따로 띄우지 않아도 됩니다.

```bash
cd backend
python conformance_test.py      # DB를 켜고 한 번, 끄고 한 번 돌려 보세요
```

| 항목 | 자동 검사 |
|---|---|
| 20개 슬롯이 모두 DB에 존재하고 `role`이 고정되어 있는가 | ✅ 1번 |
| 부품을 추가·교체할 때 코드 수정 없이 반영되는가 | ✅ 2번 |
| pi가 배치 API(`desired-states` / `states`)로 통신하는가 | ✅ 3번 |
| 미사용 슬롯이 `enabled=false`로만 처리되고 삭제되지 않았는가 | ✅ 4번 |
| 비활성 슬롯 제어·보고가 거부되는가 (배치 전체는 살아남는가) | ✅ 4번 |
| 액추에이터의 `current_state`를 백엔드가 직접 쓰지 않는가 (pi 보고만) | ✅ 3번 |
| 숫자 센서가 `{"value": 숫자}` 형식으로 보고되어 차트가 동작하는가 | ✅ 6번 |
| 자동화가 코드가 아니라 규칙으로 표현되는가 (트리거 3종·액션 2종) | ✅ 7번 |
| DB를 꺼도 제어·폴링·목록이 500 없이 동작하는가 | ✅ DB를 끄고 실행 |
| 감지 대상·검출기를 코드 없이 바꿀 수 있는가 | ✅ 7-3번 |
| 처음 보는 팀 라벨도 **신고만으로** 사물 대상에서 제외되는가 | ✅ 7-3번 |
| 백엔드·vision 코드에 **다른 팀** 디바이스 이름이 0개인가 | ✅ 8번 |
| 백엔드에 **팀 시나리오 라벨**(게임·자세 이름)이 0개인가 | ✅ 8번 |
| vision 공통층(`main.py`·`camera.py`·`detectors/{base,__init__,objects}`)에 팀 라벨이 0개인가 | ✅ 8번 |
| 팀 고유 검출기가 `detectors/` 안에만 있는가 | ✅ 8번 |
| 팀 브랜치의 `backend/`·`vision/` 공통층 diff가 공통 키트와 **동일**한가 | 수동 (`git diff platform -- backend vision/main.py vision/camera.py vision/detectors/base.py vision/detectors/__init__.py vision/detectors/objects.py`) |

검사 결과(P6 시점, `platform` 브랜치): **DB 켠 상태 69건 전부 통과 / DB 끈 상태 51건 전부 통과**.

전체 자가 점검 목록:

| 무엇 | 실행 | 항목 |
|---|---|---|
| 키트 적합성 | `cd backend && python conformance_test.py` | 69 |
| 백엔드 기본 동작 | `cd backend && python smoke_test.py` | 32 |
| pi 드라이버·배치표 | `cd pi && python test_slot_daemon.py` | 39 |
| 시나리오 판정 규칙 | `cd frontend && node --experimental-strip-types scenarios/wakeupEngine.test.ts` | 30 |
| 영상인식 설정·검출기 계층 | `cd vision && python test_vision_config.py` | 38 |
| 팀별 배치표 예시 | `cd pi && python test_team_examples.py` | 32 |

> 8번 검사는 **모든 팀 고유 이름**을 실패로 셉니다(wakeup의 `buzzer_1` 포함).
> 예외는 `db/database.py`의 이관 대응표 하나뿐입니다 — 1차 완성본을 올린 팀이
> 그대로 올라오려면 옛 이름을 알아야 하기 때문입니다.
>
> ⚠️ P4까지 8번 검사는 디바이스 **이름**만 봤고 **라벨**은 보지 않았습니다.
> 그래서 `backend/services/vision_config.py`에 `GESTURE_LABELS`로 박혀 있던
> wakeup 게임 라벨을 놓쳤습니다. P6에서 라벨도 금지 목록에 넣었습니다 —
> **금지 목록에 없는 것은 검사되지 않는다**는 뜻이니, 팀 고유 이름을 새로 만들면
> `conformance_test.py`의 `team_names` · `scenario_labels`에 함께 추가하세요.

---

## 12. 기존 코드 마이그레이션

| 팀 | 기존 ID | → 슬롯 |
|---|---|---|
| wakeup | `buzzer_1` | `actuator_01` |
| wakeup | `touch_pad_1` | `sensor_01` |
| wakeup | `camera_1` | 슬롯 없음 (vision_events) |
| classroom | `servo_door` / `seat_led` / `neopixel_seat` / `buzzer` / `relay_light` | `actuator_01` ~ `actuator_05` |
| study | `rgb_led` / `vibration_motor_a` / `vibration_motor_b` / `relay_power` | `actuator_01` ~ `actuator_04` |
| study | `touch_display` | `sensor_01` |
| subway | `led_congestion` / `motor_conveyor` | `actuator_01`, `actuator_02` |
| subway | `sensor_seat_pressure` | `sensor_01` |

**wakeup 팀 이행은 완료되었습니다 (P3.5).** 백엔드가 DB를 열 때 자동으로 옮깁니다.

| 옛 것 | 새 것 |
|---|---|
| `buzzer_1` | `actuator_01` (라벨·종류를 그대로 물려받음) |
| `touch_pad_1` | `sensor_01` (종류는 `touch`로 변환) |
| `camera_1` | 슬롯 없음 — `vision_events`로 들어옴 |
| `POST /api/alarm/schedule` | 자동화 규칙 (`schedule` 트리거) |
| `services/trigger_service.py` (미션 엔진) | `frontend/scenarios/wakeupEngine.ts` + `useWakeup.ts` |
| `pi/main.py` | `pi/daemon.py` + `pi/slot_map.py` |

레거시 행은 **지우지 않고 숨깁니다**(`enabled=false`) — `sensor_readings`·`control_log`가
`device_id`로 이력을 가리키고 있어서, 지우면 학생들이 만든 기록이 통째로 고아가 됩니다.

**이행 방법**: 기존 팀 브랜치는 이력 보존용으로 남기고, 공통 키트 브랜치에서 새로 분기한 뒤
`pi/slot_map.py`와 프론트 화면만 옮깁니다(이식 대상이 작도록 설계한 이유입니다).
wakeup 팀을 첫 검증 대상으로 삼습니다 — 기존 테스트 54개(스모크 36 + 미션 18)가 기준선입니다.

---

## 13. 다음 단계 (P1~P5)

| 단계 | 내용 | 주 담당 |
|---|---|---|
| **P1** | 백엔드 코어: 슬롯 레지스트리, 배치 API, register/PATCH, 규칙 엔진, 적합성 테스트 | 키트(공통) |
| **P2** | pi 프레임워크: `slot_map.py` + 드라이버 11종 + Mock + 공통 데몬 | 키트(공통) |
| **P3** | 프론트 키트: SlotGrid·카드·HardwareSetup·RuleEditor·시나리오 SDK | 키트(공통) |
| **P4** | vision 일반화: 설정 기반 감지 대상 | 키트(공통) |
| **P5** | 4팀 배포: 팀별 `slot_map` 예시, 매뉴얼 갱신, wakeup 마이그레이션 검증 | 키트 + 각 팀 |

P1~P4가 끝나면 각 팀의 2차 개발은 **`frontend/` + `pi/slot_map.py`** 작업만 남습니다.

---

## 14. 이 규약의 사전 검증 결과

스키마를 확정하기 전에 실제 MariaDB에 올려 보고, 계약 로직을 최소 구현해 시뮬레이션했습니다.

| 검증 항목 | 결과 |
|---|---|
| 4장 DB 스키마 6개 테이블 생성 | ✅ 문법 오류 없음 |
| 슬롯 20개 시드 (`sensor_01`~`10`, `actuator_01`~`10`) | ✅ 정상 생성 |
| classroom 구성(액추에이터 5개 + 센서 1개) 등록 → 폴링·제어·배치 보고 | ✅ |
| 부품 제거(네오픽셀) → 폴링 대상 자동 제외, 나머지는 계속 동작 | ✅ |
| subway 구성으로 전면 교체 → **같은 코드로** level·pwm 제어 | ✅ |
| 규칙만으로 자동 제어 (압력 52kg → 혼잡 3단계, 12kg → 1단계) | ✅ 프론트 코드 0줄 |
| 숫자 센서 이력이 `sensor_readings.value`에 적재 (차트 자동 동작 조건) | ✅ |
| 비활성 슬롯 보고는 거부되지만 배치 전체가 실패하지 않음 | ✅ |

총 14개 항목 전부 통과. **서로 다른 세 팀의 하드웨어 구성을 백엔드 코드 변경 없이 수용**함을
확인했으므로, 이 규약대로 P1 구현을 진행할 수 있습니다.
