"""
자동화 규칙 엔진 v1 (플랫폼 키트 코어, docs/부록F 7장)

반복적인 자동화(임계값·스케줄·비전 라벨)를 **코드 없이 데이터로** 처리합니다.
복잡한 게임·미션 로직은 여기서 다루지 않고 프론트엔드 시나리오가 담당합니다.

트리거 3종
  - sensor_threshold : {"slot_id","field","op",">=","value",28,"for_seconds":5}
  - vision_label     : {"label":"person" 또는 "labels":[...], "min_confidence":0.6, "count_at_least":1}
  - schedule         : {"at":"07:30"}  (PLATFORM_TIMEZONE 기준, 하루 한 번)

액션 2종
  - set_actuator : {"slot_id","state","value",("after_seconds":60)}
  - notify       : {"level":"info|warn|alert","message",("after_seconds":60)}

`after_seconds`가 타이머 역할을 합니다 — "미션 성공 후 60초 뒤 확인" 같은 순차 동작을
규칙만으로 표현할 수 있습니다.

임계값 규칙은 **상태가 바뀔 때만** 발동합니다(엣지 트리거). 센서가 1초마다 보고해도
같은 액션을 반복해서 쏟아내지 않습니다.
"""
import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.database import list_rules, touch_rule_fired
from services.device_control import set_actuator
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.rule_engine")

# 시간대 (알람 스케줄러와 같은 값을 쓰되, 키트 이름을 우선한다)
PLATFORM_TIMEZONE = os.getenv("PLATFORM_TIMEZONE") or os.getenv("ALARM_TIMEZONE", "Asia/Seoul")

_OPERATORS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

TRIGGER_TYPES = ("sensor_threshold", "vision_label", "schedule")
ACTION_TYPES = ("set_actuator", "notify")


def _tzinfo():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(PLATFORM_TIMEZONE)
    except Exception:
        return datetime.now().astimezone().tzinfo


def _local_now() -> datetime:
    return datetime.now(_tzinfo())


def validate_definition(definition: Dict[str, Any]) -> Optional[str]:
    """규칙 JSON을 검증합니다. 문제가 없으면 None, 있으면 사람이 읽을 오류 메시지."""
    if not isinstance(definition, dict):
        return "규칙 정의는 객체여야 합니다."

    when = definition.get("when")
    if not isinstance(when, dict):
        return "'when'(트리거)이 없습니다."
    trigger = when.get("type")
    if trigger not in TRIGGER_TYPES:
        return f"지원하지 않는 트리거입니다: {trigger} (가능: {', '.join(TRIGGER_TYPES)})"

    if trigger == "sensor_threshold":
        if not when.get("slot_id"):
            return "sensor_threshold에는 slot_id가 필요합니다."
        if when.get("op") not in _OPERATORS:
            return f"지원하지 않는 비교 연산자입니다: {when.get('op')}"
        if not isinstance(when.get("value"), (int, float)):
            return "sensor_threshold의 value는 숫자여야 합니다."
    elif trigger == "vision_label":
        if not (when.get("label") or when.get("labels")):
            return "vision_label에는 label 또는 labels가 필요합니다."
    elif trigger == "schedule":
        at = when.get("at")
        if not isinstance(at, str) or ":" not in at:
            return "schedule에는 'HH:MM' 형식의 at이 필요합니다."

    for key in ("then", "otherwise"):
        actions = definition.get(key, [])
        if not isinstance(actions, list):
            return f"'{key}'는 액션 목록이어야 합니다."
        for action in actions:
            if not isinstance(action, dict):
                return f"'{key}'의 액션은 객체여야 합니다."
            kind = action.get("action")
            if kind not in ACTION_TYPES:
                return f"지원하지 않는 액션입니다: {kind} (가능: {', '.join(ACTION_TYPES)})"
            if kind == "set_actuator" and not action.get("slot_id"):
                return "set_actuator에는 slot_id가 필요합니다."
    if not definition.get("then"):
        return "'then'에 실행할 액션이 하나 이상 필요합니다."
    return None


