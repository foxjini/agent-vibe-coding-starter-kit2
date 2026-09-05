import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from db.database import (
    get_device,
    log_control_action,
    update_current_state,
    update_desired_state,
)
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.trigger_service")


class TriggerService:
    """
    AGENTS.md 팀 정보 트리거 규칙 관리 서비스:
    - 설정한 알람 시간이 되면 알람을 동작시키고 기상 미션을 시작한다.
    - 미션 성공 시 알람(buzzer_1)을 종료하고, 약 1~2분 후 기상 확인 팝업을 표시한다.
    - 팝업을 확인하지 않으면 알람을 다시 울린다.
    """

    def __init__(self) -> None:
        self._second_sleep_task: Optional[asyncio.Task] = None
        self._wakeup_confirmed: bool = False
        # 시연 및 테스트 환경을 위해 대기 시간을 25초, 확인 제한 시간을 15초로 기본 설정 (원할 경우 조절 가능)
        self.popup_delay_seconds: int = 25
        self.confirm_timeout_seconds: int = 15

    async def handle_vision_event(
        self,
        event_type: str,
        detected: bool,
        count: int,
        confidence: Optional[float],
    ) -> None:
        """
        비전 이벤트 수신 시 트리거 규칙을 판정하고 액추에이터 desired-state를 갱신합니다.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # 기상 미션 성공 판정:
        # 사람(person) 또는 지정 사물(bottle, cup, book, cell phone 등)이 감지되었을 때
        is_mission_success = detected and (
            "detected" in event_type
            or "person" in event_type
            or "bottle" in event_type
            or "cup" in event_type
            or "book" in event_type
            or "phone" in event_type
        )

        if not is_mission_success:
            return

        buzzer = get_device("buzzer_1")
        is_ringing = buzzer and buzzer.get("current_state") in ("ringing", "on")

        if is_ringing:
            logger.info(
                f"[트리거 발동] 기상 미션 성공 감지 ({event_type}, conf={confidence}) -> 알람 종료"
            )
            # 1. DB desired_state 및 current_state를 'off'로 갱신
            update_desired_state("buzzer_1", "off", None)
            update_current_state("buzzer_1", "off", None)
            log_control_action(
                device_id="buzzer_1",
                action="off",
                value={"reason": "mission_success", "event_type": event_type},
                actor="trigger",
            )


            # 2. WebSocket으로 액추에이터 상태 및 미션 성공 즉시 브로드캐스트
            await ws_manager.broadcast({
                "type": "device_state",
                "device_id": "buzzer_1",
                "kind": "buzzer",
                "state": "off",
                "value": None,
                "actor": "trigger (기상 미션 성공)",
                "updated_at": now_iso,
            })

            await ws_manager.broadcast({
                "type": "mission_success",
                "event_type": event_type,
                "confidence": confidence,
                "message": "기상 미션을 완수했습니다! 알람이 해제되었습니다.",
                "countdown": self.popup_delay_seconds,
                "updated_at": now_iso,
            })

            # 3. 2차 수면 방지 루틴 시작 (백그라운드 비동기 태스크)
            if self._second_sleep_task and not self._second_sleep_task.done():
                self._second_sleep_task.cancel()
            self._second_sleep_task = asyncio.create_task(self._run_second_sleep_guard())

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
            now_iso = datetime.now(timezone.utc).isoformat()
            logger.info("[2차 수면 방지] 기상 확인 팝업 브로드캐스트 전송")
            await ws_manager.broadcast({
                "type": "wakeup_check_popup",
                "timeout": self.confirm_timeout_seconds,
                "message": "기상 확인: 2차 수면 방지를 위해 화면을 터치하거나 확인 버튼을 누르세요!",
                "created_at": now_iso,
            })

            # 3단계: 확인 응답 대기 (제한시간)
            await asyncio.sleep(self.confirm_timeout_seconds)

            # 4단계: 응답 확인 여부 검사
            if not self._wakeup_confirmed:
                logger.warning(
                    "[2차 수면 방지 경보] 기상 확인 미응답! 2차 수면 방지 재알람을 울립니다."
                )
                now_re = datetime.now(timezone.utc).isoformat()
                # 알람 다시 울리기
                update_desired_state("buzzer_1", "ringing", {"volume": 90, "frequency": 1200})
                update_current_state("buzzer_1", "ringing", {"volume": 90, "frequency": 1200})
                log_control_action(
                    device_id="buzzer_1",
                    action="ringing",
                    value={"volume": 90, "frequency": 1200, "reason": "second_sleep_detected"},
                    actor="trigger",
                )


                # 브로드캐스트
                await ws_manager.broadcast({
                    "type": "device_state",
                    "device_id": "buzzer_1",
                    "kind": "buzzer",
                    "state": "ringing",
                    "value": {"volume": 90, "frequency": 1200},
                    "actor": "trigger (2차 수면 감지)",
                    "updated_at": now_re,
                })

                await ws_manager.broadcast({
                    "type": "re_alarm",
                    "message": "기상 확인 시간 초과로 알람이 다시 동작합니다!",
                    "updated_at": now_re,
                })
            else:
                logger.info("[2차 수면 방지] 사용자가 기상을 확인하여 루틴이 안전하게 종료되었습니다.")

        except asyncio.CancelledError:
            logger.info("[2차 수면 방지] 감시 태스크가 정상 취소되었습니다.")
        except Exception as exc:
            logger.error(f"[2차 수면 방지] 루틴 실행 중 오류: {exc}", exc_info=True)

    async def confirm_wakeup(self, actor: str = "user") -> None:
        """
        사용자가 팝업 확인 버튼을 누르거나 터치패드를 입력하여 기상 상태를 증명했을 때 호출됩니다.
        """
        self._wakeup_confirmed = True
        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info(f"[기상 확인 완료] actor={actor}")

        await ws_manager.broadcast({
            "type": "wakeup_confirmed",
            "actor": actor,
            "message": "기상 확인 완료! 활기찬 하루를 시작하세요.",
            "updated_at": now_iso,
        })


# 싱글톤 트리거 서비스 인스턴스
trigger_service = TriggerService()
