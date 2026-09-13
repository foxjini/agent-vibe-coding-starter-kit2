"""
objects — YOLOv8로 사물·사람을 찾습니다. **모든 팀이 공통으로 씁니다.**

무엇을 찾을지는 코드에 없습니다. 서버 설정(`object_labels`)에서 받아옵니다
(대시보드 /kit → 영상인식 설정, docs/부록F 10장).

혼잡도·인원수처럼 "몇 명 보이는가"가 필요한 팀은 이벤트의 `count`를 쓰면 됩니다.
그 숫자가 혼잡인지 여유인지 판단하는 것은 프론트엔드 시나리오의 몫입니다.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np

from detectors.base import DetectionEvent, FrameDetector

logger = logging.getLogger("vision.detectors.objects")

# COCO 80종 클래스 이름 — YOLOv8n 모델이 내보내는 순서 그대로입니다.
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]
CLASS_INDEX = {name: index for index, name in enumerate(COCO_CLASSES)}

#: 자주 쓰는 클래스의 한글 이름 (없으면 영문 라벨을 그대로 보여 줍니다)
LABEL_KO: Dict[str, str] = {
    "person": "사람", "bottle": "물병", "cup": "컵", "book": "책",
    "cell phone": "휴대폰", "chair": "의자", "laptop": "노트북", "mouse": "마우스",
    "keyboard": "키보드", "backpack": "가방", "umbrella": "우산", "clock": "시계",
    "tv": "TV", "bed": "침대", "dog": "개", "cat": "고양이", "banana": "바나나",
    "apple": "사과", "scissors": "가위(사물)", "teddy bear": "곰인형", "toothbrush": "칫솔",
}


def label_ko(label: str) -> str:
    return LABEL_KO.get(label, label)


class Detector(FrameDetector):
    name = "objects"
    labels = ()           # COCO 80종 전체 — 설정에서 고른 것만 실제로 찾습니다
    description = "사물·사람 감지 (YOLOv8)"

    def __init__(self, model_path: str = None, conf_threshold: float = 0.45,
                 iou_threshold: float = 0.45):
        super().__init__()
        # 구역별로 나눠 보는 팀 검출기(좌석·구간 등)가 같은 엔진을 쓰도록 자기를 등록합니다.
        # 모델을 두 번 올리면 메모리도 두 배, 프레임도 느려집니다.
        global _SHARED
        if _SHARED is None:
            _SHARED = self
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = (640, 640)
        self.session = None
        self.net = None
        self.engine_name = "없음"
        #: 화면·단축키에서 쓰려고 마지막으로 본 대상 목록을 기억합니다
        self.watching: List[str] = []
        self.last_events: List[DetectionEvent] = []

        model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolov8n.onnx"
        )
        if not os.path.exists(model_path):
            self.disable(f"모델 파일이 없습니다: {model_path}")
            return

        try:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(
                model_path, options, providers=["CPUExecutionProvider"]
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.engine_name = "ONNX Runtime (CPU)"
        except Exception as exc:
            logger.warning(f"onnxruntime 로드 실패 ({exc}), OpenCV DNN으로 폴백합니다.")
            try:
                self.net = cv2.dnn.readNetFromONNX(model_path)
                self.engine_name = "OpenCV DNN (Fallback)"
            except Exception as inner:
                self.disable(f"YOLO 모델을 열지 못했습니다: {inner}")
                return
        logger.info(f"사물 감지 엔진: {self.engine_name}")

    # ------------------------------------------------------------------

    def _letterbox(self, img: np.ndarray):
        """비율을 유지하며 640x640 패딩 이미지를 만듭니다."""
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

    def _raw_detect(self, img: np.ndarray, target_classes: List[int]) -> List[Dict[str, Any]]:
        h_orig, w_orig = img.shape[:2]
        canvas, scale, (pad_x, pad_y) = self._letterbox(img)
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, self.input_size, swapRB=True, crop=False)

        if self.session is not None:
            outputs = self.session.run([self.output_name], {self.input_name: blob})[0]
        else:
            self.net.setInput(blob)
            outputs = self.net.forward()

        # YOLOv8 출력: (1, 84, 8400) → 84 = [cx, cy, w, h, 80개 클래스 점수]
        output = np.squeeze(outputs).T
        boxes = output[:, 0:4]
        scores = output[:, 4:]
        class_ids = np.argmax(scores, axis=1)
        confidences = scores[np.arange(len(scores)), class_ids]

        mask = confidences >= self.conf_threshold
        # 대상 클래스를 NMS보다 **먼저** 거른다.
        # (NMS를 먼저 돌리면 관심 없는 큰 물체가 대상 박스를 눌러 감지가 사라진다)
        if target_classes:
            mask &= np.isin(class_ids, target_classes)

        boxes = boxes[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]
        if len(boxes) == 0:
            return []

        # cxcywh → xyxy (원본 좌표계로 되돌리기)
        xyxy = np.empty_like(boxes)
        xyxy[:, 0] = (boxes[:, 0] - boxes[:, 2] / 2 - pad_x) / scale
        xyxy[:, 1] = (boxes[:, 1] - boxes[:, 3] / 2 - pad_y) / scale
        xyxy[:, 2] = (boxes[:, 0] + boxes[:, 2] / 2 - pad_x) / scale
        xyxy[:, 3] = (boxes[:, 1] + boxes[:, 3] / 2 - pad_y) / scale

        nms_boxes = [[int(x1), int(y1), int(x2 - x1), int(y2 - y1)] for x1, y1, x2, y2 in xyxy]
        indices = cv2.dnn.NMSBoxes(nms_boxes, confidences.tolist(),
                                   self.conf_threshold, self.iou_threshold)
        if len(indices) == 0:
            return []

        results = []
        for index in np.array(indices).flatten():
            x1, y1, x2, y2 = xyxy[index]
            class_id = int(class_ids[index])
            results.append({
                "box": [max(0, int(x1)), max(0, int(y1)),
                        min(w_orig, int(x2)), min(h_orig, int(y2))],
                "class_id": class_id,
                "class_name": COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else str(class_id),
                "confidence": float(confidences[index]),
            })
        return results

    # ------------------------------------------------------------------

    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        watching = [label for label in (config.get("object_labels") or []) if label in CLASS_INDEX]
        self.watching = watching
        if not watching:
            self.last_events = []
            return []

        min_confidence = float(config.get("min_confidence") or 0.0)
        target_classes = [CLASS_INDEX[label] for label in watching]

        detections = [d for d in self._raw_detect(frame_bgr, target_classes)
                      if d["confidence"] >= min_confidence]
        self._boxes = detections

        # 라벨별로 묶어 "무엇이 몇 개 보이는가"로 만든다
        grouped: Dict[str, List[float]] = {}
        for detection in detections:
            grouped.setdefault(detection["class_name"], []).append(detection["confidence"])

        events = [
            DetectionEvent(
                label=label,
                detected=True,
                confidence=max(confidences),
                count=len(confidences),
                event_type="object_detected",
            )
            for label, confidences in grouped.items()
        ]
        # 보고 있는데 안 보이는 것도 알려 준다 (사라짐을 시나리오가 알 수 있게)
        events += [
            DetectionEvent(label=label, detected=False, confidence=0.0, count=0,
                           event_type="object_cleared")
            for label in watching if label not in grouped
        ]
        self.last_events = events
        return events

    def draw(self, frame_bgr, events: Sequence[DetectionEvent]) -> None:
        for detection in getattr(self, "_boxes", []):
            x1, y1, x2, y2 = detection["box"]
            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(
                frame_bgr,
                f"{detection['class_name']} {detection['confidence']:.0%}",
                (x1, max(14, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1, cv2.LINE_AA,
            )

    def status_text(self) -> str:
        seen = [e for e in self.last_events if e.detected]
        if not self.watching:
            return "감지 대상이 설정되지 않았습니다"
        if not seen:
            return "대상을 찾는 중..."
        return "감지됨: " + ", ".join(f"{label_ko(e.label)}×{e.count}" for e in seen)


# ==============================================================================
# 구역별로 나눠 보는 팀 검출기를 위한 공개 도우미
# ==============================================================================
#
# study 팀의 좌석 6개, subway 팀의 객차 구간처럼 **화면을 나눠서 각각** 봐야 할 때가
# 있습니다. 그때마다 YOLO 모델을 새로 올리면 느려지므로, 이미 올라와 있는 엔진을
# 함께 쓰라고 아래 함수를 공개합니다. (이 파일 자체는 고치지 않습니다.)

_SHARED: Optional["Detector"] = None


def shared_detector() -> "Detector":
    """이미 올라와 있는 사물 탐지 엔진을 돌려줍니다 (없으면 그때 하나 만듭니다)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = Detector()
    return _SHARED


def find_people(frame_bgr, min_confidence: float = 0.5) -> List[Dict[str, Any]]:
    """
    화면에서 **사람 상자**를 찾아 돌려줍니다.

    좌석·구간처럼 화면을 나눠 보는 검출기가 쓰라고 만든 함수입니다.
    돌려주는 것: `[{"box": [x1, y1, x2, y2], "confidence": 0.93}, ...]`
    엔진이 준비되지 않았으면 빈 목록을 돌려줍니다(그 검출기만 조용히 쉽니다).

        from .objects import find_people

        for person in find_people(frame_bgr):
            x1, y1, x2, y2 = person["box"]
    """
    detector = shared_detector()
    if not detector.available or frame_bgr is None:
        return []
    person_class = CLASS_INDEX.get("person")
    if person_class is None:
        return []
    found = detector._raw_detect(frame_bgr, [person_class])
    return [{"box": item["box"], "confidence": item["confidence"]}
            for item in found if item["confidence"] >= min_confidence]
