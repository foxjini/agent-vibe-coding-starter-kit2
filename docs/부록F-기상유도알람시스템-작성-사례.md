# 기상 유도 알람 시스템 — AGENTS.md 작성 사례

> 📂 **부록F / 참고용 작성 사례 — 우리 팀 문서가 아닙니다** · 전체 목록 [docs/README.md](README.md)

> ⚠️ **먼저 확인**: 이 문서는 **「기상 유도 알람 시스템」이라는 특정 한 팀의 결과물**입니다.
> 우리 팀 주제가 기상 알람이 아니라면 **1부의 `AGENTS.md` 초안을 그대로 복사하지 마세요.**
> 우리 팀 `AGENTS.md`는 [부록B](부록B-ChatGPT-Claude로-AGENTS-작성하기.md)의 절차로
> 직접 만듭니다. 이 문서는 **"완성된 AGENTS.md와 보충 설계가 어느 정도 수준이면 되는지"**
> 를 눈으로 보는 견본, 그리고 **기본 스킬이 안 다루는 요구사항(다단계 상태, 시간 기반
> 트리거, 다중 인식 모드)을 만났을 때 어떻게 문서로 풀어내는지** 참고하는 용도입니다.

> **이 문서는 무엇인가요?**
> 「기상 유도 알람 시스템」팀의 PRD를 스타터 킷 구조와 대조 검토한 결과를 바탕으로 만든
> 문서입니다. 두 부분으로 구성됩니다.
> - **1부**: 이 팀 전용 `AGENTS.md` 초안 — **기상 알람 팀이라면** 그대로 복사해 프로젝트
>   루트 `AGENTS.md`에 붙여넣고 `[미정]` 항목을 직접 채웁니다. 다른 팀은 형식만 참고합니다.
> - **2부**: 스타터 킷의 기본 스킬(`vision-recognition-integration`, `db-rules.md`의 최소
>   스키마 등)이 커버하지 않는, 이 팀만 추가로 설계해야 하는 부분 — vision_events 스키마
>   확장, DB 테이블 추가, 알람 스케줄링 로직.
>
> PRD 작성 원칙과 동일하게, **PRD에 없는 내용은 임의로 만들어 넣지 않고 `[미정]`으로
> 남겨두었습니다.** 킷 적용 관점에서 권장하는 내용은 `[권장]`으로 표시합니다.

---

# 1부. AGENTS.md 초안 (팀 전용)

아래 블록 전체를 프로젝트 루트의 `AGENTS.md` 파일에 그대로 붙여넣고, `[미정]`만 팀이
채웁니다. `.agents/`, `docs/`는 이미 완성되어 있으므로 손대지 않습니다.

````markdown
# AGENTS.md — [프로젝트폴더명]

## 프로젝트 개요
- 팀 주제: `기상 유도 알람 시스템`
- 한 줄 목표: `사용자가 알람을 끈 뒤 다시 잠드는 문제를 줄이기 위해 기상 미션을 수행하게
  하고, 미션 후 일정 시간이 지나면 기상 확인 팝업으로 2차 수면 여부를 확인한다`

## 기술 스택 (고정 — 임의로 바꾸지 않는다)
- 백엔드: FastAPI (Python)
- DB: MySQL (로컬 개발) → Supabase(PostgreSQL) (클라우드 배포 시 마이그레이션)
- 프론트엔드: Next.js(TypeScript)
- 하드웨어 제어: Python venv Mock(개발 전반부) → 라즈베리파이 5 + gpiozero(개발 후반부)
- 영상인식: YOLOv8(사물) + mediapipe(손동작) — Windows PC + 웹캠 `[권장 — 2부 2-1 참고]`
- 배포: Render(백엔드) / Vercel(프론트)
- 버전관리: GitHub / 문서·협업: Notion

## 핵심 데이터 흐름

> 기본 스타터 킷 예시("영상인식 감지 → 즉시 액추에이터 제어")와 달리, 이 프로젝트는
> **시간 기반 트리거 + 다단계 미션 상태**가 함께 있는 흐름입니다. 상세 설계는 2부를
> 참고합니다.

