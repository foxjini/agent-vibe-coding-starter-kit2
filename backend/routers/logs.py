import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from auth import verify_user_auth
from db.database import get_control_log
from schemas.common import DataResponse

logger = logging.getLogger("backend.routers.logs")

router = APIRouter(tags=["Logs"])


@router.get(
    "/api/logs/control",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="디바이스 제어 이력 로그 조회",
)
async def list_control_logs(
    device_id: Optional[str] = Query(None, description="특정 디바이스 ID 필터"),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(verify_user_auth),
):
    """대시보드에서 액추에이터 제어 이력 로그를 조회합니다."""
    logs = get_control_log(device_id=device_id, limit=limit)
    return {"data": logs}
