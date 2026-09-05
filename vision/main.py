import logging
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("vision.main")

# 1. 환경 변수 로드 (.env)
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

# 2. COCO 80종 클래스 이름 목록
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

# 3. 기상 미션 감지 대상 매핑
MISSION_TARGETS: Dict[int, Dict[str, str]] = {
    0: {"name": "person", "ko": "사람 (기상/기립 확인)"},
    39: {"name": "bottle", "ko": "물병 (물 한 잔 마시기)"},
    41: {"name": "cup", "ko": "컵 (양치/물 마시기)"},
    73: {"name": "book", "ko": "책 (독서/두뇌 깨우기)"},
    67: {"name": "cell phone", "ko": "휴대폰 (알람 해제 확인)"},
}

# 4. 한글 폰트 로드 유틸리티
_FONT_CACHE: Dict[int, ImageFont.FreeTypeFont] = {}

def get_korean_font(size: int = 18) -> ImageFont.ImageFont:
    """Windows 시스템 맑은 고딕 폰트를 우선 로드합니다."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    font_paths = [
        "C:/Windows/Fonts/malgun.ttf",  # 맑은 고딕
        "C:/Windows/Fonts/malgunbd.ttf",# 맑은 고딕 볼드
        "C:/Windows/Fonts/gulim.ttc",   # 굴림
        "C:/Windows/Fonts/batang.ttc",  # 바탕
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue

    # 폴백: 기본 비트맵 폰트
    font = ImageFont.load_default()
    return font


def put_korean_text(
    img: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_size: int = 18,
    color: Tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """OpenCV 이미지(BGR) 위에 깨짐 없는 한글 텍스트를 오버레이합니다."""
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    font = get_korean_font(font_size)

    # PIL 색상은 RGB 기준
    rgb_color = (color[2], color[1], color[0])
    draw.text(position, text, font=font, fill=rgb_color)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


# 5. 초경량 YOLOv8 ONNX 추론 엔진 (ONNX Runtime + OpenCV DNN 폴백)
class YOLOv8ONNXDetector:
    """
    PyTorch 설치 없이 onnxruntime 또는 cv2.dnn 만으로 동작하는
    초경량 YOLOv8 검출기.
    """
    def __init__(self, model_path: str, conf_threshold: float = 0.45, iou_threshold: float = 0.45):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = (640, 640)
        self.engine_name = "Unknown"
        self.session = None
        self.net = None

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX 모델 파일이 없습니다: {model_path}")

        # 1차 시도: onnxruntime (초고속 SIMD 최적화)
        try:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.engine_name = "ONNX Runtime (CPU)"
            logger.info(f"성공적으로 로드됨: {self.engine_name}")
        except Exception as e:
            logger.warning(f"onnxruntime 로드 실패 ({e}), OpenCV DNN으로 폴백합니다.")
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.engine_name = "OpenCV DNN (Fallback)"
            logger.info(f"성공적으로 로드됨: {self.engine_name}")

    def _letterbox(self, img: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """비율을 유지하며 640x640 패딩 이미지를 생성합니다."""
        h, w = img.shape[:2]
        target_w, target_h = self.input_size
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)

        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        return canvas, scale, (pad_x, pad_y)

    def detect(self, img: np.ndarray, target_classes: Optional[List[int]] = None) -> List[Dict]:
        """
        이미지에서 객체를 감지하여 바운딩 박스 목록을 반환합니다.
        반환: [{"box": [x1, y1, x2, y2], "class_id": int, "class_name": str, "confidence": float}]
        """
        h_orig, w_orig = img.shape[:2]
        canvas, scale, (pad_x, pad_y) = self._letterbox(img)

        # HWC(BGR) -> CHW(RGB) 정규화
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, self.input_size, swapRB=True, crop=False)

        if self.session is not None:
            outputs = self.session.run([self.output_name], {self.input_name: blob})[0]
        else:
            self.net.setInput(blob)
            outputs = self.net.forward()

        # YOLOv8 출력 텐서 형태: (1, 84, 8400) -> 84 = [cx, cy, w, h, 80개 클래스 점수]
        output = np.squeeze(outputs).T  # (8400, 84)

        boxes = output[:, 0:4]
        scores = output[:, 4:]
        class_ids = np.argmax(scores, axis=1)
        confidences = scores[np.arange(len(scores)), class_ids]

        # 1차 필터링: 신뢰도 기준
        mask = confidences >= self.conf_threshold
        boxes = boxes[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]

        if len(boxes) == 0:
            return []

        # 원본 이미지 좌표로 변환
        boxes_xywh = []
        for box in boxes:
            cx, cy, w, h = box
            x1 = (cx - w / 2.0 - pad_x) / scale
            y1 = (cy - h / 2.0 - pad_y) / scale
            bw = w / scale
            bh = h / scale
            boxes_xywh.append([int(x1), int(y1), int(bw), int(bh)])

        indices = cv2.dnn.NMSBoxes(boxes_xywh, confidences.tolist(), self.conf_threshold, self.iou_threshold)

        results = []
        if len(indices) > 0:
            for idx in indices.flatten():
                cid = int(class_ids[idx])
                if target_classes is not None and cid not in target_classes:
                    continue

                x, y, w, h = boxes_xywh[idx]
                x1 = max(0, min(w_orig, x))
                y1 = max(0, min(h_orig, y))
                x2 = max(0, min(w_orig, x + w))
                y2 = max(0, min(h_orig, y + h))

                class_name = COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else f"cls_{cid}"
                results.append({
                    "box": [x1, y1, x2, y2],
                    "class_id": cid,
                    "class_name": class_name,
                    "confidence": float(confidences[idx]),
                })

        return results


# 6. 백엔드 이벤트 전송 함수
def send_vision_event(
    event_type: str,
    detected: bool,
    count: int = 0,
    confidence: Optional[float] = None
) -> None:
    url = f"{BACKEND_URL}/api/v1/vision/events"
    headers = {
        "X-Device-Api-Key": DEVICE_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "event_type": event_type,
        "detected": detected,
        "count": count,
        "confidence": round(float(confidence), 2) if confidence is not None else None,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=2.5)
        if response.status_code == 200:
            logger.info(
                f"[이벤트 전송 성공] {event_type} (detected={detected}, count={count}, conf={payload['confidence']})"
            )
        else:
            logger.warning(
                f"[이벤트 전송 응답 오류] {response.status_code} - {response.text}"
            )
    except requests.exceptions.RequestException as exc:
        logger.warning(f"[백엔드 통신 실패] {url} 연결 불가: {exc}")


# 7. 메인 루프
def main():
    # 모델 파일 경로 확인 (yolov8n.onnx 우선, 없으면 yolov8n.pt 안내)
    onnx_path = os.path.join(os.path.dirname(__file__), "yolov8n.onnx")
    if not os.path.exists(onnx_path):
        logger.error(f"yolov8n.onnx 모델을 찾을 수 없습니다: {onnx_path}")
        return

    logger.info(f"초경량 YOLOv8 ONNX 검출기 초기화 중: {onnx_path}")
    detector = YOLOv8ONNXDetector(onnx_path, conf_threshold=0.45, iou_threshold=0.45)

    # 웹캠 초기화 (Windows에서는 DirectShow 백엔드로 열어야 안정적)
    logger.info(f"카메라 인덱스 {CAMERA_INDEX} 초기화 시도...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        logger.warning("CAP_DSHOW로 카메라 열기 실패, 기본 백엔드로 재시도합니다.")
        cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        logger.error(f"카메라(인덱스 {CAMERA_INDEX})를 열 수 없습니다. 웹캠 연결을 확인하세요.")
        return

    # 해상도 설정
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 현재 활성 미션 대상 (기본: person)
    current_target_id = 0
    current_target_info = MISSION_TARGETS[0]
    detect_all_mode = False

    # 이벤트 전송 상태 관리
    last_detected_state: Optional[bool] = None
    last_event_time: float = 0.0
    EVENT_COOLDOWN_SECONDS = 2.5

    print("\n" + "=" * 68)
    print(" [스마트 기상 시스템 - 초경량 ONNX 기상 미션 비전 클라이언트]")
    print(f" * 엔진: {detector.engine_name}")
    print(f" * 백엔드 URL: {BACKEND_URL}")
    print(f" * 기본 미션 대상: [{current_target_info['ko']}]")
    print(" * 키보드 단축키:")
    print("   - [1]: 사람(person) 기상 감지 모드")
    print("   - [2]: 물병(bottle) 기상 미션 모드")
    print("   - [3]: 컵(cup) 양치/물 기상 미션 모드")
    print("   - [4]: 책(book) 독서 기상 미션 모드")
    print("   - [5]: 휴대폰(cell phone) 기상 미션 모드")
    print("   - [A]: 전체 사물 자동 감지 모드 (All)")
    print("   - [Q]: 프로그램 종료")
    print("=" * 68 + "\n")

    fps_time = time.time()
    fps_count = 0
    fps_display = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("프레임을 읽을 수 없습니다.")
                time.sleep(0.1)
                continue

            fps_count += 1
            if time.time() - fps_time >= 1.0:
                fps_display = round(fps_count / (time.time() - fps_time), 1)
                fps_count = 0
                fps_time = time.time()

            # 좌우 반전 (거울 효과)
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # ONNX 객체 감지 추론
            target_classes = list(MISSION_TARGETS.keys()) if detect_all_mode else [current_target_id]
            detections = detector.detect(frame, target_classes=target_classes)

            detected_count = len(detections)
            is_detected = detected_count > 0

            max_confidence = 0.0
            primary_label = current_target_info["name"]

            # 감지된 객체 바운딩 박스 렌더링
            for det in detections:
                cid = det["class_id"]
                conf = det["confidence"]
                if conf > max_confidence:
                    max_confidence = conf
                    primary_label = det["class_name"]

                x1, y1, x2, y2 = det["box"]
                color = (0, 220, 0) if is_detected else (200, 200, 200)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # 라벨 표시 (한글 이름 매핑 지원)
                ko_name = MISSION_TARGETS.get(cid, {}).get("ko", det["class_name"])
                label_text = f"{det['class_name']} ({conf * 100:.0f}%)"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
                cv2.putText(
                    frame,
                    label_text,
                    (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0),
                    1,
                    cv2.LINE_AA,
                )

            # 백엔드 이벤트 전송 판정
            now = time.time()
            should_send = False
            if last_detected_state is None or is_detected != last_detected_state:
                should_send = True
            elif now - last_event_time >= EVENT_COOLDOWN_SECONDS:
                should_send = True

            if should_send:
                event_type = f"{primary_label}_detected" if is_detected else f"{current_target_info['name']}_cleared"
                send_vision_event(
                    event_type=event_type,
                    detected=is_detected,
                    count=detected_count,
                    confidence=max_confidence if is_detected else 0.0,
                )
                last_detected_state = is_detected
                last_event_time = now

            # ==================================================================
            # 화면 상단 HUD 정보 오버레이 (한글 렌더링 지원)
            # ==================================================================
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 52), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

            # 타깃 정보 텍스트 (한글)
            mode_text = "전체 사물 감지" if detect_all_mode else current_target_info["ko"]
            status_text = f"미션 감지 성공! ({detected_count}개)" if is_detected else "미션 대상 찾는 중..."
            status_color = (100, 255, 100) if is_detected else (180, 180, 180)

            # 한글 오버레이
            frame = put_korean_text(frame, f"현재 미션: {mode_text}", (14, 6), font_size=17, color=(255, 255, 255))
            frame = put_korean_text(frame, status_text, (14, 28), font_size=15, color=status_color)

            # 우측 상단 FPS 및 엔진 정보
            engine_info = f"{detector.engine_name} | {fps_display} FPS"
            cv2.putText(
                frame,
                engine_info,
                (w - 240, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

            # 하단 조작 단축키 안내 띠
            cv2.rectangle(frame, (0, h - 26), (w, h), (15, 15, 15), -1)
            frame = put_korean_text(
                frame,
                "단축키: [1]사람 [2]물병 [3]컵 [4]책 [5]휴대폰 [A]전체모드 [Q]종료",
                (10, h - 22),
                font_size=13,
                color=(210, 210, 210)
            )

            # 윈도우 창 표시
            cv2.imshow("Wakeup Vision Mission (ONNX Ultra-Light)", frame)

            # 키보드 입력 처리
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("사용자에 의해 종료 명령(q)이 입력되었습니다.")
                break
            elif key == ord("1"):
                current_target_id = 0
                current_target_info = MISSION_TARGETS[0]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("2"):
                current_target_id = 39
                current_target_info = MISSION_TARGETS[39]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("3"):
                current_target_id = 41
                current_target_info = MISSION_TARGETS[41]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("4"):
                current_target_id = 73
                current_target_info = MISSION_TARGETS[73]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("5"):
                current_target_id = 67
                current_target_info = MISSION_TARGETS[67]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("a"):
                detect_all_mode = not detect_all_mode
                logger.info(f"전체 감지 모드 토글: {detect_all_mode}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        logger.info("웹캠 및 OpenCV 리소스가 안전하게 해제되었습니다.")


if __name__ == "__main__":
    main()