1. 사용자가 대시보드(또는 패드 화면)에서 알람 시각과 기상 미션 종류를 설정한다
2. 백엔드의 알람 스케줄링 루프(2-4절)가 주기적으로 현재 시각을 확인하다가, 설정 시각이
   되면 알람 액추에이터의 desired-state를 ON으로 바꾼다
3. 사용자가 기상 미션(가위바위보 / 사물인식 / 패턴 순서 기억)을 수행한다. 영상 기반
   미션은 vision 클라이언트가 "지금 어떤 미션인지"를 백엔드에 폴링해 확인하고(2-2절)
   해당 인식만 수행해 결과를 이벤트로 전송한다
4. 미션을 통과하면 백엔드가 알람 desired-state를 OFF로 바꾸고, 완료 시각을 기록한 뒤
   내부 타이머를 시작한다
5. 설정된 대기 시간(약 1~2분, `[미정]`)이 지나면 프론트엔드(패드 화면)에 기상 확인
   팝업을 WebSocket으로 띄운다
6. 팝업을 일정 시간 안에 확인하지 않으면 백엔드가 이를 감지해 알람 desired-state를
   다시 ON으로 바꾼다(2차 알람). **경보성 디바이스 원칙(`db-rules.md`)과 동일하게, 사람이
   대시보드/패드에서 직접 확인하기 전까지 자동으로 꺼지지 않는다**
7. 하드웨어(Mock 또는 라즈베리파이)가 desired-state를 폴링해 실제로 알람을 울리거나 끈다

## AI 사용 원칙
- 모든 작업은 `.agents/rules/karpathy-principles.md`의 4원칙(생각 먼저·단순함 우선·
  외과적 변경·목표 기반 실행)을 기본으로 따른다
- AI가 생성한 코드는 반드시 학생이 직접 실행하고 결과를 눈으로 확인한다
- "AI가 알아서 잘했다"는 요약만 믿고 다음 단계로 넘어가지 않는다
- 시크릿(API 키, 비밀번호)은 절대 채팅/프롬프트에 직접 입력하지 않는다 (security-rules.md 참고)
- 이 킷의 `.agents/rules`, `.agents/skills`는 이미 완성되어 있다 — **다시 만들어달라고
  요청하지 않는다.** 새 기능을 요청할 때 "역할 지정 + 관련 rules/skills 참고" 문구만
  붙이면 AI가 알아서 참고한다 (토큰 절약)
- 이 프로젝트는 기본 스킬 범위를 넘는 부분(알람 스케줄링, 손동작 인식, 다단계 미션
  상태)이 있다 — 해당 작업을 요청할 때는 **이 문서 2부의 절 번호를 함께 언급**한다
  (예: "2-4절을 참고해서 알람 스케줄링 루프를 만들어줘")

## 폴더 구조
```
[프로젝트폴더명]/
├── AGENTS.md
├── .agents/            (하네스: rules/skills/workflows/hooks/agents — 이미 완성됨)
├── docs/               (설치 매뉴얼·로드맵·인터페이스 가이드 — 이미 완성됨)
├── backend/            (FastAPI, .env.example 포함)
├── frontend/           (Next.js, .env.example 포함)
├── vision/             (영상인식 클라이언트, Windows PC에서 실행, .env.example 포함)
└── pi/                 (라즈베리파이에서 실행되는 하드웨어 데몬, 3주차부터, .env.example 포함)
```

## 팀 정보

| 항목 | 값 |
|---|---|
| 팀 주제 | 기상 유도 알람 시스템 |
| 액추에이터(제어 대상) 목록 | 알람 출력 장치 (부저/스피커 등 구체 종류 `[미정]` — PRD A-01) |
| 센서(모니터링 대상) 목록 | 카메라(손동작·사물 인식용), 패드 화면/터치 입력(하드웨어 여부 `[미정]`) |
| 영상인식 감지 대상 | ① 가위/바위/보 손동작(mediapipe Hands) — 미션 F-02용<br>② 미션 지정 사물(YOLOv8n, COCO 클래스 내 선정 `[권장]`) — 미션 F-03용<br>*(단일 항목이 아니라 미션별로 전환되는 다중 모드입니다 — 2-2절 참고)* |
| 트리거 규칙 | 시간 기반 + 상태 기반 조합 — "핵심 데이터 흐름" 1~7단계 및 2-4절 알람 스케줄링 참고 |
| 팀원 역할 분담 | `[미정]` |
````

