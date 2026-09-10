import logging
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from gesture import RockPaperScissorsDetector

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

HAND_EMOJI_KO = {"rock": "주먹", "paper": "보", "scissors": "가위"}

# 4. 한글 폰트 로드 유틸리티
_FONT_CACHE: Dict[int, ImageFont.ImageFont] = {}


def get_korean_font(size: int = 18) -> ImageFont.ImageFont:
    """시스템 한글 폰트를 로드합니다 (윈도우 맑은 고딕 우선, 없으면 리눅스 폰트)."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    font_paths = [
        "C:/Windows/Fonts/malgun.ttf",   # 맑은 고딕
        "C:/Windows/Fonts/malgunbd.ttf",  # 맑은 고딕 볼드
        "C:/Windows/Fonts/gulim.ttc",    # 굴림
        "C:/Windows/Fonts/batang.ttc",   # 바탕
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # 리눅스
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",       # macOS
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue

    # 폴백: 기본 비트맵 폰트 (한글은 깨질 수 있음)
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
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


# ==============================================================================
# 5. 백엔드 통신 (영상 루프를 절대 멈추지 않도록 별도 스레드에서 처리)
# ==============================================================================

class BackendClient:
    """
    이벤트 전송과 미션 상태 조회를 백그라운드 스레드에서 처리합니다.

    예전에는 영상 루프 안에서 곧바로 requests.post를 호출해서,
    백엔드가 꺼져 있으면 매 프레임 최대 2.5초씩 멈추고 화면이 얼어붙었습니다.
    이제 큐에 넣기만 하므로 영상은 끊기지 않습니다.
    """

    def __init__(self, backend_url: str, api_key: str):
        self.backend_url = backend_url
        self.headers = {
            "X-Device-Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=32)
        self._running = True
        self._session = requests.Session()

        self.last_send_ok: Optional[bool] = None
        self.mission: Dict[str, Any] = {"active": False}

        self._sender = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender.start()
        self._poller = threading.Thread(target=self._status_loop, daemon=True)
        self._poller.start()

    def send_event(
        self,
        event_type: str,
        detected: bool,
        label: Optional[str] = None,
        count: int = 0,
        confidence: Optional[float] = None,
    ) -> None:
        """이벤트를 큐에 넣습니다 (즉시 반환 — 영상 루프를 막지 않음)."""
        payload = {
            "event_type": event_type,
            "detected": detected,
            "count": count,
            "confidence": round(float(confidence), 2) if confidence is not None else None,
            "label": label,
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.debug("전송 큐가 가득 차 이벤트를 건너뜁니다 (백엔드 응답 지연).")

    def _sender_loop(self) -> None:
        url = f"{self.backend_url}/api/v1/vision/events"
        while self._running:
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                res = self._session.post(url, json=payload, headers=self.headers, timeout=2.5)
                if res.status_code == 200:
                    self.last_send_ok = True
                    logger.info(
                        f"[이벤트 전송] {payload['event_type']} "
                        f"label={payload['label']} conf={payload['confidence']}"
                    )
                else:
                    self.last_send_ok = False
                    logger.warning(f"[이벤트 응답 오류] {res.status_code} - {res.text[:120]}")
            except requests.exceptions.RequestException as exc:
                self.last_send_ok = False
                logger.warning(f"[백엔드 통신 실패] {url}: {exc}")

    def _status_loop(self) -> None:
        """1초마다 미션 상태를 읽어 화면에 '무엇을 내야 하는지' 표시한다."""
        url = f"{self.backend_url}/api/alarm/status"
        while self._running:
            try:
                res = self._session.get(url, timeout=2.0)
                if res.status_code == 200:
                    self.mission = res.json().get("data", {}).get("mission", {"active": False})
            except requests.exceptions.RequestException:
                self.mission = {"active": False}
            time.sleep(1.0)

    def close(self) -> None:
        self._running = False


# ==============================================================================
# 6. 초경량 YOLOv8 ONNX 추론 엔진 (ONNX Runtime + OpenCV DNN 폴백)
# ==============================================================================

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

        # 미션 대상 클래스만 먼저 걸러낸다.
        # (NMS를 먼저 돌리면, 관심 없는 큰 물체가 미션 대상 박스를 눌러 버려 감지가 사라질 수 있다)
        if target_classes is not None:
            mask &= np.isin(class_ids, list(target_classes))

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
            for idx in np.array(indices).flatten():
                cid = int(class_ids[idx])
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


# ==============================================================================
# 7. 메인 루프
# ==============================================================================

def main():
    if not DEVICE_API_KEY:
        print("[안내] DEVICE_API_KEY가 설정되어 있지 않습니다. vision/.env에 백엔드와 같은 키를 넣어 주세요.\n")

    # 모델 파일 경로 확인
    onnx_path = os.path.join(os.path.dirname(__file__), "yolov8n.onnx")
    if not os.path.exists(onnx_path):
        logger.error(f"yolov8n.onnx 모델을 찾을 수 없습니다: {onnx_path}")
        return

    logger.info(f"초경량 YOLOv8 ONNX 검출기 초기화 중: {onnx_path}")
    detector = YOLOv8ONNXDetector(onnx_path, conf_threshold=0.45, iou_threshold=0.45)

    # 가위바위보 손동작 검출기 (MediaPipe가 없으면 자동으로 꺼짐)
    gesture_detector = RockPaperScissorsDetector()

    # 백엔드 통신 (백그라운드 스레드)
    backend = BackendClient(BACKEND_URL, DEVICE_API_KEY)

    # 웹캠 초기화 (Windows에서는 DirectShow 백엔드로 열어야 안정적)
    logger.info(f"카메라 인덱스 {CAMERA_INDEX} 초기화 시도...")
    if os.name == "nt":
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            logger.warning("CAP_DSHOW로 카메라 열기 실패, 기본 백엔드로 재시도합니다.")
            cap = cv2.VideoCapture(CAMERA_INDEX)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        logger.error(f"카메라(인덱스 {CAMERA_INDEX})를 열 수 없습니다. 웹캠 연결을 확인하세요.")
        backend.close()
        return

    # 해상도 설정
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 현재 활성 미션 대상 (기본: person)
    current_target_id = 0
    current_target_info = MISSION_TARGETS[0]
    detect_all_mode = False
    gesture_mode = gesture_detector.available

    # 이벤트 전송 상태 관리
    last_detected_state: Optional[bool] = None
    last_event_time: float = 0.0
    EVENT_COOLDOWN_SECONDS = 2.5

    last_hand: Optional[str] = None
    last_hand_sent_at: float = 0.0
    HAND_COOLDOWN_SECONDS = 1.5

    print("\n" + "=" * 68)
    print(" [스마트 기상 시스템 - 기상 미션 비전 클라이언트]")
    print(f" * 엔진: {detector.engine_name}")
    print(f" * 백엔드 URL: {BACKEND_URL}")
    print(f" * 가위바위보(MediaPipe): {'사용 가능' if gesture_detector.available else '사용 불가 → 사물 미션만'}")
    print(f" * 기본 미션 대상: [{current_target_info['ko']}]")
    print(" * 키보드 단축키:")
    print("   - [1]: 사람(person) 기상 감지 모드")
    print("   - [2]: 물병(bottle) 기상 미션 모드")
    print("   - [3]: 컵(cup) 양치/물 기상 미션 모드")
    print("   - [4]: 책(book) 독서 기상 미션 모드")
    print("   - [5]: 휴대폰(cell phone) 기상 미션 모드")
    print("   - [A]: 전체 사물 자동 감지 모드 (All)")
    print("   - [G]: 가위바위보 손동작 인식 켜기/끄기")
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
            now = time.time()

            # -------- 가위바위보 손동작 인식 --------
            hand_result = None
            if gesture_mode and gesture_detector.available:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hand_result = gesture_detector.detect(frame_rgb)

            if hand_result:
                gesture_detector.draw(frame, hand_result.get("points"))
                hand = hand_result["hand"]
                # 손 모양이 바뀌었거나 쿨다운이 지났을 때만 전송한다
                if hand != last_hand or now - last_hand_sent_at >= HAND_COOLDOWN_SECONDS:
                    backend.send_event(
                        event_type="gesture_detected",
                        detected=True,
                        label=hand,
                        count=1,
                        confidence=hand_result["confidence"],
                    )
                    last_hand = hand
                    last_hand_sent_at = now
            elif gesture_mode:
                last_hand = None

            # -------- 사물 감지 (YOLO) --------
            target_classes = list(MISSION_TARGETS.keys()) if detect_all_mode else [current_target_id]
            detections = detector.detect(frame, target_classes=target_classes)

            detected_count = len(detections)
            is_detected = detected_count > 0

            max_confidence = 0.0
            primary_label = current_target_info["name"]

            # 감지된 객체 바운딩 박스 렌더링
            for det in detections:
                conf = det["confidence"]
                if conf > max_confidence:
                    max_confidence = conf
                    primary_label = det["class_name"]

                x1, y1, x2, y2 = det["box"]
                color = (0, 220, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

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

            # 사물 이벤트 전송 판정 (상태가 바뀌거나 쿨다운 경과 시)
            should_send = (
                last_detected_state is None
                or is_detected != last_detected_state
                or now - last_event_time >= EVENT_COOLDOWN_SECONDS
            )

            if should_send:
                backend.send_event(
                    event_type="object_detected" if is_detected else "object_cleared",
                    detected=is_detected,
                    label=primary_label if is_detected else current_target_info["name"],
                    count=detected_count,
                    confidence=max_confidence if is_detected else 0.0,
                )
                last_detected_state = is_detected
                last_event_time = now

            # ==================================================================
            # 화면 상단 HUD 정보 오버레이 (한글 렌더링 지원)
            # ==================================================================
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 74), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

            mode_text = "전체 사물 감지" if detect_all_mode else current_target_info["ko"]
            status_text = f"미션 감지 성공! ({detected_count}개)" if is_detected else "미션 대상 찾는 중..."
            status_color = (100, 255, 100) if is_detected else (180, 180, 180)

            frame = put_korean_text(frame, f"현재 미션: {mode_text}", (14, 4), font_size=17, color=(255, 255, 255))
            frame = put_korean_text(frame, status_text, (14, 26), font_size=15, color=status_color)

            # 진행 중인 기상 미션이 있으면 '무엇을 내야 하는지' 크게 보여준다
            mission = backend.mission or {}
            if mission.get("active"):
                ai_hand = mission.get("ai_hand")
                expected = mission.get("expected_hand")
                wins = mission.get("wins", 0)
                need = mission.get("required_wins", 2)
                if ai_hand and expected:
                    guide = (
                        f"AI: {HAND_EMOJI_KO.get(ai_hand, ai_hand)}  →  "
                        f"당신은 [{HAND_EMOJI_KO.get(expected, expected)}]  ({wins}/{need}승)"
                    )
                    frame = put_korean_text(frame, guide, (14, 48), font_size=16, color=(120, 220, 255))
            elif gesture_mode and hand_result:
                frame = put_korean_text(
                    frame,
                    f"인식된 손동작: {HAND_EMOJI_KO.get(hand_result['hand'], hand_result['hand'])}",
                    (14, 48), font_size=15, color=(120, 220, 255)
                )

            # 우측 상단 FPS / 엔진 / 백엔드 연결 상태
            conn = "백엔드 OK" if backend.last_send_ok else ("백엔드 응답없음" if backend.last_send_ok is False else "대기")
            engine_info = f"{detector.engine_name} | {fps_display} FPS"
            cv2.putText(frame, engine_info, (w - 250, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
            frame = put_korean_text(
                frame, conn, (w - 250, 34), font_size=14,
                color=(120, 255, 120) if backend.last_send_ok else (150, 150, 255)
            )

            # 하단 조작 단축키 안내 띠
            cv2.rectangle(frame, (0, h - 26), (w, h), (15, 15, 15), -1)
            gesture_badge = "ON" if gesture_mode else ("OFF" if gesture_detector.available else "불가")
            frame = put_korean_text(
                frame,
                f"단축키: [1]사람 [2]물병 [3]컵 [4]책 [5]휴대폰 [A]전체 [G]가위바위보({gesture_badge}) [Q]종료",
                (10, h - 22),
                font_size=13,
                color=(210, 210, 210)
            )

            # 윈도우 창 표시
            cv2.imshow("Wakeup Vision Mission (ONNX + MediaPipe)", frame)

            # 키보드 입력 처리
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("사용자에 의해 종료 명령(q)이 입력되었습니다.")
                break
            elif key in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5")):
                target_map = {ord("1"): 0, ord("2"): 39, ord("3"): 41, ord("4"): 73, ord("5"): 67}
                current_target_id = target_map[key]
                current_target_info = MISSION_TARGETS[current_target_id]
                detect_all_mode = False
                last_detected_state = None
                logger.info(f"미션 대상 변경: {current_target_info['ko']}")
            elif key == ord("a"):
                detect_all_mode = not detect_all_mode
                last_detected_state = None
                logger.info(f"전체 감지 모드 토글: {detect_all_mode}")
            elif key == ord("g"):
                if gesture_detector.available:
                    gesture_mode = not gesture_mode
                    logger.info(f"가위바위보 인식 토글: {gesture_mode}")
                else:
                    logger.warning("MediaPipe가 설치되어 있지 않아 가위바위보 인식을 켤 수 없습니다.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        gesture_detector.close()
        backend.close()
        logger.info("웹캠 및 OpenCV 리소스가 안전하게 해제되었습니다.")


if __name__ == "__main__":
    main()
