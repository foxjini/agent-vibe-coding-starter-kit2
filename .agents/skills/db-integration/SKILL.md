---
name: db-integration
description: >-
  MySQL/MariaDB 로컬 개발 환경 연결 설정, DB 헬퍼 함수 패턴, init.sql 스키마 및 디바이스 시드 데이터를 생성하고 연동할 때 사용하는 스킬.
---

# db-integration (MySQL, 로컬 개발)

## 연결 설정
- XAMPP로 MariaDB를 실행하고 phpMyAdmin에서 DB를 생성한다
- `backend/.env`: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (`.env.example` 참고)
- `pymysql` 사용을 권장한다

## 기본 헬퍼 함수 패턴
```python
def log_sensor_reading(device_id: str, value: float, unit: str) -> None: ...
def log_control_action(device_id: str, action: str, value, actor: str) -> None: ...
def get_sensor_history(device_id: str, limit: int = 50) -> list[dict]: ...
```
서버 시작 시 `init_db()`로 테이블 존재 여부를 확인/생성한다 (db-rules.md의 최소 스키마 참고).

## init.sql — 스키마 + 시드 데이터
`backend/db/init.sql`을 만들 때는 `CREATE TABLE`뿐 아니라, `AGENTS.md`의 "팀 정보"
표에 적힌 액추에이터/센서 목록을 `devices` 테이블 시드 데이터로 함께 넣는다. 재실행해도
중복 에러가 안 나도록 `ON DUPLICATE KEY UPDATE`를 쓴다.
파일 맨 앞에 `CREATE DATABASE` + `USE`를 반드시 넣는다 — 이게 없으면 학생이
`mysql -u root < init.sql`로 실행할 때 `ERROR 1046 (3D000): No database selected`가 난다.

```sql
-- MySQL-only (db-migration 스킬에서 Supabase 전환 시 이 두 줄은 제거한다)
CREATE DATABASE IF NOT EXISTS smart_control
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_control;

CREATE TABLE IF NOT EXISTS devices (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  kind VARCHAR(30) NOT NULL,
  desired_state VARCHAR(30) NULL,   -- 대시보드/트리거가 지정한 목표 상태
  current_state VARCHAR(30) NULL,   -- 파이(또는 Mock)가 보고한 실제 상태
  desired_value JSON NULL,          -- on/off로 안 되는 값 (서보 각도, LED 밝기 등)
  current_value JSON NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- AGENTS.md 팀 정보의 액추에이터/센서 개수만큼 반복
INSERT INTO devices (id, name, kind) VALUES ('led_1', 'LED 조명', 'led')
  ON DUPLICATE KEY UPDATE name = VALUES(name), kind = VALUES(kind);
```
> 시드 `INSERT`에는 `desired_state`/`current_state`를 넣지 않는다 — 재실행해도 현재
> 상태를 덮어쓰지 않도록 `ON DUPLICATE KEY UPDATE` 대상에서 빼 둔다.
이 파일은 자동 실행되지 않는다 — 학생이 직접 MySQL에 실행해야 한다(학생용
매뉴얼 "2-2-1. DB 초기화 스크립트 실행" 참고).
