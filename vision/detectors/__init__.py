"""
검출기 로더 (vision/detectors/__init__.py) — 키트 제공, 수정하지 마세요.

`detectors/`에 파일을 넣으면 자동으로 인식됩니다. 여기에 등록할 필요가 없습니다.
pi의 `drivers/`와 같은 방식입니다.

규칙 두 가지만 지키면 됩니다.
  1) 파일 안에 `FrameDetector`를 상속한 `Detector` 클래스를 둡니다.
  2) 검출기가 아닌 보조 모듈(모델 로딩 코드 등)은 파일 이름을 `_`로 시작하세요
     (예: `_hands_rps_engine.py`). 그러면 로더가 건너뜁니다.
"""
import importlib
import logging
import pkgutil
from typing import Dict, List

from detectors.base import DetectionEvent, FrameDetector

logger = logging.getLogger("vision.detectors")

#: 검출기로 취급하지 않는 파일
_NOT_DETECTORS = {"base"}


def available_detectors() -> List[str]:
    """`detectors/` 폴더에서 쓸 수 있는 검출기 이름 목록."""
    names = []
    for module in pkgutil.iter_modules(__path__):
        if not module.name.startswith("_") and module.name not in _NOT_DETECTORS:
            names.append(module.name)
    return sorted(names)


def load_detectors() -> Dict[str, FrameDetector]:
    """
    폴더의 검출기를 모두 만들어 돌려줍니다.

    하나가 준비되지 않아도(라이브러리 없음 등) 나머지는 그대로 동작합니다 —
    MediaPipe가 없다고 사물 감지까지 멈추면 수업이 멈춥니다.
    """
    detectors: Dict[str, FrameDetector] = {}
    for name in available_detectors():
        try:
            module = importlib.import_module(f"detectors.{name}")
        except Exception as exc:
            logger.warning(f"검출기 '{name}'을(를) 불러오지 못했습니다: {exc}")
            continue

        detector_class = getattr(module, "Detector", None)
        if detector_class is None or not issubclass(detector_class, FrameDetector):
            logger.warning(f"detectors/{name}.py에 FrameDetector를 상속한 'Detector'가 없습니다.")
            continue

        try:
            detector = detector_class()
        except Exception as exc:
            logger.warning(f"검출기 '{name}'을(를) 만들지 못했습니다: {exc}")
            continue

        detectors[detector.name or name] = detector
    return detectors


__all__ = [
    "DetectionEvent",
    "FrameDetector",
    "available_detectors",
    "load_detectors",
]
