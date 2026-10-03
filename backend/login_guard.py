"""
비밀번호 무차별 대입 막기 — 관리자 로그인 · 키패드 인증

4자리 PIN은 경우의 수가 1만 개뿐이다. 아무것도 막지 않으면 스크립트로 몇 분 만에
전부 넣어 볼 수 있고, 관리자 PIN이 뚫리면 도어락과 220V 전원을 원격으로 조작할
수 있다. 그래서 진짜 디지털 도어락처럼 동작하게 한다.

  1) 같은 곳(접속 주소)에서 5번 연속 틀리면 30초 동안 막는다.
     막힌 뒤에도 또 틀리면 1분, 2분 … 으로 늘어난다 (최대 15분).
     한 번 맞히면 그 곳의 기록은 지운다.

  2) 주소를 바꿔 가며 시도하는 경우를 대비해, 전체적으로 10분 안에 20번 틀리면
     1분 동안 모두 막는다. 계속되면 이것도 두 배씩 늘어난다 (최대 30분).
     문을 "여는" 쪽보다 "잠그는" 쪽으로 실패하는 편이 안전하기 때문이다.
     30분 동안 실패가 없으면 원래대로 돌아온다.

라즈베리파이 키패드는 백엔드 입장에서 접속 주소가 하나다. 그래서 키패드에서
5번 연속 틀리면 키패드 전체가 30초 쉬게 된다 — 시판 도어락과 같은 동작이다.

기록은 서버 메모리에만 둔다. 급하게 풀어야 하면 백엔드를 재시작하면 된다.
"""

import logging
import time
from typing import Dict, List

from fastapi import HTTPException, Request, status

logger = logging.getLogger("backend.login_guard")

MAX_FAILS = 5
BASE_LOCK_SEC = 30
MAX_LOCK_SEC = 15 * 60

GLOBAL_WINDOW_SEC = 10 * 60
GLOBAL_MAX_FAILS = 20
GLOBAL_BASE_LOCK_SEC = 60
GLOBAL_MAX_LOCK_SEC = 30 * 60
GLOBAL_QUIET_RESET_SEC = 30 * 60


def client_key(request: Request) -> str:
    """요청을 보낸 곳을 구분하는 값.

    Render 같은 클라우드에서는 앞단 프록시를 거쳐 들어오므로, 프록시가 적어 주는
    X-Forwarded-For 의 첫 주소가 실제 접속 주소다. 이 값은 꾸며 보낼 수도 있지만,
    그렇게 주소를 바꿔 가며 시도하면 위 2) 전체 제한에 걸린다.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


class LoginGuard:
    """한 종류의 비밀번호 입력(예: 관리자 로그인)에 대한 실패 기록."""

    def __init__(self, scope: str) -> None:
        self.scope = scope
        self._fails: Dict[str, int] = {}
        self._locked_until: Dict[str, float] = {}
        self._recent: List[float] = []
        self._global_locks = 0
        self._global_locked_until = 0.0

    def _reject(self, wait: float) -> None:
        seconds = max(1, int(wait + 0.999))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "TOO_MANY_ATTEMPTS",
                "message": f"비밀번호를 여러 번 틀려 잠시 막혔습니다. {seconds}초 뒤에 다시 시도해 주세요.",
            },
            headers={"Retry-After": str(seconds)},
        )

    def check(self, key: str) -> None:
        """지금 시도해도 되는지 확인한다. 막혀 있으면 429 로 돌려보낸다."""
        now = time.monotonic()
        if now < self._global_locked_until:
            self._reject(self._global_locked_until - now)
        until = self._locked_until.get(key, 0.0)
        if now < until:
            self._reject(until - now)

    def fail(self, key: str) -> None:
        """틀렸을 때 부른다."""
        now = time.monotonic()

        count = self._fails.get(key, 0) + 1
        self._fails[key] = count
        if count >= MAX_FAILS:
            # 5번째에 30초, 그 뒤로는 한 번 틀릴 때마다 두 배
            lock = min(MAX_LOCK_SEC, BASE_LOCK_SEC * 2 ** (count - MAX_FAILS))
            self._locked_until[key] = now + lock
            logger.warning(f"[{self.scope}] {key} — {count}회 연속 실패, {lock}초 잠금")

        # 전체 실패 기록 (오래된 것은 버린다)
        if self._recent and now - self._recent[-1] > GLOBAL_QUIET_RESET_SEC:
            self._global_locks = 0
        self._recent = [t for t in self._recent if now - t < GLOBAL_WINDOW_SEC] + [now]
        if len(self._recent) >= GLOBAL_MAX_FAILS:
            lock = min(GLOBAL_MAX_LOCK_SEC, GLOBAL_BASE_LOCK_SEC * 2 ** self._global_locks)
            self._global_locks += 1
            self._global_locked_until = now + lock
            self._recent = []
            logger.warning(f"[{self.scope}] 전체 실패 {GLOBAL_MAX_FAILS}회 — 모든 시도를 {lock}초 잠금")

    def succeed(self, key: str) -> None:
        """맞혔을 때 부른다. 그 곳의 연속 실패 기록을 지운다."""
        self._fails.pop(key, None)
        self._locked_until.pop(key, None)


admin_login_guard = LoginGuard("admin-login")
keypad_guard = LoginGuard("keypad")
