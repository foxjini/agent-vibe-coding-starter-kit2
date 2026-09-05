---
name: db-migration
description: >-
  MySQL 스키마를 Supabase(PostgreSQL)로 변환하고 Row Level Security(RLS) 정책을 수립 및 적용할 때 사용하는 스킬.
---

# db-migration (MySQL → Supabase/PostgreSQL)

> 4주차(클라우드 배포) 진행 시 이 스킬을 참고한다.

## 문법 변환 체크리스트

| MySQL | PostgreSQL(Supabase) |
|---|---|
| `AUTO_INCREMENT` | `GENERATED ALWAYS AS IDENTITY` 또는 `SERIAL` |
| `ENUM(...)` | 별도 `CHECK` 제약 또는 Postgres `ENUM` 타입 |
| `DATETIME` | `TIMESTAMPTZ` |
| 백틱 `` ` `` 식별자 | 큰따옴표 `"` 식별자 |

## RLS(Row Level Security) 설계
1. 테이블마다 `ENABLE ROW LEVEL SECURITY`
2. `authenticated` 역할에 SELECT 전용 정책(`using (true)`) — 필요 이상으로 넓히지 않는다
3. `anon` 역할에는 정책을 주지 않는다 (비로그인 접근 차단)
4. 쓰기는 백엔드가 `service_role` 키로 수행한다(RLS 우회) — INSERT/UPDATE/DELETE 정책은
   만들지 않는다 (기본 거부)
5. 적용 후 Supabase 보안 어드바이저로 이슈 0건인지 확인한다

## 순서
로컬 MySQL 스키마 확정 → Supabase 프로젝트 생성 → 스키마 변환 적용 → RLS 정책 적용 →
백엔드 `.env`를 Supabase 접속 정보로 교체 → 동작 재검증
