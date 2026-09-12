"""
비전 감지 설정 (services/vision_config.py) — 플랫폼 키트 코어, 부록F 10장.

`vision/main.py`가 **무엇을 감지할지 코드에 두지 않도록**, 감지 대상을 여기서 산출해 줍니다.
두 곳에서 모읍니다.

 1) 자동화 규칙의 `vision_label` 트리거 — 규칙에 쓰인 라벨은 당연히 감지해야 합니다.
 2) 대시보드 설정(`app_settings`의 `vision_config`) — 규칙 없이 감지만 하고 싶을 때,
    그리고 프론트엔드 시나리오가 쓰는 라벨을 적어 두는 곳.

둘을 합치므로, 팀이 규칙을 만들면 vision이 자동으로 그 대상을 찾기 시작합니다.
"""
import logging
from typing import Any, Dict, List, Optional

from db.database import get_app_setting, list_rules, set_app_setting

logger = logging.getLogger("backend.services.vision_config")

SETTING_KEY = "vision_config"
#: 비전 클라이언트가 신고한 검출기 목록 (이름·내보내는 라벨·사용 가능 여부)
DETECTORS_KEY = "vision_detectors"

#: 사물 탐지(YOLO) 검출기의 이름. 이것만은 키트가 알고 있어야 합니다 —
#: `object_labels` 설정이 이 검출기에 주는 값이기 때문입니다.
OBJECT_DETECTOR = "objects"

#: 팀이 아무 설정도 하지 않았을 때 — 1차 완성본에서 쓰던 기본 대상
DEFAULT_OBJECT_LABELS = ["person", "bottle", "cup", "book", "cell phone"]

DEFAULTS: Dict[str, Any] = {
    "object_labels": DEFAULT_OBJECT_LABELS,
    "detectors": [],          # 비우면 비전 클라이언트가 가진 것을 모두 씁니다
    "min_confidence": 0.6,
    "cooldown_seconds": 2.5,
}


def gesture_labels(detectors: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """
    사물 탐지가 아닌 검출기들이 내보내는 라벨 목록.

    **이 목록을 코드에 두지 않습니다.** 비전 클라이언트가 부팅할 때 신고한 것을 씁니다
    (`POST /api/v1/vision/detectors`). 그래서 팀이 새 손동작·자세 감지를 추가해도
    백엔드는 고치지 않습니다 — 어떤 팀의 라벨 이름도 이 파일에 없습니다.
    """
    if detectors is None:
        detectors = get_detectors()
    labels: List[str] = []
    for detector in detectors or []:
        if not isinstance(detector, dict) or detector.get("name") == OBJECT_DETECTOR:
            continue
        for label in detector.get("labels") or []:
            text = str(label or "").strip().lower()
            if text and text not in labels:
                labels.append(text)
    return labels


def _clean_labels(values: Any, exclude: Optional[List[str]] = None) -> List[str]:
    """
    라벨 목록을 다듬습니다 (소문자·중복 제거).

    exclude에는 사물 탐지가 아닌 검출기의 라벨을 넘깁니다. 손동작 같은 것은
    YOLO가 찾는 대상이 아니므로 사물 목록에 들어가면 안 됩니다.
    """
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, (list, tuple, set)):
        return []

    blocked = set(exclude or [])
    cleaned: List[str] = []
    for value in values:
        label = str(value or "").strip().lower()
        if not label or label in blocked or label in cleaned:
            continue
        cleaned.append(label)
    return cleaned


def labels_from_rules(rules: List[Dict[str, Any]]) -> List[str]:
    """활성 규칙의 vision_label 트리거에서 감지 대상을 모읍니다."""
    labels: List[str] = []
    for rule in rules:
        definition = rule.get("definition") or {}
        if not isinstance(definition, dict):
            continue
        when = definition.get("when") or {}
        if not isinstance(when, dict) or when.get("type") != "vision_label":
            continue
        labels.extend(_clean_labels(when.get("labels") or [when.get("label")]))
    return labels


