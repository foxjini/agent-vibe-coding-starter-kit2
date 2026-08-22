---
name: vision-recognition-integration
description: >-
  웹캠 기반 YOLOv8/mediapipe 영상인식 파이프라인 구성, Windows 패키지 의존성 설정 및 감지 이벤트 백엔드 전송을 구현할 때 사용하는 스킬.
---

# vision-recognition-integration

> 웹캠 영상인식(YOLO/mediapipe) 연동 작업 시 이 스킬을 참고한다.

## 패키지 설치 (Windows 주의)
Windows 기본 경로 길이 제한(260자)과 최신 NumPy 2.x·PyTorch 바이너리 충돌로
`pip install ultralytics`가 `[WinError 206] 파일 이름이나 확장명이 너무 깁니다`로
실패할 수 있다. 아래처럼 버전을 고정해서 설치한다.
```powershell
cd vision
python -m venv venv
.\venv\Scripts\Activate.ps1
# 1. 경로 에러가 없는 경량 CPU PyTorch 설치
pip install torch==2.2.2+cpu torchvision==0.17.2+cpu --extra-index-url https://download.pytorch.org/whl/cpu
# 2. 호환 패키지 설치
pip install "numpy<2" opencv-python==4.9.0.80 ultralytics mediapipe requests python-dotenv
```
그래도 경로 에러가 나면 관리자 권한 PowerShell에서 Windows 긴 경로 제한을 아예
해제한다(FAQ 참고):
```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## 최소 파이프라인 (YOLOv8n 예시 — 실제 검증된 조합)
사람 감지처럼 "특정 인물 식별이 아닌 사람/사물 존재 여부"에는 mediapipe의
얼굴 감지보다 YOLOv8n(경량 객체 감지 모델)이 더 적합하고 실제로도 검증됐다.
```python
import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Windows에서는 CAP_DSHOW로 열어야 웹캠 인식이 안정적

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    results = model(frame, classes=[0], verbose=False)  # class 0 = person
    detected = len(results[0].boxes) > 0
    # 상태가 바뀔 때만 이벤트 전송 (vision-rules.md 참고)
```

<details>
<summary>mediapipe로도 가능 (얼굴 감지 등 다른 용도일 때)</summary>

```python
import cv2
import mediapipe as mp

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
detector = mp.solutions.face_detection.FaceDetection()

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    result = detector.process(frame)
    detected = bool(result.detections)
```
</details>

## 이벤트 전송
```python
import requests
requests.post(
    f"{BACKEND_URL}/api/v1/vision/events",
    json={"event_type": "person_detected", "detected": True, "count": 1, "confidence": 0.9},
    headers={"X-Device-Api-Key": DEVICE_API_KEY},
)
```

## 트리거 연결
백엔드(backend-agent)가 `vision_events`를 받아 팀이 정한 트리거 규칙(AGENTS.md의
"팀 정보" 표 참고)에 따라 desired-state를 갱신한다. vision 클라이언트는 감지 사실만
보고할 뿐, 제어를 직접 판단하지 않는다.

## 손동작 인식 (mediapipe Hands, 학습 없음)
가위바위보처럼 손가락 개수/모양을 구분해야 하는 미션에는 mediapipe의 Hands 솔루션을
쓴다. 위의 얼굴 감지 예시와 같은 라이브러리이며, 사전학습된 모델이라 별도 데이터 수집·
학습이 필요 없다.
```python
import mediapipe as mp

hands = mp.solutions.hands.Hands(max_num_hands=1)
result = hands.process(frame_rgb)
if result.multi_hand_landmarks:
    landmarks = result.multi_hand_landmarks[0].landmark
    # 각 손가락 끝(tip) 관절이 그 아래 관절보다 위에 있으면 "펴짐"으로 판정해
    # 펴진 손가락 개수를 센다: 0개=바위, 2개(검지+중지)=가위, 5개=보
```
`vision/requirements.txt`에 `mediapipe`가 필요하다.

## 미션별 감지 대상 전환 (현재 미션 폴링)
감지 대상이 하나로 고정되지 않고 단계에 따라 바뀌는 프로젝트(예: 기상 미션)에서는,
desired-state 폴링과 동일한 패턴으로 "지금 무엇을 인식해야 하는지"를 몇 초마다
백엔드에 물어본다. 엔드포인트 정의와 백엔드 구현은
`alarm-scheduling-integration` 스킬을 참고한다.
```python
r = requests.get(
    f"{BACKEND_URL}/api/v1/vision/current-mission",
    headers={"X-Device-Api-Key": DEVICE_API_KEY},
)
mission = r.json()["data"]  # {"mission_type": "rps"|"object"|None, "active": bool, "target_object": str|None}
```
`active`가 `False`면 인식을 멈추고 대기한다(불필요한 카메라 연산·오탐 방지).

## 이벤트 형식 확장 (다중 미션용)
감지 대상이 여러 개일 때는 기본 이벤트 형식(`event_type`/`detected`/`count`/
`confidence`)에 `mission_type`, `label`을 추가해 어떤 미션에서 무엇이 인식됐는지
구분한다.
```python
requests.post(
    f"{BACKEND_URL}/api/v1/vision/events",
    json={
        "event_type": "mission_result",
        "mission_type": "rps",       # "rps" | "object"
        "label": "scissors",         # 인식된 결과
        "detected": True,
        "count": 1,
        "confidence": 0.92,
    },
    headers={"X-Device-Api-Key": DEVICE_API_KEY},
)
```