---

# 2부. 이 팀에 필요한 보충 설계

> 아래 내용은 스타터 킷의 기본 스킬(`iot-endpoint-generator`, `db-integration`,
> `vision-recognition-integration`)이 다루는 "디바이스 하나 추가"나 "단순 감지→트리거"
> 범위를 넘는 것들입니다. 해당 작업을 backend-agent/db-agent/vision-agent에게 요청할 때
> 이 절 번호를 프롬프트에 함께 적어주면 AI가 맥락을 정확히 참고합니다.

## 2-1. 영상인식: 학습 없이 구현하는 방법 `[권장]`

PRD상 가위바위보·사물인식 모두 "학습 필요"로 되어 있지만, 커스텀 모델 학습은 고등학교
프로젝트 일정(3주차까지 하드웨어 전환)에 비해 부담이 큽니다. 아래처럼 **사전학습된
모델만으로** 구현하는 것을 권장합니다.

| 미션 | 권장 방법 | 이유 |
|---|---|---|
| 가위바위보 손동작 | `mediapipe.solutions.hands`로 손 랜드마크(21개 점) 추출 → 펴진 손가락 개수를 규칙 기반으로 세어 가위(2)/바위(0)/보(5) 판정 | mediapipe Hands는 사전학습된 모델이라 별도 데이터 수집·학습이 필요 없음. `vision-recognition-integration` 스킬에 이미 mediapipe 예시(얼굴 감지용)가 있어 같은 라이브러리를 다른 solution으로 확장하는 것뿐임 |
| 사물인식 | 미션에서 요청할 사물을 **COCO 80종 안에서** 선정(예: 컵, 책, 가위, 시계, 핸드폰, 칫솔, 숟가락 등) → 사전 탑재된 `vision/yolov8n.pt`로 바로 인식 | 학내망 다운로드/학습 없이 3주차 일정 안에 완료 가능 |

`vision/requirements.txt`에 `mediapipe`가 빠져 있으므로 추가해야 합니다.

```
mediapipe
```
> ⚠️ mediapipe는 최신 파이썬(3.13+)용 휠 제공이 늦는 편입니다. 설치가 실패하면
> `python --version`을 확인하고, 이 팀은 **파이썬 3.11 또는 3.12**로 `vision/venv`를
> 다시 만드는 것이 가장 확실합니다 (`vision/requirements.txt`의 3.13 미만 분기와도
> 맞습니다).

> 임의의 사물(COCO에 없는 것)을 꼭 쓰고 싶다면 별도 데이터 수집·학습이 필요하다는 점을
> 팀·지도교사가 먼저 확인하고 일정에 반영해야 합니다.

## 2-2. vision_events 페이로드 확장 및 "현재 미션" 폴링

### 문제
기본 스킬의 이벤트 형식은 다음처럼 고정되어 있습니다(`vision-recognition-integration/SKILL.md`).

```json
{"event_type": "person_detected", "detected": true, "count": 1, "confidence": 0.9}
```

이 형식에는 "가위/바위/보 중 무엇이 인식됐는지", "어떤 미션에서 온 이벤트인지"를 담을
필드가 없고, vision 클라이언트도 "지금 어떤 미션이 진행 중인지" 알 방법이 없습니다
(기본 설계는 감지 대상이 한 가지로 고정된 경우를 가정합니다).

### 확장된 이벤트 형식 `[권장]`

```json
{
  "event_type": "mission_result",
  "mission_type": "rps",
  "label": "scissors",
  "detected": true,
  "count": 1,
  "confidence": 0.92
}
```

- `mission_type`: `"rps"`(가위바위보) | `"object"`(사물인식)
- `label`: 인식된 구체적 결과 — 가위바위보는 `"rock"/"paper"/"scissors"`, 사물인식은
  인식된 사물명(예: `"cup"`)

