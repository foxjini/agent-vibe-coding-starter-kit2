# 프론트엔드 UI/UX 디자인 교재 — 학생용

> 대한민국 전자계열 마이스터고 정보통신과 2학년 · IoT 개발 플랫폼 키트 2차 작업용
> **짝 문서:** 기능은 [00 · 2차 개발 통합 매뉴얼](00-2차개발-통합-매뉴얼.md), 화면은 이 문서.

---

## 0. 이 교재를 보기 전에

### 0-1. 무엇을 배우나

**"AI에게 예쁘게 만들어 줘"라고 하는 것은 바이브 코딩이 아닙니다.**
사용자와 문제를 정의하고, 디자인 원칙과 제한 조건을 프롬프트로 전달한 뒤,
AI가 만든 결과를 **직접 확인하면서** 반복해서 고치는 것이 바이브 코딩입니다.

이 교재는 그 반복을 13단계로 나눠 놓은 것입니다.

```text
아이디어 → 화면 설계 → AI에게 요구사항 전달 → 코드 생성
   → 브라우저에서 확인 → 문제 발견 → 프롬프트로 수정 → 최종 검수
```

### 0-2. 두 문서의 역할

| | [00 통합 매뉴얼](00-2차개발-통합-매뉴얼.md) | 이 교재 (06) |
|---|---|---|
| 다루는 것 | **기능** — 부품·시나리오·감지·규칙 | **화면** — 색·글자·배치·아이콘 |
| 언제 | 2차 작업 **처음부터** | 기능이 **동작한 다음** |
| 고치는 파일 | `pi/slot_map.py` · `scenarios/` · `vision/detectors/` | `app/globals.css` · `app/layout.tsx` · `app/page.tsx` |

> **순서를 지키세요.** 동작하지 않는 화면을 예쁘게 만들면, 나중에 기능을 붙일 때
> 디자인을 다시 합니다. 먼저 **되게** 만들고, 그다음 **보기 좋게** 만듭니다.

### 0-3. 우리는 채팅형 AI로 작업합니다

우리 학생은 Claude Code · CODEX 같은 **에이전트 도구를 쓰지 않습니다.**
Claude.ai · ChatGPT · Gemini 같은 **채팅창**에 직접 물어봅니다.

채팅창은 우리 프로젝트 폴더를 볼 수 없습니다. 그래서 **컨텍스트 팩**을 만들어 올립니다.

```bash
python tools/context_pack.py frontend
```

`context_packs/context_pack_frontend.md` 파일 하나가 생깁니다. 이것을 채팅창에 올립니다.
자세한 방법은 **17장**과 [00 매뉴얼 8장](00-2차개발-통합-매뉴얼.md)에 있습니다.

### 0-4. 시작하기 전 확인

```bash
cd frontend
npm run dev            # http://localhost:3000 이 뜨는가
npx next build         # 지금 상태에서 빌드가 되는가
```

**빌드가 안 되는 상태에서 디자인을 시작하지 마세요.** 무엇 때문에 깨졌는지 알 수 없게 됩니다.

---

## 1. 고치는 곳과 고치지 않는 곳

이 키트는 4개 팀(wakeup · classroom · study · subway)이 함께 씁니다.
**공통 파일을 고치면 다른 팀 화면이 깨집니다.**

### ✅ 마음껏 고치는 곳

| 파일 | 무엇 |
|---|---|
| `frontend/app/globals.css` | 색·모서리·글꼴 토큰, 애니메이션 |
| `frontend/app/layout.tsx` | 글꼴 연결, 페이지 제목 |
| `frontend/app/page.tsx` | **우리 팀 화면** (4팀 공통 출발점) |
| `frontend/scenarios/` | 우리 팀 판정 규칙·진행 |
| `frontend/components/team/` | 우리 팀 전용 카드·모달 |
| `frontend/.env.local` | `NEXT_PUBLIC_TEAM_NAME`, `NEXT_PUBLIC_TEAM_TAGLINE` |

### 🚫 고치지 않는 곳

| 파일 | 왜 |
|---|---|
| `frontend/lib/scenario.ts` · `lib/slots.ts` · `lib/api.ts` | 4팀 공통 SDK. 고치면 전부 깨집니다 |
| `frontend/components/kit/` | 키트가 주는 슬롯 카드·설정 화면 |
| `frontend/app/kit/` | `/kit` 설정 화면 (키트 제공) |
| `frontend/app/wakeup/` | wakeup 팀 완성 본보기 (구조 참고용) |
| `backend/` · `vision/` 공통 파일 | 프론트엔드 담당이 건드릴 일 없음 |

> **`components/kit/`의 카드 모양을 바꾸고 싶다면?**
> 그 파일을 고치지 말고, `globals.css`의 **토큰 값**을 바꾸세요.
> 7장에서 배우는 토큰 구조를 쓰면 카드 파일을 건드리지 않고 색과 모서리가 바뀝니다.

### 새 파일은 자유롭게 만드세요

`components/team/MyCard.tsx` 처럼 **새로 만드는 것**은 언제든 괜찮습니다.
막히면 "공통 파일을 고치는 대신 새 파일을 만들 수 없나?"를 먼저 생각하세요.

---

## 2. 바이브 코딩이란 무엇인가

AI에게 자연어로 요구사항을 전달하고, AI가 만든 코드를 실행·확인하면서 계속 고치는 방식입니다.
**AI에게 전부 맡기는 것이 아닙니다.**

| 사람(학생)이 하는 일 | AI가 하는 일 |
|---|---|
| 문제 정의 | 코드 작성 |
| 기능 결정 | 코드 수정 |
| 화면 구성 결정 | UI 구현 |
| 결과 확인 | 오류 원인 분석 |
| **최종 판단** | 개선안 제안 |

> **AI가 코드를 쓰고, 학생이 개발을 지휘합니다.**

### 원칙 1 — 한 번에 너무 많이 요청하지 않는다

| ❌ 나쁜 요청 | ✅ 좋은 요청 |
|---|---|
| "우리 프로젝트 모든 화면을 최고 수준 디자인으로 만들어 줘" | "먼저 현재 화면의 문제점 5개만 찾아 줘. 코드는 고치지 마." |

### 원칙 2 — 기능과 디자인을 분리한다

| 유지할 것 (건드리지 말 것) | 바꿀 것 |
|---|---|
| 기능 · API 호출 · 데이터 구조 · 상태 관리 · 라우팅 | 배치 · 색 · 글자 · 여백 · 아이콘 · 애니메이션 |

프롬프트에 이 두 줄을 **항상** 넣으세요. 이것이 사고를 막는 가장 큰 장치입니다.

### 원칙 3 — 고치기 전에 분석하게 한다

```text
분석 → 계획 → 구현 → 테스트 → 검수
```

AI가 "바로 코드부터" 주려고 하면 멈추고 **"먼저 계획만 보여 줘"** 라고 하세요.

---

## 3. 전체 13단계 — 한눈에

| 단계 | 무엇 | 이 교재 | 결과물 |
|---|---|---|---|
| 1 | 지금 화면 분석 | 4장 | 문제점 목록 |
| 2 | 사용자·정보 정의 | 5장 | 요구사항 표 |
| 3 | **디자인 스타일 고르기** | **6장** | 팀이 고른 스타일 1개 |
| 4 | 디자인 토큰 | 7장 | `globals.css` |
| 5 | 타이포그래피 | 8장 | `layout.tsx` + 글자 크기 규칙 |
| 6 | 레이아웃 | 9장 | 화면 뼈대 |
| 7 | 공통 컴포넌트 | 10장 | `components/team/` |
| 8 | **아이콘 · 애니메이션** | **11장** | 상태를 알려주는 아이콘 |
| 9 | 페이지 다듬기 | 12장 | 완성된 `/` 화면 |
| 10 | 반응형 | 13장 | 모바일에서도 보임 |
| 11 | 인터랙션 | 14장 | 로딩·에러·빈 화면 |
| 12 | 접근성 | 15장 | 키보드·대비·라벨 |
| 13 | 디자인 QA | 16장 | 최종 점검 |

**처음부터 완벽한 디자인을 만들려고 하지 마세요.**

1. 첫 목표 — "기능이 잘 동작하는 **깔끔한** 화면"
2. 두 번째 — "**사용하기 편한** 화면"
3. 세 번째 — "**전문적으로 보이는** 화면"

---

## 4. 1단계 · 지금 화면을 직접 뜯어본다

### 4-1. AI보다 먼저 학생이 본다

AI에게 묻기 전에 **자기 눈으로** 봅니다. 그래야 AI 답이 맞는지 판단할 수 있습니다.

1. `npm run dev` 후 `http://localhost:3000`을 엽니다
2. 스크린샷을 찍습니다 (`F12` → 기기 툴바로 모바일 폭도 한 장)
3. 아래 표를 채웁니다 — **5개를 채우기 전에는 AI에게 묻지 않습니다**

| # | 무엇이 불편한가 | 어디 | 왜 그런가 (내 생각) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

### 4-2. 볼 때 쓰는 질문

