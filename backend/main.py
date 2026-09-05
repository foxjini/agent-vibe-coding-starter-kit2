from contextlib import asynccontextmanager
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

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.devices import user_router, device_router
from routers.reservations import reservations_router, booth_router, songs_router
from websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend.main")

# CORS 허용 출처 — 코드에 하드코딩하지 않고 .env로 관리한다 (deploy-rules.md).
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_allowed_origins() -> List[str]:
    """.env의 CORS_ALLOW_ORIGINS를 파싱해 허용 출처 목록을 반환합니다."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 및 종료 라이프사이클 이벤트 관리"""
    # 1. 서버 시작 시 DB 및 디바이스 시드 데이터 검증/초기화 시도
    try:
        from db.database import init_db
        init_db()
        logger.info("Database and seed data successfully initialized at startup.")
    except Exception as exc:
        logger.warning(
            f"DB initialization at startup skipped/failed (MariaDB connection check): {exc}"
        )

    yield

    logger.info("Backend server shutting down.")


app = FastAPI(
    title="Smart IoT Karaoke Control System API",
    version="1.0.0",
    description="웹 예약 연동 자동화 학교 노래방 부스 관리 시스템 백엔드 API",
    lifespan=lifespan
)

# CORS 설정 (Next.js 로컬 개발 및 클라우드 배포 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 공통 에러 핸들러 (api-rules.md: { "error": { "code": "...", "message": "..." } })
# ==============================================================================

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(detail)}}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": str(exc.errors())}}
    )


# ==============================================================================
# 라우터 등록
# ==============================================================================
app.include_router(user_router)
app.include_router(device_router)
app.include_router(reservations_router)
app.include_router(booth_router)
app.include_router(songs_router)



# ==============================================================================
# 기본 엔드포인트
# ==============================================================================

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """백엔드 서버 헬스체크 엔드포인트"""
    return {"status": "ok", "message": "Backend server is running healthy."}


@app.get("/")
async def root() -> Dict[str, Any]:
    """루트 안내 엔드포인트"""
    return {
        "message": "Smart IoT Karaoke Booth Management Backend is active.",
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
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket connection closed with error: {exc}")
        ws_manager.disconnect(websocket)
