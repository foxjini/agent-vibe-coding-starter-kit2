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

from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db.database import init_db
from routers.alarm import router as alarm_router
from routers.devices import router as devices_router
from routers.logs import router as logs_router
from routers.vision import router as vision_router
from websocket_manager import ws_manager


logger = logging.getLogger("backend.main")

# CORS 허용 출처 — 코드에 하드코딩하지 않고 .env로 관리한다 (deploy-rules.md).
# 쉼표로 구분해서 여러 개를 넣을 수 있다.
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_allowed_origins() -> List[str]:
    """.env의 CORS_ALLOW_ORIGINS를 파싱해 허용 출처 목록을 반환합니다."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB 연결 및 테이블/시드 데이터 존재를 보장합니다."""
    try:
        init_db()
        logger.info("Database initialized successfully at server startup.")
    except Exception as exc:
        logger.warning(
            f"DB 초기화 실패 (Mock 모드로 단독 실행 가능): {exc}"
        )
    yield


app = FastAPI(
    title="Smart IoT & Vision Control System API",
    version="1.0.0",
    description="스마트 기상 시스템: 알람 피에조 부저 제어, 터치패드/카메라 센서 모니터링, 영상인식 트리거 백엔드 API",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(devices_router)
app.include_router(alarm_router)
app.include_router(vision_router)
app.include_router(logs_router)



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
        "health_url": "/health",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """실시간 디바이스 상태 스트리밍용 WebSocket 엔드포인트"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # 대시보드는 주로 수신만 하지만, 연결 유지를 위해 수신 대기한다.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket connection closed with error: {exc}")
        ws_manager.disconnect(websocket)