- 처음 보는 사람이 **3초 안에** 가장 중요한 정보를 찾을 수 있나?
- 글자 크기가 몇 종류인가? (5종류가 넘으면 정리가 안 된 것)
- 색이 몇 가지인가? (의미 없이 쓰인 색이 있나?)
- **모든 것이 카드**에 담겨 있지 않나?
- 폭을 좁히면 가로 스크롤이 생기나?

### 4-3. 그다음 AI에게 확인받기

컨텍스트 팩을 올리고 아래를 그대로 씁니다.

```text
[역할] 너는 시니어 프론트엔드 개발자이자 UI/UX 디자이너다.

[상황] 마이스터고 2학년 IoT 작품의 대시보드 화면이다.
올린 컨텍스트 팩에 현재 코드가 들어 있다.

[할 일] 현재 화면의 UI/UX 문제점을 찾아라.

확인할 것:
1. 정보 계층 (무엇이 먼저 보이는가)
2. 색 사용 (의미 없는 색이 있는가)
3. 글자 크기 종류 (너무 많은가)
4. 여백 일관성
5. 아이콘 사용 방식
6. 반응형에서 깨지는 곳
7. 접근성 문제

[금지]
- 코드를 고치지 마라
- 기능·API·데이터 구조를 바꾸지 마라
- 새 라이브러리를 제안하지 마라

[출력]
현재 구조 → 문제점 → 개선 방향 → 우선순위(High/Medium/Low) 순으로
표로 정리하라. 각 문제는 파일명과 함께 적어라.
```

### 4-4. 내가 찾은 것과 비교

| 확인 | |
|---|---|
| ☐ | AI가 코드를 고치지 않았는가 |
| ☐ | 내가 찾은 5개 중 AI도 찾은 것은 몇 개인가 |
| ☐ | AI만 찾은 것 중 **실제로 그런지 화면에서 확인**했는가 |
| ☐ | AI가 찾았지만 **내가 보기엔 문제가 아닌 것**이 있는가 |

> 마지막 줄이 중요합니다. AI는 컨텍스트 팩만 보고 답하므로
> **실제 화면에는 없는 문제**를 말하기도 합니다. 반드시 눈으로 확인하세요.

---

## 5. 2단계 · 사용자와 정보를 정한다

화면을 만들기 전에 **누가 보는가**를 정합니다.

### 5-1. 우리 팀 요구사항 표

| 항목 | 우리 팀 답 | 예시 (참고만) |
|---|---|---|
| 주요 사용자 | | 전시회 관람객 / 우리 반 학생 |
| 가장 중요한 기능 | | 지금 장치가 동작하는지 보여주기 |
| 가장 먼저 보여줄 정보 | | 센서 현재값과 연결 상태 |
| 사용 장소 | | 전시회 부스 (밝음 / 사람 많음) |
| 보는 기기 | | 27" 모니터 / 태블릿 / 휴대폰 |
| 보는 거리 | | 1m / 3m 떨어져서 |
| 필요한 화면 | | `/` 하나로 충분 |

> **보는 거리**를 꼭 적으세요. 3m 떨어져서 보는 전시회 화면과
> 책상에서 보는 화면은 글자 크기가 완전히 달라야 합니다. 6장에서 씁니다.

### 5-2. 3초 규칙

> 처음 보는 사람이 **3초 안에** "이 작품이 지금 무엇을 하고 있는지" 알 수 있어야 합니다.

3초 안에 보여야 할 것을 **딱 하나**만 고르세요. 그것을 화면에서 가장 크게 만듭니다.

| 팀 | 3초 안에 보여야 할 것 (예) |
|---|---|
| wakeup | 지금 알람이 울리는가 / 미션이 진행 중인가 |
| study | 6자리 중 몇 자리가 차 있는가 |
| classroom | 지금 교실에 사람이 있는가 |
| subway | 지금 혼잡도가 몇 단계인가 |

---
## 6. 3단계 · 디자인 스타일 고르기

### 6-1. 왜 "미니멀" 하나로 통일하지 않는가

미니멀은 **안전한 기본값**이지만 정답은 아닙니다.
전시회 부스에서 3m 떨어져 보는 화면과, 책상에서 6개 좌석을 관리하는 화면은
좋은 디자인의 모양이 다릅니다.

그래서 이 교재는 **5가지 스타일을 실제로 적용해 보고 팀이 고르게** 합니다.
7장의 토큰 구조를 쓰면 **화면 코드는 한 줄도 고치지 않고** 스타일이 통째로 바뀝니다.

### 6-2. 5가지 스타일

#### ① `minimal` — 깔끔한 기본

|  |  |
|---|---|
| 느낌 | 조용하고 정돈됨. 상용 관리 도구 같은 인상 |
| 어울리는 팀 | 정보가 적고, 한 가지를 또렷이 보여줄 때 |
| 조심할 점 | 멀리서 보면 밋밋함. 전시회 부스에서는 눈에 안 띌 수 있음 |
| 명암비 | 본문 17.9 : 1 (기준 4.5 : 1) |

#### ② `soft` — 따뜻하고 둥글다

|  |  |
|---|---|
| 느낌 | 부드럽고 친근함. 크림색 배경, 큰 모서리 |
| 어울리는 팀 | 사람을 돕는 느낌을 주고 싶을 때 (기상·학습·건강) |
| 조심할 점 | 모서리를 너무 키우면(24px 초과) 장난감처럼 보임 |
| 명암비 | 본문 12.3 : 1 |

#### ③ `console` — 어두운 관제실

|  |  |
|---|---|
| 느낌 | 어두운 배경에 밝은 강조. 장비를 감시하는 인상 |
| 어울리는 팀 | 센서가 많고 숫자가 계속 바뀔 때 (혼잡도·좌석·환경) |
| 조심할 점 | 어두운 배경에서 얇은 글씨는 읽기 어려움 → 400 대신 500 두께 |
| 명암비 | 본문 14.5 : 1 |

> **전시회 부스에서 가장 눈에 띕니다.** 주변이 밝을수록 어두운 화면이 도드라집니다.

#### ④ `bold` — 멀리서도 보인다

|  |  |
|---|---|
| 느낌 | 굵은 검은 테두리, 진한 강조색, 큰 글씨 |
| 어울리는 팀 | **3m 떨어져서** 보는 전시회 화면 |
| 조심할 점 | 정보가 많으면 시끄러움. 카드 6개를 넘기지 말 것 |
| 명암비 | 본문 18.9 : 1 (가장 높음) |

#### ⑤ `editorial` — 정보가 많을 때

|  |  |
|---|---|
| 느낌 | 모서리 거의 없음. 카드 대신 **선**으로 구분. 신문·보고서 느낌 |
| 어울리는 팀 | 표·목록이 많을 때 (좌석 6개, 이벤트 기록) |
| 조심할 점 | 카드가 없어 허전해 보일 수 있음 → 여백과 제목으로 구분 |
| 명암비 | 본문 17.5 : 1 |

### 6-3. 값 비교표

| 토큰 | minimal | soft | console | bold | editorial |
|---|---|---|---|---|---|
| 배경 | `#f8fafc` | `#fdf8f4` | `#0b1220` | `#fffdf5` | `#ffffff` |
| 카드 | `#ffffff` | `#ffffff` | `#151d2e` | `#ffffff` | `#ffffff` |
| 선 | `#e2e8f0` | `#f0e4d8` | `#2a3750` | `#111111` | `#d4d4d4` |
| 본문 글자 | `#0f172a` | `#3f322b` | `#e8eefc` | `#111111` | `#1c1917` |
| 흐린 글자 | `#64748b` | `#806858` | `#93a4c0` | `#4a4a4a` | `#57534e` |
| 강조 | `#2563eb` | `#b44d18` | `#38bdf8` | `#b91c1c` | `#15803d` |
| 카드 모서리 | `12px` | `24px` | `10px` | `4px` | `2px` |
| 선 굵기 | `1px` | `1px` | `1px` | `2px` | `1px` |
| 카드 그림자 | 아주 옅게 | 옅게 | 없음 | 없음 | 없음 |

> 모든 조합은 **WCAG AA 기준(4.5 : 1)을 통과**하도록 계산해서 골랐습니다.
> 값을 바꿀 때는 15장의 명암비 확인을 다시 하세요.

### 6-4. 3분 비교 실험 — 팀이 고르는 방법

1. 7장의 `globals.css`를 그대로 붙여넣습니다 (5가지가 전부 들어 있습니다)
2. 7-5의 스타일 전환 스위처를 화면 아래에 잠깐 붙입니다
3. **팀원 전부가 모니터 앞에 서서** 버튼을 눌러 가며 봅니다
4. 실제 사용 거리에서 봅니다 — 전시회용이면 **3m 뒤로 물러나서**
5. 아래 표에 점수를 매기고 합계가 높은 것을 고릅니다

| 기준 | minimal | soft | console | bold | editorial |
|---|---|---|---|---|---|
| 3초 안에 핵심이 보이나 (5점) | | | | | |
| 실제 거리에서 읽히나 (5점) | | | | | |
| 우리 작품 주제와 어울리나 (5점) | | | | | |
| 눈이 편한가 (5점) | | | | | |
| **합계** | | | | | |

### 6-5. 고른 다음

