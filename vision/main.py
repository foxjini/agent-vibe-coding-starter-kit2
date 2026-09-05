import logging
import os
import sys
import time
import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

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
ONNX_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.onnx")

if not DEVICE_API_KEY:
    logger.error("DEVICE_API_KEY가 설정되지 않았습니다. vision/.env를 확인하세요.")
    sys.exit(1)


class YOLOv8ONNXDetector:
    """
    PyTorch/Ultralytics 없이 순수 ONNX Runtime / OpenCV DNN으로
    초경량·초고속 사람 감지(Person Detection)를 수행하는 엔진
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.session = None
        self.net = None
        self.engine_name = "None"
        self.input_name = None
        self.input_shape = (640, 640)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}")

        # 1. ONNX Runtime 시도 (가장 최적화된 고속 C++ 엔진)
        try:
            import onnxruntime as ort
            # 경고 억제
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.engine_name = f"ONNX Runtime ({ort.__version__})"
            logger.info(f"ONNX Runtime 엔진 로드 완료: {model_path}")
            return
        except Exception as exc:
            logger.warning(f"ONNX Runtime 로드 스킵 ({exc}) -> OpenCV DNN으로 전환 시도")

        # 2. OpenCV DNN 시도 (의존성 없는 내장 순수 엔진)
        try:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.engine_name = "OpenCV DNN (Built-in)"
            logger.info(f"OpenCV DNN 엔진 로드 완료: {model_path}")
        except Exception as exc:
            logger.error(f"OpenCV DNN 로드 실패: {exc}")
            raise exc

    def detect(self, img: np.ndarray, conf_threshold: float = 0.45, nms_threshold: float = 0.5):
        """사람(Person, COCO Class 0) 감지 및 바운딩 박스 반환"""
        img_h, img_w = img.shape[:2]

        # 640x640 정규화 blob 생성 (BGR -> RGB, 0~1 스케일링)
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (640, 640), swapRB=True, crop=False)

        if self.session is not None:
            outputs = self.session.run(None, {self.input_name: blob})
            preds = np.transpose(outputs[0][0])  # shape: (8400, 84)
        else:
            self.net.setInput(blob)
            output = self.net.forward()
            preds = np.transpose(output[0])  # shape: (8400, 84)

        boxes = []
        confidences = []
        scale_x = img_w / 640.0
        scale_y = img_h / 640.0

        for i in range(preds.shape[0]):
            # 84개 값: [cx, cy, w, h, class0_score, class1_score, ...]
            # class 0 = person
            person_score = float(preds[i][4])
            if person_score >= conf_threshold:
                cx, cy, w, h = preds[i][:4]
                x1 = int((cx - w / 2.0) * scale_x)
                y1 = int((cy - h / 2.0) * scale_y)
                bw = int(w * scale_x)
                bh = int(h * scale_y)
                boxes.append([x1, y1, bw, bh])
                confidences.append(person_score)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
        detected_boxes = []
        detected_confs = []

        if len(indices) > 0:
            for idx in np.array(indices).flatten():
                detected_boxes.append(boxes[idx])
                detected_confs.append(confidences[idx])

        return detected_boxes, detected_confs


def put_korean_text(img: np.ndarray, text: str, pos: tuple, font_size: int = 20, color: tuple = (255, 255, 255)) -> np.ndarray:
    """Pillow를 이용해 웹캠 화면에 한글 폰트 깨짐 없이 텍스트 렌더링"""
    try:
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        # Windows 시스템 기본 맑은 고딕(malgun.ttf) 로드 시도
        try:
            font = ImageFont.truetype("malgun.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text(pos, text, font=font, fill=color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    except Exception:
        # Fallback to OpenCV putText
        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return img


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
    logger.info("스마트 학교 노래방 부스 초경량 영상인식 클라이언트 (Pure ONNX)")
    logger.info(f"백엔드 주소: {BACKEND_URL}")

    detector = None
    if os.path.exists(ONNX_MODEL_PATH):
        try:
            detector = YOLOv8ONNXDetector(ONNX_MODEL_PATH)
            logger.info(f"추론 엔진: {detector.engine_name}")
        except Exception as exc:
            logger.warning(f"ONNX 모델 로드 실패 ({exc})")
    else:
        logger.warning(f"ONNX 모델 파일이 없습니다: {ONNX_MODEL_PATH}")

    logger.info("단축키: 'p' = 사람 감지 토글 | 'q' = 종료")
    logger.info("=" * 60)

    # OpenCV 배경 차분 모션 감지기 (ONNX 모델 부재 시 경량 fallback)
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
                frame = put_korean_text(frame, "스마트 학교 노래방 부스 비전 클라이언트", (30, 30), font_size=22, color=(255, 255, 255))
                engine_str = detector.engine_name if detector else "OpenCV Motion / Virtual"
                frame = put_korean_text(frame, f"추론 엔진: {engine_str}", (30, 70), font_size=16, color=(160, 200, 255))
                frame = put_korean_text(frame, "단축키: 'p' = 입장 감지 토글 | 'q' = 프로그램 종료", (30, 105), font_size=15, color=(200, 200, 200))

                state_text = "상태: 사람 입장 감지됨 (WELCOME)" if simulated_detected else "상태: 부스 대기 중 (STANDBY)"
                state_color = (50, 220, 50) if simulated_detected else (80, 80, 220)
                cv2.rectangle(frame, (25, 180), (615, 300), (30, 30, 30), -1)
                cv2.rectangle(frame, (25, 180), (615, 300), state_color, 2)
                frame = put_korean_text(frame, state_text, (45, 225), font_size=24, color=state_color)

                detected = simulated_detected
                count = 1 if detected else 0
                conf = 0.95 if detected else 0.0
            else:
                if detector:
                    boxes, confs = detector.detect(frame, conf_threshold=0.45)
                    count = len(boxes)
                    detected = count > 0 or simulated_detected
                    conf = confs[0] if len(confs) > 0 else (0.95 if simulated_detected else 0.0)

                    for (x, y, w, h), c in zip(boxes, confs):
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        label = f"사람 (입장) {c:.2f}"
                        frame = put_korean_text(frame, label, (x, max(0, y - 25)), font_size=16, color=(0, 255, 0))
                else:
                    # 배경 차분 모션 감지 fallback
                    fg_mask = subtractor.apply(frame)
                    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    large_contours = [c for c in contours if cv2.contourArea(c) > 6000]
                    count = len(large_contours)
                    detected = count > 0 or simulated_detected
                    conf = 0.85 if detected else 0.0

                    for c in large_contours:
                        (x, y, w, h) = cv2.boundingRect(c)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        frame = put_korean_text(frame, "움직임 감지", (x, max(0, y - 25)), font_size=15, color=(0, 255, 0))

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

            cv2.imshow("Smart Karaoke Booth - Vision Client (Pure ONNX)", frame)
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
