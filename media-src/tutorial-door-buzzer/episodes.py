"""
episodes.py — 실습 영상 두 편의 장면 대본.

자막 한 줄 = 내레이션 한 문장이다 (같은 내용이 .srt 대본으로도 나간다).
화면에 나오는 코드 변경(diff)과 터미널 출력은 captured/ 의 실제 기록을 가리키기만 한다.
"""

TREE_PI = [
    {"name": ".agents", "dir": True, "depth": 0, "path": ".agents"},
    {"name": "backend", "dir": True, "depth": 0, "path": "backend"},
    {"name": "frontend", "dir": True, "depth": 0, "path": "frontend"},
    {"name": "pi", "dir": True, "depth": 0, "path": "pi"},
    {"name": "booth_pins.py", "depth": 1, "path": "pi/booth_pins.py"},
    {"name": "main.py", "depth": 1, "path": "pi/main.py"},
    {"name": "mock_door.py", "depth": 1, "path": "pi/mock_door.py"},
    {"name": "test_hardware_gpio.py", "depth": 1, "path": "pi/test_hardware_gpio.py"},
    {"name": "01_ping_backend.py", "depth": 1, "path": "pi/01_ping_backend.py"},
    {"name": "02_karaoke_daemon_mock.py", "depth": 1, "path": "pi/02_karaoke_daemon_mock.py"},
    {"name": "requirements.txt", "depth": 1, "path": "pi/requirements.txt"},
    {"name": ".env", "depth": 1, "path": "pi/.env"},
    {"name": "AGENTS.md", "depth": 0, "path": "AGENTS.md"},
]

TREE_WEB = [
    {"name": ".agents", "dir": True, "depth": 0, "path": ".agents"},
    {"name": "backend", "dir": True, "depth": 0, "path": "backend"},
    {"name": "db", "dir": True, "depth": 1, "path": "backend/db"},
    {"name": "database.py", "depth": 2, "path": "backend/db/database.py"},
    {"name": "init.sql", "depth": 2, "path": "backend/db/init.sql"},
    {"name": "init_supabase.sql", "depth": 2, "path": "backend/db/init_supabase.sql"},
    {"name": "iot", "dir": True, "depth": 1, "path": "backend/iot"},
    {"name": "mock_provider.py", "depth": 2, "path": "backend/iot/mock_provider.py"},
    {"name": "routers", "dir": True, "depth": 1, "path": "backend/routers"},
    {"name": "devices.py", "depth": 2, "path": "backend/routers/devices.py"},
    {"name": "services", "dir": True, "depth": 1, "path": "backend/services"},
    {"name": "booth_service.py", "depth": 2, "path": "backend/services/booth_service.py"},
    {"name": "frontend", "dir": True, "depth": 0, "path": "frontend"},
    {"name": "components/booth", "dir": True, "depth": 1, "path": "frontend/components/booth"},
    {"name": "VirtualBoothSimulator.tsx", "depth": 2, "path": "frontend/components/booth/VirtualBoothSimulator.tsx"},
    {"name": "hooks", "dir": True, "depth": 1, "path": "frontend/hooks"},
    {"name": "useBoothData.ts", "depth": 2, "path": "frontend/hooks/useBoothData.ts"},
    {"name": "pi", "dir": True, "depth": 0, "path": "pi"},
    {"name": "AGENTS.md", "depth": 0, "path": "AGENTS.md"},
]

# 관리자 화면 녹화(1600x900)에서 '부스 기기 관제' 패널만 잘라 보여 줄 영역
PANEL = [205, 100, 680, 430]
DOOR_ROW = [232, 448, 620, 42]   # 문 열림 센서 · 경고 부저 줄

DONE_ITEMS = [
    {"text": "문을 열고 닫으면 관리자 화면의 '문 열림 센서'가 바로 바뀐다"},
    {"text": "도어락이 잠긴 채 문이 열리면 경고 부저가 울리고, 문을 닫으면 멈춘다"},
    {"text": "파이를 끄면 부저도 꺼진 안전 상태로 돌아간다"},
]


def prompt(text, caps=None, cps=26):
    return {"kind": "prompt", "text": text, "caps": caps, "cps": cps}


def reply(text, files=None, caps=None):
    return {"kind": "reply", "text": text, "files": files, "caps": caps}


def edit(diff, file, hunks="all", caps=None, **kw):
    return {"kind": "edit", "diff": diff, "file": file, "hunks": hunks, "caps": caps, **kw}


def term(cap, caps=None, **kw):
    return {"kind": "term", "cap": cap, "caps": caps, **kw}


def hold(caps, dur=0.5):
    return {"kind": "hold", "caps": caps, "dur": dur}


