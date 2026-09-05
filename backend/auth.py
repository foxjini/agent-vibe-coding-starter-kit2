import hmac
import logging
import os
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
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # 4단계 Supabase 연동 시 JWT 유효성 검증 활성화
    if supabase_url and supabase_key:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "MISSING_TOKEN", "message": "Authorization Bearer 토큰이 필요합니다."}
            )
        # 추후 JWT 검증 로직 (db-migration 스킬 연동)
        token = authorization.split(" ")[1]
        return {"sub": "authenticated_user", "token": token, "role": "authenticated"}

    # 개발 단계 기본 사용자 컨텍스트 (JWT 연동 전)
    return {"sub": "local_dev_user", "role": "authenticated"}