### "현재 미션" 조회 엔드포인트 (신규, 디바이스 인증)

라즈베리파이의 desired-state 폴링과 동일한 패턴입니다
(`docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` 3장 참고). vision 클라이언트가
몇 초마다 아래 엔드포인트를 호출해 지금 무엇을 인식해야 하는지 확인하고, 해당하는
인식기만 실행합니다.

**`GET /api/v1/vision/current-mission`** (헤더: `X-Device-Api-Key`)

```json
{
  "data": {
    "mission_type": "object",
    "active": true,
    "target_object": "cup"
  }
}
```

- 가위바위보 미션 중: `{"mission_type": "rps", "active": true, "target_object": null}`
- 진행 중인 미션이 없을 때(예: 패턴 순서 기억 미션 — 영상인식 불필요, 또는 알람 대기 중):
  `{"mission_type": null, "active": false, "target_object": null}`

vision 클라이언트는 `active: false`일 때는 인식을 멈추고 대기만 합니다(불필요한 카메라
연산·오탐 방지).

## 2-3. DB 테이블 확장

`db-rules.md`의 최소 4테이블(`devices`, `sensor_readings`, `control_log`,
`vision_events`)은 최소 기준이므로 그대로 두고, 아래 2개 테이블과 1개 컬럼 확장을
추가하는 것을 권장합니다.

### `vision_events` 컬럼 확장

```sql
ALTER TABLE vision_events
  ADD COLUMN mission_type VARCHAR(20) NULL,
  ADD COLUMN label VARCHAR(50) NULL;
```

### `alarms` (신규) — 알람 설정

```sql
CREATE TABLE IF NOT EXISTS alarms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  alarm_time TIME NOT NULL,
  mission_type VARCHAR(20) NOT NULL,   -- 'rps' | 'object' | 'pattern'
  target_object VARCHAR(50) NULL,      -- mission_type='object'일 때만 사용
  enabled BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `wakeup_sessions` (신규) — 알람 1회 발생부터 종료까지의 전체 흐름 추적

```sql
CREATE TABLE IF NOT EXISTS wakeup_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  alarm_id INT NOT NULL,
  status VARCHAR(30) NOT NULL,         -- ringing → mission_in_progress → mission_done
                                        -- → awaiting_confirmation → confirmed | resnoozed
  mission_attempt_count INT DEFAULT 0,
  alarm_started_at DATETIME NOT NULL,
  mission_completed_at DATETIME NULL,
  popup_shown_at DATETIME NULL,
  popup_confirmed_at DATETIME NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (alarm_id) REFERENCES alarms(id)
);
```

> 기존 `control_log`는 그대로 "알람 액추에이터 on/off 이력"(누가/언제 켰는지) 감사
> 로그로 사용하고, `wakeup_sessions`는 그 위에 있는 "미션·확인 진행 상태"를 관리하는
> 역할로 나누면 역할이 겹치지 않습니다.

## 2-4. 알람 스케줄링 (백엔드 폴링 루프)

시간 기반 트리거는 어떤 기본 스킬에도 없는 이 프로젝트만의 로직입니다. 새 라이브러리
(APScheduler 등)를 들이기보다, 킷 전체에서 이미 쓰고 있는 "폴링" 철학을 그대로 백엔드
내부에 적용하는 것을 권장합니다(단순함 우선).

```python
# backend/main.py (또는 별도 모듈)에 추가하는 형태의 예시
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

POPUP_CONFIRM_TIMEOUT_SEC = 60   # [미정] — 팝업 확인 대기 시간, 팀이 정해서 상수로 관리
SCHEDULER_TICK_SEC = 5           # 알람은 분 단위이므로 1초마다 DB를 두드릴 필요가 없다

