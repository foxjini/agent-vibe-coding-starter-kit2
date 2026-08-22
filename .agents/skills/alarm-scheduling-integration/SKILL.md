---
name: alarm-scheduling-integration
description: >-
  시간 기반 알람 트리거, 다단계 기상 미션 상태(alarms/wakeup_sessions), 팝업 미확인 시
  재알람(경보성 디바이스 원칙) 백그라운드 스케줄링 루프를 구현할 때 사용하는 스킬.
---

# alarm-scheduling-integration

> "기상 유도 알람 시스템"처럼 영상인식 감지가 아니라 **시각 기반**으로 액추에이터를
> 제어해야 할 때 이 스킬을 참고한다. `iot-endpoint-generator`(디바이스 CRUD 4단계)와는
> 별개로, 시간 흐름에 따른 상태 전이(알람 → 미션 → 확인 → 재알람)를 다룬다.

## DB 스키마 확장
`db-rules.md`의 최소 4테이블(`devices`/`sensor_readings`/`control_log`/
`vision_events`)은 그대로 두고 아래를 추가한다.

```sql
CREATE TABLE IF NOT EXISTS alarms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  alarm_time TIME NOT NULL,
  mission_type VARCHAR(20) NOT NULL,   -- 'rps' | 'object' | 'pattern'
  target_object VARCHAR(50) NULL,      -- mission_type='object'일 때만 사용
  enabled BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

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

`control_log`는 그대로 "알람 액추에이터 on/off 이력"(누가/언제 켰는지) 감사 로그로
쓰고, `wakeup_sessions`는 그 위의 "미션·확인 진행 상태"를 관리하는 역할로 나눈다.

## 백그라운드 스케줄링 루프
새 스케줄러 라이브러리(APScheduler 등)를 들이지 않고, 킷 전체가 쓰는 "폴링" 철학을
백엔드 내부에도 그대로 적용한다 (`karpathy-principles.md`의 단순함 우선).

```python
import asyncio
from datetime import datetime

POPUP_CONFIRM_TIMEOUT_SEC = 60  # 팀이 정해서 상수로 관리 ([미정] 값)

async def alarm_scheduler_loop():
    while True:
        now = datetime.now()
        # 1) 설정 시각이 된 활성 알람(alarms.enabled=TRUE, 오늘 아직 세션 없음)
        #    → wakeup_sessions 행 생성 + 알람 desired-state ON
        # 2) status='awaiting_confirmation'인 세션 중
        #    popup_shown_at + POPUP_CONFIRM_TIMEOUT_SEC 가 지났는데
        #    popup_confirmed_at이 NULL이면
        #    → 알람 desired-state 다시 ON, status='resnoozed'
        await asyncio.sleep(1)

@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(alarm_scheduler_loop())
```

미션 완료 → 팝업 표시까지의 대기 시간(PRD상 약 1~2분, `[미정]`)도 같은 방식으로
상수화해 나중에 쉽게 값을 바꿀 수 있게 한다.

## 경보성 디바이스 원칙 재확인
`db-rules.md`의 경보성 디바이스 원칙과 동일하게, 이 루프는 알람을 스스로 끄지 않는다.
사람이 대시보드/패드에서 직접 확인해야만 desired-state가 OFF로 바뀐다
(`dashboard-ui-design` 스킬의 `AlertCard` 패턴을 그대로 재사용할 수 있다).

## 현재 미션 조회 엔드포인트
vision 클라이언트가 폴링할 수 있도록 디바이스 인증 엔드포인트를 제공한다
(`vision-recognition-integration` 스킬의 "미션별 감지 대상 전환" 참고).

**`GET /api/v1/vision/current-mission`** (헤더: `X-Device-Api-Key`)

진행 중인 `wakeup_sessions` 행을 참고해 아래처럼 반환한다.
```json
{
  "data": {
    "mission_type": "object",
    "active": true,
    "target_object": "cup"
  }
}
```
진행 중인 미션이 없을 때(패턴 순서 기억 미션 — 영상인식 불필요, 또는 알람 대기 중)는
`{"mission_type": null, "active": false, "target_object": null}`을 반환한다.

## vision_events 컬럼 확장
```sql
ALTER TABLE vision_events
  ADD COLUMN mission_type VARCHAR(20) NULL,
  ADD COLUMN label VARCHAR(50) NULL;
```

## 예시 프롬프트
```
너는 이 프로젝트의 backend-agent다. .agents/rules/db-rules.md와
.agents/skills/alarm-scheduling-integration/SKILL.md를 따른다.

alarms/wakeup_sessions 테이블, 알람 스케줄링 백그라운드 태스크, GET
/api/v1/vision/current-mission 엔드포인트를 만들어줘.
```
