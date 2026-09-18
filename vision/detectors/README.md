# `vision/detectors/` — 감지 "방법"을 넣는 곳

팀마다 카메라로 보는 것이 다릅니다. wakeup은 손동작, classroom은 출입, study는 좌석과 집중도,
subway는 혼잡도. 그래서 **vision을 통째로 공통화하지 않고** pi의 `drivers/`와 같은 구조로 쪼갰습니다.

```
main.py                  공통 — 카메라를 열고, 검출기를 돌리고, 보내고, 보여 줌 (고치지 않음)
camera.py                공통 — USB 웹캠 / Pi Camera 자동 선택 (고치지 않음)
detectors/
  base.py                공통 — 검출기 계약 (고치지 않음)
  __init__.py            공통 — 폴더를 훑어 자동으로 찾는 로더 (고치지 않음)
  objects.py             공통 — 사물 탐지(YOLO). 4팀이 같이 씀 (고치지 않음)
  hands_rps.py           ★ wakeup 팀 — 가위바위보 손동작
  _hands_rps_engine.py     `_`로 시작하면 검출기가 아닌 보조 모듈
  study_focus.py         ★ study 팀 — 한 사람의 집중도 (눈·고개·시선)
  _focus_engine.py         EAR·고개각·시선 계산 (보조 모듈)
  study_seats.py         본보기 — 화면을 좌석 구역으로 나눠 보는 법
  <우리팀>.py             ★ 여기에 파일 하나 추가하면 끝
```

다른 팀은 자기 것이 아닌 팀 파일(`hands_rps*`, `study_*`)을 지워도 됩니다.
다만 **본보기로 남겨 두는 편이 편합니다** — 구조를 볼 때 씁니다.

- `study_focus.py` — **한 사람을 정밀하게** 볼 때 (얼굴·눈)
- `study_seats.py` — **여러 구역을 나눠서** 볼 때 (좌석·구간·분단)

## 규칙 두 가지

1. 파일 안에 `FrameDetector`를 상속한 **`Detector` 클래스**를 둡니다.
2. 검출기가 아닌 보조 모듈은 파일 이름을 **`_`로 시작**하세요 (로더가 건너뜁니다).

등록할 곳은 없습니다. 파일을 넣으면 자동으로 인식되고, 부팅할 때 백엔드에 라벨을 신고합니다.

---

## 무엇을 어디에 담나 — 이것만 지키면 됩니다

| 담을 것 | 어디에 | 예 |
|---|---|---|
| **무엇을/어디를** 봤나 | `label` | `"person"` · `"rock"` · `"seat_3"` |
| 보였나 / 사라졌나 | `detected` | `True` / `False` |
| **얼마나 확신**하나 | `confidence` | `0.91` |
| 같은 것이 몇 개인가 | `count` | `7` (사람 7명) |
| **그 밖의 값** | `extra` | `{"state": "drowsy", "focus_score": 0.21}` |

### ⚠️ `confidence`에 측정 점수를 넣지 마세요

`confidence`는 "내가 얼마나 확신하는가"입니다. 집중도·밝기·거리 같은 **측정값**을 여기 넣으면
자동화 규칙의 `min_confidence`가 낮은 값을 걸러내서 **조용히 무시됩니다.**
측정값은 `extra`에 담으세요.

### ⚠️ `extra`는 실시간에만 갑니다

`extra`는 검출기 → 백엔드 → **화면(WebSocket)**까지 그대로 갑니다.
하지만 **DB에는 저장되지 않습니다.** 나중에 다시 볼 이력은 `label`로 남기세요.

- 크기: JSON 2KB · 키 20개까지. 넘으면 **422로 분명히 거절**합니다(조용히 버리지 않습니다).
- 좌표 배열이나 이미지를 통째로 담지 마세요 — 실시간 중계가 밀립니다. **요약된 값**만.

---

## 여러 곳을 따로 봐야 할 때 (좌석·구역)

라벨은 **'어디'**, extra는 **'어떤 상태'**로 나눕니다.

```python
class Detector(FrameDetector):
    name = "study_seats"
    labels = ("seat_1", "seat_2", "seat_3", "seat_4", "seat_5", "seat_6")   # 어디

    def detect(self, frame_bgr, config):
        return [
            DetectionEvent(
                label="seat_3", detected=True, confidence=0.92,
                event_type="seat_state",
                extra={"state": "drowsy", "focus_score": 0.21},             # 어떤
            ),
        ]
```

화면에서는 이렇게 받습니다.

```tsx
onVision(["seat_1", "seat_2", "seat_3", "seat_4", "seat_5", "seat_6"], (e) => {
  const seat = e.label;                      // "seat_3"
  const state = e.extra?.state;              // "drowsy"
  const focus = e.extra?.focus_score;        // 0.21
});
```

