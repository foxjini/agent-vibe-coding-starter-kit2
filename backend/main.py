import logging
import os
import sys

# ==============================================================================
# sys.path 자동 경로 주입 (어느 디렉토리에서 실행하든 절대/상대 경로 임포트 오류 방지)
# ==============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from websocket_manager import ws_manager

logger = logging.getLogger("backend.main")

# CORS 허용 출처 — 코드에 하드코딩하지 않고 .env로 관리한다 (deploy-rules.md).
# 쉼표로 구분해서 여러 개를 넣을 수 있다.
#   예) CORS_ALLOW_ORIGINS=http://localhost:3000,https://our-team.vercel.app
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_allowed_origins() -> List[str]:
    """.env의 CORS_ALLOW_ORIGINS를 파싱해 허용 출처 목록을 반환합니다."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="Smart IoT & Vision Control System API",
    version="1.0.0",
    description="IoT 센서 및 액추에이터 제어, 영상인식 트리거 백엔드 API"
)

# CORS 설정 (Next.js 로컬 개발 및 클라우드 배포 지원)
# 주의: allow_origins=["*"]와 allow_credentials=True를 함께 쓰면 브라우저의
# 교차출처 보호가 사실상 무력화된다(임의의 사이트가 인증정보를 실어 이 API를 호출할 수
# 있게 된다). 그래서 허용 출처를 명시적으로 지정한다 — security-rules.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """백엔드 서버 헬스체크 엔드포인트"""
    return {"status": "ok", "message": "Backend server is running healthy."}


@app.get("/")
async def root() -> Dict[str, Any]:
    """루트 안내 엔드포인트"""
    return {
        "message": "Smart IoT & Vision Control Backend is active.",
        "docs_url": "/docs",
        "health_url": "/health"
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """실시간 디바이스 상태 스트리밍용 WebSocket 엔드포인트"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # 대시보드는 주로 수신만 하지만, 연결 유지를 위해 수신 대기한다.
            # 클라이언트가 보낸 메시지를 처리할 일이 생기면 여기에 추가한다.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:  # 예외를 조용히 삼키지 않는다 — coding-standards.md
        logger.warning(f"WebSocket connection closed with error: {exc}")
        ws_manager.disconnect(websocket)
