"""
비전 감지 설정 (services/vision_config.py) — 플랫폼 키트 코어, 부록F 10장.

`vision/main.py`가 **무엇을 감지할지 코드에 두지 않도록**, 감지 대상을 여기서 산출해 줍니다.
두 곳에서 모읍니다.

 1) 자동화 규칙의 `vision_label` 트리거 — 규칙에 쓰인 라벨은 당연히 감지해야 합니다.
 2) 대시보드 설정(`app_settings`의 `vision_config`) — 규칙 없이 감지만 하고 싶을 때,
    그리고 프론트엔드 시나리오가 쓰는 라벨(가위바위보 등)을 적어 두는 곳.

둘을 합치므로, 팀이 규칙을 만들면 vision이 자동으로 그 대상을 찾기 시작합니다.
"""
import logging
from typing import Any, Dict, List, Optional

from db.database import get_app_setting, list_rules, set_app_setting

logger = logging.getLogger("backend.services.vision_config")

SETTING_KEY = "vision_config"

#: 손동작 라벨은 사물 탐지(YOLO)가 아니라 MediaPipe가 판정하므로 대상 목록에서 제외합니다.
GESTURE_LABELS = ("rock", "paper", "scissors")

#: 팀이 아무 설정도 하지 않았을 때 — 1차 완성본에서 쓰던 기본 대상
DEFAULT_OBJECT_LABELS = ["person", "bottle", "cup", "book", "cell phone"]

DEFAULTS: Dict[str, Any] = {
    "object_labels": DEFAULT_OBJECT_LABELS,
    "gesture_enabled": True,
    "min_confidence": 0.6,
    "cooldown_seconds": 2.5,
}


def _clean_labels(values: Any) -> List[str]:
    """라벨 목록을 다듬습니다 (소문자·중복 제거·손동작 제외)."""
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, (list, tuple, set)):
        return []

    cleaned: List[str] = []
    for value in values:
        label = str(value or "").strip().lower()
        if not label or label in GESTURE_LABELS or label in cleaned:
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
) -> Dict[str, Any]:
    """
    저장된 설정과 규칙을 합쳐 최종 설정을 만듭니다.

    DB가 꺼져 있으면 stored=None, rules=[]로 들어와 기본값이 나옵니다 —
    설정을 못 읽었다고 vision이 아무것도 감지하지 않으면 수업이 멈춥니다.
    """
    stored = stored if isinstance(stored, dict) else {}
    config = dict(DEFAULTS)

    chosen = _clean_labels(stored.get("object_labels"))
    from_rules = labels_from_rules(rules or [])

    if chosen or from_rules:
        # 규칙에 쓰인 라벨은 반드시 포함합니다 (규칙을 만들었는데 감지가 안 되면 원인을 찾기 어렵습니다)
        merged = list(chosen)
        merged.extend(label for label in from_rules if label not in merged)
        config["object_labels"] = merged

    if isinstance(stored.get("gesture_enabled"), bool):
        config["gesture_enabled"] = stored["gesture_enabled"]

    for key in ("min_confidence", "cooldown_seconds"):
        raw = stored.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
            config[key] = float(raw)

    config["min_confidence"] = max(0.0, min(1.0, float(config["min_confidence"])))
    config["cooldown_seconds"] = max(0.0, min(60.0, float(config["cooldown_seconds"])))
    return config


def get_vision_config() -> Dict[str, Any]:
    """현재 감지 설정을 돌려줍니다 (DB 장애 시 기본값)."""
    stored = get_app_setting(SETTING_KEY)
    rules = list_rules(True)
    config = build_config(stored if isinstance(stored, dict) else None, rules)
    config["source"] = "saved" if stored else "default"
    return config


def save_vision_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """대시보드에서 바꾼 감지 설정을 저장합니다."""
    stored = get_app_setting(SETTING_KEY)
    stored = dict(stored) if isinstance(stored, dict) else {}

    if "object_labels" in payload:
        stored["object_labels"] = _clean_labels(payload.get("object_labels"))
    if isinstance(payload.get("gesture_enabled"), bool):
        stored["gesture_enabled"] = payload["gesture_enabled"]
    for key in ("min_confidence", "cooldown_seconds"):
        raw = payload.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            stored[key] = float(raw)

    set_app_setting(SETTING_KEY, stored)
    logger.info(f"[비전 설정] 감지 대상 {stored.get('object_labels')}")
    return get_vision_config()
