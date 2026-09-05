---
name: vision-recognition-integration
description: >-
  웹캠 기반 YOLOv8/mediapipe 영상인식 파이프라인 구성, Windows 패키지 의존성 설정 및 감지 이벤트 백엔드 전송을 구현할 때 사용하는 스킬.
---

# vision-recognition-integration

> 웹캠 영상인식(YOLO/mediapipe) 연동 작업 시 이 스킬을 참고한다.

## 패키지 설치 (Windows 환경 최적화)
Windows에서 Python 3.14/3.13 혼재로 인한 C++ DLL 로드 에러(`[WinError 1114]`)와 260자 경로 길이 제한 에러를 방지하기 위해 **반드시 Python 3.12로 `venv`를 생성**하고 사전 구성된 `requirements.txt`로 설치한다.

```powershell
cd vision
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> ⚠️ **가상환경 폴더명 주의**: `.gitignore`에 `venv/`가 등록되어 있으므로 반드시 폴더명을 `venv`로 통일한다 (`venv312` 등 임의 명칭 금지).

> ⚠️ **얼굴인식 라이브러리 주의**: Windows에서 Visual Studio C++ 빌드 도구 미설치로 컴파일 에러를 내는 `dlib` / `face_recognition` 라이브러리는 **절대 사용하지 않는다.**  
> 대신 C++ 빌드 없이 100% 휠로 설치되는 **`onnxruntime` (경량 ArcFace ONNX, LFW 99.5%+)** 또는 **OpenCV DNN (`YuNet` + `SFace`)**을 사용한다.
> OpenCV 웹캠 화면에 한글 텍스트 출력 시 글자 깨짐 방지를 위해 `Pillow(PIL)`를 활용한다.

## 최소 파이프라인 (YOLOv8n ONNX 예시 — PyTorch 없는 순수 초경량 추론)
PyTorch 설치 없이 사전 제공된 `yolov8n.onnx` 모델과 `onnxruntime` 또는 OpenCV DNN으로 초고속 추론을 수행한다.
```python
import cv2
import numpy as np
import onnxruntime as ort

session = ort.InferenceSession("yolov8n.onnx")
input_name = session.get_inputs()[0].name
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Windows에서는 CAP_DSHOW로 열어야 안정적

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    # 640x640 정규화 blob 생성 (BGR -> RGB)
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
    outputs = session.run(None, {input_name: blob})
    preds = np.transpose(outputs[0][0])  # shape: (8400, 84)

    # COCO Class 0 = Person 감지
    person_scores = preds[:, 4]
    detected = np.any(person_scores >= 0.45)
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