# ══════════════════════════════════════════════════════════════════════════
# ① 라즈베리파이 편
# ══════════════════════════════════════════════════════════════════════════
def ep_pi(Ep):
    ep = Ep("pi", "실습 ①", "문 열림 센서 + 경고 부저 · 라즈베리파이 편",
            [("1", "만들 것"), ("2", "배선"), ("3", "AI에게 부탁"), ("4", "main.py"), ("5", "핀 겹침"),
             ("6", "자가진단"), ("7", "모의 실행"), ("8", "함께 확인"), ("9", "정리")], TREE_PI)

    ep.title_card("AI와 함께하는 바이브 코딩 실습 ①", ["문 열림 센서와", "경고 부저 달기"], "라즈베리파이 담당 편 · pi 폴더",
                  ["리드 스위치 1개", "액티브 부저 모듈 1개", "점퍼선 5가닥", "AI 코딩 도우미"], [
        "라즈베리파이 담당 친구를 위한 실습 영상입니다.",
        "노래방 부스에 문 열림 센서와 경고 부저를 새로 달고, AI에게 코드를 부탁해 고치는 과정을 처음부터 끝까지 보여 드립니다.",
        "화면에 나오는 코드와 터미널 출력은 모두 실제로 실행한 결과입니다. 오류도 실제로 난 오류입니다.",
    ])

    # 1 ─────────────────────────────────────────────
    ep.chapter_card("오늘 만들 것", "완료 기준부터 정합니다")
    ep.diagram("flow", [
        (["door"], ["리드 스위치는 자석이 가까이 오면 붙는 스위치입니다. 문틀에 스위치를, 문에 자석을 붙이면 문이 열렸는지 알 수 있습니다."]),
        (["rule"], ["규칙은 하나입니다. 도어락이 잠긴 상태인데 문이 열려 있으면 부저가 울리고, 문을 닫으면 멈춥니다.",
                    "이용이 끝났는데 문을 안 닫고 나가면, 다음 사람이 비밀번호 없이 들어올 수 있기 때문입니다."]),
        (["door", "e_door", "pi", "e_report", "be"], ["① 파이는 문이 열리고 닫힐 때마다 그 사실을 백엔드에 보고합니다."]),
        (["be", "e_rule", "rule"], ["② 백엔드는 규칙에 따라 부저의 목표 상태를 on 또는 off로 정합니다."]),
        (["e_poll", "pi", "e_buzz", "buzzer"], ["③ 파이는 2~3초마다 목표 상태를 물어보고, ④ on이면 GPIO25로 부저를 울립니다."]),
        (["e_ws", "fe"], ["⑤ 관리자 화면은 WebSocket으로 이 변화를 실시간으로 받습니다."]),
        (["role_pi", "door", "pi", "buzzer"], ["이 가운데 파이 담당이 고칠 곳은 pi 폴더뿐입니다. 백엔드와 화면은 2편에서 다룹니다."],
         ["be", "rule", "fe"]),
    ])
    ep.card("완료 기준 — 먼저 적어 둡니다", DONE_ITEMS, [
        ["기능을 만들기 전에, 무엇이 되면 '완료'인지부터 적습니다. 프로젝트 규칙 feature-development의 첫 단계입니다."],
        ["이 기준은 영상 마지막에 눈으로 직접 확인합니다."],
        ["AI가 '다 됐어요'라고 해도, 이 세 가지를 직접 보기 전에는 끝난 게 아닙니다."],
    ])

    # 2 ─────────────────────────────────────────────
    ep.chapter_card("부품과 배선", "선 다섯 가닥이면 됩니다")
    ep.diagram("wiring", [
        (["used"], ["이름 옆에 쓰임새가 적힌 핀은 도어락, 릴레이, LED, PIR, 키패드가 이미 쓰고 있는 핀입니다."], ["reed", "buzzer", "w_reed", "w_buz"]),
        (["p16", "p22"], ["새 부품은 비어 있는 GPIO23(물리 16번 핀)과 GPIO25(물리 22번 핀)를 씁니다."], ["reed", "buzzer", "w_reed", "w_buz"]),
        (["reed", "p16", "p14", "w_reed"], ["리드 스위치는 한쪽 선을 GPIO23에, 다른 쪽 선을 GND(14번 핀)에 꽂습니다.",
                                            "저항은 따로 달지 않습니다. 파이 안쪽의 풀업 저항을 코드에서 켭니다."], ["buzzer", "w_buz"]),
        (["buzzer", "p22", "p20", "p17", "w_buz"], ["부저 모듈은 S를 GPIO25(22번), VCC를 3.3V(17번), GND를 20번 핀에 꽂습니다.",
                                                   "모듈마다 쓰는 전압이 다를 수 있으니 판매 페이지의 설명을 꼭 확인하세요."]),
        (["legend", "p16", "p22"], ["코드에는 물리 핀 번호가 아니라 BCM 번호, 곧 GPIO23과 GPIO25를 씁니다. 가장 흔한 실수입니다."]),
    ])
    ep.card("배선 안전 수칙", [
        {"text": "배선은 반드시 라즈베리파이 전원을 끄고 한다", "warn": True, "b": "!"},
        {"text": "처음 실기기에 연결할 때는 선생님과 함께한다", "warn": True, "b": "!"},
        {"text": "부품이 오기 전에는 Mock(가짜 GPIO)으로 먼저 연습한다", "b": "✓"},
    ], [
        ["프로젝트의 hardware-rules에 적힌 안전 수칙입니다. 이 부스에는 220V 릴레이가 있습니다."],
        ["전원을 켠 채 선을 꽂다가 핀끼리 닿으면 파이가 고장 날 수 있습니다."],
        ["이 영상도 Mock으로 먼저 연습합니다."],
    ])

    # 3 ─────────────────────────────────────────────
    ep.chapter_card("AI에게 부탁하기", "역할 + 참고 규칙 + 구체적인 요구")
    ep.ide("hardware-agent", [
        prompt("너는 이 프로젝트의 hardware-agent다. `.agents/rules/hardware-rules.md`와 `.agents/skills/hardware-integration`을 참고해.\n\n"
               "문 열림 센서(리드 스위치, GPIO23, 내부 풀업)와 경고 부저(액티브 부저, GPIO25)를 pi 폴더에 추가해 줘.\n"
               "- 핀 번호는 `booth_pins.py`에만 적어\n"
               "- 문 상태가 바뀔 때만 `door_sensor_1`로 보고해 (1 = 열림, 0 = 닫힘)\n"
               "- `buzzer_1`은 다른 액추에이터처럼 desired-state를 폴링해서 켜고 꺼\n"
               "- 관련 없는 파일은 건드리지 마", [
            "AGENTS.md에 적힌 대로 역할을 먼저 지정하고, 참고할 규칙 파일을 알려 줍니다.",
            "무엇을, 어느 핀에, 어떤 이름으로 보고할지를 구체적으로 적을수록 AI의 결과가 정확해집니다.",
            "마지막 줄 '관련 없는 파일은 건드리지 마'는 외과적 변경 원칙입니다.",
        ], cps=30),
        reply("고치기 전에 계획부터 말씀드릴게요.\n\n"
              "1. `booth_pins.py` — `BUZZER_PIN = 25`, `DOOR_SENSOR_PIN = 23` 추가\n"
              "2. `main.py` — 문 센서는 `Button`(풀업), 부저는 `Buzzer`로 만들고, 문 상태가 바뀌면 `POST /api/v1/devices/door_sensor_1/state`\n"
              "3. `buzzer_1`을 폴링 목록 · 안전 상태 · 시작/종료 보고에 추가\n\n괜찮으면 바로 고칠게요.",
              ["pi/booth_pins.py", "pi/main.py"], [
            "좋은 AI 도우미는 고치기 전에 계획을 먼저 말합니다.",
            "계획이 요구와 다르면 이때 바로잡습니다. 코드를 다 고친 뒤에 되돌리는 것보다 훨씬 쉽습니다.",
        ]),
        prompt("좋아, 그렇게 고쳐 줘."),
        edit("pi_diff_booth_pins", "pi/booth_pins.py", [0, 1], [
            "첫 번째 파일 booth_pins.py입니다. 초록색 줄이 새로 생긴 줄입니다.",
            "핀 번호 두 줄과, 시작할 때 핀 배치를 화면에 보여 주는 두 줄이 늘었습니다.",
            "핀 번호를 이 파일 한 곳에만 두기 때문에, 배선을 바꿔도 여기만 고치면 됩니다.",
        ]),
    ])

    # 4 ─────────────────────────────────────────────
    ep.chapter_card("main.py 읽어 보기", "AI가 고친 코드는 직접 읽습니다")
    ep.ide("hardware-agent", [
        edit("pi_diff_main", "pi/main.py", [0], ["main.py의 첫 변경은 gpiozero에서 Button과 Buzzer를 더 가져오는 한 줄입니다."]),
        edit("pi_diff_main", "pi/main.py", [1], [
            "부저는 Buzzer로, 문 센서는 Button으로 만듭니다.",
            "pull_up=True라서 문이 닫혀 자석이 붙으면 '눌림'으로 읽힙니다. bounce_time은 스위치가 떨리는 0.1초를 무시하는 값입니다.",
        ]),
        edit("pi_diff_main", "pi/main.py", [2], [
            "백엔드가 buzzer_1을 on으로 시키면 삐- 삐- 울리고, off면 끕니다.",
            "background=True 덕분에 부저가 울리는 동안에도 프로그램이 멈추지 않고 키패드를 계속 읽습니다.",
        ]),
        edit("pi_diff_main", "pi/main.py", [3], ["자석이 떨어져 스위치가 열려 있으면 문이 열린 것입니다. 센서 값을 해석하는 곳은 이 한 줄뿐입니다."]),
        edit("pi_diff_main", "pi/main.py", [4], ["프로그램을 끄거나 오류가 나면 부르는 안전 상태 safe_state에 부저 끄기를 넣었습니다. 아주 중요한 줄입니다."]),
        edit("pi_diff_main", "pi/main.py", [5], [
            "문 상태는 1(열림) 또는 0(닫힘)으로 보고합니다.",
            "401이나 404가 오면 무슨 뜻인지 알기 쉽게 출력합니다. 이 메시지는 잠시 뒤 실제로 보게 됩니다.",
            "맨 아래에서는 buzzer_1을 폴링 목록에 넣었습니다.",
        ]),
        edit("pi_diff_main", "pi/main.py", [6], ["시작할 때 안전 상태 보고와 현재 상태 목록에도 buzzer_1을 넣었습니다."]),
        edit("pi_diff_main", "pi/main.py", [7], [
            "메인 루프입니다. 문 상태가 '바뀔 때만' 보고하도록 했습니다.",
            "0.05초마다 보고하면 1초에 스무 번씩 백엔드를 두드리게 되기 때문입니다.",
        ]),
        edit("pi_diff_main", "pi/main.py", [8], ["끝낼 때도 부저를 끈 상태로 보고합니다. 이렇게 main.py를 한 덩어리씩 모두 읽었습니다."]),
    ])

    # 5 ─────────────────────────────────────────────
    ep.chapter_card("시행착오 ① 핀이 겹쳤다", "오류는 마지막 줄부터 읽습니다")
    ep.ide("hardware-agent", [
        hold(["자주 하는 실수를 일부러 해 보겠습니다. 배선표를 잘못 보고 문 센서 핀을 17번으로 적었다고 해 봅시다."]),
        edit("pi_trial_pin17_diff", "pi/booth_pins.py", [0], ["booth_pins.py에 17번이라고 적었습니다."], focus=["DOOR_SENSOR_PIN"]),
        term("pi_trial_pin17", [
            "라즈베리파이가 없어도 GPIOZERO_PIN_FACTORY=mock을 붙이면 gpiozero가 가짜 핀으로 진짜 코드를 실행합니다.",
            "실행하자마자 멈췄습니다. GPIOPinInUse, 17번 핀은 이미 도어락이 쓰고 있다는 오류입니다.",
            "오류는 맨 아래 줄부터 읽습니다. AI에게 물어볼 때도 이 마지막 줄을 그대로 붙여 넣으면 됩니다.",
        ], gap=0.06),
        prompt("main.py 를 실행했더니 이런 오류가 나:\n"
               "gpiozero.exc.GPIOPinInUse: pin GPIO17 is already in use by <gpiozero.OutputDevice object on pin GPIO17 ...>\n"
               "왜 그런 거야?", cps=40),
        reply("`booth_pins.py`의 `DOOR_SENSOR_PIN`이 17로 되어 있는데, 17번은 이미 `DOOR_LOCK_PIN`(도어락)이 쓰는 핀입니다. "
              "한 핀에 두 부품을 연결할 수 없어서 나는 오류예요.\n\n"
              "비어 있는 23번으로 바꾸고, 실제 선도 물리 16번 핀에 꽂혀 있는지 확인하세요.", ["pi/booth_pins.py"], [
            "AI가 원인과 함께, 실제 선도 확인하라고 알려 줍니다. 코드만 고치고 선을 그대로 두면 소용이 없습니다.",
        ]),
        edit("pi_diff_booth_pins", "pi/booth_pins.py", [0], ["23번으로 되돌렸습니다. 핀 번호를 한 파일에서 관리하니 고칠 곳도 한 곳입니다."],
             focus=["DOOR_SENSOR_PIN"]),
    ])

    # 6 ─────────────────────────────────────────────
    ep.chapter_card("배선 자가진단", "실기기에서 1분 만에 확인하는 도구")
    ep.ide("hardware-agent", [
        prompt("`test_hardware_gpio.py` 자가진단에도 문 센서 읽기와 부저 세 번 울리기 검사를 추가해 줘."),
        edit("pi_diff_test_hardware_gpio", "pi/test_hardware_gpio.py", [6], [
            "자가진단 스크립트에 6번, 7번 검사를 더했습니다.",
            "문 센서는 지금 값을 읽어 보여 주고, 부저는 세 번 울려 봅니다.",
        ]),
        term("pi_selftest", [
            "mock 모드라 센서 값은 가짜지만, 코드가 끝까지 도는지는 확인할 수 있습니다.",
            "실기기에서는 문을 열었다 닫으며 값이 0과 1로 바뀌는지, 부저가 세 번 울리는지 보세요.",
        ], speed=1.6, drop=r"^\s*$"),
    ])

    # 7 ─────────────────────────────────────────────
    ep.chapter_card("부품 없이 돌려 보기", "404와 401의 뜻")
    ep.ide("hardware-agent", [
        prompt("부품이 오기 전에 연습할 수 있게, main.py 를 그대로 돌리면서 키보드로 문 센서를 흉내 내는 `mock_door.py` 를 만들어 줘."),
        edit("pi_diff_mock_door", "pi/mock_door.py", "all", [
            "mock_door.py입니다. main.py를 그대로 실행하면서, 키보드 o와 c로 문 센서 핀의 전압만 바꿉니다.",
            "main.py의 폴링, 보고, 부저 코드는 진짜로 돌아갑니다. 바뀌는 것은 GPIO뿐입니다.",
        ], reveal=6.5, scrollTo=19),
        term("pi_run_404", [
            "실행해 보니 404가 납니다. devices 테이블에 door_sensor_1과 buzzer_1이 없다는 뜻입니다.",
            "파이 코드가 틀린 게 아닙니다. 백엔드에 기기 등록이 아직 안 된 것입니다.",
            "새 부품을 달 때는 백엔드 담당과 순서를 맞춥니다. 기기 등록은 2편에서 합니다.",
        ], speed=2.0),
        term("pi_trial_401", [
            "하나 더 보겠습니다. pi/.env의 DEVICE_API_KEY가 백엔드와 한 글자라도 다르면 이렇게 401이 납니다.",
            "401은 출입증이 틀렸다는 뜻이고, 404는 그런 부품이 없다는 뜻입니다.",
        ], speed=1.5, max_lines=30),
        term("pi_run_ok", [
            "백엔드 등록이 끝난 뒤 다시 실행했습니다. 처음에는 문이 닫혀 있습니다.",
            "o를 눌러 문을 열자, 백엔드가 부저를 켜라고 지시합니다.",
            "지시를 받아 부저를 울리고, '보고 완료'로 실제 상태를 알립니다.",
            "c로 문을 닫으면 부저가 꺼지고, 끝낼 때는 모두 안전 상태로 돌아갑니다.",
        ], speed=1.25),
    ])

    # 8 ─────────────────────────────────────────────
    ep.chapter_card("관리자 화면과 함께", "완료 기준을 눈으로 확인")
    ep.browser("web_ui_live", 2.0, 24.5, PANEL, [
        (2.2, "왼쪽은 파이 터미널, 오른쪽은 선생님의 관리자 화면입니다."),
        (6.4, "o로 문을 열자 '문 열림 센서: 열림'과 '경고 부저 울림'이 함께 바뀝니다."),
        (16.4, "c로 문을 닫으면 둘 다 원래대로 돌아옵니다."),
        (20.6, "처음에 정한 완료 기준을 눈으로 확인했습니다."),
    ], term="pi_with_ui_live", highlights=[
        {"from": 6.3, "to": 16.2, "box": DOOR_ROW, "label": "문 열림 → 부저 울림"},
        {"from": 16.4, "to": 22.0, "box": DOOR_ROW, "label": "문 닫힘 → 부저 꺼짐"},
    ])

    # 9 ─────────────────────────────────────────────
    ep.chapter_card("정리", "실기기에서 할 일")
    ep.card("실기기에서 할 일", [
        {"text": "전원을 끄고 배선한다 (GPIO23–GND, GPIO25 · 3.3V · GND)"},
        {"text": "`python test_hardware_gpio.py` 로 6번 · 7번 확인"},
        {"text": "`python main.py` 를 켜고 문을 열고 닫으며 관리자 화면 확인"},
        {"text": "확인이 끝나면 커밋한다"},
    ], [["실제 라즈베리파이에서는 이 순서로 합니다. 먼저 전원을 끄고 배선합니다."],
        ["자가진단으로 배선부터 확인합니다."],
        ["그다음 main.py를 켜고, 처음에 정한 기준을 실물로 확인합니다."],
        ["모두 확인한 뒤에 커밋합니다. 요약만 읽고 넘어가지 않습니다."]])
    ep.card("기억할 것", [
        {"text": "핀 번호는 `booth_pins.py` 한 곳에만"},
        {"text": "`GPIOPinInUse` = 핀이 겹쳤다"},
        {"text": "404 = 백엔드에 기기 등록이 안 됐다 · 401 = 키가 다르다"},
        {"text": "오류는 마지막 줄부터 읽고, 그대로 AI에게 붙여 넣는다"},
    ], [["오늘 겪은 시행착오를 네 줄로 정리했습니다."], ["핀이 겹치면 실행하자마자 멈춥니다."],
        ["404와 401은 파이 코드가 아니라 연결 설정을 의심합니다."], ["오류 메시지를 그대로 붙여 넣으면 AI가 원인을 훨씬 빨리 찾습니다."]],
        reveal=True)
    ep.end_card("다음 편 · 백엔드 · 프론트엔드", "docs/실습-문센서-부저 폴더에 단계별 패치와 대본이 있습니다", [
        "다음 편에서는 백엔드에 기기를 등록하고, 규칙과 관리자 화면을 만듭니다. 수고하셨습니다.",
    ])
    return ep


