# 실습: 문 열림 센서 + 경고 부저를 바이브 코딩으로 달기

센서 하나와 액추에이터 하나를 새로 달 때 **누가, 어떤 파일을, 어떤 순서로** 고치는지 처음부터
끝까지 보여 주는 실습입니다. AI에게 부탁하는 문장, AI가 고친 코드, 실행 결과, 그리고 실제로 난
오류와 고치는 과정까지 영상 두 편에 담았습니다.

> 이 실습의 코드는 **karaoke 본 코드에 들어 있지 않습니다.** 부품을 갖춘 학생이 영상을 따라
> 직접 바이브 코딩으로 추가해 보는 연습용입니다. 따라 하다 막히면 `patches/`의 단계별 변경과
> 비교해 보세요. 실제 부스에 달기로 정했다면 AGENTS.md의 팀 정보 표는 학생이 직접 고칩니다.

## 영상

| 편 | 누가 보나 | 길이 | 파일 |
|---|---|---|---|
| ① 라즈베리파이 편 | 라즈베리파이 담당 | 8분 37초 | [`영상/1-라즈베리파이편.mp4`](영상/1-라즈베리파이편.mp4) · 대본 [`.srt`](영상/1-라즈베리파이편.srt) |
| ② 백엔드·프론트엔드 편 | 백엔드·프론트엔드 담당 | 7분 47초 | [`영상/2-백엔드-프론트엔드편.mp4`](영상/2-백엔드-프론트엔드편.mp4) · 대본 [`.srt`](영상/2-백엔드-프론트엔드편.srt) |

