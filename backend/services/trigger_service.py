"""
기상 미션 트리거 서비스.

AGENTS.md 팀 정보의 트리거 규칙을 그대로 구현합니다:
- 설정한 알람 시간이 되면 알람을 동작시키고 기상 미션을 시작한다.
- 미션 성공 시 알람(buzzer_1)을 종료하고, 약 1~2분 후 기상 확인 팝업을 표시한다.
- 팝업을 확인하지 않으면 알람을 다시 울린다.
- 미션 오답 또는 시간 초과 시 미션을 재시도한다.

미션 방식은 MISSION_MODE 환경변수로 고릅니다.
- rps    : 가위바위보 배틀만 인정 (MediaPipe 손동작)
- object : 지정 사물/사람 감지만 인정 (YOLO)
- auto   : 가위바위보 라운드를 제시하되, 사물 미션 성공으로도 라운드를 통과 (기본값)
           → 비전 PC에 MediaPipe가 없어도 시연이 막히지 않습니다.
"""
import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.device_control import BUZZER_ID, is_buzzer_ringing, set_actuator
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.trigger_service")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# 가위바위보 규칙 (key가 value를 이긴다)
RPS_HANDS = ("rock", "paper", "scissors")
_BEATS: Dict[str, str] = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
# AI가 낸 손을 이기려면 사용자가 내야 하는 손
_WINNING_HAND: Dict[str, str] = {ai: user for user, ai in _BEATS.items()}
_HAND_KO: Dict[str, str] = {"rock": "주먹(바위)", "paper": "보", "scissors": "가위"}

RINGING_STATES = ("ringing", "on")


@dataclass
class MissionSession:
    """진행 중인 기상 미션 한 판의 상태."""
    mode: str
    required_wins: int
    reason: str
    grace_seconds: float = 2.0
    wins: int = 0
    round_index: int = 0
    ai_hand: Optional[str] = None
    expected_hand: Optional[str] = None
    round_deadline: float = 0.0
    round_started_at: float = 0.0
    object_hits: int = 0
    started_at: float = field(default_factory=time.monotonic)
    last_event_key: Optional[str] = None
    last_event_at: float = 0.0

    def snapshot(self) -> Dict[str, Any]:
        remaining = max(0, int(round(self.round_deadline - time.monotonic())))
        return {
            "active": True,
            "mode": self.mode,
            "round": self.round_index,
            "wins": self.wins,
            "required_wins": self.required_wins,
            "ai_hand": self.ai_hand,
            "expected_hand": self.expected_hand,
            "remaining_seconds": remaining,
            "grace_until": max(0.0, self.round_started_at + self.grace_seconds - time.monotonic()),
            "reason": self.reason,
        }