1. 고른 스타일 이름을 `app/layout.tsx`의 `<html data-style="...">`에 **고정**합니다
2. **스위처는 지웁니다** (제출본에 남기지 마세요)
3. 안 고른 4개의 토큰 블록은 **지워도 되고 남겨도 됩니다** — 남겨 두면 나중에 다시 비교할 수 있습니다

### 6-6. 팀 결정 기록

| 항목 | 내용 |
|---|---|
| 고른 스타일 | |
| 고른 이유 (한 문장) | |
| 바꾼 값이 있다면 | |
| 결정한 날짜 / 참여자 | |

> 이 표를 채워 두세요. **16장 디자인 QA와 20장 평가에서 "왜 이 색인가"를 묻습니다.**

---

## 7. 4단계 · 디자인 토큰 (Tailwind v4)

### 7-1. ⚠️ 가장 많이 틀리는 곳 — 먼저 읽으세요

인터넷 글과 AI 답변 대부분은 **Tailwind v3** 기준입니다.
**우리 프로젝트는 Tailwind v4입니다.** v3 방식으로 쓰면 이렇게 됩니다.

```css
/* ❌ 이렇게 하면 아무 일도 일어나지 않습니다 */
:root {
  --color-primary: #2563eb;
}
```

```tsx
<button className="bg-primary">확인</button>
```

**실제로 해 본 결과:**

| | 결과 |
|---|---|
| `npx next build` | ✅ **성공** |
| 콘솔 에러 | **없음** |
| 생성된 CSS에 `.bg-primary` 규칙 | **0개** |
| 화면 | 버튼 색이 **안 바뀜** |

> **에러가 안 나기 때문에** 학생이 가장 오래 헤매는 문제입니다.
> "AI가 준 코드인데 왜 색이 안 바뀌지?"의 90%가 이것입니다.

**Tailwind v4에서는 `@theme` 안에 넣어야 유틸리티 클래스가 만들어집니다.**
`:root`는 그냥 CSS 변수일 뿐, Tailwind가 보지 않습니다.

### 7-2. 우리가 쓸 2단 구조

스타일을 **실행 중에** 바꾸려면 두 단으로 나눕니다.

```text
① @theme inline   유틸리티 이름을 만든다        (빌드할 때 한 번)
       ↓ var()로 연결
② :root / [data-style]   실제 색 값을 정한다     (실행 중에 바꿀 수 있음)
```

`@theme inline`은 `.bg-brand { background-color: var(--ui-brand) }` 처럼
**변수를 그대로 참조하는** 규칙을 만듭니다. 그래서 `--ui-brand` 값만 바꾸면
화면 전체가 즉시 바뀝니다.

**확인된 동작** — 아래 7-3의 CSS를 그대로 넣고 `data-style` 하나만 바꿔서
브라우저가 실제로 계산한 값을 읽은 결과입니다. **화면 코드는 한 줄도 고치지 않았습니다.**

| `data-style` | 배경 | 카드 | 모서리 | 테두리 | 본문 글자 | 강조 |
|---|---|---|---|---|---|---|
| `minimal` | `rgb(248,250,252)` | `rgb(255,255,255)` | `12px` | `1px` | `rgb(15,23,42)` | `rgb(37,99,235)` |
| `soft` | `rgb(253,248,244)` | `rgb(255,255,255)` | `24px` | `1px` | `rgb(63,50,43)` | `rgb(180,77,24)` |
| `console` | `rgb(11,18,32)` | `rgb(21,29,46)` | `10px` | `1px` | `rgb(232,238,252)` | `rgb(56,189,248)` |
| `bold` | `rgb(255,253,245)` | `rgb(255,255,255)` | `4px` | **`2px`** | `rgb(17,17,17)` | `rgb(185,28,28)` |
| `editorial` | `rgb(255,255,255)` | `rgb(255,255,255)` | `2px` | `1px` | `rgb(28,25,23)` | `rgb(21,128,61)` |

### 7-3. `app/globals.css` — 통째로 바꾸세요

```css
@import "tailwindcss";

/* =========================================================================
   ① 유틸리티 이름 만들기 — 빌드할 때 한 번 (여기 이름을 className에 씁니다)
   ⚠️ :root에 적으면 유틸리티가 안 만들어집니다. 반드시 @theme 안에.
   ========================================================================= */
@theme inline {
  --color-bg:       var(--ui-bg);        /* bg-bg        페이지 배경 */
  --color-surface:  var(--ui-surface);   /* bg-surface   카드 배경 */
  --color-line:     var(--ui-line);      /* border-line  테두리 */
  --color-ink:      var(--ui-ink);       /* text-ink     본문 글자 */
  --color-muted:    var(--ui-muted);     /* text-muted   흐린 글자 */
  --color-brand:    var(--ui-brand);     /* bg-brand     강조 */
  --color-on-brand: var(--ui-on-brand);  /* text-on-brand 강조 위 글자 */

  --color-ok:    var(--ui-ok);           /* 정상 */
  --color-warn:  var(--ui-warn);         /* 주의 */
  --color-bad:   var(--ui-bad);          /* 이상 */

  --radius-card: var(--ui-radius-card);  /* rounded-card */
  --radius-pill: var(--ui-radius-pill);  /* rounded-pill */

  --font-sans: var(--font-kr);           /* 8장에서 연결합니다 */
}

/* =========================================================================
   ② 스타일별 값 — 실행 중에 바뀝니다 (<html data-style="...">)
   ========================================================================= */

/* ① minimal — 깔끔한 기본 (기본값) */
:root,
[data-style="minimal"] {
  --ui-bg: #f8fafc;  --ui-surface: #ffffff;  --ui-line: #e2e8f0;
  --ui-ink: #0f172a; --ui-muted: #64748b;
  --ui-brand: #2563eb; --ui-on-brand: #ffffff;
  --ui-ok: #059669;  --ui-warn: #b45309;  --ui-bad: #dc2626;
  --ui-radius-card: 12px; --ui-radius-pill: 9999px;
  --ui-border-width: 1px;
  --ui-shadow-card: 0 1px 2px rgb(15 23 42 / 0.05);
}

/* ② soft — 따뜻하고 둥글다 */
[data-style="soft"] {
  --ui-bg: #fdf8f4;  --ui-surface: #ffffff;  --ui-line: #f0e4d8;
  --ui-ink: #3f322b; --ui-muted: #806858;
  --ui-brand: #b44d18; --ui-on-brand: #ffffff;
  --ui-ok: #4d7c0f;  --ui-warn: #b45309;  --ui-bad: #be123c;
  --ui-radius-card: 24px; --ui-radius-pill: 9999px;
  --ui-border-width: 1px;
  --ui-shadow-card: 0 2px 8px rgb(120 80 50 / 0.08);
}

/* ③ console — 어두운 관제실 */
[data-style="console"] {
  --ui-bg: #0b1220;  --ui-surface: #151d2e;  --ui-line: #2a3750;
  --ui-ink: #e8eefc; --ui-muted: #93a4c0;
  --ui-brand: #38bdf8; --ui-on-brand: #06121f;
  --ui-ok: #34d399;  --ui-warn: #fbbf24;  --ui-bad: #fb7185;
  --ui-radius-card: 10px; --ui-radius-pill: 9999px;
  --ui-border-width: 1px;
  --ui-shadow-card: none;
}

/* ④ bold — 멀리서도 보인다 */
[data-style="bold"] {
  --ui-bg: #fffdf5;  --ui-surface: #ffffff;  --ui-line: #111111;
  --ui-ink: #111111; --ui-muted: #4a4a4a;
  --ui-brand: #b91c1c; --ui-on-brand: #ffffff;
  --ui-ok: #15803d;  --ui-warn: #a16207;  --ui-bad: #b91c1c;
  --ui-radius-card: 4px; --ui-radius-pill: 4px;
  --ui-border-width: 2px;
  --ui-shadow-card: none;
}

/* ⑤ editorial — 정보가 많을 때 */
[data-style="editorial"] {
  --ui-bg: #ffffff;  --ui-surface: #ffffff;  --ui-line: #d4d4d4;
  --ui-ink: #1c1917; --ui-muted: #57534e;
  --ui-brand: #15803d; --ui-on-brand: #ffffff;
  --ui-ok: #15803d;  --ui-warn: #a16207;  --ui-bad: #b91c1c;
  --ui-radius-card: 2px; --ui-radius-pill: 2px;
  --ui-border-width: 1px;
  --ui-shadow-card: none;
}

/* =========================================================================
   ③ 스타일을 따라 움직이는 공통 클래스
   ========================================================================= */
body {
  background: var(--ui-bg);
  color: var(--ui-ink);
}

/* 카드 하나 = 이 클래스 하나. 스타일을 바꾸면 모서리·테두리·그림자가 같이 바뀝니다 */
.card {
  background: var(--ui-surface);
  border: var(--ui-border-width) solid var(--ui-line);
  border-radius: var(--ui-radius-card);
  box-shadow: var(--ui-shadow-card);
}

/* 키보드로 이동할 때 어디에 있는지 보이게 (15장 접근성) */
:focus-visible {
  outline: 2px solid var(--ui-brand);
  outline-offset: 2px;
}
```

### 7-4. `app/layout.tsx` — 고른 스타일 고정하기

```tsx
<html lang="ko" data-style="minimal" className="h-full antialiased">
```

