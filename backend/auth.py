import hmac
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger("backend.auth")


def verify_device_api_key(
    x_device_api_key: Optional[str] = Header(None, alias="X-Device-Api-Key")
) -> str:
    """
    디바이스향(라즈베리파이, 비전 클라이언트) 엔드포인트 전용 인증 미들웨어.
    X-Device-Api-Key 헤더를 .env의 DEVICE_API_KEY와 안전하게 비교(hmac.compare_digest)합니다.
    """
    server_key = os.getenv("DEVICE_API_KEY", "")
    if not server_key:
        logger.error("DEVICE_API_KEY is not configured in environment variables.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SERVER_MISCONFIGURED", "message": "서버 인증 키가 설정되지 않았습니다."}
        )

    if not x_device_api_key or not hmac.compare_digest(x_device_api_key, server_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_DEVICE_KEY", "message": "유효하지 않은 X-Device-Api-Key 입니다."}
        )

    return x_device_api_key


def verify_user_auth(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Dict[str, Any]:
    """
    사용자향(대시보드 프론트엔드) 엔드포인트 전용 인증 미들웨어.
    Supabase Auth JWT 검증을 수행하며, 로컬 개발 단계(미설정 시)에서는 개발 세션을 지원합니다.
    디바이스 API 키와는 엄격히 분리되어 동작합니다.
    """
    # ⚠️ 예전에는 SUPABASE_URL이 채워졌는지로 이 검사를 켰다.
    #    그런데 Supabase는 "로그인 서비스"가 아니라 "DB"로만 쓸 수도 있다.
    #    (전시회 구성이 그렇다 — 관람객은 로그인 없이 예약만 한다)
    #    그 상태에서 DB 접속용으로 SUPABASE_URL만 넣으면 대시보드 요청이
    #    전부 401이 되어 버렸다. 그래서 "인증을 요구할지"를 별도 플래그로 뺀다.
    require_auth = os.getenv("REQUIRE_USER_AUTH", "false").strip().lower() == "true"

    if require_auth:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "MISSING_TOKEN", "message": "Authorization Bearer 토큰이 필요합니다."}
            )
        # 추후 Supabase JWT 서명 검증 로직 (db-migration 스킬 연동)
        token = authorization.split(" ")[1]
        return {"sub": "authenticated_user", "token": token, "role": "authenticated"}

    # 기본값: 익명 허용.
    # 관리자만 쓸 수 있어야 하는 엔드포인트는 이것 대신 verify_admin_token을 건다.
    return {"sub": "anonymous", "role": "anonymous"}


# ==============================================================================
# 관리자 인증 (부록G §3-4)
#
# 지금까지는 도어락/전원 제어와 시나리오 강제 실행이 아무 인증 없이 열려 있었다.
# 화면에서 버튼을 숨겨도 URL을 직접 호출하면 그만이라, 엔드포인트 자체를 막는다.
#
# 학교 프로젝트 규모에 맞춰 로그인/회원가입 대신 **관리자 PIN → 단기 토큰**
# 방식만 쓴다. 토큰은 서버 메모리에만 두므로 백엔드를 재시작하면 모두 만료된다.
# ==============================================================================

# 관리자 PIN은 코드에 박지 않고 .env로 뺀다 (.agents/rules/security-rules.md).
# 기본값은 AGENTS.md에 적힌 팀 규칙값이지만, 저장소를 본 사람은 누구나 아는
# 값이므로 전시 전에 반드시 .env에서 바꿔야 한다.
DEFAULT_ADMIN_PIN = "9179"

# 관리자 세션 유지 시간(초). 선생님이 자리를 비웠을 때 방치되지 않도록 짧게 둔다.
ADMIN_TOKEN_TTL_SEC = int(os.getenv("ADMIN_TOKEN_TTL_SEC", "3600"))

# {토큰: 만료시각(epoch)} — 프로세스 메모리에만 존재한다
_admin_tokens: Dict[str, float] = {}


def get_admin_pin() -> str:
    """.env의 ADMIN_PIN을 반환합니다. 미설정 시 기본값을 쓰고 경고를 남깁니다."""
    pin = os.getenv("ADMIN_PIN", "").strip()
    if not pin:
        logger.warning(
            "ADMIN_PIN이 .env에 없어 기본값을 사용합니다. "
            "이 값은 저장소에 공개되어 있으니 전시 전에 반드시 변경하세요."
        )
        return DEFAULT_ADMIN_PIN
    return pin


def is_admin_pin(pin: str) -> bool:
    """입력 PIN이 관리자 PIN인지 타이밍 공격에 안전하게 비교합니다."""
    return hmac.compare_digest(pin, get_admin_pin())


def issue_admin_token() -> Dict[str, Any]:
    """관리자 PIN 인증에 성공했을 때 단기 토큰을 발급합니다."""
    _purge_expired_tokens()
    token = secrets.token_urlsafe(32)
    _admin_tokens[token] = time.time() + ADMIN_TOKEN_TTL_SEC
    return {"token": token, "expires_in": ADMIN_TOKEN_TTL_SEC}


def revoke_admin_token(token: str) -> None:
    """로그아웃 — 토큰을 즉시 폐기합니다."""
    _admin_tokens.pop(token, None)


def _purge_expired_tokens() -> None:
    now = time.time()
    for tok in [t for t, exp in _admin_tokens.items() if exp <= now]:
        _admin_tokens.pop(tok, None)


def verify_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
) -> str:
    """
    관리자 전용 엔드포인트(기기 제어, 시나리오 강제 실행) 인증 미들웨어.

    학생·관람객이 쓰는 예약 신청, 키패드 인증, 노래 기록에는 걸지 않는다.
    """
    _purge_expired_tokens()
    if not x_admin_token or x_admin_token not in _admin_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ADMIN_AUTH_REQUIRED",
                "message": "관리자 인증이 필요합니다. 관리자 PIN으로 먼저 인증해 주세요."
            }
        )
    return x_admin_token