async def alarm_scheduler_loop() -> None:
    while True:
        now = datetime.now()

        # 1) 설정 시각이 된 활성 알람 → wakeup_session 생성 + 알람 desired-state ON
        #    (alarms.enabled=TRUE, alarm_time == now의 시:분, 오늘 아직 세션 없음)

        # 2) status='awaiting_confirmation'인 세션 중
        #    popup_shown_at + POPUP_CONFIRM_TIMEOUT_SEC 가 지났는데
        #    popup_confirmed_at이 NULL이면 → 알람 desired-state 다시 ON, status='resnoozed'

        await asyncio.sleep(SCHEDULER_TICK_SEC)


# FastAPI의 @app.on_event("startup")은 deprecated다 — lifespan을 쓴다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(alarm_scheduler_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)   # 기존 FastAPI(...) 호출에 lifespan 인자만 추가한다
```

- 미션 완료 → 팝업 표시까지의 대기 시간(PRD상 약 1~2분, `[미정]`)도 같은 방식으로 상수화해
  나중에 쉽게 값을 바꿀 수 있게 합니다.
- 알람 desired-state를 다시 켜는 부분은 **db-rules.md의 경보성 디바이스 원칙**과 같습니다
  — 이 루프가 스스로 다시 끄지 않고, 반드시 사람이 대시보드/패드에서 확인해야 꺼지도록
  구현합니다.

## 2-5. AI 프롬프트 예시

각 담당자가 아래 프롬프트를 참고해 진행할 수 있습니다. 실제 프롬프트에 이 문서의 절
번호를 함께 적으면 토큰을 아끼면서도 정확히 참고시킬 수 있습니다.

**DB 확장 (db-agent)**
```
너는 이 프로젝트의 db-agent다. .agents/rules/db-rules.md와
.agents/skills/db-integration/SKILL.md를 따른다.

기존 devices/sensor_readings/control_log/vision_events 4테이블은 그대로 두고,
docs/부록F-기상유도알람시스템-작성-사례.md의 2-3절 스키마대로 alarms와
wakeup_sessions 테이블을 추가하고, vision_events에 mission_type/label 컬럼을 추가해줘.
```

**알람 스케줄링 (backend-agent)**
```
너는 이 프로젝트의 backend-agent다. .agents/rules/api-rules.md와
.agents/rules/db-rules.md를 따른다.

docs/부록F-기상유도알람시스템-작성-사례.md의 2-4절을 참고해서 FastAPI lifespan에서
시작되는 알람 스케줄링 백그라운드 태스크(5초 주기)를 추가해줘. 경보성 디바이스 원칙에 따라
사람이 직접 확인하기 전까지는 알람이 자동으로 꺼지면 안 돼.

같은 문서 2-2절대로 GET /api/v1/vision/current-mission 엔드포인트(디바이스 인증)도
추가해줘.
```

**영상인식 확장 (vision-agent)**
```
너는 이 프로젝트의 vision-agent다. .agents/rules/vision-rules.md와
.agents/skills/vision-recognition-integration/SKILL.md를 따른다.

docs/부록F-기상유도알람시스템-작성-사례.md의 2-1, 2-2절을 참고해서
vision/main.py가 mediapipe Hands로 가위바위보를, yolov8n.pt로 지정 사물을 인식하도록
만들어줘. 몇 초마다 백엔드의 현재 미션 엔드포인트를 폴링해서 활성화된 미션에 해당하는
인식만 수행하고, 결과를 mission_type/label을 포함한 이벤트로 전송해줘.
```

---

# 3부. 참고

- 이 문서는 팀의 「프로젝트 개발 계획서」/PRD(기상 유도 알람 시스템) 검토를 바탕으로
  작성되었습니다. PRD에 없는 내용은 임의로 만들지 않고 `[미정]`으로 남겼습니다 —
  실제 값은 팀이 채웁니다.
- `docs/부록C-백엔드-라즈베리파이5-연동-인터페이스-가이드.md` — desired-state 폴링 계약(2-2절의
  "현재 미션" 폴링이 동일한 패턴을 따릅니다)
- `.agents/rules/vision-rules.md`, `.agents/skills/vision-recognition-integration/SKILL.md`
- `.agents/rules/db-rules.md`, `.agents/skills/db-integration/SKILL.md`
- `.agents/rules/api-rules.md`
- `docs/01-학생용-설치-및-사용-매뉴얼.md`
