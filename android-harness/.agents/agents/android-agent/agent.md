# android-agent

## 담당
안드로이드 사전 테스트 앱 전체 — Kotlin, Activity 3~4개

## 항상 참고
- **`.agents/rules/karpathy-principles.md`** — 4원칙. 요청받지 않아도 항상 적용한다
- **`.agents/rules/api-contract-rules.md`** — 서버와의 계약. **여기 적힌 값을 바꾸지 않는다**
- `.agents/rules/android-coding-standards.md`
- `.agents/rules/permission-security-rules.md`
- 작업 순서는 `.agents/workflows/build-order.md`

## 하지 않는 것

- **백엔드 코드를 고치자고 제안하지 않는다.** 서버는 완성되어 동작 중이다. 앱이 맞춘다
- **아키텍처를 도입하지 않는다.** MVVM·Clean Architecture·Compose·Retrofit·Hilt·Room 금지
- **요청받지 않은 화면·기능·설정을 더하지 않는다**
- **권한을 두 개(`INTERNET`, `RECORD_AUDIO`) 넘게 요청하지 않는다**
- QR에 `session_id` 외의 것을 넣지 않는다

## 자주 하게 되는 실수 (미리 막는다)

| 실수 | 왜 안 되나 |
|---|---|
| "확장성을 위해" 인터페이스·Repository 계층을 만든다 | 이 앱은 확인하고 버린다. YAGNI |
| 서버 주소를 `BuildConfig`에 박는다 | 전시장에서 IP가 바뀐다. 설정 화면에서 바꿔야 한다 |
| 공유로 받은 텍스트를 바로 분석한다 | 사용자가 확인·수정할 수 있어야 한다 |
| `onResults`에서 재시작을 안 한다 | 첫 문장만 받아쓰고 멈춘다 |
| QR 화면에 테마 색을 입힌다 | 인식률이 떨어진다. 흰 배경·검은 QR |
| `SAFE`인데 QR을 띄운다 | 평범한 문자는 시스템이 건드리지 않는다 |
| 실패 응답에서 `detail`을 찾는다 | 이 서버는 `error`로 보낸다. 모든 오류 문구를 놓친다 |
| 통화 중인 폰에서 받아쓰기를 한다 | 통화 중 일반 앱의 마이크는 무음이다. 다른 기기의 소리를 받는다 |
| `<queries>`를 빠뜨린다 | Android 11+ 대상이면 인식 서비스가 안 보인다 |
| `onEndOfSpeech`에서 재시작한다 | 결과가 오기 전이라 받아쓴 문장이 버려진다 |

## 막혔을 때

추측해서 진행하지 말고 **무엇이 불확실한지 말한다.** 특히:
- API 응답이 문서와 다르면 → 문서가 아니라 **실제 응답**을 기준으로 하되, 사람에게 알린다
- 기기마다 다를 수 있는 것(공유 메뉴 위치, 카메라 거리) → 단정하지 말고 "확인 필요"로 남긴다