- 해설은 화면 아래 **자막**입니다. 소리 해설이 필요하면 아래 [해설 음성 입히기](#해설-음성-입히기)를 보세요.
- 영상 속 코드 변경과 터미널 출력, 관리자 화면은 모두 **실제로 실행해 기록한 것**입니다.
  라즈베리파이 실물 대신 `gpiozero`의 가짜 핀(Mock)으로 실행했습니다 — 실물에서 할 일은 영상 끝에 정리했습니다.

## 만들 것과 완료 기준

**규칙:** 도어락이 잠긴(locked) 상태인데 문이 열려 있으면 경고 부저가 울리고, 문을 닫으면 멈춘다.
이용이 끝났는데 문을 안 닫고 나가면 다음 사람이 비밀번호 없이 들어올 수 있기 때문입니다.

완료 기준 (먼저 정하고, 마지막에 눈으로 확인합니다)

1. 문을 열고 닫으면 관리자 화면의 '문 열림 센서'가 바로 바뀐다
2. 도어락이 잠긴 채 문이 열리면 경고 부저가 울리고, 문을 닫으면 멈춘다
3. 파이를 끄면 부저도 꺼진 안전 상태로 돌아간다

```
문(리드 스위치) ─GPIO23→ 라즈베리파이 ─① POST door_sensor_1/state {value: 1|0}→ 백엔드
                          ▲                                               │ ② check_door_alarm()
                          └──③ GET buzzer_1/desired-state (폴링) ─────────┘
라즈베리파이 ─④ GPIO25→ 경고 부저          백엔드 ─⑤ WebSocket→ 관리자 화면(/admin)
```

## 부품과 배선

| 부품 | 선 | 라즈베리파이 핀 (물리 번호) | 코드의 이름 |
|---|---|---|---|
| 리드 스위치(자석 포함) | 한쪽 선 | 16번 = **GPIO23** | `DOOR_SENSOR_PIN = 23` |
| | 다른 쪽 선 | 14번 = GND | 내부 풀업 사용 — 저항 없음 |
| 액티브 부저 모듈 | S(신호) | 22번 = **GPIO25** | `BUZZER_PIN = 25` |
| | VCC | 17번 = 3.3V | 모듈 설명서의 전압 확인 |
| | GND | 20번 = GND | |

- 코드에는 **BCM 번호**(GPIO23, GPIO25)를 씁니다. 물리 핀 번호와 헷갈리는 것이 가장 흔한 실수입니다.
- 배선은 **전원을 끄고**, 처음 실기기에 연결할 때는 **선생님과 함께** 합니다 (`.agents/rules/hardware-rules.md`).

## 단계별 진행

AI에게 부탁할 때는 AGENTS.md에 적힌 대로 **역할 지정 + 참고 규칙/스킬**을 붙입니다. 아래 문장은 영상에서 쓴 그대로입니다.

### 라즈베리파이 담당 (① 편)

| 단계 | AI에게 부탁한 말 (요약) | 바뀌는 파일 | 확인 | 패치 |
|---|---|---|---|---|
| P1 | "너는 이 프로젝트의 hardware-agent다. hardware-rules.md와 hardware-integration을 참고해. 문 열림 센서(GPIO23, 내부 풀업)와 경고 부저(GPIO25)를 pi 폴더에 추가해 줘. 핀 번호는 booth_pins.py에만, 문 상태가 바뀔 때만 door_sensor_1로 보고(1=열림, 0=닫힘), buzzer_1은 desired-state 폴링, 관련 없는 파일은 건드리지 마" | `pi/booth_pins.py`, `pi/main.py` | `GPIOZERO_PIN_FACTORY=mock python main.py` | [`pi-1-핀과-데몬.patch`](patches/pi-1-핀과-데몬.patch) |
| P2 | "test_hardware_gpio.py 자가진단에도 문 센서 읽기와 부저 세 번 울리기 검사를 추가해 줘" | `pi/test_hardware_gpio.py` | `python test_hardware_gpio.py` (실기기) | [`pi-2-배선-자가진단.patch`](patches/pi-2-배선-자가진단.patch) |
| P3 | "부품이 오기 전에 연습할 수 있게, main.py를 그대로 돌리면서 키보드로 문 센서를 흉내 내는 mock_door.py를 만들어 줘" | `pi/mock_door.py`, `pi/02_karaoke_daemon_mock.py` | `python mock_door.py` → `o`/`c`/`q` + Enter | [`pi-3-부품-없이-연습.patch`](patches/pi-3-부품-없이-연습.patch) |

### 백엔드 담당 (② 편)

| 단계 | AI에게 부탁한 말 (요약) | 바뀌는 파일 | 확인 | 패치 |
|---|---|---|---|---|
| B1 | "너는 이 프로젝트의 backend-agent다. iot-endpoint-generator와 db-rules.md를 참고해. door_sensor_1(kind reed)과 buzzer_1(kind buzzer)을 등록해 줘. 시드 세 곳을 같이 맞추고, 문 센서 이력은 sensor_readings에서" → 시행착오 ①을 거쳐 `mock_provider.py`까지 | `backend/db/database.py`, `init.sql`, `init_supabase.sql`, `backend/iot/mock_provider.py`, `backend/routers/devices.py` | 서버 재시작 직후 `curl … /api/devices/buzzer_1/control` 이 200 | [`be-1-기기-등록.patch`](patches/be-1-기기-등록.patch) |
| B2 | "도어락이 잠금인데 door_sensor_1이 열림(1)이면 buzzer_1 on, 아니면 off. BoothService에 check_door_alarm()으로 만들고, 문 센서 보고·이용 종료·키패드 인증 때 불러. 부저가 바뀌면 WebSocket으로 알려 줘" → 시행착오 ②를 거쳐 고침 | `backend/services/booth_service.py`, `backend/routers/devices.py` | `curl -X POST …/door_sensor_1/state -d '{"value":1,"unit":"door_open"}'` 뒤 `buzzer_1/desired-state` 가 on | [`be-2-문-열림-경고-규칙.patch`](patches/be-2-문-열림-경고-규칙.patch) |

### 프론트엔드 담당 (② 편)

| 단계 | AI에게 부탁한 말 (요약) | 바뀌는 파일 | 확인 | 패치 |
|---|---|---|---|---|
| F1 | "너는 이 프로젝트의 frontend-agent다. ui-ux-rules.md와 dashboard-ui-design을 참고해. VirtualBoothSimulator.tsx의 PIR 줄 아래에 문 열림 센서와 경고 부저를 보여 주고, 직접 제어에 '경고 부저 울리기/끄기'를 추가해 줘. 기존 색 토큰만, 아이콘은 lucide-react, current_value가 1이면 열림" | `frontend/components/booth/VirtualBoothSimulator.tsx` | `npm run build` | [`fe-1-관리자-화면.patch`](patches/fe-1-관리자-화면.patch) |
| F2 | 시행착오 ③ — "문을 열면 '경고 부저 울림'은 바로 바뀌는데 '문 열림 센서'는 새로고침해야 바뀌어. 왜 그래?" | `frontend/hooks/useBoothData.ts` | 파이와 함께 돌려 새로고침 없이 바뀌는지 | [`fe-2-실시간-반영.patch`](patches/fe-2-실시간-반영.patch) |

## 영상에 나온 시행착오

| # | 증상 (실제 출력) | 원인 | 고친 곳 |
|---|---|---|---|
| 파이 ① | `gpiozero.exc.GPIOPinInUse: pin GPIO17 is already in use` | 문 센서 핀을 도어락이 쓰는 17번으로 적음 | `booth_pins.py` 23번, 선도 16번 핀 |
| 파이 ② | `🔍 [부품 없음 404] door_sensor_1: devices 테이블에 없는 id 입니다.` | 백엔드에 기기 등록 전 | 백엔드 담당과 순서 맞추기 (B1) |
| 파이 ③ | `⚠️ 보고 실패 (코드 401)` | `pi/.env`의 `DEVICE_API_KEY`가 백엔드와 다름 | 두 `.env` 값을 똑같이 |
| 백엔드 ① | 재시작 직후 `404 Unknown device_id: buzzer_1`, 한 번 조회한 뒤에는 됨 | 새 기기가 DB에만 있고 `mock_provider.py`의 `_devices` 사전에 없음 | 사전에 두 기기 추가 |
| 백엔드 ② | 문 열림을 보고했는데 `buzzer_1` 목표가 `off` | 새 DB의 도어락은 `desired_state`가 `null` → 규칙 조건이 거짓 | 비어 있으면 `current_state`를 봄 |
| 프론트 ③ | 부저는 바로 '울림', 문 센서는 새로고침해야 '열림' | `useBoothData.ts`가 WebSocket `sensor_reading`을 처리하지 않음 | `sensor_reading` 분기 추가 |

## 패치로 따라 하기 · 비교하기

저장소 맨 위 폴더에서 (karaoke 브랜치 기준):

```bash
# 미리 확인 — 아무 출력이 없으면 깨끗하게 들어갑니다
git apply --check docs/실습-문센서-부저/patches/pi-1-핀과-데몬.patch
# 적용
git apply docs/실습-문센서-부저/patches/pi-1-핀과-데몬.patch
# 되돌리기
git apply -R docs/실습-문센서-부저/patches/pi-1-핀과-데몬.patch
```

일곱 개를 `pi-1 → pi-2 → pi-3 → be-1 → be-2 → fe-1 → fe-2` 순서로 모두 적용하면 영상에서 실행한
코드와 똑같아집니다 (깨끗한 karaoke 체크아웃에서 확인함). 파이·백엔드·프론트 패치는 서로 다른 파일을
고치므로 자기 담당 것만 적용해도 됩니다.

## 부품 없이 연습하기 (Mock)

```bash
cd pi
# 라즈베리파이가 아닌 PC라면 먼저: pip install gpiozero requests python-dotenv
python mock_door.py          # o + Enter = 문 열기, c + Enter = 문 닫기, q + Enter = 끝내기
```

- `mock_door.py`는 `main.py`를 그대로 실행하면서 GPIO만 가짜로 바꿉니다. 폴링·보고·부저 코드는 진짜로 돕니다.
- `main.py`만 가짜 핀으로 돌려 보려면: Linux·macOS `GPIOZERO_PIN_FACTORY=mock python main.py`,
  Windows PowerShell `$env:GPIOZERO_PIN_FACTORY="mock"; python main.py`
- `test_hardware_gpio.py`는 `lgpio`를 불러오므로 라즈베리파이에서 실행합니다.

## 해설 음성 입히기

영상에는 소리 해설이 없습니다 (영상을 만든 환경에서 한국어 음성 합성 서비스에 접속할 수 없었습니다).
인터넷이 되는 학교 PC에서 다음을 실행하면 자막 대본을 읽는 해설 음성이 들어간 영상이 만들어집니다.

```bash
pip install edge-tts            # ffmpeg 도 설치되어 있어야 합니다
python docs/실습-문센서-부저/voiceover.py docs/실습-문센서-부저/영상/1-라즈베리파이편.mp4
# → 영상/1-라즈베리파이편-해설.mp4   (남성 목소리: --voice ko-KR-InJoonNeural)
```

- 자막이 떠 있는 동안 다 읽도록 문장마다 읽는 빠르기를 맞춥니다.
- `--dry-run`을 붙이면 음성 대신 신호음으로 시각만 맞춰 봅니다 (인터넷 없이 시험).
- 직접 녹음하고 싶다면 `.srt` 파일을 대본으로 읽으며 녹음해 영상 편집기에서 붙이면 됩니다.

## 영상 다시 만들기

영상 제작 소스(장면 대본, 실행 기록, 화면 렌더러)는 [`media-src/tutorial-door-buzzer`](../../media-src/tutorial-door-buzzer/README.md)에 있습니다.
자막 문장을 고치려면 `episodes.py`를 고친 뒤 `build_video.py`를 다시 실행합니다.
