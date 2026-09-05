---
name: vision-recognition-integration
description: >-
  웹캠 기반 YOLOv8/mediapipe 영상인식 파이프라인 구성, Windows 패키지 의존성 설정 및 감지 이벤트 백엔드 전송을 구현할 때 사용하는 스킬.
---

# vision-recognition-integration

> 웹캠 영상인식(YOLO/mediapipe) 연동 작업 시 이 스킬을 참고한다.

## 패키지 설치 (Windows 초경량 ONNX 환경)
수 GB에 달하는 무거운 PyTorch(`torch`, `ultralytics`) 없이, 표준 `onnxruntime`과 `opencv-python`만으로 약 5~10초 만에 환경을 구축한다. Python 3.13/3.14 설치 시 발생하는 NumPy 2.x 바이너리 충돌과 DLL 로드 오류(`[WinError 1114]`)를 방지하기 위해 반드시 Python 3.12로 가상환경을 구성하고 `requirements.txt`를 설치한다.

```powershell
cd vision
# 1. Python 3.12 가상환경 생성 (.gitignore 호환을 위해 폴더명은 반드시 venv로 고정)
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# 2. 초경량 의존성 일괄 설치 (PyTorch 불필요, 5~10초 완료)
pip install -r requirements.txt
```

> ⚠️ **비전 AI 개발 4대 원칙**:
> 1. **PyTorch 불필요 (초경량 ONNX 구동)**: `yolov8n.onnx`와 `onnxruntime`을 사용하여 메모리 사용량을 100MB대로 낮추고 30+ FPS 실시간 추론을 보장합니다.
> 2. **venv 폴더명 유지**: `venv312` 등으로 바꾸면 Git 추적 제외 목록(.gitignore)에서 벗어나 불필요한 파일이 커밋될 수 있습니다.
> 3. **C++ 빌드 지옥 방지 (dlib 절대 금지)**: Windows에서 Visual Studio C++ 빌드 에러를 일으키는 `dlib`/`face_recognition` 대신, LFW 99.5%+ 인식률의 `onnxruntime`(ArcFace ONNX), OpenCV DNN(YuNet+SFace), 또는 `mediapipe`를 사용합니다.
> 4. **웹캠 한글 깨짐 방지**: OpenCV `cv2.putText` 대신 `Pillow`(PIL ImageDraw)를 사용해 한글 텍스트를 출력합니다.

그래도 경로 에러(`[WinError 206]`)가 발생하면 관리자 권한 PowerShell에서 Windows 긴 경로 제한을 해제한다:
```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## 최소 파이프라인 (YOLOv8 ONNX 예시 — 실제 검증된 조합)
`onnxruntime` 또는 OpenCV 내장 `cv2.dnn`을 사용하여 `yolov8n.onnx`를 로드하고 추론한다.
```python
import cv2
import onnxruntime as ort

# ONNX 모델 로드
session = ort.InferenceSession("yolov8n.onnx", providers=["CPUExecutionProvider"])
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Windows에서는 CAP_DSHOW로 열어야 웹캠 인식이 안정적

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    # vision/main.py의 YOLOv8ONNXDetector 참조
    # 상태가 바뀔 때만 백엔드로 이벤트 전송 (vision-rules.md 참고)
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