> 라벨에 상태까지 욱여넣으면(`seat_3_drowsy`) 좌석 수 × 상태 수만큼 라벨이 불어나고
> 화면에서 문자열을 쪼개야 합니다. 자리와 상태를 나누면 둘 다 깔끔해집니다.

---

## 화면을 나눠 볼 때는 `find_people()`을 쓰세요

좌석·구간처럼 화면을 나눠 보려면 사람 상자가 필요합니다.
**YOLO 모델을 새로 올리지 마세요** — 이미 올라와 있는 것을 함께 씁니다.

```python
from .objects import find_people

for person in find_people(frame_bgr, min_confidence=0.5):
    x1, y1, x2, y2 = person["box"]      # 이 상자가 어느 구역에 드는지 보면 됩니다
    person["confidence"]                # 0.93
```

돌아가는 예시가 `study_seats.py`에 있습니다 — 화면을 좌석 구역으로 나누고
구역마다 점유를 봅니다. 좌석 위치는 파일 맨 위 `SEATS`에서 **화면 비율**로 고칩니다.

---

## 얼굴·눈을 보려면 — 거리와 해상도가 먼저입니다

MediaPipe는 얼굴을 잘라 **192×192로 맞춰** 눈을 찾습니다. 얼굴이 그보다 작게 잡히면
늘려 쓰느라 눈꺼풀·눈동자가 뭉갭니다. **대수를 늘리기 전에 거리와 해상도를 보세요.**

| 배치 | 얼굴 폭(추정) | 눈을 잴 수 있나 |
|---|---|---|
| FHD · 0.5~1.0m (책상 앞) | 220~530px | ✅ 눈동자·시선까지 |
| 640×480 · 3m (여러 자리를 한 화면에) | 24~30px | ❌ 안 됨 |

`vision/.env`에 `CAMERA_WIDTH=1920` `CAMERA_HEIGHT=1080`을 넣고,
웹캠 창의 `face ___px` 숫자를 보며 카메라를 옮겨 맞춥니다.

돌아가는 예시가 `study_focus.py`입니다 — 눈 감김(EAR)·고개 숙임·시선 이탈을 재서
`extra`로 보냅니다. **"졸고 있다"는 판정은 하지 않습니다** — 프론트엔드가 합니다.

### 전송 주기보다 짧은 일은 창(window)으로 모으세요

전송은 `cooldown_seconds`(기본 2.5초)에 한 번입니다. 그 순간 한 프레임만 실어 보내면
하필 눈을 깜빡인 프레임이 잡혀 "졸고 있음"이 됩니다. `_focus_engine.py`의
`WindowAccumulator`처럼 **모았다가 요약해서** 보내세요.

### 사람마다 다른 것은 처음 몇 초로 배우세요

얼굴 비율은 사람마다 다릅니다. "고개를 숙였다"를 고정 숫자로 판단하면 누구는 늘 숙인
것이 되고 누구는 절대 안 숙인 것이 됩니다. `Calibration`이 처음 8초로 그 사람의 '정면'을
기록해 기준으로 삼습니다.

## 라이브러리가 없을 때

`self.disable("이유")`를 부르면 **그 검출기만** 빠지고 나머지는 그대로 돌아갑니다.
MediaPipe가 없다고 사물 감지까지 멈추면 수업이 멈춥니다.

```python
def __init__(self) -> None:
    super().__init__()
    try:
        import mediapipe
    except Exception as exc:
        self.disable(f"MediaPipe를 쓸 수 없습니다: {exc}")
```

웹캠 창을 켤 때 `[O]` / `[X]`로 상태가 보이고, `[X]`면 옆에 이유가 적힙니다.

---

## 검출기는 판정하지 않습니다

"무엇이 보이는가"만 말하고, **이겼는지·혼잡한지·졸고 있는지는 프론트엔드 시나리오**가 판정합니다
(docs/부록F 9-2절). 그래야 같은 감지 결과를 팀마다 다르게 쓸 수 있습니다.

---

## 확인

```bash
cd vision && python test_vision_config.py     # 검출기 계약 자가 점검 (45항목)
cd vision && python test_study_focus.py       # 집중도 측정 자가 점검 (63항목, 웹캠 없이)
python -c "import sys; sys.path.insert(0,'.'); from detectors import available_detectors; print(available_detectors())"
```

자세한 규약은 [docs/부록F 10장](../../docs/부록F-IoT-개발-플랫폼-키트-규약.md),
학생용 안내는 [docs/00 매뉴얼 6장](../../docs/00-2차개발-통합-매뉴얼.md)에 있습니다.
