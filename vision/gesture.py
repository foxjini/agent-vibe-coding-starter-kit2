"""
가위바위보 손동작 인식 모듈 (MediaPipe Hands)
=============================================================================
웹캠 프레임에서 손을 찾아 '가위/바위/보' 중 무엇인지 판별합니다.

MediaPipe는 버전에 따라 API가 두 가지입니다. 이 모듈은 둘 다 지원합니다.
  1) Tasks API (mediapipe 0.10.20 이후 / 1.x) — `hand_landmarker.task` 모델 파일 필요
  2) 레거시 solutions API (mediapipe 0.10 초기 버전) — 모델 내장

모델 파일(`vision/hand_landmarker.task`)이 저장소에 함께 들어 있습니다.
혹시 없다면 아래 주소에서 받아 vision 폴더에 두면 됩니다:
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

MediaPipe가 아예 없거나 초기화에 실패하면 `available`이 False가 되고,
비전 클라이언트는 자동으로 사물 감지 미션으로만 동작합니다 (프로그램이 죽지 않습니다).

판별 방법(아주 단순한 규칙): 펴진 손가락 개수를 세어서
  0개 -> 주먹(rock) / 2개(검지+중지) -> 가위(scissors) / 4개 이상 -> 보(paper)
  그 외(손가락 하나만 편 경우 등)는 판정을 보류합니다.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("vision.gesture")

# MediaPipe 손 랜드마크 번호 (두 API 공통)
_FINGER_TIPS = [8, 12, 16, 20]      # 검지, 중지, 약지, 새끼 끝
_FINGER_PIPS = [6, 10, 14, 18]      # 각 손가락의 중간 관절
_THUMB_TIP = 4
_THUMB_IP = 3

MODEL_FILENAME = "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# 손끝을 잇는 연결선 (화면에 뼈대를 그릴 때 사용)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def classify_hand(landmarks: List[Any], handedness_label: str = "Right") -> Optional[str]:
    """
    손 랜드마크 21개로부터 가위/바위/보를 판별합니다.
    landmarks의 각 원소는 .x, .y 속성을 가지면 됩니다 (두 API 모두 동일).
    판별이 애매하면 None을 돌려줍니다.
    """
    if not landmarks or len(landmarks) < 21:
        return None

    # 손끝이 중간 관절보다 위(y가 작다)에 있으면 펴진 것으로 본다
    extended = sum(
        1 for tip, pip in zip(_FINGER_TIPS, _FINGER_PIPS)
        if landmarks[tip].y < landmarks[pip].y
    )

    index_up = landmarks[8].y < landmarks[6].y
    middle_up = landmarks[12].y < landmarks[10].y

    # 네 손가락이 모두 접혀 있어야 주먹으로 본다.
    # (손가락 하나만 편 '가리키기'를 주먹으로 오인하면 미션이 엉뚱하게 통과된다)
    if extended == 0:
        return "rock"
    if extended == 2 and index_up and middle_up:
        return "scissors"
    if extended >= 4:
        return "paper"
    return None  # 애매한 손 모양은 판정하지 않는다


class RockPaperScissorsDetector:
    """MediaPipe 기반 가위바위보 손동작 검출기 (Tasks API / 레거시 API 모두 지원)."""

    def __init__(self, min_detection_confidence: float = 0.5, model_path: Optional[str] = None):
        self.available = False
        self.api = None            # "tasks" | "solutions"
        self._landmarker = None    # Tasks API
        self._hands = None         # 레거시 API
        self._mp = None

        model_path = model_path or os.path.join(os.path.dirname(__file__), MODEL_FILENAME)

        try:
            import mediapipe as mp
            self._mp = mp
        except Exception as exc:
            logger.warning(
                f"MediaPipe를 불러올 수 없어 가위바위보 미션이 꺼집니다 ({exc}). "
                "사물 감지 미션으로만 동작합니다."
            )
            return

        # 1) 최신 Tasks API 시도
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"손 인식 모델 파일이 없습니다: {model_path}\n"
                    f"   아래 주소에서 받아 vision 폴더에 두세요:\n   {MODEL_URL}"
                )

            options = mp_vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=model_path),
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=min_detection_confidence,
                min_tracking_confidence=0.5,
            )
            self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
            self.api = "tasks"
            self.available = True
            self._timestamp_ms = 0
            logger.info("MediaPipe Tasks API 로드 완료 — 가위바위보 미션을 사용할 수 있습니다.")
            return
        except Exception as exc:
            logger.info(f"MediaPipe Tasks API 사용 불가 ({exc}) — 레거시 API를 시도합니다.")

        # 2) 레거시 solutions API 시도 (구버전 mediapipe)
        try:
            self._hands = self._mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=0.5,
            )
            self.api = "solutions"
            self.available = True
            logger.info("MediaPipe 레거시 API 로드 완료 — 가위바위보 미션을 사용할 수 있습니다.")
        except Exception as exc:
            logger.warning(
                f"MediaPipe 손 인식을 초기화하지 못해 가위바위보 미션이 꺼집니다 ({exc}). "
                "사물 감지 미션으로만 동작합니다."
            )

    def close(self) -> None:
        for obj in (self._landmarker, self._hands):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass

    def detect(self, frame_rgb) -> Optional[Dict[str, Any]]:
        """
        RGB 프레임(numpy 배열)에서 손동작을 판별합니다.
        반환: {"hand": "rock"|"paper"|"scissors", "confidence": float, "points": [(x, y), ...]} 또는 None
        """
        if not self.available:
            return None

        try:
            if self.api == "tasks":
                return self._detect_tasks(frame_rgb)
            return self._detect_solutions(frame_rgb)
        except Exception as exc:
            logger.debug(f"MediaPipe 처리 실패: {exc}")
            return None

    def _detect_tasks(self, frame_rgb) -> Optional[Dict[str, Any]]:
        mp = self._mp
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self._timestamp_ms += 33  # 약 30fps 가정 (VIDEO 모드는 시간이 증가해야 한다)
        result = self._landmarker.detect_for_video(image, self._timestamp_ms)

        if not result.hand_landmarks:
            return None

        landmarks = result.hand_landmarks[0]
        label = "Right"
        score = 0.8
        if result.handedness:
            category = result.handedness[0][0]
            label = category.category_name or "Right"
            score = float(category.score)

        hand = classify_hand(landmarks, label)
        if hand is None:
            return None
        return {
            "hand": hand,
            "confidence": round(score, 2),
            "points": [(lm.x, lm.y) for lm in landmarks],
        }

    def _detect_solutions(self, frame_rgb) -> Optional[Dict[str, Any]]:
        results = self._hands.process(frame_rgb)
        if not results.multi_hand_landmarks:
            return None

        landmarks = results.multi_hand_landmarks[0].landmark
        label = "Right"
        score = 0.8
        if results.multi_handedness:
            classification = results.multi_handedness[0].classification[0]
            label = classification.label
            score = float(classification.score)

        hand = classify_hand(landmarks, label)
        if hand is None:
            return None
        return {
            "hand": hand,
            "confidence": round(score, 2),
            "points": [(lm.x, lm.y) for lm in landmarks],
        }

    @staticmethod
    def draw(frame_bgr, points: Optional[List[Tuple[float, float]]]) -> None:
        """감지된 손의 뼈대를 화면에 그립니다 (좌표는 0~1 비율)."""
        if not points:
            return
        try:
            import cv2

            h, w = frame_bgr.shape[:2]
            pixels = [(int(x * w), int(y * h)) for x, y in points]
            for a, b in _HAND_CONNECTIONS:
                if a < len(pixels) and b < len(pixels):
                    cv2.line(frame_bgr, pixels[a], pixels[b], (120, 220, 255), 2)
            for px in pixels:
                cv2.circle(frame_bgr, px, 3, (255, 255, 255), -1)
        except Exception:
            pass