`data-style` 값을 `soft` · `console` · `bold` · `editorial`로 바꾸면 화면 전체가 바뀝니다.

> ⚠️ 지금 `layout.tsx`의 `<body>`에는 `className="bg-slate-50 text-slate-900"`이
> 적혀 있습니다. **이 두 개를 지우세요.** 안 지우면 토큰을 무시하고 늘 회색 배경이 됩니다.
> (`console` 스타일을 골랐는데 배경이 안 어두워지면 이것 때문입니다.)

### 7-5. 비교용 스위처 (고른 다음 지웁니다)

`components/team/StyleSwitcher.tsx`를 새로 만듭니다.

```tsx
"use client";
import { useEffect, useState } from "react";

const STYLES = ["minimal", "soft", "console", "bold", "editorial"] as const;

/** 스타일 비교용. 팀이 하나를 고르면 이 파일과 사용하는 줄을 지우세요. */
export default function StyleSwitcher() {
  const [style, setStyle] = useState<string>("minimal");

  useEffect(() => {
    document.documentElement.dataset.style = style;
  }, [style]);

  return (
    <div className="card fixed bottom-4 left-1/2 flex -translate-x-1/2 gap-1 p-2">
      {STYLES.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => setStyle(s)}
          aria-pressed={style === s}
          className={`rounded-pill px-3 py-1 text-sm ${
            style === s ? "bg-brand text-on-brand" : "text-muted"
          }`}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
```

`app/page.tsx` 맨 아래에 잠깐 붙입니다.

```tsx
import StyleSwitcher from "@/components/team/StyleSwitcher";
// ... </main> 바로 앞에
<StyleSwitcher />
```

### 7-6. 화면에서 토큰 쓰기

```tsx
{/* 전 */}
<div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
  <h2 className="text-slate-900">좌석 현황</h2>
  <p className="text-slate-500">6자리 중 4자리 사용 중</p>
</div>

{/* 후 — 스타일을 바꾸면 이 카드도 같이 바뀝니다 */}
<div className="card p-6">
  <h2 className="text-ink">좌석 현황</h2>
  <p className="text-muted">6자리 중 4자리 사용 중</p>
</div>
```

| 바꾸기 전 | 바꾼 뒤 |
|---|---|
| `bg-white` `border-slate-200` `rounded-xl` `shadow-sm` | `.card` 하나 |
| `text-slate-900` | `text-ink` |
| `text-slate-500` | `text-muted` |
| `bg-blue-600` | `bg-brand` |
| `text-white` (강조 버튼 글자) | `text-on-brand` |
| `bg-slate-50` (페이지 배경) | `bg-bg` 또는 지우기(body가 처리) |

### 7-7. 자가 점검 — 토큰이 진짜 동작하나

```bash
cd frontend
npx next build

# 유틸리티가 만들어졌는지 확인 (0이면 @theme에 안 들어간 것)
grep -o '\.bg-brand{[^}]*}' .next/static/chunks/*.css
```

| 나와야 하는 것 | 뜻 |
|---|---|
| `.bg-brand{background-color:var(--ui-brand)}` | ✅ 정상 |
| 아무것도 안 나옴 | ❌ `@theme` 밖에 적었거나 이름이 다름 |
| `.bg-brand{background-color:#2563eb}` | ⚠️ `@theme inline`이 아니라 `@theme`로 적음 → 스타일 전환 안 됨 |

브라우저에서도 확인합니다.

1. `F12` → Console
2. `document.documentElement.dataset.style = "console"` 입력
3. 화면이 어두워지면 정상. 안 바뀌면 7-4의 `<body>` className을 확인하세요

---
## 8. 5단계 · 한글 타이포그래피

### 8-1. ⚠️ 지금 프로젝트의 글꼴은 한글을 담고 있지 않습니다

`app/layout.tsx`는 **Geist** 글꼴을 씁니다. 실제로 확인해 보면:

| 확인한 것 | 결과 |
|---|---|
| Geist가 내려받는 글자 영역 | 라틴 · 라틴확장 · 키릴 · 베트남어 — **한글 없음** |
| 그럼 한글은 어떻게 보이나 | 각자 **컴퓨터에 깔린 아무 글꼴**로 보입니다 |
| 그래서 생기는 일 | 내 화면과 친구 화면, 발표용 PC 화면의 **글자 모양이 다릅니다** |

전시회 발표용 PC에서 글자가 갑자기 달라 보이는 사고가 여기서 납니다.

### 8-2. ⚠️ 글꼴은 "선언"만으로 적용되지 않습니다

이것도 **에러가 안 나는** 함정입니다. 실제로 측정한 결과입니다.

| `layout.tsx`에 `Noto_Sans_KR`을 선언하고 `<html>`에 변수 class를 붙였을 때 | 실제 적용된 글꼴 |
|---|---|
| `globals.css`의 `@theme`에 **연결하지 않음** | `-apple-system, BlinkMacSystemFont, ...` ❌ **적용 안 됨** |
| `@theme`에 `--font-sans: var(--font-kr)` **연결함** | `"Noto Sans KR"` ✅ 적용됨 |

7장의 `globals.css`에는 이미 `--font-sans: var(--font-kr);` 줄이 들어 있습니다.
이제 `layout.tsx`에서 `--font-kr`을 만들어 주기만 하면 됩니다.

### 8-3. `app/layout.tsx` — 한글 글꼴 연결

