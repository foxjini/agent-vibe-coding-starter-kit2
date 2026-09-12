"""
백엔드 통신 (pi/backend_client.py) — 키트 제공, 수정하지 마세요.

슬롯 20개를 개별 폴링하면 초당 20요청이 됩니다. 그래서 **한 번에 묶어서** 주고받습니다
(부록F 5-2절).
  등록  POST /api/v1/devices/register
  폴링  GET  /api/v1/devices/desired-states
  보고  POST /api/v1/devices/states
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("pi.backend")

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "3.0"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackendClient:
    """백엔드와 주고받는 일만 담당합니다 (하드웨어는 모릅니다)."""

    def __init__(self, base_url: str, device_api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.device_api_key = device_api_key
        self.session = requests.Session()
        #: 연결이 끊겼다 돌아올 때 한 번만 로그를 남기기 위한 상태
        self._online: Optional[bool] = None

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "X-Device-Api-Key": self.device_api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # 내부 공통 처리
    # ------------------------------------------------------------------

    def _mark_online(self) -> None:
        if self._online is not True:
            logger.info(f"백엔드에 연결되었습니다: {self.base_url}")
        self._online = True

    def _mark_offline(self, detail: str) -> None:
        if self._online is not False:
            logger.warning(
                f"백엔드에 연결할 수 없습니다 ({self.base_url}). 다음 회차에 다시 시도합니다 — {detail}"
            )
            logger.warning(
                "확인할 것: 1) 백엔드가 켜져 있는지  2) .env의 BACKEND_URL이 PC의 "
                "Wi-Fi IP인지 (localhost는 파이 자신을 가리킵니다)"
            )
        self._online = False

    def _request(self, method: str, path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        try:
            res = self.session.request(
                method, url, headers=self.headers, timeout=REQUEST_TIMEOUT, **kwargs
            )
        except requests.exceptions.RequestException as exc:
            self._mark_offline(f"{type(exc).__name__}")
            return None

        self._mark_online()
        if res.status_code == 200:
            try:
                return res.json().get("data", {})
            except ValueError:
                logger.warning(f"{path}: 응답이 JSON이 아닙니다 — {res.text[:120]}")
                return None

        if res.status_code in (401, 403):
            logger.error(
                "인증 실패! pi/.env의 DEVICE_API_KEY가 백엔드 .env와 똑같은지 확인하세요."
            )
        elif res.status_code == 503:
            logger.warning(f"{path}: 백엔드가 아직 준비되지 않았습니다 — {res.text[:160]}")
        else:
            logger.warning(f"{path} 실패 ({res.status_code}): {res.text[:200]}")
        return None

    # ------------------------------------------------------------------
    # 키트 3개 엔드포인트
    # ------------------------------------------------------------------

    def register(self, slots: List[Dict[str, Any]], exclusive: bool = True) -> Optional[Dict[str, Any]]:
        """
        배치표를 등록합니다. exclusive=True면 목록에 없는 슬롯은 자동으로 꺼집니다
        → slot_map.py에서 한 줄을 지우면 대시보드에서도 사라집니다.
        """
        return self._request(
            "POST", "/api/v1/devices/register",
            json={"slots": slots, "exclusive": exclusive},
        )

    def poll_desired_states(self) -> Optional[Dict[str, Any]]:
        """활성 액추에이터의 목표 상태를 한 번에 받아옵니다."""
        data = self._request("GET", "/api/v1/devices/desired-states")
        if data is None:
            return None
        return data.get("slots") or {}

    def report_states(self, states: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """반영 결과와 센서 측정값을 한 번에 보고합니다."""
        if not states:
            return {"accepted": 0}
        return self._request(
            "POST", "/api/v1/devices/states",
            json={"states": states, "reported_at": now_iso()},
        )
