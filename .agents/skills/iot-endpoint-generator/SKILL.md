---
name: iot-endpoint-generator
description: >-
  새로운 센서나 액추에이터 디바이스 종류(device kind)를 추가할 때 DB 스키마, Pydantic 모델, 엔드포인트 및 인증을 4단계로 생성하는 스킬.
---

# iot-endpoint-generator

> 새 센서/액추에이터 종류(device kind)를 하나 추가할 때마다 이 스킬을 참고한다.

## 4단계 체크리스트
1. **DB**: `devices` 테이블에 kind 값 추가(또는 enum 확장), 필요한 컬럼 추가
2. **Pydantic 모델**: 요청/응답 스키마 정의 (`backend/schemas/`)
3. **엔드포인트**: CRUD 또는 ingest 엔드포인트 작성 (api-rules.md 네이밍 규칙 준수)
4. **인증 미들웨어**: 사용자용인지 디바이스용인지 판단해서 적절한 인증을 적용
   (api-rules.md의 "인증 분리" 표 참고)

## 예시 프롬프트
```
너는 이 프로젝트의 backend-agent다. .agents/skills/iot-endpoint-generator/SKILL.md를 따른다.
[센서/액추에이터 이름]을 위 4단계로 추가해줘.
```