```tsx
import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";
import "./globals.css";

/** globals.css의 @theme이 이 --font-kr을 찾아 씁니다. 이름을 바꾸면 양쪽 다 바꾸세요. */
const notoSansKr = Noto_Sans_KR({
  variable: "--font-kr",
  subsets: ["latin"],      // 한글은 이 값과 관계없이 함께 내려받습니다 (8-4 참고)
  weight: ["400", "500", "700"],
  display: "swap",         // 글꼴 오기 전에도 글자가 보입니다
});

export const metadata: Metadata = {
  title: "우리 팀 IoT 시스템",        // ← 팀 이름으로 바꾸세요
  description: "센서와 장치 상태를 실시간으로 보여 주는 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ko"
      data-style="minimal"                          // ← 6장에서 고른 스타일
      className={`${notoSansKr.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
```

### 8-4. 글꼴이 무겁지 않나요

무겁지 않습니다. 실제로 측정했습니다.

| | 값 |
|---|---|
| 내려받은 글꼴 조각 수 | 8개 |
| **브라우저가 실제로 받은 용량** | **39.8 KB** |
| 적용된 글꼴 | `"Noto Sans KR"` |

한글 글꼴은 글자 영역별로 잘게 쪼개져 있어서, 브라우저는 **화면에 실제로 나온 글자**가
들어 있는 조각만 내려받습니다. 사진 한 장보다 가볍습니다.

> **Pretendard · SUIT를 쓰고 싶다면?** `next/font/google`에 없습니다.
> `next/font/local`로 파일을 직접 넣어야 하는데 설정이 늘어납니다.
> **2차 작업에서는 Noto Sans KR을 권합니다.**

### 8-5. 글자 크기 규칙

글자 크기는 **5종류를 넘기지 마세요.** 넘어가면 정돈돼 보이지 않습니다.

| 이름 | 쓰는 곳 | 가까이서 볼 때 | **3m 떨어져 볼 때** | Tailwind |
|---|---|---|---|---|
| 큰 제목 | 화면 이름 | 32px / 700 | 48px / 700 | `text-3xl` / `text-5xl` |
| 중간 제목 | 구역 이름 | 20px / 600 | 30px / 700 | `text-xl` / `text-3xl` |
| **핵심 숫자** | 센서값·좌석 수 | 36px / 700 | **72px / 700** | `text-4xl` / `text-7xl` |
| 본문 | 설명 | 16px / 400 | 20px / 400 | `text-base` / `text-xl` |
| 작은 글씨 | 시각·단위 | 13px / 400 | 16px / 400 | `text-sm` / `text-base` |

> **5-1에서 적은 "보는 거리"에 맞는 열을 쓰세요.** 전시회용이면 오른쪽 열입니다.
> 3m에서 16px 글자는 읽을 수 없습니다.

### 8-6. 한글에서 더 챙길 것

| 항목 | 값 | 왜 |
|---|---|---|
| 줄 간격 | `leading-relaxed` (1.625) | 한글은 영문보다 넉넉해야 읽힙니다 |
| 자간 | 건드리지 않기 | 한글은 자간을 좁히면 오히려 답답해집니다 |
| 줄바꿈 | `break-keep` | 단어 중간에서 잘리지 않습니다 |
| 굵기 | 400 / 500 / 700만 | 한글은 굵기 차이가 영문보다 잘 안 보입니다 |

```tsx
<p className="text-base leading-relaxed break-keep">
  6자리 중 4자리가 사용 중입니다
</p>
```

---

## 9. 6단계 · 레이아웃

### 9-1. 사이드바부터 만들지 마세요

AI에게 "대시보드"라고 하면 거의 항상 **왼쪽 사이드바**를 만듭니다.
화면이 `/` 하나뿐인데 사이드바를 만들면 **갈 곳 없는 메뉴**가 생깁니다.

| 화면 수 | 권하는 구조 |
|---|---|
| 1개 (대부분의 팀) | 머리말 + 본문. 메뉴 없음 |
| 2~3개 | 머리말 안에 가로 링크 |
| 4개 이상 | 그때 사이드바를 생각 |

### 9-2. 권하는 뼈대

```text
┌──────────────────────────────────────────┐
│ 머리말 — 팀 이름 · 연결 상태 · /kit 링크  │
├──────────────────────────────────────────┤
│ 알림 (있을 때만)                          │
├──────────────────────────────────────────┤
│ ★ 3초 안에 보여야 할 것 — 가장 크게        │
├──────────────────────────────────────────┤
│ 부품 카드 (SlotGrid — 키트가 그려 줌)      │
├──────────────────────────────────────────┤
│ 최근 감지 기록 (VisionLogCard)            │
└──────────────────────────────────────────┘
```

`app/page.tsx`에 이미 이 뼈대가 들어 있습니다. **★ 자리**만 우리 팀 것으로 바꾸면 됩니다.

### 9-3. 여백은 4의 배수로

| 쓰는 곳 | 값 | Tailwind |
|---|---|---|
| 붙어 있는 요소 사이 | 8px | `gap-2` |
| 카드 안쪽 | 24px | `p-6` |
| 구역 사이 | 32px | `mt-8` |
| 화면 좌우 | 16px (모바일) / 24px | `px-4 sm:px-6` |

**한 화면에서 여백 종류를 4가지 안으로.** 이것만 지켜도 훨씬 정돈돼 보입니다.

---

## 10. 7단계 · 공통 컴포넌트

### 10-1. 전부 카드에 넣지 마세요

AI가 만든 화면의 가장 흔한 문제입니다.

| 보여줄 것 | 쓸 것 |
|---|---|
| 짧은 설명 | 그냥 문단 |
| 목록 | 목록 (`<ul>`) |
| 데이터가 많을 때 | 표 |
| **강조할 것** | 카드 |
| 상태 한 단어 | 배지 |
| 행동 | 버튼 |

```text
❌ 나쁜 구조              ✅ 좋은 구조
Card                      Page
 └ Card                    ├ Section — 제목 + 내용
    └ Card                 ├ Section — 표
                           └ Section — 버튼
```

> **카드 안에 카드를 넣지 마세요.** 넣고 싶으면 바깥 카드를 지우세요.

### 10-2. 우리 팀 컴포넌트는 `components/team/`에

```text
components/
  kit/      ← 고치지 않음 (키트 제공)
  team/     ← 여기에 만듭니다
    SeatGrid.tsx
    FocusBadge.tsx
```

### 10-3. 만들기 전에 확인

| 확인 | |
|---|---|
| ☐ | `components/kit/`에 이미 비슷한 것이 있나? (`SlotGrid` · `SensorSlotCard` · `VisionLogCard`) |
| ☐ | 같은 모양이 **2번 이상** 나오나? (1번이면 아직 컴포넌트로 뺄 때가 아님) |
| ☐ | 이름만 보고 무엇인지 알 수 있나? |

### 10-4. 상태 배지 예시

```tsx
/** components/team/StatusBadge.tsx */
const TONE = {
  ok:   "text-ok",
  warn: "text-warn",
  bad:  "text-bad",
} as const;

export default function StatusBadge({
  tone,
  children,
}: {
  tone: keyof typeof TONE;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`rounded-pill border-line border px-2.5 py-0.5 text-sm font-medium ${TONE[tone]}`}
    >
      {children}
    </span>
  );
}
```

색을 `text-green-600`이 아니라 `text-ok`로 쓴 것을 보세요.
**스타일을 바꾸면 이 배지 색도 같이 바뀝니다.**

---

## 11. 8단계 · 아이콘과 애니메이션

### 11-1. 설치할 것이 없습니다

교재나 인터넷 글이 `npm install lucide-react`를 하라고 해도 **하지 마세요.**
이 프로젝트에는 **이미 들어 있습니다** (`package.json`의 `lucide-react: ^1.41.0`).

```tsx
import { Bell, Wifi, WifiOff, Settings2 } from "lucide-react";

<Bell className="h-5 w-5" />
```

| 규칙 | |
|---|---|
| 크기 | `h-4 w-4`(작게) · `h-5 w-5`(기본) · `h-6 w-6`(크게) — **이 3개만** |
| 색 | `text-muted` · `text-brand` · `text-ok` 등 **토큰으로** |
| 이모지 | 기능 아이콘으로 **쓰지 않습니다** (기기마다 모양이 다름) |
| 라이브러리 | 섞지 않습니다. lucide 하나로 |
| 아이콘만 있는 버튼 | **반드시** `aria-label` (15장) |

### 11-2. 애니메이션의 유일한 규칙

> **보여주려고 움직이지 않습니다. 상태를 알려주려고 움직입니다.**

| ✅ 움직여도 되는 것 | ❌ 움직이면 안 되는 것 |
|---|---|
| 지금 연결 중 (아직 안 끝남) | 그냥 있는 제목 |
| 알람이 울리는 중 | 장식용 배경 도형 |
| 새 감지가 방금 들어옴 | 카드가 나타날 때마다 통통 튐 |
| 값이 위험 범위에 들어감 | 로고가 계속 회전 |

**움직이는 것이 화면에 3개를 넘으면 시끄럽습니다.** 세어 보세요.

### 11-3. 방법 ① CSS 애니메이션 — 이것부터 쓰세요

**설치 0 · 인터넷 0 · 용량 0.** 전시회장 인터넷이 끊겨도 동작합니다.
`globals.css` 맨 아래에 붙입니다.

```css
/* =========================================================================
   애니메이션 — 상태를 알려줄 때만 씁니다
   ========================================================================= */
@keyframes kit-pulse   { 0%, 100% { opacity: 1 }   50% { opacity: .35 } }
@keyframes kit-breathe { 0%, 100% { transform: scale(1) } 50% { transform: scale(1.15) } }
@keyframes kit-ring {
  0%, 100% { transform: rotate(0) }
  20% { transform: rotate(-14deg) }  40% { transform: rotate(12deg) }
  60% { transform: rotate(-8deg) }   80% { transform: rotate(5deg) }
}
@keyframes kit-slide-in { from { opacity: 0; transform: translateY(-6px) } to { opacity: 1; transform: none } }

/** 기다리는 중 — 연결 대기, 응답 대기 */
.anim-pulse   { animation: kit-pulse 1.6s ease-in-out infinite }
/** 살아 있음 — 센서가 값을 보내는 중 */
.anim-breathe { animation: kit-breathe 2s ease-in-out infinite }
/** 지금 울림 — 알람, 경고 */
.anim-ring    { animation: kit-ring 1.1s ease-in-out infinite; transform-origin: 50% 12% }
/** 방금 들어옴 — 새 알림 (한 번만) */
.anim-in      { animation: kit-slide-in .22s ease-out }

/* 움직임이 불편한 사람을 위해 — 이 블록을 지우지 마세요 (15장) */
@media (prefers-reduced-motion: reduce) {
  .anim-pulse, .anim-breathe, .anim-ring, .anim-in { animation: none }
}
```

**확인된 동작:** `.anim-ring`을 붙인 `<Bell>`의 변형 행렬이
`matrix(0.9995, -0.0322, ...)` → `matrix(0.99999, 0.0040, ...)` 로 실제로 바뀝니다.

### 11-4. 상태에 연결하기 — 핵심

**항상 움직이면 아무 뜻이 없습니다.** 조건을 붙이세요.

```tsx
"use client";
import { Bell, Wifi, WifiOff } from "lucide-react";
import { useScenario } from "@/lib/scenario";

export default function StatusHeader() {
  const { connected, notices } = useScenario();
  const ringing = notices.some((n) => n.level === "alert");

  return (
    <div className="flex items-center gap-3">
      {/* 연결될 때까지만 깜빡입니다 */}
      {connected ? (
        <Wifi className="text-ok h-5 w-5" />
      ) : (
        <WifiOff className="anim-pulse text-warn h-5 w-5" />
      )}

      {/* 경고 알림이 있을 때만 흔들립니다 */}
      <Bell className={`h-5 w-5 ${ringing ? "anim-ring text-bad" : "text-muted"}`} />
    </div>
  );
}
```

| 나쁜 예 | 좋은 예 |
|---|---|
| `<Wifi className="anim-pulse" />` — 항상 깜빡임 | `{!connected && <WifiOff className="anim-pulse" />}` |
| `<Bell className="anim-ring" />` — 항상 흔들림 | `className={ringing ? "anim-ring" : ""}` |

### 11-5. 무료 애니메이션 아이콘 — 어디서 구하나

| 출처 | 라이선스 | 인터넷 필요 | 권함 |
|---|---|---|---|
| **Lucide + 위 CSS** | ISC (무료·출처 표기 불필요) | 필요 없음 | ⭐ **기본으로 이것** |
| **LottieFiles** 무료 애니메이션 | 항목마다 다름 — **받기 전에 확인** | 받을 때만 (파일로 저장) | 전시회 화면 1~2개 |
| Lordicon 무료 | 무료 항목은 **출처 표기 필요** | 매번 필요 (CDN) | ⚠️ 학교 방화벽에서 막힐 수 있음 |
| SVG Spinners | MIT | 필요 없음 | 로딩 표시에 좋음 |

> ⚠️ **CDN을 쓰는 방식은 전시회에서 위험합니다.** 인터넷이 끊기면 아이콘이 안 나옵니다.
> 실제로 이 저장소를 만든 환경에서도 `cdn.lordicon.com` 접속이 막혔습니다.
> **파일로 받아서 프로젝트 안에 넣는 방식**을 쓰세요.

### 11-6. 방법 ② Lottie — 꼭 필요할 때만

큰 화면 가운데에 **하나 정도** 넣는 용도입니다. 아이콘마다 쓰지 마세요.

```bash
cd frontend
npm install lottie-react
```

애니메이션 JSON 파일을 `frontend/public/anim/` 에 저장합니다.

#### ⚠️ AI가 알려주는 사용법은 대부분 틀립니다

`lottie-react`는 **3버전에서 사용법이 완전히 바뀌었습니다.**
인터넷 글과 AI 답변은 거의 다 2버전 기준입니다.

| | 2버전 (인터넷·AI가 알려주는 것) | **3버전 (지금 설치되는 것)** |
|---|---|---|
| 불러오기 | `import Lottie from "lottie-react"` | `import { LottieLight } from "lottie-react"` |
| 데이터 넘기기 | `animationData={data}` | `src={data}` |
| 2버전대로 쓰면 | `Export default doesn't exist in target module` **빌드 실패** | |