class RuleEngine:
    """규칙을 평가하고 액션을 실행합니다."""

    def __init__(self) -> None:
        self._last_branch: Dict[int, str] = {}     # 규칙별 마지막 분기 (엣지 트리거용)
        self._condition_since: Dict[int, float] = {}  # for_seconds 측정
        self._last_fired_at: Dict[int, float] = {}    # cooldown 측정
        self._schedule_done: Dict[int, str] = {}      # 규칙별 '오늘 발동했는지'
        self._timers: List[asyncio.Task] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 트리거 입구
    # ------------------------------------------------------------------

    async def on_sensor_value(
        self, slot_id: str, value: Any, numeric: Optional[float] = None
    ) -> None:
        """센서 보고가 들어올 때마다 호출됩니다."""
        rules = await asyncio.to_thread(list_rules, True)
        for rule in rules:
            definition = rule.get("definition") or {}
            when = definition.get("when") or {}
            if when.get("type") != "sensor_threshold" or when.get("slot_id") != slot_id:
                continue

            observed = self._extract_field(when.get("field", "value"), value, numeric)
            if observed is None:
                continue

            matched = self._compare(when, observed)
            await self._handle_branch(rule, definition, matched, when.get("for_seconds", 0),
                                      context={"slot_id": slot_id, "observed": observed})

    async def on_vision_event(
        self,
        label: Optional[str],
        detected: bool,
        confidence: Optional[float] = None,
        count: int = 0,
    ) -> None:
        """비전 이벤트가 들어올 때마다 호출됩니다."""
        if not label:
            return
        label = label.strip().lower()
        rules = await asyncio.to_thread(list_rules, True)
        for rule in rules:
            definition = rule.get("definition") or {}
            when = definition.get("when") or {}
            if when.get("type") != "vision_label":
                continue

            targets = when.get("labels") or [when.get("label")]
            targets = {str(t).strip().lower() for t in targets if t}
            if label not in targets:
                continue
            if not detected:
                continue
            if confidence is not None and confidence < float(when.get("min_confidence", 0.0)):
                continue
            if count and count < int(when.get("count_at_least", 1)):
                continue

            await self._fire(rule, definition, branch="then",
                             context={"label": label, "confidence": confidence})

    async def tick(self) -> None:
        """스케줄 트리거 점검 (백그라운드에서 주기적으로 호출)."""
        now = _local_now()
        today = now.strftime("%Y-%m-%d")
        rules = await asyncio.to_thread(list_rules, True)
        for rule in rules:
            definition = rule.get("definition") or {}
            when = definition.get("when") or {}
            if when.get("type") != "schedule":
                continue

            at = str(when.get("at", ""))
            parts = at.split(":")
            try:
                hour, minute = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                continue

            rule_id = int(rule["id"])
            if self._schedule_done.get(rule_id) == today:
                continue
            if now.hour == hour and now.minute == minute:
                self._schedule_done[rule_id] = today
                await self._fire(rule, definition, branch="then", context={"at": at})

    # ------------------------------------------------------------------
    # 판정 보조
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_field(field: str, value: Any, numeric: Optional[float]) -> Optional[Any]:
        if isinstance(value, dict) and field in value:
            return value[field]
        if field == "value":
            return numeric
        return None

    @staticmethod
    def _compare(when: Dict[str, Any], observed: Any) -> bool:
        op = _OPERATORS.get(when.get("op", ">"))
        target = when.get("value")
        try:
            return bool(op(float(observed), float(target)))
        except (TypeError, ValueError):
            return bool(op(observed, target)) if op else False

    async def _handle_branch(
        self,
        rule: Dict[str, Any],
        definition: Dict[str, Any],
        matched: bool,
        for_seconds: float,
        context: Dict[str, Any],
    ) -> None:
        """임계값 규칙: 조건 유지 시간과 엣지(분기 변화)를 판단해 발동합니다."""
        rule_id = int(rule["id"])
        now = time.monotonic()

        if matched and for_seconds:
            since = self._condition_since.get(rule_id)
            if since is None:
                self._condition_since[rule_id] = now
                return
            if now - since < float(for_seconds):
                return
        elif not matched:
            self._condition_since.pop(rule_id, None)

        branch = "then" if matched else "otherwise"
        if self._last_branch.get(rule_id) == branch:
            return  # 같은 상태가 계속될 때는 다시 실행하지 않는다 (엣지 트리거)
        if not definition.get(branch):
            self._last_branch[rule_id] = branch
            return

        self._last_branch[rule_id] = branch
        await self._fire(rule, definition, branch=branch, context=context)

    async def _fire(
        self,
        rule: Dict[str, Any],
        definition: Dict[str, Any],
        branch: str,
        context: Dict[str, Any],
    ) -> None:
        rule_id = int(rule["id"])
        cooldown = float(definition.get("cooldown_seconds", 0) or 0)
        now = time.monotonic()
        if cooldown and now - self._last_fired_at.get(rule_id, -1e9) < cooldown:
            return
        self._last_fired_at[rule_id] = now

        actions = definition.get(branch) or []
        logger.info(
            f"[규칙 발동] #{rule_id} '{rule.get('name')}' 분기={branch} "
            f"액션={len(actions)}개 근거={context}"
        )
        await asyncio.to_thread(touch_rule_fired, rule_id)
        await ws_manager.broadcast({
            "type": "rule_fired",
            "rule_id": rule_id,
            "name": rule.get("name"),
            "branch": branch,
            "context": context,
            "updated_at": datetime.now().astimezone().isoformat(),
        })
        await self._run_actions(rule, actions)

    async def _run_actions(self, rule: Dict[str, Any], actions: List[Dict[str, Any]]) -> None:
        for action in actions:
            delay = float(action.get("after_seconds", 0) or 0)
            if delay > 0:
                task = asyncio.create_task(self._delayed_action(rule, action, delay))
                self._timers.append(task)
                self._timers = [t for t in self._timers if not t.done()]
            else:
                await self._run_action(rule, action)

    async def _delayed_action(self, rule: Dict[str, Any], action: Dict[str, Any], delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await self._run_action(rule, action)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning(f"지연 액션 실행 실패: {exc}", exc_info=True)

    async def _run_action(self, rule: Dict[str, Any], action: Dict[str, Any]) -> None:
        kind = action.get("action")
        try:
            if kind == "set_actuator":
                await set_actuator(
                    action["slot_id"],
                    action.get("state", "on"),
                    value=action.get("value"),
                    operator=f"rule:{rule.get('id')}",
                )
            elif kind == "notify":
                await ws_manager.broadcast({
                    "type": "notify",
                    "level": action.get("level", "info"),
                    "message": action.get("message", ""),
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "updated_at": datetime.now().astimezone().isoformat(),
                })
        except ValueError as exc:
            # 비활성 슬롯이나 센서를 제어하려 한 경우 — 규칙만 건너뛰고 시스템은 계속 동작
            logger.warning(f"규칙 #{rule.get('id')} 액션을 건너뜁니다: {exc}")
        except Exception as exc:
            logger.warning(f"규칙 #{rule.get('id')} 액션 실행 실패: {exc}", exc_info=True)

    # ------------------------------------------------------------------
    # 백그라운드 스케줄 루프
    # ------------------------------------------------------------------

    async def run_scheduler(self, interval_seconds: float = 20.0) -> None:
        """스케줄 트리거를 주기적으로 점검합니다 (lifespan에서 태스크로 실행)."""
        logger.info(f"[규칙 엔진] 스케줄 점검 루프 시작 (주기 {interval_seconds}초, {PLATFORM_TIMEZONE})")
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[규칙 엔진] 스케줄 점검 중 오류: {exc}", exc_info=True)
            await asyncio.sleep(interval_seconds)

    def reset_state(self) -> None:
        """테스트·규칙 변경 후 내부 추적 상태를 초기화합니다."""
        self._last_branch.clear()
        self._condition_since.clear()
        self._last_fired_at.clear()
        self._schedule_done.clear()


rule_engine = RuleEngine()
