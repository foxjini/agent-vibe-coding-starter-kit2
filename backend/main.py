import asyncio
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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from db.database import get_db_status, init_db
from routers.devices import router as devices_router
from routers.logs import router as logs_router
from routers.slots import router as slots_router
from routers.vision import router as vision_router
from services.rule_engine import rule_engine
from websocket_manager import ws_manager


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
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
            "DB 초기화에 실패했습니다. 알람·미션·대시보드는 계속 동작하지만 "
            f"기록(제어 이력/센서 이력/비전 이벤트)은 저장되지 않습니다: {exc}"
        )
        logger.warning(
            "해결 방법: XAMPP 등에서 MySQL/MariaDB를 켠 뒤 서버를 재시작하세요. "
            "현재 DB 상태는 GET /health 로 확인할 수 있습니다."
        )

    # 플랫폼 키트 규칙 엔진의 스케줄 트리거 점검 루프
    # (알람 예약은 schedule 트리거 규칙으로 저장되므로 서버를 재시작해도 살아 있습니다)
    rule_task = asyncio.create_task(
        rule_engine.run_scheduler(float(os.getenv("RULE_TICK_SECONDS", "20")))
    )

    yield

    rule_task.cancel()


app = FastAPI(
    title="IoT 개발 플랫폼 키트 API",
    version="2.0.0",
    description=(
        "4개 팀이 공통으로 쓰는 IoT 플랫폼 키트 백엔드. "
        "센서·액추에이터 슬롯 20개를 중계하고, 자동화 규칙을 실행합니다. "
        "시나리오(게임·미션) 로직은 프론트엔드가 맡습니다 — docs/부록F 참고."
    ),
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


# ==============================================================================
# 공통 에러 응답 형식 (api-rules.md: 실패는 항상 {"error": {"code", "message"}})
# ==============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTPException을 api-rules.md의 에러 껍데기로 변환합니다."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        payload = detail
    else:
        payload = {
            "error": {
                "code": _default_error_code(exc.status_code),
                "message": detail if isinstance(detail, str) else str(detail),
            }
        }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """입력값 검증 실패(422)도 동일한 에러 껍데기로 반환합니다."""
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "입력값이 올바르지 않습니다.")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"{location}: {message}" if location else message,
            }
        },
    )


def _default_error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        422: "VALIDATION_ERROR",
    }.get(status_code, "INTERNAL_ERROR")


# 라우터 등록
app.include_router(devices_router)
app.include_router(vision_router)
app.include_router(logs_router)
app.include_router(slots_router)   # 플랫폼 키트 (슬롯·배치 통신·규칙)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """백엔드 서버 헬스체크 엔드포인트 (DB 연결 상태 포함)"""
    db_status = get_db_status()
    return {
        "status": "ok",
        "message": "Backend server is running healthy.",
        "database": db_status,
        "device_mode": os.getenv("DEVICE_MODE", "mock"),
    }


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