올바른 코드입니다.

```tsx
"use client";
import { LottieLight } from "lottie-react";
import wave from "@/public/anim/wave.json";

export default function HeroAnimation() {
  return <LottieLight src={wave} className="h-32 w-32" autoplay loop />;
}
```

| 불러올 이름 | 언제 |
|---|---|
| `LottieLight` | **보통 이것.** 가장 가벼움 |
| `LottieSvg` | 표현식이 든 애니메이션 |
| `Lottie` | 전부 필요할 때 (가장 무거움) |

#### 넣기 전에 생각할 것

| | |
|---|---|
| 설치 용량 | 약 768 KB (lucide는 이미 있으므로 추가 0) |
| 우리 화면에 정말 필요한가 | 대부분의 팀은 **11-3으로 충분합니다** |
| 라이선스 확인했나 | 받은 곳의 라이선스를 캡처해 두세요 |

### 11-7. 자가 점검

```bash
cd frontend && npx next build
```

| 확인 | |
|---|---|
| ☐ | 움직이는 것이 화면에 3개 이하인가 |
| ☐ | 움직이는 것이 **전부 상태와 연결**되어 있는가 (항상 움직이는 것이 없는가) |
| ☐ | `prefers-reduced-motion` 블록을 지우지 않았는가 |
| ☐ | 아이콘만 있는 버튼에 `aria-label`이 있는가 |
| ☐ | 이모지를 기능 아이콘으로 쓰지 않았는가 |
| ☐ | 인터넷을 끊어도 아이콘이 나오는가 (F12 → Network → Offline) |

---
## 12. 9단계 · 페이지 다듬기

### 12-1. 순서

```text
① 정보 계층 (무엇을 가장 크게)  →  ② 배치  →  ③ 글자  →  ④ 여백
      →  ⑤ 컴포넌트  →  ⑥ 색  →  ⑦ 아이콘  →  ⑧ 인터랙션
```

**색부터 만지지 마세요.** 배치와 글자 크기가 정리되면 색은 조금만 써도 됩니다.

### 12-2. `app/page.tsx`에서 할 일

지금 `app/page.tsx`에는 `ScenarioPlaceholder`(점선 안내 카드)가 들어 있습니다.
이것이 **"우리 팀 시나리오 자리"** 입니다.

1. `ScenarioPlaceholder` 컴포넌트와 그것을 부르는 줄을 **지웁니다**
2. 그 자리에 5-2에서 고른 **3초 안에 보여야 할 것**을 가장 크게 넣습니다
3. `SlotGrid`와 `VisionLogCard`는 **그대로 둡니다** (키트가 그려 줍니다)

### 12-3. 예시 — study 팀 "3초 카드"

```tsx
<section className="card mb-8 p-6">
  <p className="text-muted text-sm">지금 열람실</p>
  <p className="text-ink mt-1 text-6xl font-bold tabular-nums">
    {occupied}
    <span className="text-muted text-2xl font-normal"> / {total}</span>
  </p>
  <p className="text-muted mt-2 text-base">자리가 차 있습니다</p>
</section>
```

| 이 예시가 지킨 것 | |
|---|---|
| 숫자를 가장 크게 (`text-6xl`) | 3초 규칙 |
| `tabular-nums` | 숫자가 바뀔 때 폭이 흔들리지 않음 |
| `.card` · `text-ink` · `text-muted` | 스타일을 바꾸면 같이 바뀜 |
| 색을 안 씀 | 숫자 크기만으로 충분 |

### 12-4. 페이지 개선 프롬프트

```text
[역할] 너는 시니어 프론트엔드 개발자이자 UI/UX 디자이너다.

[상황]
- Next.js 16 + React 19 + TypeScript + Tailwind CSS v4
- 마이스터고 2학년 IoT 작품의 대시보드 (app/page.tsx)
- 사용자: (5-1에서 적은 것)
- 보는 거리: (5-1에서 적은 것)
- 고른 디자인 스타일: (6장에서 고른 것)

[목표]
사용자가 3초 안에 "(5-2에서 고른 것)"을 파악할 수 있게 한다.

[반드시 지킬 것]
- 색은 토큰만 쓴다: bg-bg, bg-surface, text-ink, text-muted,
  bg-brand, text-on-brand, text-ok/warn/bad, border-line
- 카드는 .card 클래스를 쓴다 (rounded-xl, shadow-sm 등을 직접 쓰지 않는다)
- slate-500 같은 Tailwind 기본 색 이름을 쓰지 않는다
- 아이콘은 lucide-react만 쓴다. 이모지를 아이콘으로 쓰지 않는다
- 애니메이션은 상태와 연결된 것만 쓴다

[바꾸지 말 것]
- lib/scenario.ts, lib/slots.ts, lib/api.ts (공통 SDK)
- components/kit/ 안의 파일
- useScenario()가 주는 값의 이름과 형태
- API 호출, 데이터 구조, 라우팅

[출력 형식]
1. 먼저 현재 문제점 5개 이내
2. 그다음 바꿀 계획
3. 마지막에 전체 파일 내용 (일부만 주지 말 것)
   - 파일은 3개 이하로
   - +, - 같은 diff 기호를 붙이지 말 것
```

---

## 13. 10단계 · 반응형

### 13-1. 폭만 줄이는 것이 아닙니다

화면이 좁아지면 **정보 순서를 바꿉니다.**

| | 넓은 화면 | 좁은 화면 |
|---|---|---|
| 배치 | 3열 | 1열 |
| 덜 중요한 정보 | 같이 보임 | 접어두기 |
| 표 | 표 그대로 | 카드 목록으로 |
| 글자 | 기본 | 조금 작게 |

### 13-2. Tailwind 반응형은 "작은 화면이 기본"

```tsx
{/* 기본(모바일) 1열 → 640px 이상 2열 → 1024px 이상 3열 */}
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
```

| 접두사 | 언제부터 | 기기 |
|---|---|---|
| (없음) | 항상 | 휴대폰 |
| `sm:` | 640px~ | 큰 휴대폰·작은 태블릿 |
| `md:` | 768px~ | 태블릿 |
| `lg:` | 1024px~ | 노트북 |

### 13-3. 확인 방법

1. `F12` → 왼쪽 위 기기 아이콘(`Ctrl+Shift+M`)
2. 폭을 **375px**(휴대폰) · **768px**(태블릿) · **1280px**(노트북)로 바꿔 봅니다

| 확인 | |
|---|---|
| ☐ | 가로 스크롤이 생기지 않는가 (가장 흔한 문제) |
| ☐ | 글자가 잘리지 않는가 |
| ☐ | 버튼을 손가락으로 누를 수 있는가 (최소 44×44px) |
| ☐ | 375px에서 제목이 3줄 넘게 늘어지지 않는가 |

> **가로 스크롤이 생겼다면** 대부분 고정 폭(`w-[800px]`)이나 긴 영문 문자열 때문입니다.
> `max-w-full` · `overflow-x-auto` · `break-words`로 잡습니다.

---

## 14. 11단계 · 인터랙션

### 14-1. 화면에는 5가지 상태가 있습니다

정상 화면만 만들면 **실제로 쓸 때 대부분 깨집니다.**

| 상태 | 언제 | 보여줄 것 |
|---|---|---|
| 로딩 | 아직 안 왔을 때 | "불러오는 중" (빈 화면 금지) |
| 정상 | 값이 있을 때 | 데이터 |
| **빈 상태** | 값이 0개일 때 | 왜 비었는지 + **무엇을 하면 되는지** |
| **오류** | 실패했을 때 | 무엇이 잘못됐는지 + 어떻게 고치는지 |
| 연결 끊김 | 백엔드가 죽었을 때 | "연결 대기 중" |

> **전시회에서 심사위원이 보는 것은 대부분 "빈 상태"와 "오류"입니다.**
> 라즈베리파이를 아직 안 켠 상태로 화면을 열기 때문입니다. 여기를 잘 만드세요.

