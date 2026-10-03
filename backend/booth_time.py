"""
부스가 있는 곳의 시간 (부록G §2-① · ③)

서버 시계를 그대로 쓰면 안 된다. Render 같은 클라우드는 UTC로 돌기 때문에,
"오늘"과 "12시 30분"의 기준이 학교와 9시간 어긋난다. 점심 타임이 새벽에 도는
일이 실제로 벌어진다.

스케줄러와 대기열이 같은 기준을 써야 하므로 이 파일 하나에만 둔다.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

logger = logging.getLogger("backend.booth_time")

try:
    from zoneinfo import ZoneInfo

    TZ: Optional[ZoneInfo] = ZoneInfo(os.getenv("BOOTH_TIMEZONE", "Asia/Seoul"))
except Exception:
    # Windows 는 시간대 정보를 운영체제가 주지 않아 `tzdata` 패키지가 있어야 한다
    # (requirements.txt 에 들어 있다). 그래도 못 찾으면 이 PC의 시계를 쓴다.
    TZ = None
    logger.warning(
        "시간대 정보를 불러오지 못해 이 PC의 시계로 동작합니다. "
        "`pip install -r requirements.txt` 로 tzdata 를 설치하세요."
    )


def now_local() -> datetime:
    """부스가 있는 곳의 현재 시각 (항상 시간대가 붙은 값).

    시간대 없는 값(naive)을 돌려주면, DB에서 읽은 시각(시간대 있음)과 비교하는
    순간 TypeError 가 난다. 대기열이 그 자리에서 멈춘다. 그래서 시간대 정보를
    못 불러왔을 때도 이 PC의 시간대를 붙여서 돌려준다.
    """
    return datetime.now(TZ) if TZ else datetime.now().astimezone()


def today_str() -> str:
    """부스 기준 오늘 날짜 (YYYY-MM-DD)."""
    return now_local().strftime("%Y-%m-%d")


def today_utc_range() -> Tuple[datetime, datetime]:
    """부스 기준 '오늘' 하루를 UTC 시각 구간 [시작, 끝) 으로.

    DB의 시각은 UTC로 저장된다. "오늘의 순위"를 DB의 날짜 함수(CURDATE 등)로
    자르면 그 기준이 UTC 라서 한국 시간 오전 9시에 하루가 바뀐다.
    """
    now = now_local()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def tz_name() -> str:
    return str(TZ) if TZ else "server-local"
