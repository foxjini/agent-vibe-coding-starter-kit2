"""
부스가 있는 곳의 시간 (부록G §2-① · ③)

서버 시계를 그대로 쓰면 안 된다. Render 같은 클라우드는 UTC로 돌기 때문에,
"오늘"과 "12시 30분"의 기준이 학교와 9시간 어긋난다. 점심 타임이 새벽에 도는
일이 실제로 벌어진다.

스케줄러와 대기열이 같은 기준을 써야 하므로 이 파일 하나에만 둔다.
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("backend.booth_time")

try:
    from zoneinfo import ZoneInfo

    TZ: Optional[ZoneInfo] = ZoneInfo(os.getenv("BOOTH_TIMEZONE", "Asia/Seoul"))
except Exception:  # tzdata가 없는 최소 이미지 등
    TZ = None
    logger.warning("시간대 정보를 불러오지 못해 서버 로컬 시간으로 동작합니다.")


def now_local() -> datetime:
    """부스가 있는 곳의 현재 시각."""
    return datetime.now(TZ) if TZ else datetime.now()


def today_str() -> str:
    """부스 기준 오늘 날짜 (YYYY-MM-DD)."""
    return now_local().strftime("%Y-%m-%d")


def tz_name() -> str:
    return str(TZ) if TZ else "server-local"
