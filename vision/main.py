import logging
import os
import sys
import time
import cv2
import numpy as np
import requests
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("vision.main")

# .env 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")

if not DEVICE_API_KEY:
    logger.error("DEVICE_API_KEY가 설정되지 않았습니다. vision/.env를 확인하세요.")
    sys.exit(1)

# PyTorch / YOLO 로드 시도 (Python 3.14 등 환경에서 DLL 이슈 발생 시 모션/가상 시뮬레이터로 자동 fallback)
yolo_model = None
try:
    from ultralytics import YOLO
    if os.path.exists(MODEL_PATH):
        logger.info("YOLOv8n 모델 로딩 중...")
        yolo_model = YOLO(MODEL_PATH)
        logger.info("YOLOv8n 모델 로드 성공.")
except Exception as exc:
    logger.warning(f"PyTorch/YOLO 네이티브 모듈 로드 스킵 ({exc})")
    logger.info("OpenCV 모션 감지기 및 가상 시뮬레이터 모드로 자동 동작합니다.")


def send_vision_event(event_type: str, detected: bool, count: int = 1, confidence: float = 0.9) -> bool:
    """백엔드 API로 비전 감지 이벤트 전송"""
    url = f"{BACKEND_URL}/api/v1/vision/events"
    headers = {
        "X-Device-Api-Key": DEVICE_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "event_type": event_type,
        "detected": detected,
        "count": count,
        "confidence": confidence
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=2.0)
        if res.status_code == 200:
            logger.info(f"-> 비전 이벤트 백엔드 전송 성공: {event_type} (감지: {detected}, 인원: {count})")
            return True
        else:
            logger.warning(f"비전 이벤트 전송 실패 [HTTP {res.status_code}]: {res.text}")
            return False
    except Exception as exc:
        logger.warning(f"백엔드 연결 실패 ({BACKEND_URL}): {exc}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("스마트 학교 노래방 부스 영상인식 클라이언트")
    logger.info(f"백엔드 주소: {BACKEND_URL}")
    logger.info(f"엔진 모드: {'YOLOv8n' if yolo_model else 'OpenCV Motion / Virtual Simulator'}")
    logger.info("단축키: 'p' = 사람 감지 토글 | 'q' = 종료")
    logger.info("=" * 60)

    # OpenCV 배경 차분 모션 감지기 (YOLO 불가 시 경량 fallback)
    subtractor = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=50, detectShadows=False)

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    has_real_camera = cap.isOpened()

    if not has_real_camera:
        logger.warning("웹캠 장치를 찾을 수 없어 [가상 카메라 시뮬레이터 화면]으로 동작합니다.")
        logger.info("창을 클릭하고 키보드 'p' 키를 누르면 사람 감지/미감지 상태를 즉시 토글할 수 있습니다.")

    prev_detected = False
    simulated_detected = False
    last_report_time = 0.0

    try:
        while True:
            frame = None
            if has_real_camera:
                ret, frame = cap.read()
                if not ret:
                    has_real_camera = False

            if not has_real_camera or frame is None:
                # 640x480 가상 화면 캔버스
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "KARAOKE BOOTH VISION CLIENT", (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                cv2.putText(frame, "Engine: " + ("YOLOv8n" if yolo_model else "OpenCV Motion / Virtual Simulator"), (30, 85),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 200, 255), 1)
                cv2.putText(frame, "Press 'p': Toggle Person Detection", (30, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(frame, "Press 'q': Quit", (30, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

                state_text = "STATUS: PERSON DETECTED (ENTERING)" if simulated_detected else "STATUS: STANDBY (NO PERSON)"
                state_color = (50, 220, 50) if simulated_detected else (80, 80, 220)
                cv2.rectangle(frame, (25, 200), (615, 320), (30, 30, 30), -1)
                cv2.rectangle(frame, (25, 200), (615, 320), state_color, 2)
                cv2.putText(frame, state_text, (45, 270),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, state_color, 2)

                detected = simulated_detected
                count = 1 if detected else 0
                conf = 0.95 if detected else 0.0
            else:
                if yolo_model:
                    results = yolo_model(frame, classes=[0], verbose=False)
                    boxes = results[0].boxes
                    count = len(boxes)
                    detected = count > 0
                    conf = float(boxes.conf[0].item()) if detected and boxes.conf is not None else 0.0
                    frame = results[0].plot()
                else:
                    # 배경 차분 모션 감지
                    fg_mask = subtractor.apply(frame)
                    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    large_contours = [c for c in contours if cv2.contourArea(c) > 6000]
                    count = len(large_contours)
                    detected = count > 0 or simulated_detected
                    conf = 0.85 if detected else 0.0

                    for c in large_contours:
                        (x, y, w, h) = cv2.boundingRect(c)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(frame, "Person Motion", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # 상태가 변경되었거나 주기(10초) 경과 시 백엔드 트리거 전송
            current_time = time.time()
            if detected != prev_detected or (detected and (current_time - last_report_time > 10.0)):
                send_vision_event(
                    event_type="person_detected",
                    detected=detected,
                    count=count,
                    confidence=round(conf, 2)
                )
                prev_detected = detected
                last_report_time = current_time

            cv2.imshow("Smart Karaoke Booth - Vision Client", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                simulated_detected = not simulated_detected
                logger.info(f"사람 감지 상태 수동 토글: {simulated_detected}")

    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
