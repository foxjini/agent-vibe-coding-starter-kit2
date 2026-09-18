# 스마트 금융 보안 ATM — 실행 및 시연 가이드

> 코드를 받은 뒤 처음부터 끝까지 직접 돌려 보는 순서다.
> AI가 만든 코드는 **반드시 직접 실행해서 눈으로 확인한다** (AGENTS.md AI 사용 원칙).

---

## 1. 준비 — `.env` 채우기

세 폴더의 `.env.example`을 각각 `.env`로 복사한 뒤 값을 채운다.
`.env`는 커밋되지 않는다 (`.gitignore`).

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
cp pi/.env.example pi/.env
```

반드시 직접 만들어 넣어야 하는 값 두 가지:

```bash
# JWT_SECRET (backend/.env) — 32바이트 이상
python -c "import secrets; print(secrets.token_urlsafe(48))"

# DEVICE_API_KEY (backend/.env와 pi/.env에 같은 값)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> 실제 시크릿 값을 AI 채팅에 붙여넣지 않는다. 한 번이라도 붙여넣었다면 노출된 것으로
> 보고 즉시 새로 만든다 (`.agents/rules/security-rules.md`).

---

## 2. 백엔드 (FastAPI + MySQL)

### 2-1. DB 초기화
XAMPP나 MySQL 서버를 켠 뒤 스키마를 만든다.
```bash
mysql -u root -p < backend/db/init.sql
```

### 2-2. 패키지 설치와 시연 데이터
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
source venv/bin/activate
pip install -r requirements.txt

python -m db.seed      # 시연용 계정·채팅·문자·장치 생성
```
`seed`가 출력하는 계정으로 로그인한다 (`halmeoni` = 사용자, `callcenter` = 상담원).

### 2-3. 실행
```bash
uvicorn main:app --reload --port 8000
```
확인:
- <http://localhost:8000/health> → `{"data":{"status":"ok", ...}}`
- <http://localhost:8000/health/db> → `{"data":{"status":"ok"}}`
- <http://localhost:8000/docs> → API 목록

> **MySQL이 아직 준비되지 않았다면**, `backend/.env`에
> `DATABASE_URL=sqlite:///./smart_atm.db` 한 줄을 넣으면 SQLite로 바로 돌릴 수 있다.
> 규격은 같으므로 나중에 MySQL로 되돌려도 코드는 바꾸지 않는다.

---

## 3. 프론트엔드 (Next.js)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

| 경로 | 화면 | 누가 보는가 |
|---|---|---|
| `/` | 시작 화면 | 사용자 |
| `/login` | 로그인 | 사용자·상담원 |
| `/messages` | 문자 선택 / 직접 입력 | 사용자 |
| `/result/[id]` | 분석 결과 + QR | 사용자 |
| `/atm` | ATM 7인치 화면 | ATM 디스플레이 |
| `/callcenter` | 상담원 확인 화면 | 콜센터 |

> **음성 안내**: `/atm`과 `/result` 화면 오른쪽에 "음성 안내" 버튼이 있다. 한 번 누르면
> 안내 문구를 소리로 읽어 주고, 그 설정은 같은 브라우저에 남는다. 브라우저 내장 기능이라
> 따로 설치할 것도, 인터넷도 필요 없다 (FR-10 노약자 안내).

> `NEXT_PUBLIC_API_BASE_URL`의 호스트와 브라우저 주소창의 호스트를 맞춘다.
> 백엔드 `CORS_ORIGINS`에 없는 주소로 접속하면 화면은 뜨는데 데이터만 안 나온다
> (`localhost`와 `127.0.0.1`은 서로 다른 출처로 취급된다).

---

## 4. 라즈베리파이 ATM 데몬

