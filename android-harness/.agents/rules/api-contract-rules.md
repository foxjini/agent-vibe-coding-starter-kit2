# API 계약 규칙

> **서버는 이미 완성되어 동작 중이다. 앱이 서버에 맞춘다.**
> 여기 적힌 값은 실제 백엔드 코드에서 확인한 것이다. 추측으로 바꾸지 않는다.
> 이 앱에 필요한 것은 이 파일에 다 있다. 더 넓은 규격(ATM·콜센터 쪽)이 궁금하면
> 팀 저장소의 `docs/03_데이터-연동-규격.md`를 본다 (이 프로젝트에 복사할 필요는 없다).

## 절대 하지 않는 것

- 백엔드 코드를 고치자고 제안하지 않는다 (앱이 맞춘다)
- 응답에 없는 필드를 있다고 가정하지 않는다
- 엔드포인트 경로를 추측하지 않는다 — 아래 셋이 전부다

## 공통

- 성공 응답은 **항상** `{"data": ...}` 로 감싸여 온다
- 실패 응답은 `{"error": {"code": "...", "message": "..."}}` 이다
  — **`detail`이 아니다.** FastAPI 기본값은 `detail`이지만 이 백엔드는
  `backend/main.py`의 처리기가 전부 `error`로 바꿔 보낸다 (서버를 띄워 확인한 값)
- 입력 형식 오류(422)는 같은 `error` 안에 `details` 목록이 더 붙는다
- `error.message`는 **사용자용 한국어 문구**다. 앱은 대부분 그대로 띄우면 된다
- 사용자용 API는 `Authorization: Bearer <토큰>` 헤더가 필요하다
- 토큰 유효 시간은 **12시간**

## 1. 연결 확인

```
GET /health          ← /api/v1 접두사가 없다. 주의.
```
```json
{"data": {"status": "ok", "device_mode": "hardware"}}
```

## 2. 로그인

```
POST /api/v1/auth/login
{"username": "halmeoni", "password": "<시연 비밀번호>"}
```
```json
{"data": {"access_token": "eyJ...", "token_type": "bearer"}}
```
실패: `401` + `{"error": {"code": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다."}}`

## 3. 분석 요청 ← 이 앱의 핵심 호출

```
POST /api/v1/analysis
Authorization: Bearer <토큰>
{"message": "<검사할 텍스트>"}
```

**`message`는 최대 2000자다.** 한국어 통화는 분당 200~300자이므로 5분이 넘는
받아쓰기는 잘린다. 앱에서 글자 수를 보여 주고 넘치면 줄이게 한다.

### 실제로 돌아온 오류 코드

| 상황 | HTTP | `error.code` | 앱이 할 일 |
|---|---|---|---|
| 토큰 없이 요청 | 401 | `UNAUTHORIZED` | 설정 화면 → 다시 로그인 |
| 토큰 만료 (12시간) | 401 | `TOKEN_EXPIRED` | 〃 |
| 토큰 손상 | 401 | `INVALID_TOKEN` | 〃 |
| 서버 DB를 새로 만든 뒤 옛 토큰 | 401 | `USER_NOT_FOUND` | 〃 |
| 빈 텍스트 | 400 | `MESSAGE_REQUIRED` | `message`를 띄운다 |
| 2000자 초과 | 422 | `VALIDATION_ERROR` | `message`를 띄운다 |

```jsonc
{"data": {
  "analysis_id": 12,
  "risk_level": "DANGER",      // SAFE | CAUTION | DANGER
  "risk_score": 100,           // 0~100
  "reasons": ["기관 사칭 표현 감지", "범죄 연루 언급 감지"],
  "summary": "기관 사칭 표현 및 범죄 연루 언급 감지",
  "detected_at": "2026-09-20T05:12:33",
  "message_text": "...",
  "session_id": "VP-000012",   // QR에 넣을 값
  "atm_action": "BLOCK"        // ALLOW | VERIFY | BLOCK
}}
```

## 4. QR에 넣을 값

**`session_id`만** 넣는다. 아래 JSON 문자열 **그대로**를 QR로 만든다.

```json
{"session_id": "VP-000012"}
```

위험 상세나 개인정보를 QR에 넣지 않는다 — ATM이 서버에서 직접 조회한다.
형식을 바꾸면 **라즈베리파이가 읽지 못한다.**

## 5. QR을 띄우는 조건

```
risk_level != "SAFE"  그리고  session_id != null   →  QR 표시
```

`SAFE`일 때는 띄우지 않는다. 서버는 등급과 무관하게 `session_id`를 항상
만들지만, **평범한 문자는 시스템이 건드리지 않는다**는 것이 이 작품의 원칙이다.
