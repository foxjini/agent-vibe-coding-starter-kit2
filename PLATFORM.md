# `platform` 브랜치 — IoT 개발 플랫폼 키트 (4팀 공통 기준선)

> **이 브랜치가 무엇인지 한 줄로**: wakeup · classroom · study · subway **4개 팀이 공통으로 쓰는
> 백엔드 · DB · vision 코드**입니다. 팀별 작업은 이 브랜치에서 분기한 팀 브랜치에서 합니다.

| 브랜치 | 정체 | 누가 고치나 |
|---|---|---|
| **`platform`** | **공통 키트 (이 브랜치)** | 공동 관리 — 4팀에 영향이 가므로 합의 후 변경 |
| `wakeup` / `classroom` / `study` / `subway` | 팀 작업 브랜치 | 각 팀이 `frontend/` + `pi/slot_map.py`만 |
| `main` | 원본 스타터 킷 2.0 (빈 템플릿) | 보존용 |

---

## 1. 이 키트의 약속

팀이 2차 개발에서 **센서·액추에이터의 종류나 개수를 바꿔도
`backend/` · `backend/db/` · `vision/`을 한 줄도 고치지 않습니다.**

```
[고정층] backend · db · vision     → 4팀 코드 100% 동일. 슬롯 20개만 안다.
            sensor_01 … sensor_10        (센서 최대 10개)
            actuator_01 … actuator_10    (액추에이터 최대 10개)

[매핑층] DB 메타데이터 (코드 아님)  → "actuator_01 = 알람 부저, 주파수 제어"
            pi가 부팅 시 등록하거나 대시보드 설정 화면에서 지정

[팀층]   frontend + pi              → 팀이 자유롭게 수정
```

상세 규약은 **[`docs/부록F-IoT-개발-플랫폼-키트-규약.md`](docs/부록F-IoT-개발-플랫폼-키트-규약.md)** 를 봅니다.
슬롯 ID·DB 스키마·API 형식은 **한 번 확정하면 바꾸지 않습니다**(바꾸면 4팀이 모두 영향).

### 팀이 하는 일 / 하지 않는 일

| 상황 | 고치는 곳 | 고치지 않는 곳 |
|---|---|---|
| 센서·액추에이터 추가/제거 | `pi/slot_map.py` 한 줄 | backend, db, vision |
| 부품 종류 변경 (부저→서보) | `pi/slot_map.py`의 `driver` | backend, db, vision |
| 화면 디자인·UX | `frontend/` | backend, db, vision |
| 시나리오·게임 로직 | `frontend/` (시나리오 SDK) | backend, db, vision |
| 단순 자동화 (임계값·스케줄) | 대시보드 규칙 편집 (데이터) | 코드 전부 |

---

## 2. 현재 상태 (P0·P1 완료)

### 이미 들어 있는 것 — wakeup 브랜치에서 검증된 기반

| 항목 | 상태 |
|---|---|
| DB 계층 (커넥션 풀, JSON 컬럼 디코드, DB 장애 시 안전 폴백) | ✅ 검증됨 |
| 에러 응답 규격 통일 `{"error":{code,message}}` | ✅ |
| desired/current 상태 계약 (하드웨어 반영 여부 구분) | ✅ |
| 시간대 인식 스케줄러 + DB 영속화 | ✅ |
| 자가 점검 스크립트 `backend/smoke_test.py` (36항목) | ✅ |
| 문서 부록A(파이 연동 계약) · 부록F(키트 규약) | ✅ |

### P1에서 추가된 백엔드 코어 (기존 동작을 깨지 않는 **덧붙이기**)

| 항목 | 파일 | 검증 |
|---|---|---|
| 슬롯 20개 레지스트리 + 자동 컬럼 마이그레이션 | `db/database.py`, `iot/device_catalog.py` | ✅ 실제 DB 이행 |
| 슬롯 목록·메타데이터 수정 API | `routers/slots.py` (`/api/slots`) | ✅ |
| pi 배치 통신 (폴링 1회 / 보고 1회 / 부팅 등록) | `services/slot_service.py` | ✅ |
| 자동화 규칙 엔진 (트리거 3종 · 액션 2종) | `services/rule_engine.py` | ✅ |
| 적합성 검사 스크립트 | `backend/conformance_test.py` | ✅ 38건 (DB 끈 상태 32건) |

검증 결과: **적합성 38/38, wakeup 회귀 `smoke_test.py` 36/36 · `test_mission.py` 18/18**
— DB를 켠 상태와 끈 상태 양쪽 모두 통과. `GET /api/devices`는 여전히 wakeup의 3개만
돌려주므로 1차 완성본 대시보드는 그대로 동작합니다.

### P2에서 추가된 pi 프레임워크 (팀은 `slot_map.py` 한 파일만 고칩니다)

| 항목 | 파일 | 검증 |
|---|---|---|
| 드라이버 10종 (`apply`/`read` 2개 메서드 계약) | `pi/drivers/` | ✅ |
| GPIO 없는 PC에서 부품 자동 흉내내기 | `pi/drivers/gpio.py` | ✅ |
| 팀 하드웨어 배치표 | `pi/slot_map.py` | ✅ |
| 배치표 오타를 실행 전에 잡는 검사기 | `pi/slot_config.py` | ✅ 5종 오류 |
| 배치 통신 (등록·폴링·보고) | `pi/backend_client.py` | ✅ |
| 공통 데몬 루프 (`--check` 모드 포함) | `pi/daemon.py` | ✅ |
| 자가 점검 (GPIO·백엔드 없이) | `pi/test_slot_daemon.py` | ✅ 28건 |