# ══════════════════════════════════════════════════════════════════════════
# ② 백엔드 · 프론트엔드 편
# ══════════════════════════════════════════════════════════════════════════
def ep_web(Ep):
    ep = Ep("web", "실습 ②", "문 열림 센서 + 경고 부저 · 백엔드 · 프론트엔드 편",
            [("1", "만들 것"), ("2", "기기 등록"), ("3", "가끔 404"), ("4", "규칙"), ("5", "안 울린다"),
             ("6", "관리자 화면"), ("7", "새로고침"), ("8", "함께 확인"), ("9", "정리")], TREE_WEB)

    ep.title_card("AI와 함께하는 바이브 코딩 실습 ②", ["문 열림 센서와", "경고 부저 달기"], "백엔드 · 프론트엔드 담당 편",
                  ["기기 등록", "규칙 만들기", "관리자 화면", "실시간 반영"], [
        "백엔드와 프론트엔드 담당 친구를 위한 실습 영상입니다.",
        "1편에서 라즈베리파이는 문 센서와 부저를 다룰 준비를 마쳤습니다. 이번에는 백엔드에 기기를 등록하고, 규칙과 관리자 화면을 만듭니다.",
        "이번 편에도 실제로 난 오류 세 가지와 고치는 과정이 그대로 들어 있습니다.",
    ])

    # 1 ─────────────────────────────────────────────
    ep.chapter_card("오늘 만들 것", "파이 · 백엔드 · 화면이 주고받는 것")
    ep.diagram("flow", [
        (["pi", "e_report", "e_poll", "be"], ["파이는 문 상태를 door_sensor_1로 보고하고, buzzer_1의 목표 상태를 물어봅니다. 1편에서 만들었습니다."]),
        (["be", "rule", "e_rule"], ["백엔드 담당이 할 일은 둘입니다. 두 기기를 등록하는 것, 그리고 잠긴 문이 열리면 부저를 켜는 규칙입니다."]),
        (["fe", "e_ws"], ["프론트 담당은 관리자 화면에 문 센서와 부저를 보여 주고, 새로고침 없이 바로 바뀌게 합니다."]),
        (["role_be", "role_fe", "be", "rule", "fe"], ["고칠 곳은 backend와 frontend 폴더입니다."], ["door", "pi", "buzzer"]),
    ])
    ep.card("완료 기준 — 먼저 적어 둡니다", DONE_ITEMS, [
        ["무엇이 되면 '완료'인지부터 적습니다. 1편과 같은 기준입니다."],
        ["세 사람의 코드가 모두 맞아야 이 기준이 채워집니다."],
        ["마지막에 파이와 관리자 화면을 함께 돌려서 눈으로 확인합니다."],
    ])

    # 2 ─────────────────────────────────────────────
    ep.chapter_card("기기 등록", "시드 데이터 세 곳을 함께")
    ep.ide("backend-agent", [
        prompt("너는 이 프로젝트의 backend-agent다. `.agents/skills/iot-endpoint-generator`와 `.agents/rules/db-rules.md`를 참고해.\n\n"
               "문 열림 센서(`door_sensor_1`, kind `reed`)와 경고 부저(`buzzer_1`, kind `buzzer`)를 기기로 등록해 줘.\n"
               "- 시드 데이터 세 곳(`database.py`, `init.sql`, `init_supabase.sql`)을 같이 맞춰\n"
               "- 문 센서 이력은 `sensor_readings`에서 읽게 해\n"
               "- 관련 없는 파일은 건드리지 마", [
            "역할은 backend-agent, 참고 파일은 iot-endpoint-generator 스킬과 db-rules입니다.",
            "기기 id와 종류(kind)를 정확히 적습니다. 파이 코드의 이름과 한 글자까지 같아야 합니다.",
        ], cps=30),
        reply("계획입니다.\n\n"
              "1. 시드 데이터 세 곳에 두 기기를 추가합니다 — `database.py`(서버가 켜질 때 넣는 목록), `init.sql`(MariaDB), `init_supabase.sql`(Supabase)\n"
              "2. `routers/devices.py`의 이력 조회가 `reed` 종류도 `sensor_readings`에서 읽도록 합니다\n\n테이블 구조는 바꾸지 않습니다.",
              ["backend/db/database.py", "backend/db/init.sql", "backend/db/init_supabase.sql", "backend/routers/devices.py"], [
            "세 시드 파일을 함께 맞추는 것이 중요합니다. 하나만 고치면 컴퓨터마다 기기 목록이 달라집니다.",
        ]),
        edit("web_diff_b1", "backend/db/database.py", [0], ["database.py입니다. 서버가 켜질 때마다 이 목록을 DB에 넣습니다."]),
        edit("web_diff_b1", "backend/db/init.sql", [0], ["init.sql, 학교 노트북의 MariaDB용 초기 데이터입니다."]),
        edit("web_diff_b1", "backend/db/init_supabase.sql", [0], ["init_supabase.sql, 클라우드 Supabase용입니다. 세 파일의 기기 목록이 같아졌습니다."]),
        edit("web_diff_b1", "backend/routers/devices.py", [0], ["문 센서는 센서이므로, 이력을 조회할 때 sensor_readings 표에서 읽도록 reed를 더했습니다."]),
        term("web_be_start", ["서버를 다시 켭니다. 'seed data verified'가 보이면 새 기기가 DB에 들어간 것입니다."],
             cmd="uvicorn main:app --port 8000", speed=1.0),
    ])

    # 3 ─────────────────────────────────────────────
    ep.chapter_card("시행착오 ① 가끔만 되는 404", "재시작 직후를 의심합니다")
    ep.ide("backend-agent", [
        hold(["화면이 아직 없으니 curl로 부저를 직접 켜 보겠습니다. 기기 제어는 관리자만 할 수 있어서 로그인 토큰이 필요합니다."]),
        term("web_login", ["관리자 PIN으로 로그인하면 토큰을 줍니다. 이 토큰을 다음 명령에 붙입니다."]),
        term("web_trial_unknown", ["그런데 404, Unknown device_id: buzzer_1이 나옵니다. 방금 DB에 넣었는데 없다고 합니다."]),
        term("web_trial_get", ["이상해서 buzzer_1을 조회해 보니 잘 나옵니다."]),
        term("web_trial_retry", ["그리고 다시 켜 보면, 이번에는 됩니다. 서버를 막 켰을 때는 안 되고, 한 번 조회하고 나면 됩니다.",
                                 "이렇게 '가끔만 되는' 오류가 가장 헷갈립니다."]),
        prompt("서버를 재시작한 직후에 buzzer_1 을 control 하면 404 Unknown device_id: buzzer_1 이 나와. "
               "GET /api/devices/buzzer_1 을 한 번 하고 나면 control 이 돼. 원인이 뭐야?", [
            "무엇을 했을 때 안 되고, 무엇을 한 뒤에는 되는지를 있는 그대로 적었습니다.",
        ], cps=34),
        reply("원인은 `backend/iot/mock_provider.py`의 `_devices` 사전입니다.\n\n"
              "제어(`set_actuator_state`)는 이 사전에 있는 기기만 받는데, 새 기기는 DB에만 있고 사전에는 없습니다. "
              "조회를 하면 DB 행이 사전에 복사되기 때문에 그다음부터 되는 거예요.\n\n"
              "사전에 `buzzer_1`과 `door_sensor_1`을 넣어 두면 재시작 직후에도 됩니다.", ["backend/iot/mock_provider.py"], [
            "기기 등록은 DB 시드만으로 끝나지 않았습니다. 메모리에 있는 기기 사전에도 넣어야 합니다.",
        ]),
        edit("web_diff_b1fix", "backend/iot/mock_provider.py", [0, 1], [
            "두 기기를 사전에 추가합니다. 하드웨어 모드도 이 사전을 함께 씁니다.",
        ]),
        term("web_fix_retry", ["서버를 다시 켜고 곧바로 부저를 켜 봅니다. 이번에는 처음부터 됩니다."]),
    ])

    # 4 ─────────────────────────────────────────────
    ep.chapter_card("규칙 만들기", "언제 확인하는지까지 적습니다")
    ep.ide("backend-agent", [
        prompt("이제 규칙을 추가해 줘. 도어락이 잠금(locked)인데 `door_sensor_1`이 열림(1)이면 `buzzer_1`을 on, 아니면 off.\n"
               "- `BoothService`에 `check_door_alarm()`으로 만들고\n"
               "- 문 센서 보고를 받을 때, 이용 종료로 문을 잠글 때, 키패드로 문을 열 때 불러\n"
               "- 부저가 바뀌면 WebSocket으로 알려 줘", [
            "규칙을 말로 정확히 적습니다. 규칙을 언제 확인하는지, 곧 호출 시점까지 적는 것이 핵심입니다.",
        ], cps=30),
        reply("계획입니다.\n\n"
              "1. `services/booth_service.py`에 `check_door_alarm()` 추가 — 도어락 · 문 센서 · 부저 상태를 읽고, 부저가 이미 그 상태면 아무것도 하지 않습니다\n"
              "2. 부르는 곳: 문 센서 보고(`routers/devices.py`), 이용 종료, 키패드 인증 두 곳\n"
              "3. 부저가 바뀌면 `device_state`를 방송합니다",
              ["backend/services/booth_service.py", "backend/routers/devices.py"]),
        edit("web_diff_b2", "backend/services/booth_service.py", [3], [
            "규칙 함수입니다. 문이 열렸는지, 도어락이 잠겼는지 보고 부저를 켤지 끌지 정합니다.",
            "부저가 이미 그 상태면 아무것도 하지 않습니다. 같은 지시를 되풀이해 보내지 않기 위해서입니다.",
        ]),
        edit("web_diff_b2", "backend/services/booth_service.py", [0, 1, 2], [
            "키패드로 문을 열 때 두 곳, 이용 종료로 문을 잠글 때 한 곳에서 규칙을 부릅니다.",
        ]),
        edit("web_diff_b2", "backend/routers/devices.py", [0], [
            "파이가 문 상태를 보고하면 곧바로 규칙을 확인합니다.",
            "규칙에서 오류가 나도 파이의 보고까지 실패하지 않도록 try로 감쌌습니다.",
        ]),
    ])

    # 5 ─────────────────────────────────────────────
    ep.chapter_card("시행착오 ② 부저가 안 울린다", "이 영상을 만들다 실제로 난 오류")
    ep.ide("backend-agent", [
        hold(["파이 대신 curl로 '문 열림'을 보고해 보겠습니다. X-Device-Api-Key에는 backend/.env의 DEVICE_API_KEY를 넣습니다."]),
        term("web_rule_open1", ["보고는 잘 들어갔습니다."]),
        term("web_rule_check1", ["그런데 부저의 목표 상태가 off입니다. 문이 열렸는데 부저가 켜지지 않았습니다."]),
        term("web_rule_lock", ["도어락을 조회해 봅니다. current_state는 locked인데 desired_state가 null입니다."]),
        prompt("door_sensor_1 에 value 1 을 보고했는데 buzzer_1 desired_state 가 off 야. "
               "door_lock_1 을 조회하면 desired_state 는 null, current_state 는 locked 로 나와. check_door_alarm 이 왜 부저를 안 켜?", [
            "조회 결과를 그대로 붙여 넣었습니다.",
        ], cps=36),
        reply("원인을 찾았습니다.\n\n"
              "규칙이 `lock.get(\"desired_state\") == \"locked\"`만 보는데, 한 번도 제어하지 않은 도어락은 `desired_state`가 비어(null) 있습니다. "
              "그래서 잠겨 있는데도 조건이 거짓이 됐어요.\n\n"
              "`desired_state`가 비어 있으면 파이가 보고한 `current_state`를 보도록 고치겠습니다.", ["backend/services/booth_service.py"], [
            "이 오류는 이 영상을 만들면서 실제로 났습니다. 새 DB에서 처음 실행할 때만 생겨서 지나치기 쉽습니다.",
        ]),
        edit("web_diff_b2fix", "backend/services/booth_service.py", [0], [
            "desired_state가 비어 있으면 current_state를 보도록 두 줄을 고쳤습니다.",
        ], focus=["lock_state"]),
        term("web_rule_open2", ["서버를 다시 켜고 같은 보고를 다시 보냅니다."]),
        term("web_rule_check2", ["이번에는 부저 목표 상태가 on입니다."]),
        term("web_rule_close", ["문 닫힘, 곧 0을 보고하면"]),
        term("web_rule_check3", ["부저가 off로 돌아옵니다."]),
        term("web_rule_serverlog", ["서버 로그에도 규칙이 언제, 왜 부저를 켜고 껐는지 남습니다. 문제가 생기면 이 로그부터 봅니다."],
             cmd="", label="백엔드 서버 로그", only=r"문 열림 경고|door_sensor_1/state", gap=0.5),
    ])

    # 6 ─────────────────────────────────────────────
    ep.chapter_card("관리자 화면", "있는 버튼과 토큰을 그대로 씁니다")
    ep.ide("frontend-agent", [
        prompt("너는 이 프로젝트의 frontend-agent다. `.agents/rules/ui-ux-rules.md`와 `.agents/skills/dashboard-ui-design`을 참고해.\n\n"
               "관리자 화면 `VirtualBoothSimulator.tsx`에서 PIR 줄 아래에 문 열림 센서(열림/닫힘)와 경고 부저(울림/꺼짐)를 보여 주고, "
               "직접 제어 버튼에 '경고 부저 울리기/끄기'를 추가해 줘.\n"
               "- 기존 색 토큰만 쓰고, 아이콘은 lucide-react\n"
               "- 문 센서는 `current_value`가 1이면 열림", [
            "이제 프론트 담당 차례입니다. 역할은 frontend-agent, UI 규칙 파일을 참고하게 합니다.",
            "어느 파일의 어디에, 무엇을 보여 줄지, 값을 어떻게 해석할지까지 적습니다.",
        ], cps=30),
        reply("계획입니다.\n\n"
              "1. `door_sensor_1`, `buzzer_1`을 기기 목록에서 찾아 상태를 계산합니다\n"
              "2. PIR 줄 아래에 '문 열림 센서: 열림/닫힘'과 '경고 부저 울림/꺼짐'을 표시합니다\n"
              "3. 직접 제어에 '경고 부저 울리기/끄기' 버튼을 추가합니다 — 제어는 이미 있는 `onDeviceControl`을 그대로 씁니다",
              ["frontend/components/booth/VirtualBoothSimulator.tsx"]),
        edit("web_diff_f1", "frontend/components/booth/VirtualBoothSimulator.tsx", [0], ["lucide-react에서 문과 종 아이콘 네 개를 가져옵니다."]),
        edit("web_diff_f1", "frontend/components/booth/VirtualBoothSimulator.tsx", [1, 2], [
            "기기 목록에서 두 기기를 찾고, current_value가 1이면 열림, current_state가 on이면 울림으로 해석합니다.",
        ]),
        edit("web_diff_f1", "frontend/components/booth/VirtualBoothSimulator.tsx", [5], [
            "PIR 줄 아래에 문 센서와 부저를 표시합니다. 위험한 상태는 이미 있는 빨간색 live 토큰으로 보여 줍니다.",
        ]),
        edit("web_diff_f1", "frontend/components/booth/VirtualBoothSimulator.tsx", [6], [
            "버튼은 다른 버튼과 같은 모양이고, 누르면 이미 있는 onDeviceControl로 제어합니다. 새 API는 필요 없습니다.",
        ]),
        term("web_build1", ["npm run build로 타입 검사와 빌드를 합니다. 오류 없이 끝났습니다."], speed=3.0,
             drop=r"^\s*$|^> "),
    ])

    # 7 ─────────────────────────────────────────────
    ep.chapter_card("시행착오 ③ 새로고침해야 바뀐다", "비교해서 적으면 원인이 보입니다")
    ep.browser("web_ui_trial", 2.0, 22.0, PANEL, [
        (2.2, "1편의 파이 프로그램을 켜고, o를 눌러 문을 열어 봅니다."),
        (6.6, "경고 부저는 '울림'으로 바뀌었는데, 문 열림 센서는 아직 '닫힘'입니다."),
        (14.2, "새로고침을 하자 그제야 '열림'으로 바뀝니다. 실시간이 아닙니다."),
    ], term="pi_with_ui_trial", highlights=[
        {"from": 6.6, "to": 13.9, "box": DOOR_ROW, "label": "부저는 울리는데 문은 '닫힘'?"},
        {"from": 15.4, "to": 20.0, "box": DOOR_ROW, "label": "새로고침하니 '열림'"},
    ])
    ep.ide("frontend-agent", [
        prompt("문을 열면 '경고 부저 울림'은 바로 바뀌는데 '문 열림 센서'는 새로고침해야 '열림'으로 바뀌어. 왜 그래?", [
            "무엇은 바로 바뀌고 무엇은 안 바뀌는지, 비교해서 적은 것이 원인을 찾는 열쇠였습니다.",
        ], cps=30),
        reply("백엔드는 센서 값이 오면 WebSocket으로 `sensor_reading`을, 부저가 바뀌면 `device_state`를 보냅니다.\n\n"
              "그런데 `hooks/useBoothData.ts`는 `device_state`만 처리하고 `sensor_reading`은 무시하고 있습니다. 부저만 바로 바뀐 이유예요.\n\n"
              "`sensor_reading`을 처리하는 부분을 추가하겠습니다.", ["frontend/hooks/useBoothData.ts"]),
        edit("web_diff_f2", "frontend/hooks/useBoothData.ts", [0], [
            "sensor_reading을 받으면 그 기기의 current_value를 바로 바꿉니다. 일곱 줄입니다.",
        ]),
        term("web_build2", ["다시 빌드합니다."], speed=3.0, drop=r"^\s*$|^> "),
    ])

    # 8 ─────────────────────────────────────────────
    ep.chapter_card("함께 돌려 보기", "완료 기준을 눈으로 확인")
    ep.browser("web_ui_live", 2.0, 24.5, PANEL, [
        (2.2, "고친 화면을 1편의 파이 프로그램과 함께 돌립니다."),
        (6.4, "이제 문을 열자 문 센서와 부저가 동시에 바뀝니다. 새로고침은 필요 없습니다."),
        (16.4, "문을 닫으면 둘 다 곧바로 돌아옵니다."),
        (20.6, "처음에 정한 완료 기준을 눈으로 확인했습니다."),
    ], term="pi_with_ui_live", highlights=[
        {"from": 6.3, "to": 16.2, "box": DOOR_ROW, "label": "문 열림 → 부저 울림"},
        {"from": 16.4, "to": 22.0, "box": DOOR_ROW, "label": "문 닫힘 → 부저 꺼짐"},
    ])

    # 9 ─────────────────────────────────────────────
    ep.chapter_card("정리", "단계마다 확인하고 커밋")
    ep.ide("", [
        term("wrap_gitlog", [
            "확인을 마칠 때마다 커밋했습니다. 1편과 2편을 합쳐 일곱 단계입니다.",
            "이 일곱 커밋은 docs/실습-문센서-부저/patches 폴더에 패치 파일로 들어 있습니다.",
        ], label="git"),
    ], keep=False)
    ep.card("기억할 것", [
        {"text": "새 기기는 시드 세 곳과 `mock_provider.py` 사전에 함께 등록한다"},
        {"text": "'가끔만 된다'는 오류는 서버를 막 켠 직후를 의심한다"},
        {"text": "규칙은 처음 실행하는 빈 DB에서도 시험한다"},
        {"text": "센서 값의 실시간 반영은 `sensor_reading` 처리"},
    ], [["오늘 겪은 시행착오를 네 줄로 정리했습니다."], ["재시작 직후에 안 되고 나중에 되면, 메모리와 DB가 다른 경우가 많습니다."],
        ["빈 DB에서는 값이 null인 경우가 있습니다."], ["백엔드가 보내는 메시지 종류와 화면이 처리하는 종류가 맞는지 확인합니다."]])
    ep.end_card("실습 끝", "docs/실습-문센서-부저 폴더에 단계별 패치와 대본이 있습니다", [
        "AI가 고친 코드는 직접 읽고, 직접 실행하고, 눈으로 확인하세요. 수고하셨습니다.",
    ])
    return ep


def build(which, Ep):
    return {"pi": ep_pi, "web": ep_web}[which](Ep)