`app/page.tsx`의 `SlotGrid`에는 이미 `emptyHint`가 들어 있습니다. 문구를 우리 팀 것으로 바꾸세요.

### 14-2. 손이 닿는 곳마다 반응

```tsx
<button
  type="button"
  className="bg-brand text-on-brand rounded-pill px-4 py-2
             transition-colors hover:opacity-90
             disabled:cursor-not-allowed disabled:opacity-50"
  disabled={!connected}
>
  불 켜기
</button>
```

| 상태 | 반드시 보여야 함 |
|---|---|
| `hover` | 마우스를 올렸을 때 |
| `focus-visible` | 키보드로 이동했을 때 (7-3에서 전역 설정함) |
| `disabled` | 지금 누를 수 없을 때 — **왜 안 되는지도** 적어 주세요 |

### 14-3. 시간 규칙

| 무엇 | 길이 |
|---|---|
| 색·투명도 변화 | 0.15 ~ 0.2초 |
| 나타나기 | 0.2 ~ 0.3초 |
| 반복 애니메이션 | 1 ~ 2초 |

**0.5초를 넘기지 마세요.** 느리다고 느낍니다.

---

## 15. 12단계 · 접근성

### 15-1. 왜 하나

"장애인을 위해"만이 아닙니다. **전시회에서 실제로 생기는 일**입니다.

- 부스가 밝아서 화면이 잘 안 보임 → **명암비**
- 마우스가 없어서 키보드로 시연 → **키보드 이동**
- 심사위원이 화면을 확대해서 봄 → **글자 크기**

### 15-2. 체크리스트

| 확인 | 어떻게 |
|---|---|
| ☐ 키보드로 전부 쓸 수 있나 | `Tab`만으로 끝까지 눌러 보기 |
| ☐ 지금 어디 있는지 보이나 | 7-3의 `:focus-visible`이 살아 있는지 |
| ☐ 아이콘만 있는 버튼에 라벨 | `aria-label="알림 닫기"` |
| ☐ 명암비 4.5:1 이상 | 아래 15-3 |
| ☐ 제목 순서 | `h1` → `h2` → `h3` (건너뛰지 않기) |
| ☐ 색만으로 뜻을 전하지 않기 | 빨강 = 위험 → **"위험"이라는 글자도** 넣기 |
| ☐ 움직임 줄이기 설정 존중 | 11-3의 `prefers-reduced-motion` |

### 15-3. 명암비 확인

1. `F12` → Elements → 글자가 있는 요소 선택
2. Styles 패널의 `color` 옆 색 네모 클릭
3. **Contrast ratio** 숫자를 봅니다

| 값 | 판정 |
|---|---|
| 4.5 : 1 이상 | ✅ 통과 (본문) |
| 3 : 1 이상 | ✅ 통과 (24px 이상 큰 글자) |
| 그 미만 | ❌ 색을 진하게 |

> 6장의 5가지 스타일은 **전부 통과하도록 계산해서** 골랐습니다.
> 색을 직접 바꿨다면 여기서 다시 확인하세요.

### 15-4. 아이콘 버튼

```tsx
{/* ❌ 읽어 주는 도구가 "버튼"이라고만 말합니다 */}
<button><X className="h-4 w-4" /></button>

{/* ✅ */}
<button type="button" aria-label="알림 닫기">
  <X className="h-4 w-4" />
</button>
```

---

## 16. 13단계 · 디자인 QA

### 16-1. 최종 검수 프롬프트

```text
[역할] 너는 시니어 UI/UX 디자이너이자 디자인 QA 엔지니어다.

[상황] 올린 컨텍스트 팩은 마이스터고 2학년 IoT 작품의 프론트엔드다.
Next.js 16 + React 19 + TypeScript + Tailwind CSS v4.
디자인 스타일은 "(고른 것)"이고, globals.css의 토큰으로 관리한다.

[할 일] 상용 서비스 수준의 UI/UX 관점에서 검수하라.

확인 항목:
1. 정보 계층      2. 타이포그래피     3. 색 일관성
4. 여백 일관성    5. 컴포넌트 일관성   6. 반응형
7. 접근성         8. 아이콘 일관성     9. 로딩/빈/오류 상태
10. 애니메이션이 상태와 연결되어 있는가

특히 이런 것을 찾아라:
- Tailwind 기본 색 이름(slate-500 등)을 직접 쓴 곳 → 토큰으로 바꿔야 함
- .card 대신 rounded-xl border bg-white를 직접 쓴 곳
- 항상 움직이는 애니메이션
- 이모지를 기능 아이콘으로 쓴 곳
- 카드 안에 카드가 들어간 곳
- aria-label이 없는 아이콘 버튼

[출력]
High / Medium / Low로 나누고, 각 항목에 파일명과 줄 내용을 적어라.
코드는 아직 주지 마라. 목록만 먼저 보여 줘라.
```

### 16-2. 받은 목록에서 High부터 하나씩

한꺼번에 다 고치라고 하지 마세요. **하나 고치고 → 빌드 → 화면 확인 → 다음.**

### 16-3. 직접 찾아보는 명령

```bash
cd frontend

# 토큰 대신 기본 색 이름을 쓴 곳 (0이 목표)
grep -rn "slate-\|gray-\|blue-600\|zinc-" app/ components/team/ | wc -l

# .card 대신 직접 그린 카드
grep -rn "rounded-xl\|shadow-sm" app/ components/team/

# aria-label 없는 아이콘 버튼 후보 — 눈으로 확인하세요
grep -rn "<button" app/ components/team/ | grep -v "aria-label"
```

> `components/kit/`은 키트 파일이므로 세지 않습니다.

---

## 17. 채팅형 AI에게 부탁하는 법

### 17-1. 컨텍스트 팩 만들기

```bash
cd /path/to/agent-vibe-coding-starter-kit2
python tools/context_pack.py frontend
```

`context_packs/context_pack_frontend.md` 파일 하나가 생깁니다.
**채팅창에 이 파일을 올리고** 질문하세요.

| 확인 | |
|---|---|
| ☐ | 파일을 **새 대화마다** 다시 올리기 (AI는 지난 대화를 기억하지 못합니다) |
| ☐ | 코드를 고친 뒤에는 **다시 만들어서** 올리기 |
| ☐ | `.env.local` 같은 비밀 파일은 **절대 올리지 않기** (생성기가 걸러 주지만 한 번 더 확인) |

### 17-2. 프롬프트 기본 틀

```text
[역할]     너는 시니어 프론트엔드 개발자이자 UI/UX 디자이너다.
[상황]     Next.js 16 + React 19 + TypeScript + Tailwind CSS v4
           마이스터고 2학년 IoT 작품 / 사용자 · 보는 거리 · 고른 스타일
[목표]     무엇을 개선할 것인가 (한 문장)
[바꿀 것]  파일과 범위를 구체적으로
[바꾸지 말 것]
           lib/, components/kit/, API, 데이터 구조, 라우팅
[디자인]   토큰만 사용 / .card 사용 / 아이콘은 lucide / 애니메이션은 상태 연결
[진행]     분석 → 계획 → 구현 순서. 계획을 먼저 보여 줄 것
[출력]     파일 3개 이하, 전체 내용, diff 기호 금지
```

### 17-3. 나쁜 요청과 좋은 요청

| ❌ | 왜 나쁜가 |
|---|---|
| "홈페이지 예쁘게 만들어 줘" | 기준·사용자·범위·금지가 전부 없음 |
| "전체 다 고쳐 줘" | 어디가 바뀌었는지 확인 불가 |
| "최신 라이브러리 써서 멋지게" | 설치할 수 없는 것을 제안받음 |

| ✅ | 왜 좋은가 |
|---|---|
| "app/page.tsx의 '우리 팀 시나리오 자리'에 좌석 6칸 현황을 넣어 줘. 3m 떨어져서 봐야 하니 숫자를 가장 크게. 색은 토큰만. lib/과 components/kit/은 건드리지 마." | 파일·목표·거리·제약·금지가 전부 있음 |

### 17-4. AI가 이렇게 말하면 멈추세요

| AI가 한 말 | 왜 위험한가 | 어떻게 하나 |
|---|---|---|
| "tailwind.config.js를 만들어서..." | v4는 그 파일을 안 씁니다 | "Tailwind v4다. `@theme`로 해 줘" |
| "`:root`에 `--color-primary`를 넣고..." | 유틸리티가 안 만들어집니다 (7-1) | "`@theme inline` 안에 넣어 줘" |
| "`npm install lucide-react`" | 이미 있습니다 | 무시하고 그냥 import |
| "`import Lottie from 'lottie-react'`" | 3버전은 named export (11-6) | "`import { LottieLight }`로 해 줘" |
| "`lib/scenario.ts`를 이렇게 바꾸면..." | **4팀 공통 파일** | "그 파일은 못 고친다. 다른 방법으로" |
| "먼저 프로젝트 구조를 보여 주세요" | 컨텍스트 팩을 안 읽은 것 | 팩을 다시 올리고 "올린 파일에 있다" |

### 17-5. 받은 코드를 붙여넣기 전에

