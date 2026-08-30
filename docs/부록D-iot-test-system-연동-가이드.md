# `iot-test-system` ↔ 우리 팀 실제 백엔드 연동 가이드 (백엔드·프론트 담당자용)

> 📂 **부록D / 백엔드·DB 담당 / 4단계 직전 — 임시 테스트 시스템으로 연습한 팀만** · 전체 목록 [docs/README.md](README.md)

> **한 줄 요약**: 라즈베리파이 담당자가 연습한 임시 테스트 시스템(`iot-test-system`)과
> 이 킷으로 만드는 우리 팀 실제 백엔드는 **경로·인증 헤더·데이터 모델이 전부 다릅니다.**
> 파이 담당자의 `client.py`는 그대로 붙지 않습니다. 이 문서는 그 차이를 정확히 알고,
> 백엔드 쪽에서 무엇을 준비해 넘겨야 하는지 정리한 것입니다.

## 0. 두 시스템의 관계

| | `iot-test-system` (임시 테스트) | 이 킷으로 만드는 우리 팀 시스템 |
|---|---|---|
| 목적 | 진짜 백엔드가 생기기 전, 파이 담당자가 gpiozero·REST 감각을 익히는 연습장 | 팀의 실제 작품 |
| 구성 | backend/frontend/mock_pi가 **이미 완성**되어 있음 | 설계도 + AI 프롬프트 지침 (코드는 팀이 생성) |
| 파이 쪽 플러그인 | `antigravity-plugin` (파이 담당자가 설치) | 이 킷의 `.agents/` (백엔드·프론트 담당자가 사용) |
| 운영 형태 | 6개 팀이 한 인스턴스를 공유 → 경로에 `device_id` 필수 | 팀당 독립 배포 |

파이 담당자가 `antigravity-plugin`으로 만든 코드 중 **그대로 유효한 것**은 gpiozero
클래스 선택·배선·lgpio 핀팩토리 같은 하드웨어 지식이고, **다시 만들어야 하는 것**은
REST 클라이언트(`client.py`) 전체입니다.

전환 절차 자체는 `iot-test-system/docs/03-진짜-백엔드-연동-확인-매뉴얼.md`에 6단계로 정리돼
있습니다. 그 문서의 **1·2단계가 백엔드 담당자의 몫**입니다 — 이 문서는 그 준비를
빠짐없이 하기 위한 체크리스트입니다.

---

## 1. 무엇이 다른가 (실제로 호출해서 확인한 결과)

`iot-test-system/backend`를 띄워 놓고 우리 킷의 계약대로 요청을 보내면 이렇게 됩니다.

| 보낸 요청 | 결과 |
|---|---|
| `GET /api/v1/devices/led_1/desired-state` | **404** `{"detail":"Not Found"}` — 그런 경로가 없음 |
| `POST /api/v1/devices/led_1/state` | **404** |
| `GET /api/devices/led_1/components` | **422** `int_parsing` — `device_id`가 정수여야 함 |
| `POST /api/devices/1/telemetry` 에 `{"value":24.5,"unit":"celsius"}` | **422** `items` 필드 없음 |

차이를 항목별로 정리하면:

| 항목 | `iot-test-system` | 이 킷 |
|---|---|---|
| 인증 헤더 | `X-Device-Key` | `X-Device-Api-Key` |
| 키 발급 | 디바이스 등록 시 서버가 자동 발급(디바이스별로 다름) | `.env`의 `DEVICE_API_KEY` 하나를 세 폴더가 공유 |
| 경로 접두사 | `/api/...` | `/api/v1/...` (디바이스향) |
| `device_id` 타입 | 정수 (`1`) | 슬러그 (`led_1`, `door_lock_1`) |
| **식별 단위** | `device` 1대(라즈베리파이) → 그 아래 `component` N개 | `device` 1행 = 센서/액추에이터 **1개** |
| 센서 전송 | `POST /telemetry` 로 여러 컴포넌트 **일괄 push** | `POST /api/v1/devices/{id}/state` 로 **1개씩** |
| 액추에이터 | 명령 큐 poll → `command_id`별 `ack` | desired-state 폴링 → 현재 state 보고 (큐 없음) |
| 값 형태 | 타입별 JSON dict (`{"temperature_c":24.5,"humidity_pct":55.0}`) | `{"value":24.5,"unit":"celsius"}` |
| 오류 형식 | `{"detail":"..."}` | `{"error":{"code":"...","message":"..."}}` |
| 생존 확인 | `POST /heartbeat` + 서버가 `is_online` 계산 | 없음 |
| 영상인식 | `qr_scanner`/`object_detector`를 **센서 컴포넌트**로 등록해 telemetry로 전송 (+ 선택적 `POST /api/vision/qr` 오프로드) | `POST /api/v1/vision/events` 로 감지 이벤트 전송 |

