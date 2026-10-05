# 안드로이드 사전 테스트 앱 하네스

`docs/07_안드로이드-사전테스트앱-PRD.md`와 **같이 쓰는** AI 에이전트 하네스입니다.
Antigravity에서 Gemini 에이전트로 바이브 코딩할 때, 에이전트가 PRD에서 벗어나지
않고 이 앱에 필요한 것만 만들도록 붙잡아 둡니다.

팀 저장소의 `.agents/`(스마트 ATM 하네스)와 **같은 구조와 원칙**으로 만들었습니다.
이미 익숙한 방식 그대로 쓰면 됩니다.

## 설치

안드로이드 프로젝트(안드로이드 스튜디오에서 만든 빈 프로젝트)의 **루트**에 아래처럼
복사합니다.

```
내-안드로이드-프로젝트/
├── AGENTS.md                         ← 이 폴더의 AGENTS.md
├── .agents/                          ← 이 폴더의 .agents/ 통째로
├── docs/
│   └── 07_안드로이드-사전테스트앱-PRD.md   ← 팀 저장소 docs/07을 복사
├── app/
└── ...
```

**PRD를 꼭 함께 복사하세요.** AGENTS.md가 `docs/07_…PRD.md`를 기준으로 삼는데,
파일이 프로젝트 안에 없으면 에이전트가 열어 볼 수 없습니다.

## 들어 있는 것

```
AGENTS.md                         에이전트가 가장 먼저 읽는 파일 — 목적·성공 기준·절대 규칙
.agents/
├── rules/                        항상 적용
│   ├── karpathy-principles.md      4원칙 (팀 하네스와 같은 파일)
│   ├── api-contract-rules.md       서버와의 계약 — 실서버로 확인한 값
│   ├── android-coding-standards.md 쓰지 않는 것(Compose·MVVM·Retrofit…)
│   └── permission-security-rules.md 권한 두 개 + <queries>
├── skills/                       해당 작업을 할 때 읽음
│   ├── backend-api-client/         로그인·분석 요청, 응답 봉투, 오류 코드
│   ├── share-intent-receiver/      문자 공유 받기
│   ├── continuous-speech-to-text/  통화 음성 받아쓰기 (가장 까다로움)
│   └── qr-display-for-atm/         ATM이 읽을 QR (성공 기준 S4가 여기서 갈림)
├── workflows/                    순서가 있는 절차
│   ├── build-order.md              PRD 10장의 6단계
│   ├── verify-against-prd.md       성공 기준 확인
│   └── handoff-to-flutter.md       Flutter 담당 학생에게 넘기기
└── agents/
    └── android-agent/agent.md      역할 정의 — 하지 않는 것, 자주 하는 실수
```

## 쓰는 법

팀 하네스와 같습니다. **역할과 단계를 밝히고 시작합니다.**

```
너는 이 프로젝트의 android-agent다.
AGENTS.md와 .agents/workflows/build-order.md를 따른다.
1단계(설정 화면 + /health 연결 확인)만 만든다. 끝나면 확인 방법을 알려 줘.
```

- 한 번에 한 단계만 시킵니다. 단계마다 **실제 폰에서** 확인하고 다음으로 갑니다
- 받아쓰기 단계에서는 `.agents/skills/continuous-speech-to-text/SKILL.md`를 따르라고
  한 줄 붙입니다 (나머지 스킬도 같은 방식)
- 에이전트가 "확장성을 위해" 구조를 갖추자고 하면 거절합니다 — 이 앱은 확인하고
  버리는 앱입니다 (`android-coding-standards.md`)

## Antigravity와의 관계 — 확인된 것과 아닌 것

**검색으로 확인한 것** (Antigravity 공식 문서의 검색 결과 요약 기준):

- 작업 공간 규칙의 기본 위치는 **`.agents/rules/`**다 (`.agent/rules/`도 하위 호환으로 읽음)
- 스킬은 **`SKILL.md`가 든 폴더**로 둔다
- 워크플로는 **`/이름`** 으로 부른다
- 루트의 **`AGENTS.md`**를 읽는다 (IDE 1.20.5부터, `GEMINI.md`와 함께)

이 하네스는 위 구조를 그대로 따릅니다.

**직접 확인하지 못한 것**: Antigravity 공식 문서 페이지는 이 작업 환경의 네트워크
정책에 막혀 열지 못했습니다. 특히 아래는 실제 IDE에서 한 번 확인하세요.

- **워크플로 폴더**가 `.agents/workflows/`인지 — `/build-order`가 메뉴에 뜨는지 보면
  압니다. 안 뜨면 위 프롬프트처럼 파일을 직접 가리키면 됩니다 (팀 하네스도 이 방식)
- 규칙이 **항상 적용**으로 잡혀 있는지 — IDE의 규칙 설정 화면에서 확인합니다
- "2.0"에서 바뀐 점 — 위 내용은 1.x 기준 정보입니다

> 자동으로 읽히지 않더라도 **프롬프트에서 파일을 가리키면 그대로 동작합니다.**
> 팀 하네스가 처음부터 그렇게 쓰도록 만들어져 있습니다.

## 이 하네스가 막아 주는 실수

실제로 이 PRD를 쓰는 과정에서 나왔던 것들입니다.

| 실수 | 어디서 막나 |
|---|---|
| 통화 중인 그 폰에서 받아쓰기 → **무음만 들어온다** | AGENTS.md 절대 규칙 6, `continuous-speech-to-text` |
| 실패 응답에서 `detail`을 찾음 → **모든 오류 문구를 놓친다** (이 서버는 `error`) | AGENTS.md 절대 규칙 5, `api-contract-rules` |
| `<queries>` 누락 → **받아쓰기가 아무 설명 없이 안 된다** | `permission-security-rules`, `continuous-speech-to-text` |
| `onEndOfSpeech`에서 재시작 → 받아쓴 문장이 버려진다 | `continuous-speech-to-text` |
| 서버 주소를 코드에 박음 → 전시장에서 IP가 바뀔 때마다 다시 빌드 | AGENTS.md 절대 규칙 2 |
| QR 화면이 어두움 → ATM이 못 읽는다 | `qr-display-for-atm` |