### 4-1. 먼저 PC에서 Mock으로 검증한다
하드웨어에 붙이기 전에 로직부터 확인한다 (`hardware-rules.md` 안전 수칙 3).
```bash
cd pi
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
`pi/.env`에 `DEVICE_MODE=mock`, `ENABLE_CAMERA=false`를 넣고 실행한다.
```bash
python main.py     # http://localhost:8100
```
카메라 없이 QR 내용을 직접 넣어 볼 수 있다.
```bash
curl -X POST http://localhost:8100/qr \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"session_id\": \"VP-000003\"}"}'
```

### 4-2. 라즈베리파이 5로 옮길 때
**`pi/` 폴더만 복사하면 안 된다.** `pi/main.py`는 장치 제어 Provider를
`backend/iot/`에서 가져오므로, 파이에도 저장소를 통째로 받아야 한다
(`git clone` 또는 `backend/`와 `pi/`를 같은 상위 폴더에 나란히 둔다).
`pi/`만 옮기면 실행하자마자 `ModuleNotFoundError: No module named 'iot'`가 난다.

`backend/` 전체가 부담스러우면 **`backend/iot/` 하나만 옮겨도 된다.** `iot/`는
표준 라이브러리만 쓰기 때문이다. 다만 자리는 정해져 있다 — `pi/main.py`가
`../backend`를 보므로 아래 구조여야 한다.

```
<상위폴더>/
├── pi/            ← 여기서 python main.py
└── backend/
    └── iot/       ← 이것만 있으면 된다
```

**GPIO 라이브러리는 대개 이미 깔려 있다. 설치보다 `venv`가 문제다.**
라즈베리파이 OS 데스크톱 이미지에는 `python3-gpiozero`와 `python3-lgpio`가 처음부터
들어 있다. 그런데 이것들은 **시스템 파이썬**에 있고, `--system-site-packages` 없이
만든 venv 안에서는 **보이지 않는다**. 파이에서 가장 자주 걸리는 함정이 이것이다.

```bash
# 1) 정말 있는지부터 확인한다 (venv 밖, 시스템 파이썬으로)
/usr/bin/python3 -c "import gpiozero, lgpio; print('있음')"
#    → '있음'이 나오면 설치할 필요 없다. 아래 2)로 간다.
#    → ModuleNotFoundError가 나올 때만: sudo apt install -y python3-gpiozero python3-lgpio