---

## 2. 가장 조심할 것 — 식별 단위가 다르다

이게 팀에서 시간을 가장 많이 잡아먹는 차이입니다.

```
iot-test-system            우리 팀 시스템
─────────────────          ─────────────────
device 1 (팀의 파이)         devices 테이블
 ├ component 1: led    →     ├ id='led_1'      kind='led'
 ├ component 2: dht11  →     ├ id='temp_1'     kind='dht11'
 └ component 3: servo  →     └ id='servo_1'    kind='servo'
```

파이 담당자는 **"우리 팀 = device_id 1개, 그 아래 부품 여러 개"** 로 연습했고,
우리 백엔드는 **"부품 하나 = devices 행 하나"** 입니다. 그래서:

- 파이 담당자가 연습한 `GET /components`(부품 목록 동기화)에 해당하는 것이 우리 쪽엔
  없습니다. 우리는 `init.sql` 시드로 목록을 고정하고, 그 `id` 목록을 파이 담당자에게
  직접 알려주는 방식입니다 (`docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 5장).
- 파이 담당자가 쓰던 정수 `component_id`(1, 2, 3)는 버리고, 우리 `devices.id`
  슬러그(`led_1`)를 쓰도록 처음부터 맞춰야 합니다.

> 굳이 `iot-test-system`과 같은 2단계 모델(device → components)로 바꿀 필요는 없습니다.
> 팀당 파이가 1대라면 2단계 모델은 불필요한 복잡도입니다 (`karpathy-principles.md`
> 단순함 우선). 다만 **어느 쪽을 쓸지 파이 담당자와 먼저 합의**하고, 그 결정을
> `03-진짜-백엔드-연동-확인-매뉴얼.md` 2단계 표의 "디바이스 식별 방식" 칸에 적어 둡니다.

---

## 3. 값이 여러 개인 부품 (필수 확인)

`antigravity-plugin`의 카탈로그 17종 중 **8종은 값이 2개 이상**입니다.

| 부품 | 필드 |
|---|---|
| 온습도센서(DHT11) | `temperature_c`, `humidity_pct` |
| LED | `on`, `brightness_pct` |
| 부저 | `on`, `freq_hz` |
| 네오픽셀 | `color`(r,g,b), `brightness_pct` |
| 불꽃센서 | `detected`, `intensity` |
| 숫자 키패드 | `key`, `event` |
| QR/바코드 | `detected`, `payload` |
| 영상 객체 인식 | `label`, `confidence`, `count` |

그리고 값이 1개여도 **`"on"`/`"off"` 문자열로는 표현할 수 없는 것**이 더 있습니다
(서보 `angle_deg`, DC모터 `speed_pct`, 초음파 `distance_cm`, 조도 `lux`, 압력 `value`).
17종 중 순수 on/off로 끝나는 것은 리드 스위치·푸시버튼·솔레노이드·릴레이 **4종뿐**이고,
나머지 **13종은 숫자나 문자열 값을 함께 실어야** 합니다.

DHT11 하나가 온도와 습도를 **동시에** 올리는데, `sensor_readings(value, unit)`처럼
스칼라 1개만 담는 스키마로는 한 번에 받을 수 없습니다. 둘 중 하나를 고릅니다.

- **(A) 부품 1개 = devices 행 1개, 값도 1개** — DHT11을 `temp_1`(°C)과 `humid_1`(%)
  두 행으로 나눕니다. 스키마가 단순한 대신 파이 쪽에서 2번 보고해야 합니다.
- **(B) 값 컬럼을 JSON으로** — `sensor_readings`에 `value_json`, `devices`에
  `desired_value`/`current_value`(JSON)를 두고 `{"temperature_c":24.5,"humidity_pct":55}`
  를 통째로 저장합니다. 파이 쪽 연습 코드와 모양이 같아 옮기기 쉽습니다.

**서보(각도)·LED 밝기·네오픽셀 색을 쓰는 팀은 (B)가 사실상 필수입니다** —
`desired_state VARCHAR(30)`에 `"on"`/`"off"`만 담아서는 각도 90도를 표현할 수 없습니다.
`db-rules.md`의 최소 스키마에 JSON 값 컬럼을 두는 이유입니다.

---

## 4. 백엔드 담당자가 파이 담당자에게 넘겨야 하는 것

`03-진짜-백엔드-연동-확인-매뉴얼.md` 2단계 표를 채우려면 아래가 전부 필요합니다.
**Swagger(`http://localhost:8000/docs`)에서 실제로 호출해 본 값**을 적습니다 —
문서 기본값을 그대로 옮겨 적지 않습니다.

- [ ] 백엔드 PC의 로컬 IP (`ipconfig`의 IPv4) → 파이의 `BACKEND_URL`
- [ ] `backend/.env`의 `DEVICE_API_KEY` 값
- [ ] 인증 헤더 이름이 `X-Device-Api-Key`가 맞는지 (파이 담당자는 `X-Device-Key`로
      연습했으므로 **반드시 명시**해야 합니다 — 안 그러면 401만 계속 납니다)
- [ ] `devices` 테이블의 `id` 목록 (`init.sql` 시드값 그대로)
- [ ] `GET /api/v1/devices/{id}/desired-state` 실제 응답 JSON
- [ ] `POST /api/v1/devices/{id}/state` 실제 요청 JSON (값이 여러 개인 부품 포함)
- [ ] 3장에서 (A)/(B) 중 무엇을 골랐는지
- [ ] 폴링 주기 — 우리 킷 기준 **2~5초** (파이 담당자는 1~2초로 연습했으므로 합의 필요)
- [ ] Windows 방화벽 8000 포트 인바운드 허용 여부

> 백엔드가 아직 엔드포인트를 안 만들었다면 여기서 막힙니다. 매뉴얼 2-2의
> backend-agent 프롬프트(조회/제어 엔드포인트 생성)를 먼저 끝내세요.

---

## 5. 연동 확인 순서

1. 백엔드 학생: 위 4장 항목을 전부 채운다
2. 파이 학생: `03-진짜-백엔드-연동-확인-매뉴얼.md` 3단계의 `test_backend_contract.py`를
   그 값으로 고쳐 실행 → **200번대가 나올 때까지 여기서 멈춘다**
   (401 = 헤더 이름/키, 404 = 경로/device_id, 422 = 본문 모양)
3. 통과하면 4단계에서 `pi/main.py`를 생성한다.
   이때 프롬프트에 **2단계 표의 실제 값을 반드시 포함**시킨다
4. `DEVICE_MODE=mock` 상태로 대시보드 ↔ 파이 양방향을 먼저 확인
   (`docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 10장 체크리스트)
5. 그 다음에야 배선 — 교사 입회 하에

---

## 6. 알아두면 좋은 차이

- `GET /api/devices/{id}/components`는 대시보드도 쓰는 조회용이라 `X-Device-Key` 없이도
  200을 반환합니다. 파이 클라이언트가 다른 호출과 똑같이 헤더를 붙여도 문제없습니다.
- `pi/main.py`는 `backend/iot/base.py`를 **import할 수 없습니다**(백엔드와 다른 기기).
  같은 4개 메서드 **이름만** 맞춘 독립 클래스로 만듭니다 —
  `docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 2장이 기준입니다.
  `03-진짜-백엔드-연동-확인-매뉴얼.md` 4단계 프롬프트도 이 내용으로 정정되어 있습니다.
- 폴링 주기는 두 시스템이 다릅니다 — 임시 테스트 시스템 1~2초, 우리 팀 백엔드 2~5초.
  파이 담당자가 연습할 때 쓰던 값을 그대로 가져오지 않도록 4장 체크리스트에서 합의합니다.

## 참고
- `iot-test-system/docs/03-진짜-백엔드-연동-확인-매뉴얼.md` — 전환 절차 원본(6단계)
- `iot-test-system/docs/부록B-REST-API-스펙.md` — 테스트 시스템 REST 스펙 원본
- `iot-test-system/antigravity-plugin/rules/02-catalog-contract.md` — 부품 17종 필드명
- `docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` — 우리 팀 계약(원본)
- `.agents/rules/api-rules.md`, `.agents/rules/db-rules.md`