class TriggerService:
    """기상 미션 진행과 2차 수면 방지 루틴을 담당하는 서비스."""

    def __init__(self) -> None:
        # 설정 (.env로 조절 가능 — 시연 환경에 맞춰 짧게 잡아 두었습니다)
        self.mode: str = os.getenv("MISSION_MODE", "auto").strip().lower()
        self.required_wins: int = max(1, _env_int("MISSION_REQUIRED_WINS", 2))
        self.round_timeout_seconds: int = max(3, _env_int("MISSION_ROUND_TIMEOUT_SECONDS", 15))
        self.min_confidence: float = _env_float("MISSION_MIN_CONFIDENCE", 0.6)
        self.object_required_hits: int = max(1, _env_int("MISSION_OBJECT_REQUIRED_HITS", 2))
        self.object_targets = {
            t.strip().lower()
            for t in os.getenv(
                "MISSION_OBJECT_TARGETS", "person,bottle,cup,book,cell phone"
            ).split(",")
            if t.strip()
        }
        self.popup_delay_seconds: int = _env_int("WAKEUP_POPUP_DELAY_SECONDS", 25)
        self.confirm_timeout_seconds: int = _env_int("WAKEUP_CONFIRM_TIMEOUT_SECONDS", 15)
        self.event_debounce_seconds: float = _env_float("MISSION_EVENT_DEBOUNCE_SECONDS", 1.2)
        # 라운드가 바뀐 직후에는 직전 손동작이 재전송돼 억울하게 오답 처리되는 것을 막는다
        self.round_grace_seconds: float = _env_float("MISSION_ROUND_GRACE_SECONDS", 2.0)

        if self.mode not in ("auto", "rps", "object"):
            logger.warning(f"알 수 없는 MISSION_MODE '{self.mode}' — 'auto'로 대체합니다.")
            self.mode = "auto"

        self._session: Optional[MissionSession] = None
        self._round_watcher: Optional[asyncio.Task] = None
        self._second_sleep_task: Optional[asyncio.Task] = None
        self._wakeup_confirmed: bool = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------

    def get_mission_status(self) -> Dict[str, Any]:
        if self._session:
            return self._session.snapshot()
        return {
            "active": False,
            "mode": self.mode,
            "required_wins": self.required_wins,
        }

    def is_second_sleep_guard_active(self) -> bool:
        return bool(self._second_sleep_task and not self._second_sleep_task.done())

    # ------------------------------------------------------------------
    # 미션 수명 주기
    # ------------------------------------------------------------------

    async def start_mission(self, reason: str = "alarm") -> Dict[str, Any]:
        """알람이 울리기 시작할 때 호출 — 기상 미션을 개시합니다."""
        async with self._lock:
            await self._cancel_round_watcher()
            self._session = MissionSession(
                mode=self.mode,
                required_wins=self.required_wins,
                reason=reason,
                grace_seconds=self.round_grace_seconds,
            )
            logger.info(
                f"[미션 시작] mode={self.mode}, 필요 승수={self.required_wins}, 사유={reason}"
            )
            await ws_manager.broadcast({
                "type": "mission_started",
                "mode": self.mode,
                "required_wins": self.required_wins,
                "reason": reason,
                "message": "기상 미션을 시작합니다! 카메라 앞에 서세요.",
                "updated_at": _now_iso(),
            })
            await self._begin_round()
            return self._session.snapshot()

    async def cancel_mission(self, reason: str = "manual_stop") -> None:
        """알람이 수동으로 꺼졌을 때 등, 진행 중인 미션을 중단합니다."""
        async with self._lock:
            if not self._session:
                return
            logger.info(f"[미션 취소] 사유={reason}")
            self._session = None
            await self._cancel_round_watcher()
            await ws_manager.broadcast({
                "type": "mission_cancelled",
                "reason": reason,
                "message": "기상 미션이 중단되었습니다.",
                "updated_at": _now_iso(),
            })

    async def _begin_round(self, retry_reason: Optional[str] = None) -> None:
        """새 라운드를 시작하고 대시보드에 문제(AI 손패)를 제시합니다. (_lock 안에서 호출)"""
        session = self._session
        if not session:
            return

        previous = session.ai_hand
        choices = [h for h in RPS_HANDS if h != previous] or list(RPS_HANDS)
        session.ai_hand = random.choice(choices)
        session.expected_hand = _WINNING_HAND[session.ai_hand]
        session.round_index += 1
        session.object_hits = 0
        session.round_started_at = time.monotonic()
        session.round_deadline = session.round_started_at + self.round_timeout_seconds

        await ws_manager.broadcast({
            "type": "mission_round",
            "round": session.round_index,
            "mode": session.mode,
            "ai_hand": session.ai_hand,
            "expected_hand": session.expected_hand,
            "wins": session.wins,
            "required_wins": session.required_wins,
            "timeout": self.round_timeout_seconds,
            "retry_reason": retry_reason,
            "message": (
                f"AI가 '{_HAND_KO[session.ai_hand]}'을(를) 냈습니다! "
                f"'{_HAND_KO[session.expected_hand]}'을(를) 내서 이기세요."
            ),
            "updated_at": _now_iso(),
        })

        await self._cancel_round_watcher()
        self._round_watcher = asyncio.create_task(
            self._watch_round_timeout(session.round_index)
        )

    async def _watch_round_timeout(self, round_index: int) -> None:
        """제한 시간 안에 성공하지 못하면 재시도 라운드를 엽니다."""
        try:
            await asyncio.sleep(self.round_timeout_seconds)
            async with self._lock:
                session = self._session
                if not session or session.round_index != round_index:
                    return  # 이미 다음 라운드로 넘어갔다
                logger.info(f"[미션 시간초과] round={round_index} — 재시도합니다.")
                await self._broadcast_round_result("timeout", user_hand=None)
                await self._begin_round(retry_reason="timeout")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"[미션] 라운드 타이머 오류: {exc}", exc_info=True)

    async def _cancel_round_watcher(self) -> None:
        task = self._round_watcher
        self._round_watcher = None
        if task and not task.done():
            task.cancel()

    async def _broadcast_round_result(self, result: str, user_hand: Optional[str]) -> None:
        session = self._session
        messages = {
            "win": "좋아요! 한 판 이겼습니다.",
            "lose": "아쉽네요, AI가 이겼습니다. 다시 도전!",
            "draw": "비겼습니다. 한 번 더!",
            "timeout": "시간이 초과되었습니다. 다시 도전!",
            "object": "미션 대상을 확인했습니다!",
        }
        await ws_manager.broadcast({
            "type": "mission_result",
            "result": result,
            "user_hand": user_hand,
            "wins": session.wins if session else 0,
            "required_wins": session.required_wins if session else self.required_wins,
            "message": messages.get(result, ""),
            "updated_at": _now_iso(),
        })

    # ------------------------------------------------------------------
    # 비전 이벤트 처리
    # ------------------------------------------------------------------

    async def handle_vision_event(
        self,
        event_type: str,
        detected: bool,
        count: int,
        confidence: Optional[float],
        label: Optional[str] = None,
    ) -> None:
        """
        비전 이벤트를 미션 판정에 반영합니다.
        미션이 없는데 부저가 울리고 있으면(예: 대시보드에서 부저를 직접 켠 경우) 미션을 자동 개시합니다.
        """
        resolved_label = (label or _label_from_event_type(event_type) or "").strip().lower()

        if self._session is None:
            if detected and await is_buzzer_ringing():
                await self.start_mission(reason="buzzer_ringing")
            else:
                return

        async with self._lock:
            session = self._session
            if not session:
                return

            if not detected or not resolved_label:
                if resolved_label and resolved_label not in RPS_HANDS:
                    session.object_hits = 0  # 사물이 사라지면 연속 감지 초기화
                return

            now = time.monotonic()
            # 새 라운드 직후 유예 시간: 손을 바꿀 시간을 준다
            if now - session.round_started_at < session.grace_seconds:
                return

            # 같은 감지가 연속으로 밀려 들어오는 경우 중복 판정 방지
            event_key = f"{resolved_label}:{session.round_index}"
            if (
                session.last_event_key == event_key
                and now - session.last_event_at < self.event_debounce_seconds
            ):
                return
            session.last_event_key = event_key
            session.last_event_at = now

            if resolved_label in RPS_HANDS:
                if session.mode == "object":
                    return
                await self._handle_gesture(resolved_label, confidence)
            else:
                if session.mode == "rps":
                    return
                await self._handle_object(resolved_label, confidence)

    async def _handle_gesture(self, user_hand: str, confidence: Optional[float]) -> None:
        """가위바위보 손동작 판정. (_lock 안에서 호출)"""
        session = self._session
        if not session or not session.ai_hand:
            return

        if confidence is not None and confidence < self.min_confidence:
            logger.debug(f"[미션] 신뢰도 부족으로 무시: {user_hand} ({confidence})")
            return

        if user_hand == session.ai_hand:
            result = "draw"
        elif _BEATS[user_hand] == session.ai_hand:
            result = "win"
        else:
            result = "lose"

        logger.info(
            f"[미션 판정] AI={session.ai_hand} vs 사용자={user_hand} -> {result} "
            f"(conf={confidence})"
        )

        if result == "win":
            session.wins += 1
            await self._broadcast_round_result("win", user_hand)
            if session.wins >= session.required_wins:
                await self._complete_mission(evidence=f"rps:{user_hand}")
            else:
                await self._begin_round(retry_reason=None)
        else:
            await self._broadcast_round_result(result, user_hand)
            await self._begin_round(retry_reason=result)

    async def _handle_object(self, label: str, confidence: Optional[float]) -> None:
        """지정 사물/사람 감지 미션 판정. (_lock 안에서 호출)"""
        session = self._session
        if not session:
            return

        if label not in self.object_targets:
            return
        if confidence is not None and confidence < self.min_confidence:
            return

        session.object_hits += 1
        logger.info(
            f"[미션 사물감지] {label} {session.object_hits}/{self.object_required_hits} "
            f"(conf={confidence})"
        )
        if session.object_hits < self.object_required_hits:
            return

        session.wins += 1
        session.object_hits = 0
        await self._broadcast_round_result("object", user_hand=None)
        if session.wins >= session.required_wins:
            await self._complete_mission(evidence=f"object:{label}")
        else:
            await self._begin_round(retry_reason=None)

    async def _complete_mission(self, evidence: str) -> None:
        """미션 성공 — 알람을 끄고 2차 수면 방지 루틴을 시작합니다. (_lock 안에서 호출)"""
        session = self._session
        wins = session.wins if session else self.required_wins
        self._session = None
        await self._cancel_round_watcher()

        logger.info(f"[미션 성공] 근거={evidence}, 승수={wins} -> 알람 종료")

        await set_actuator(
            BUZZER_ID,
            "off",
            value=None,
            operator="trigger",
        )

        await ws_manager.broadcast({
            "type": "mission_success",
            "evidence": evidence,
            "wins": wins,
            "countdown": self.popup_delay_seconds,
            "message": "기상 미션을 완수했습니다! 알람이 해제되었습니다.",
            "updated_at": _now_iso(),
        })

        # 2차 수면 방지 감시 루틴 시작
        if self._second_sleep_task and not self._second_sleep_task.done():
            self._second_sleep_task.cancel()
        self._second_sleep_task = asyncio.create_task(self._run_second_sleep_guard())

    # ------------------------------------------------------------------
    # 2차 수면 방지
    # ------------------------------------------------------------------

    async def _run_second_sleep_guard(self) -> None:
        """
        미션 성공 후 2차 수면 방지 감시 루틴.
        일정 시간 후 기상 확인 팝업을 표시하고, 미응답 시 알람을 다시 울립니다.
        """
        self._wakeup_confirmed = False
        logger.info(
            f"[2차 수면 방지] {self.popup_delay_seconds}초 후 기상 확인 팝업을 표시합니다."
        )

        try:
            # 1단계: 팝업 표시 전 대기
            await asyncio.sleep(self.popup_delay_seconds)

            # 2단계: 대시보드에 기상 확인 팝업 브로드캐스트
            logger.info("[2차 수면 방지] 기상 확인 팝업 브로드캐스트 전송")
            await ws_manager.broadcast({
                "type": "wakeup_check_popup",
                "timeout": self.confirm_timeout_seconds,
                "message": "기상 확인: 2차 수면 방지를 위해 화면을 터치하거나 확인 버튼을 누르세요!",
                "created_at": _now_iso(),
            })

            # 3단계: 확인 응답 대기 (제한시간)
            await asyncio.sleep(self.confirm_timeout_seconds)

            # 4단계: 응답 확인 여부 검사
            if self._wakeup_confirmed:
                logger.info("[2차 수면 방지] 사용자가 기상을 확인하여 루틴이 안전하게 종료되었습니다.")
                return

            logger.warning(
                "[2차 수면 방지 경보] 기상 확인 미응답! 2차 수면 방지 재알람을 울립니다."
            )
            await set_actuator(
                BUZZER_ID,
                "ringing",
                value={"volume": 90, "frequency": 1200},
                operator="trigger",
            )
            await ws_manager.broadcast({
                "type": "re_alarm",
                "message": "기상 확인 시간 초과로 알람이 다시 동작합니다!",
                "updated_at": _now_iso(),
            })
            # 재알람에도 동일한 기상 미션을 다시 요구한다
            await self.start_mission(reason="second_sleep_detected")

        except asyncio.CancelledError:
            logger.info("[2차 수면 방지] 감시 태스크가 정상 취소되었습니다.")
        except Exception as exc:
            logger.error(f"[2차 수면 방지] 루틴 실행 중 오류: {exc}", exc_info=True)

    async def confirm_wakeup(self, actor: str = "user") -> None:
        """
        사용자가 팝업 확인 버튼을 누르거나 터치패드를 입력하여 기상 상태를 증명했을 때 호출됩니다.
        """
        self._wakeup_confirmed = True
        if self._second_sleep_task and not self._second_sleep_task.done():
            self._second_sleep_task.cancel()
        logger.info(f"[기상 확인 완료] actor={actor}")

        await ws_manager.broadcast({
            "type": "wakeup_confirmed",
            "actor": actor,
            "message": "기상 확인 완료! 활기찬 하루를 시작하세요.",
            "updated_at": _now_iso(),
        })


def _label_from_event_type(event_type: Optional[str]) -> Optional[str]:
    """
    구버전 비전 클라이언트 호환: 'person_detected' → 'person', 'bottle_cleared' → 'bottle'.
    'gesture_rock' 처럼 접두어가 붙은 형태도 처리합니다.
    """
    if not event_type:
        return None
    name = event_type.strip().lower()
    for suffix in ("_detected", "_cleared"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if name.startswith("gesture_"):
        name = name[len("gesture_"):]
    return name.replace("_", " ") or None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 싱글톤 트리거 서비스 인스턴스
trigger_service = TriggerService()
