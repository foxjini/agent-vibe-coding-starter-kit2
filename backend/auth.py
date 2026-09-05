import hmac
import logging
import os
from typing import Optional
from fastapi import Header, HTTPException, status

logger = logging.getLogger("backend.auth")


def get_expected_device_api_key() -> str:
    """환경변수에서 DEVICE_API_KEY를 읽어옵니다."""
    return os.getenv("DEVICE_API_KEY", "")


async def verify_device_api_key(
    x_device_api_key: Optional[str] = Header(None, alias="X-Device-Api-Key")
) -> str:
    """
    디바이스향(라즈베리파이 5, 영상인식 클라이언트) 인증 의존성.
    'X-Device-Api-Key' 헤더 값을 환경 변수의 DEVICE_API_KEY와 비교합니다.
    """
    expected_key = get_expected_device_api_key()

    # 키가 설정되어 있지 않은 경우 로컬 개발 편의를 위해 로그만 남기고 통과
    if not expected_key:
        logger.warning(
            "DEVICE_API_KEY가 환경변수에 설정되어 있지 않아 인증 검사를 건너뜁니다."
        )
        return "dev-unsecured"

    if not x_device_api_key or not hmac.compare_digest(x_device_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_DEVICE_KEY",
                    "message": "X-Device-Api-Key가 누락되었거나 일치하지 않습니다.",
                }
            },
        )

    return x_device_api_key


async def verify_user_auth(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Optional[str]:
    """
    사용자향(Next.js 대시보드) 인증 의존성.
    개발 단계(1~3주차)에서는 통과시키고, 배포 단계(4주차)에서 Supabase JWT 검증을 활성화합니다.
    """
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        # 로컬 개발 단계: JWT 시크릿이 없으면 바이패스
        return authorization

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED_USER",
                    "message": "Bearer 토큰이 누락되었거나 유효하지 않습니다.",
                }
            },
        )

    # 필요 시 추후 PyJWT를 통한 검증 로직 추가
    return authorization