def build_config(
    stored: Optional[Dict[str, Any]],
    rules: Optional[List[Dict[str, Any]]] = None,
    detectors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    저장된 설정과 규칙을 합쳐 최종 설정을 만듭니다.

    DB가 꺼져 있으면 stored=None, rules=[]로 들어와 기본값이 나옵니다 —
    설정을 못 읽었다고 vision이 아무것도 감지하지 않으면 수업이 멈춥니다.
    """
    stored = stored if isinstance(stored, dict) else {}
    config = dict(DEFAULTS)
    non_object = gesture_labels(detectors or [])

    chosen = _clean_labels(stored.get("object_labels"), exclude=non_object)
    from_rules = [label for label in labels_from_rules(rules or [])
                  if label not in non_object]

    if chosen or from_rules:
        # 규칙에 쓰인 라벨은 반드시 포함합니다 (규칙을 만들었는데 감지가 안 되면 원인을 찾기 어렵습니다)
        merged = list(chosen)
        merged.extend(label for label in from_rules if label not in merged)
        config["object_labels"] = merged

    # 어떤 검출기를 돌릴지. 비워 두면 비전 클라이언트가 가진 것을 모두 씁니다.
    known = [d.get("name") for d in (detectors or []) if isinstance(d, dict) and d.get("name")]
    enabled = [str(name).strip() for name in (stored.get("detectors") or []) if name]
    if enabled and known:
        enabled = [name for name in enabled if name in known]
    config["detectors"] = enabled

    # 구버전 화면·클라이언트 호환: 사물 탐지가 아닌 검출기가 켜져 있는지를 불린으로도 알려 줍니다
    others = [name for name in (known or []) if name != OBJECT_DETECTOR]
    config["gesture_enabled"] = (
        any(name in enabled for name in others) if enabled and others
        else bool(stored.get("gesture_enabled", True))
    )

    for key in ("min_confidence", "cooldown_seconds"):
        raw = stored.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
            config[key] = float(raw)

    config["min_confidence"] = max(0.0, min(1.0, float(config["min_confidence"])))
    config["cooldown_seconds"] = max(0.0, min(60.0, float(config["cooldown_seconds"])))
    return config


def get_detectors() -> List[Dict[str, Any]]:
    """비전 클라이언트가 신고한 검출기 목록 (없으면 빈 목록)."""
    stored = get_app_setting(DETECTORS_KEY)
    return stored if isinstance(stored, list) else []


def save_detectors(detectors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    비전 클라이언트가 부팅할 때 자기 검출기를 신고합니다.

    백엔드는 이 신고를 보고 '사물이 아닌 라벨'이 무엇인지 알게 됩니다.
    그래서 팀이 새 감지를 추가해도 백엔드 코드에 라벨 이름을 적을 필요가 없습니다.

    DB가 꺼져 있으면 persisted=False로 알려 줍니다 — 저장된 척하면
    "설정은 바꿨는데 왜 안 먹지?"로 학생이 한참 헤매게 됩니다.
    """
    cleaned: List[Dict[str, Any]] = []
    for detector in detectors or []:
        if not isinstance(detector, dict) or not detector.get("name"):
            continue
        cleaned.append({
            "name": str(detector["name"]).strip(),
            "labels": [str(x).strip().lower() for x in (detector.get("labels") or []) if x],
            "description": str(detector.get("description") or "")[:200],
            "available": bool(detector.get("available", True)),
            "reason": str(detector.get("reason") or "")[:200],
        })
    persisted = bool(set_app_setting(DETECTORS_KEY, cleaned))
    logger.info(f"[비전 검출기 신고] {[d['name'] for d in cleaned]}"
                f"{'' if persisted else ' (DB 미연결 — 저장되지 않음)'}")
    return {"detectors": cleaned, "persisted": persisted}


def get_vision_config() -> Dict[str, Any]:
    """현재 감지 설정을 돌려줍니다 (DB 장애 시 기본값)."""
    stored = get_app_setting(SETTING_KEY)
    rules = list_rules(True)
    detectors = get_detectors()
    config = build_config(stored if isinstance(stored, dict) else None, rules, detectors)
    config["source"] = "saved" if stored else "default"
    config["known_detectors"] = detectors
    return config


def save_vision_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """대시보드에서 바꾼 감지 설정을 저장합니다."""
    stored = get_app_setting(SETTING_KEY)
    stored = dict(stored) if isinstance(stored, dict) else {}
    non_object = gesture_labels()

    if "object_labels" in payload:
        stored["object_labels"] = _clean_labels(payload.get("object_labels"), exclude=non_object)
    if "detectors" in payload:
        stored["detectors"] = [str(x).strip() for x in (payload.get("detectors") or []) if x]
    if isinstance(payload.get("gesture_enabled"), bool):
        stored["gesture_enabled"] = payload["gesture_enabled"]
        # 불린만 온 구버전 화면도 검출기 목록으로 옮겨 준다
        known = [d.get("name") for d in get_detectors()]
        others = [name for name in known if name and name != OBJECT_DETECTOR]
        if known:
            stored["detectors"] = ([OBJECT_DETECTOR] + others) if payload["gesture_enabled"] \
                else [OBJECT_DETECTOR]
    for key in ("min_confidence", "cooldown_seconds"):
        raw = payload.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            stored[key] = float(raw)

    persisted = bool(set_app_setting(SETTING_KEY, stored))
    logger.info(f"[비전 설정] 감지 대상 {stored.get('object_labels')}"
                f"{'' if persisted else ' (DB 미연결 — 저장되지 않음)'}")
    config = get_vision_config()
    config["persisted"] = persisted
    return config