검증 결과: **자가 점검 28/28**, 그리고 실제 데몬 프로세스를 실제 백엔드에 붙인
**종단 검증 18/18** — 배치표에 한 줄을 추가하면 대시보드에 부품이 나타나고,
한 줄을 지우면 사라지며, 규칙이 pi의 부품을 직접 제어하는 것까지 확인했습니다.
`pi/main.py`(wakeup 1차 데몬)는 P3.5까지 그대로 둡니다 — 둘을 동시에 실행하면
같은 GPIO 핀을 다투므로 `main.py` 맨 위에 안내를 적어 두었습니다.

### 아직 남아 있는 wakeup 고유 코드 — **P3.5에서 한꺼번에 교체**

공통 키트에 들어가면 안 되는 wakeup 전용 기능입니다. 프론트엔드 키트(P3)가 대체물을
갖추기 전에 지우면 1차 완성본이 멈추므로, **P3까지 끝낸 뒤 한 번에** 교체합니다.

| 파일 | 현재 | P3.5 계획 |
|---|---|---|
| `backend/iot/device_catalog.py` | 슬롯 20개 + 레거시 3개 공존 | 레거시 3개 제거 |
| `backend/db/database.py` 시드 | 슬롯 20개 + 레거시 3개 시드 | 레거시 시드 제거 |
| `backend/routers/alarm.py` | 알람 전용 스케줄러 | 규칙 엔진의 `schedule` 트리거로 대체 |
| `backend/services/trigger_service.py` | 가위바위보 미션 엔진 | **키트에서 제거** → 프론트 시나리오 SDK로 이전 |
| `pi/main.py` | buzzer_1 단일 폴링 | `slot_map.py` + 드라이버 + 배치 폴링 (P2) |
| `vision/main.py` | 감지 대상 하드코딩 | 서버 설정(`/api/v1/vision/config`) 기반 (P4) |
| `frontend/` | 부저 1개 전제 | 슬롯 자동 렌더링 + 시나리오 SDK (P3) |

> ⚠️ **지금 이 브랜치를 팀에 배포하면 안 됩니다.** P2~P4가 끝나야 "백엔드 무수정" 약속이 성립합니다.

---

## 3. 로드맵

| 단계 | 내용 | 상태 |
|---|---|---|
| **P0** | 슬롯 규약 · DB 스키마 · API 계약 확정 (부록F) | ✅ 완료 (실제 DB로 14항목 검증) |
| **P1** | 백엔드 코어: 슬롯 레지스트리, 배치 API, register/PATCH, 규칙 엔진, 적합성 테스트 | ✅ 완료 (적합성 38건 + 회귀 54건) |
| **P2** | pi 프레임워크: `slot_map.py` + 드라이버 10종 + 흉내내기 + 공통 데몬 | ✅ 완료 (자가 점검 28건 + 종단 18건) |
| **P3** | 프론트 키트: SlotGrid · 카드 · HardwareSetup · RuleEditor · 시나리오 SDK | ⬜ |
| **P4** | vision 일반화: 설정 기반 감지 대상 | ⬜ |
| **P3.5** | wakeup 고유 코드 일괄 교체 (알람·미션·레거시 디바이스 정리) | ⬜ |
| **P4** 이후 순서 주의 | P3까지 끝난 뒤 P3.5를 진행합니다 — 대체물이 없는 상태로 먼저 지우면 1차 완성본이 멈춥니다 | — |
| **P5** | 4팀 배포: 팀별 `slot_map` 예시, 매뉴얼 갱신, wakeup 마이그레이션 검증 | ⬜ |

---

## 4. 팀 브랜치 운영 방법 (P5 이후)

```bash
# 팀 작업 시작 — platform에서 새로 분기
git fetch origin
git checkout -b wakeup-v2 origin/platform

# 1) 하드웨어 매핑 (pi 담당)
#    pi/slot_map.py 에 우리 팀 부품을 슬롯에 배치
# 2) 화면·시나리오 (프론트 담당)
#    frontend/ 에서 디자인과 시나리오 작성

# 키트가 업데이트되면 받아오기
git merge origin/platform     # 충돌은 frontend/ pi/ 에서만 발생
```

**기존 팀 브랜치는 이력 보존용으로 남깁니다.** 이식 대상이 `frontend/` + `pi/slot_map.py`로
한정되도록 설계했으므로 팀당 옮길 작업량이 작습니다.

---

## 5. 변경 규칙 (이 브랜치를 고칠 때)

1. **슬롯 ID·DB 스키마·API 응답 형식은 바꾸지 않습니다.** 바꿔야 한다면 4팀 합의 후 부록F를 먼저 수정합니다.
2. 팀 고유 디바이스 이름(`buzzer_1`, `servo_door` 등)을 `backend/`·`vision/`에 넣지 않습니다.
3. 변경 후 반드시 통과해야 하는 검사:
   ```bash
   cd backend && python smoke_test.py          # 기능 회귀 (36항목)
   cd backend && python conformance_test.py    # 키트 적합성 (P1 산출물)
   cd frontend && npm run lint && npm run build
   ```
4. 액추에이터의 `current_state`는 **하드웨어 보고로만** 바뀝니다. 백엔드가 직접 쓰지 않습니다.