# 2) venv를 시스템 패키지가 보이게 다시 만든다
cd pi
rm -rf venv                                    # PC에서 만든 venv가 남아 있으면 지운다
python3 -m venv --system-site-packages venv    # ← 이 옵션이 없으면 lgpio를 못 본다
source venv/bin/activate
pip install -r requirements.txt
```

`pip install lgpio`는 권하지 않는다 — 최근 라즈베리파이 OS(Bookworm·Trixie)에서
빌드에 실패하는 일이 잦고, apt 쪽이 그 기기에 맞게 이미 준비되어 있다.
파이 5는 GPIO 칩이 달라(RP1) 예전 `RPi.GPIO`로는 동작하지 않는다.

`pi/.env`를 바꾼다.
```
DEVICE_MODE=hardware
GPIOZERO_PIN_FACTORY=lgpio
ENABLE_CAMERA=true
BACKEND_URL=http://<백엔드 PC의 IP>:8000     # localhost는 파이 자신을 뜻한다
SERVO_GATE_PIN=18                            # 조립 후 실제 핀 번호로
SERVO_PUSHER_PIN=19
SERVO_HOLD=false                             # 자세를 잡은 뒤 펄스를 끊는다 (아래 설명)
BUZZER_PIN=                                  # 부저를 안 달면 비워 둔다
```
MG996R은 **별도 5V 전원**으로 공급하고 파이는 신호선만 연결한다. 배선 변경은 반드시
전원을 끈 상태에서, 실기기 첫 연결은 교사 입회 하에 진행한다.

> **`SERVO_HOLD`가 왜 있나.** gpiozero는 각도를 준 뒤에도 펄스를 계속 내보낸다.
> MG996R은 그동안 토크를 유지하느라 전류를 먹고 미세하게 떨린다("지지직" 소리).
> 몇 시간짜리 전시 내내 그러면 발열과 전압 강하로 이어지고, 5V를 나눠 쓰는
> 배선에서는 파이가 리부팅되기도 한다. 그래서 기본값은 **펄스를 끊는다**(`false`).
> 게이트가 제 무게로 흘러내린다면 그때만 `true`로 바꾼다.

### 4-2-1. 데몬을 켜기 전에 한 번 점검한다

`python main.py`가 안 뜰 때 트레이스백만 봐서는 원인을 찾기 어렵다. 켜기 전에
아래를 먼저 돌리면 파이썬 환경 · 폴더 구조 · `.env` · GPIO · 카메라 · 백엔드 연결을
한 줄씩 확인해 준다. **서보는 움직이지 않는다.**

```bash
cd pi
python check_hardware.py
```

`[실패]` 줄 아래에 무엇을 고쳐야 하는지가 함께 나온다. 전부 통과하면
`python main.py`로 넘어간다.

서보 배선까지 확인하려면 `--servo`를 붙인다. **실제로 움직이므로 교사 입회 하에,
손이 배출구에 없는 것을 확인하고** 실행한다.

```bash
python check_hardware.py --servo
```

### 4-3. 7인치 화면
파이의 브라우저를 키오스크 모드로 `/atm`에 띄운다.
```bash
chromium-browser --kiosk http://<프론트엔드 주소>:3000/atm
# 'command not found'가 나오면 최근 라즈베리파이 OS에서는 이름이 다르다:
chromium --kiosk http://<프론트엔드 주소>:3000/atm
```

키오스크 모드에서는 주소창이 없어 새로고침이 어렵다. 리허설 중에는 `--kiosk`를
빼고 띄워 두는 편이 편하다.

---

## 5. 자동 검증

### 5-1. 단위·통합 테스트 (서버를 띄우지 않아도 된다)
저장소 루트에서:
```bash
pytest
```
- `backend/tests/test_rules.py` — TC-01~TC-03, 등급 경계값, CAUTION=VERIFY
- `backend/tests/test_api_flow.py` — 인증 분리, 전체 API 흐름, TC-04·TC-05
- `pi/tests/test_atm_controller.py` — **FR-09**(DANGER에서 배출 장치 미동작), 오프라인 백업
- `pi/tests/test_qr_end_to_end.py` — 실제 QR 이미지를 만들어 다시 읽는 검증

### 5-2. 통합 시연 검증 (백엔드 + ATM 데몬을 띄운 상태에서)
QR 이미지를 실제로 만들어 다시 읽으므로 `qrcode`가 필요하다 (없으면
`pi/tests/test_qr_end_to_end.py`도 조용히 건너뛴다).
```bash
pip install "qrcode[pil]"
python scripts/demo_e2e.py
```
정상 문자 → 출금 가능, 보이스피싱 문자 → 출금 차단 → 콜센터 해제까지 실제 HTTP로
확인하고 결과를 한 줄씩 출력한다.

---

## 6. 발표 시연 순서 (PRD 10장)

1. **정상 문자** — `/messages`에서 "병원 예약" 문자를 고르고 검사 → **안전**
   → QR 없음, ATM에서 출금 정상 동작
2. **보이스피싱 문자** — "검찰입니다..." 문자를 검사 → **위험 100점**, 근거 4개 표시
   → QR 표시
3. **ATM 인식** — 휴대폰 QR을 ATM 카메라에 보여 준다 → 화면이 빨갛게 바뀌며
   "현금 출금을 잠시 멈췄습니다"
4. **출금 시도** — 50만 원 버튼을 누른다 → **서보가 움직이지 않고** "현금이 나오지
   않습니다" 안내 (이 장면이 이 작품의 핵심이다)
5. **콜센터 확인** — "상담원 확인 요청하기" → `/callcenter` 화면에 세션이 뜬다
   → 문자 내용과 탐지 근거를 확인
6. **분기** — "보이스피싱 — 제한 유지"를 누르면 ATM은 계속 막혀 있고,
   "정상 거래 — 제한 해제"를 누르면 몇 초 뒤 ATM이 출금 가능으로 바뀐다
7. **잘못된 QR** — 아무 QR이나 비춰 본다 → "등록되지 않은 QR입니다" 안내만 뜨고
   거래 제어에는 쓰이지 않는다

### 백업 시연 (네트워크가 끊겼을 때)
- `pi/.env`에 `ENABLE_CAMERA=false`를 두고 `POST /qr`로 진행한다
- 백엔드까지 죽었다면 `{"session_id": "VP-000001", "risk_level": "DANGER"}` 형태의 QR을
  미리 만들어 둔다 — ATM이 로컬 판단으로 차단까지는 시연할 수 있다
  (콜센터 해제는 서버가 필요하다)

> **로컬 판단으로 넘어가는 경우는 '서버에 닿지 못했을 때' 하나뿐이다.**
> 서버가 401(디바이스 키 거부)로 대답했다면 그건 장애가 아니라 설정 오류이므로,
> ATM은 오프라인으로 넘어가지 않고 거래를 열지 않는다. 서버가 대답을 했는데도 QR을
> 믿기 시작하면 QR이 스스로 적어 온 위험 등급이 서버 판정을 이기게 되고, 키 오타
> 하나로 위조 QR에 현금이 나갈 수 있다. 화면에는 "지금은 이 ATM을 사용할 수
> 없습니다"가 뜨고, 진짜 원인은 ATM 데몬 로그에 남는다.

---

## 7. 자주 막히는 곳

| 증상 | 원인 · 해결 |
|---|---|
| 화면은 뜨는데 목록이 비어 있다 | CORS. 백엔드 `CORS_ORIGINS`에 브라우저 주소를 정확히 넣는다 |
| 콜센터 화면에 "실시간 이벤트 연결이 거부되었습니다" | `/ws`는 상담원 토큰을 요구한다. `callcenter` 계정으로 다시 로그인한다 (일반 사용자 계정으로는 붙을 수 없다) |
| 로그인이 계속 401 | `python -m db.seed`를 안 돌렸거나 비밀번호가 다르다. seed 출력 확인 |
| ATM API가 401 | `pi/.env`와 `backend/.env`의 `DEVICE_API_KEY`가 다르다 |
| ATM 화면에 "지금은 이 ATM을 사용할 수 없습니다" | 키 불일치다. **그 문구 아래 작은 글씨에 고칠 것이 적혀 있다.** 두 `.env`의 `DEVICE_API_KEY`를 맞추고 **데몬을 껐다 다시 켠다**(시작할 때 한 번만 읽는다) |
| 정상 문자인데도 출금 화면으로 안 바뀐다 | 십중팔구 위와 같은 인증 실패다. 서버 확인을 못 하면 거래를 열지 않는 것이 정상 동작이다. 화면 아래 작은 글씨와 데몬 로그를 본다 |
| ATM 화면이 저절로 처음으로 돌아간다 | **버그가 아니다.** 조작이 1분간 없으면 다음 사람을 위해 대기 화면으로 돌아간다(화면 아래 남은 시간이 표시된다). 오래 띄워 두려면 `pi/.env`의 `IDLE_RESET_SECONDS`를 늘리거나 `0`으로 끈다 — **데몬 재시작 필요** |
| 차단 화면에는 카운트다운이 안 뜬다 | **버그가 아니다.** 막혀 있는 동안에는 세지 않는다. 시간이 제한을 풀어 준다면 막힌 사람은 1분만 기다리면 되기 때문이다 |
| 차단 화면에서 "처음으로"가 안 먹는다 | **버그가 아니다.** 한 번 누르면 안내와 함께 **"직원 확인 후 해제"** 버튼이 나타난다. 제한을 푸는 것은 상담원 확인이거나 은행 직원이다 |
| 잠긴 ATM에 다른 QR을 비춰도 안 열린다 | **버그가 아니다.** 안전한 문자로 QR을 새로 만들어 오면 풀린다면, 그것도 해제 버튼이다 |
| QR을 안 비췄는데 ATM에서 돈이 나온다 | **버그가 아니다.** ATM은 공용 기계이고 그 앞에 선 사람은 이 시스템과 상관없을 수도 있다. 막는 대상은 '확인되지 않은 사람'이 아니라 '위험이 확인된 세션'이다 (`AGENTS.md` 핵심 데이터 흐름 0번) |
| 파이에서 백엔드에 못 붙는다 | `BACKEND_URL`이 `localhost`로 되어 있다. PC의 실제 IP로 바꾼다 |
| 파이에서 `ModuleNotFoundError: No module named 'iot'` | `pi/`만 복사했다. `backend/`가 같은 상위 폴더에 나란히 있어야 한다 (4-2 참고) |
| `gpiozero` 오류 | Pi 5는 `lgpio`가 필요하다. `pip install lgpio` 후 `GPIOZERO_PIN_FACTORY=lgpio` |
| 카메라를 못 연다 | `ENABLE_CAMERA=false`로 두고 `POST /qr`로 먼저 로직을 검증한다 |
| `Not a video capture device` / `can't open camera by index` | **번호가 있다고 카메라가 아니다.** UVC 웹캠 하나는 `/dev/video0`(영상)과 `/dev/video1`(메타데이터)을 함께 만든다. `python check_hardware.py`가 영상이 들어오는 번호를 찾아 알려 준다 |
| 로그는 "카메라 열림"인데 QR이 안 읽힌다 | 위와 같은 원인이다. 지금은 데몬이 프레임을 한 장 받아 보고 실패하면 번호를 알려 주며 멈춘다 |
| `PWMSoftwareFallback: ... use the pigpio pin factory` | **버그가 아니다.** 파이 5(RP1)에서는 `pigpio`를 쓸 수 없어 소프트웨어 PWM으로 동작한다. 서보가 미세하게 떨릴 수 있으나 배출 동작에는 문제가 없다 |
| **파이에서** `python main.py`가 바로 죽는다 | `cd pi && python check_hardware.py` 를 먼저 돌린다. 원인과 고치는 방법이 한 줄씩 나온다 |
| `No module named 'iot'` | `backend/iot/`가 없다. `pi/`와 같은 상위 폴더 아래 `backend/iot/`를 둔다 (`iot/`만 옮겨도 된다) |
| `No module named 'gpiozero'` (설치했는데도) | venv가 apt 패키지를 못 보는 것이다. `/usr/bin/python3 -c "import gpiozero"`로 시스템에는 있는지 먼저 확인하고, `python3 -m venv --system-site-packages venv`로 다시 만든다 |
| `BadPinFactory` / `Unable to load any default pin factory` | 파이 5에 `lgpio`가 없다. `sudo apt install -y python3-lgpio`, `.env`에 `GPIOZERO_PIN_FACTORY=lgpio` |
| GPIO 열 때 권한 오류 | `sudo usermod -aG gpio $USER` 후 **다시 로그인**한다 |
| `ImportError: libGL.so.1` (cv2) | `sudo apt install -y libgl1 libglib2.0-0`. 그래도 안 되면 `pip install opencv-python-headless`로 바꾼다 |
| 파이 카메라 모듈(CSI)이 안 잡힌다 | 최근 라즈베리파이 OS에서는 `cv2.VideoCapture`로 CSI 카메라를 열 수 없다. USB 웹캠을 쓴다 |
| 파이에서 `pip install`이 거부된다 | `externally-managed-environment`(Bookworm·Trixie)다. venv 안에서 설치한다 |
| QR이 잘 안 읽힌다 | 휴대폰 화면 밝기를 올리고 QR을 크게 표시한다. 초점 거리를 20cm 이상 둔다 |
| 실기기에서 출금 버튼을 눌러도 1~2초 반응이 없다 | **버그가 아니다.** 서보가 게이트를 열고·밀고·닫는 실제 시간(약 1.4초)이다. 그동안 화면은 "잠시만 기다려 주세요"를 띄우고 금액 버튼을 잠근다. PC 시뮬레이션에서는 즉시라 차이가 느껴진다 |
| 배출 뒤 서보에서 "지지직" 소리가 계속 난다 | 펄스가 끊기지 않은 것이다. `pi/.env`의 `SERVO_HOLD`가 `true`면 `false`로 바꾼다 |
| 위험 QR을 읽은 뒤 부저가 계속 울린다 | 경고음은 "삑" 두 번으로 끝나야 한다. 계속 울리면 `WARN_BEEP_SECONDS`를 확인하고, 그래도 그러면 데몬 로그를 본다 |
| QR 인식이 **느리거나 밀린다** (치웠는데 뒤늦게 읽힘) | 해상도가 크게 열린 것이다. 검출 비용은 화소 수에 거의 비례한다. `python check_hardware.py`가 이 기기에서 한 장에 몇 ms 걸리는지 재 주고, `.env`의 `CAMERA_WIDTH=640` · `CAMERA_HEIGHT=480`으로 줄인다 |