| 확인 | |
|---|---|
| ☐ | 파일 **전체**를 받았나, 일부만 받았나 (일부면 "전체로 다시" 요청) |
| ☐ | 줄 앞에 `+` `-` 기호가 붙어 있지 않나 (붙어 있으면 지우고 넣기) |
| ☐ | `lib/` · `components/kit/` 파일이 섞여 있지 않나 |
| ☐ | 붙여넣은 **직후 바로** `npx next build` 했나 |

> **한 번에 파일 하나씩.** 3개를 한꺼번에 넣고 빌드가 깨지면 원인을 못 찾습니다.

---

## 18. 제출 전 체크리스트

### 디자인

| ☐ | |
|---|---|
| ☐ | 6장에서 팀이 스타일을 **골랐고 그 이유를 적었나** (6-6 표) |
| ☐ | `StyleSwitcher`를 **지웠나** |
| ☐ | 색을 토큰으로만 쓰나 (16-3의 `grep` 결과가 0) |
| ☐ | 글자 크기가 5종류 이하인가 |
| ☐ | 여백 종류가 4가지 이하인가 |
| ☐ | 카드 안에 카드가 없는가 |

### 글꼴

| ☐ | |
|---|---|
| ☐ | 한글 글꼴이 실제로 적용됐나 (F12 → Computed → `font-family`에 `Noto Sans KR`) |
| ☐ | 보는 거리에 맞는 글자 크기인가 (8-5) |

### 아이콘 · 애니메이션

| ☐ | |
|---|---|
| ☐ | lucide 하나만 쓰나 |
| ☐ | 이모지를 기능 아이콘으로 쓰지 않았나 |
| ☐ | 움직이는 것이 3개 이하이고 **전부 상태와 연결**됐나 |
| ☐ | 인터넷을 끊어도 아이콘이 나오나 |

### 반응형 · 접근성

| ☐ | |
|---|---|
| ☐ | 375px에서 가로 스크롤이 없나 |
| ☐ | `Tab`만으로 전부 쓸 수 있나 |
| ☐ | 아이콘 버튼에 `aria-label`이 있나 |
| ☐ | 명암비가 4.5:1 이상인가 |

### 기능 (디자인을 고치다 깨뜨리지 않았는지)

| ☐ | |
|---|---|
| ☐ | `npx next build` 성공 |
| ☐ | `npm run lint` 통과 |
| ☐ | 라즈베리파이를 켜면 부품 카드가 나오나 |
| ☐ | 카메라 감지가 로그에 들어오나 |
| ☐ | 액추에이터 버튼이 실제로 동작하나 |
| ☐ | 백엔드를 껐을 때 "연결 대기 중"이 나오나 |

---

## 19. 안 될 때 — 증상표

| 증상 | 원인 | 어떻게 |
|---|---|---|
| `bg-brand`를 썼는데 **색이 안 바뀜**. 에러도 없음 | `:root`에 적음 | `@theme inline` 안으로 옮기기 (7-1) |
| `data-style`을 바꿔도 안 바뀜 | `@theme inline`이 아니라 `@theme` | `inline`을 붙이고 값은 `var(--ui-*)`로 (7-2) |
| `console`을 골랐는데 **배경이 안 어두워짐** | `<body>`에 `bg-slate-50`이 남음 | 그 className 지우기 (7-4) |
| 한글 글꼴이 안 바뀜 | `@theme`의 `--font-sans`에 연결 안 함 | 8-2·8-3 |
| 글자가 내 PC와 발표 PC에서 다름 | 한글 글꼴을 안 넣음 | 8-3 |
| `Export default doesn't exist in target module` | lottie-react 2버전 문법 | `import { LottieLight }` (11-6) |
| 가로 스크롤이 생김 | 고정 폭 · 긴 영문 | `max-w-full` · `break-words` (13-3) |
| 카드가 너무 많아 답답함 | 전부 카드로 만듦 | 10-1의 표대로 나누기 |
| 화면이 계속 깜빡여 어지러움 | 애니메이션이 상태와 연결 안 됨 | 11-4 |
| 빌드는 되는데 화면이 빈 화면 | `"use client"` 빠짐 | 파일 첫 줄에 `"use client";` |
| AI가 준 코드에 `+` `-`가 붙어 있음 | diff 형식으로 줌 | 기호 지우고 넣기. 다음부터 "diff 금지" 명시 (17-2) |
| 고치고 나니 부품 카드가 사라짐 | `SlotGrid`를 지움 | `app/page.tsx`에 되살리기 |
| 스타일을 바꿨는데 `/kit` 화면만 그대로 | `components/kit/`은 아직 기본 색 | 정상입니다. 키트 파일은 고치지 않습니다 |

---

## 20. 교사용 — 지도 포인트와 평가

### 20-1. AI가 만든 코드를 그대로 제출하게 하지 않기

학생에게 계속 묻습니다.

```text
왜 이 스타일을 골랐는가?            왜 이 정보를 가장 크게 했는가?
왜 이 색을 여기에 썼는가?           왜 이 아이콘인가?
이 애니메이션은 무엇을 알려주는가?   모바일에서는 어떻게 바뀌는가?
데이터가 없으면 무엇이 보이는가?     네트워크가 끊기면 어떻게 보이는가?
```

이 질문에 답할 수 있으면 **AI 코드 생성이 아니라 프론트엔드 설계**를 한 것입니다.

### 20-2. 이 교재에서 학생이 반드시 겪어야 할 세 가지 실패

일부러 겪게 하면 학습 효과가 큽니다.

| 실패 | 왜 시키나 | 어디 |
|---|---|---|
| `:root`에 토큰을 넣고 색이 안 바뀌는 경험 | **에러 없는 실패**를 스스로 진단해 보게 | 7-1 |
| 글꼴을 선언만 하고 적용이 안 되는 경험 | "선언 ≠ 적용"을 체감 | 8-2 |
| AI가 알려준 lottie 2버전 문법으로 빌드가 깨지는 경험 | **AI가 틀릴 수 있다**는 것을 확인 | 11-6 |

### 20-3. 평가 루브릭 (100점)

| 영역 | 배점 | A (만점) | C (절반) | F (0점) |
|---|---|---|---|---|
| 스타일 선택의 근거 | 15 | 5가지를 실제 거리에서 비교하고 6-6을 채움 | 골랐지만 이유가 "예뻐서" | 비교 없이 기본값 |
| 토큰 사용 | 20 | 기본 색 이름 0개, `.card` 사용 | 일부만 토큰 | 전부 하드코딩 |
| 정보 계층 | 15 | 3초 안에 핵심이 보임 | 보이지만 찾아야 함 | 무엇이 중요한지 모름 |
| 타이포그래피 | 10 | 한글 글꼴 적용 + 거리에 맞는 크기 | 적용은 됨 | 글꼴 미적용 |
| 아이콘·애니메이션 | 15 | 전부 상태와 연결 | 일부가 항상 움직임 | 장식용만 있음 |
| 반응형 | 10 | 375px에서 정상 | 약간 깨짐 | 가로 스크롤 |
| 접근성 | 10 | 체크리스트 전부 | 절반 | 키보드 사용 불가 |
| 기능 유지 | 5 | 빌드·린트·동작 전부 정상 | 빌드만 됨 | 기능이 깨짐 |

### 20-4. 확인 명령 (채점용)

```bash
cd frontend

npx next build                                            # 빌드
npm run lint                                              # 린트
grep -rn "slate-\|gray-\|blue-600" app/ components/team/ | wc -l   # 0이어야 함
grep -rn "StyleSwitcher" app/                             # 제출본에 없어야 함
grep -o '\.bg-brand{[^}]*}' .next/static/chunks/*.css     # 토큰이 살아 있는지
```

### 20-5. 수업 배분 (참고)

| 차시 | 내용 | 교재 |
|---|---|---|
| 1 | 화면 분석 · 사용자 정의 | 4~5장 |
| 2 | **스타일 5가지 비교 · 팀 결정** | 6장 |
| 3 | 토큰 적용 · 한글 글꼴 | 7~8장 |
| 4 | 레이아웃 · 컴포넌트 | 9~10장 |
| 5 | **아이콘 · 애니메이션** | 11장 |
| 6 | 페이지 다듬기 | 12장 |
| 7 | 반응형 · 인터랙션 · 접근성 | 13~15장 |
| 8 | 디자인 QA · 상호 평가 | 16·18장 |

---

## 부록 · 기억할 한 문장

> **AI에게 예쁜 화면을 만들어 달라고 하는 것은 바이브 코딩이 아닙니다.**
>
> **사용자와 문제를 정의하고, 디자인 원칙과 제한 조건을 프롬프트로 전달한 뒤,**
> **AI가 만든 결과를 직접 확인하면서 반복해서 개선하는 것이 바이브 코딩입니다.**

---

| 다음에 볼 것 | |
|---|---|
| 기능을 더 만들고 싶을 때 | [00 · 2차 개발 통합 매뉴얼](00-2차개발-통합-매뉴얼.md) |
| 규약 원문을 확인할 때 | [부록F · IoT 개발 플랫폼 키트 규약](부록F-IoT-개발-플랫폼-키트-규약.md) |
| 전시회 확장 기능 | [04 · 작품전시회 기능확장 로드맵](04-작품전시회-기능확장-아이디어-및-로드맵.md) |
