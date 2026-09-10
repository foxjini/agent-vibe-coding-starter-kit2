import json
import logging
import os
import queue
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Optional, Union

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# .env 환경 변수 로드
load_dotenv()

logger = logging.getLogger("backend.db.database")

# DB 접속 설정 (.env 우선, 기본값 fallback)
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smart_control")

# 커넥션 풀 크기 (라즈베리파이 폴링 + 비전 이벤트가 겹쳐도 커넥션이 폭주하지 않도록 재사용한다)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_CONNECT_TIMEOUT = float(os.getenv("DB_CONNECT_TIMEOUT", "3"))

# JSON 컬럼 목록 — PyMySQL은 JSON 컬럼을 dict가 아닌 '문자열'로 돌려주므로 직접 디코드한다.
_JSON_COLUMNS = ("desired_value", "current_value", "value_json", "value")

# DB 상태 (DB가 꺼져 있어도 시스템이 죽지 않도록 상태만 기록하고 진행한다)
_db_status: Dict[str, Any] = {
    "healthy": None,      # None=아직 시도 안 함, True=정상, False=장애
    "last_error": None,
    "last_warned_at": 0.0,
}
_WARN_INTERVAL_SECONDS = 30.0

_pool: "queue.LifoQueue[pymysql.Connection]" = queue.LifoQueue(maxsize=DB_POOL_SIZE)


def _get_connection_params(include_db: bool = True) -> Dict[str, Any]:
    """PyMySQL 연결 파라미터를 생성합니다."""
    params: Dict[str, Any] = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
        "connect_timeout": DB_CONNECT_TIMEOUT,
    }
    if include_db:
        params["database"] = DB_NAME
    return params


# ==============================================================================
# DB 상태 관리 및 커넥션 풀
# ==============================================================================

def get_db_status() -> Dict[str, Any]:
    """/health 엔드포인트에서 DB 연결 상태를 노출하기 위한 헬퍼입니다."""
    return {
        "connected": bool(_db_status["healthy"]),
        "checked": _db_status["healthy"] is not None,
        "last_error": _db_status["last_error"],
    }


def _mark_healthy() -> None:
    if _db_status["healthy"] is not True:
        logger.info("데이터베이스 연결이 정상입니다.")
    _db_status["healthy"] = True
    _db_status["last_error"] = None


def _mark_unhealthy(exc: Exception) -> None:
    _db_status["healthy"] = False
    _db_status["last_error"] = f"{type(exc).__name__}: {exc}"


def _acquire_connection() -> pymysql.Connection:
    """풀에서 커넥션을 꺼내거나(없으면) 새로 만듭니다."""
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            return pymysql.connect(**_get_connection_params(include_db=True))

        try:
            conn.ping(reconnect=True)  # 끊긴 커넥션이면 재연결
            return conn
        except Exception:
            _close_quietly(conn)
            # 다음 루프에서 새 커넥션을 만든다


def _release_connection(conn: pymysql.Connection) -> None:
    """정상 종료된 커넥션을 풀에 되돌립니다 (풀이 가득 차면 닫습니다)."""
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        _close_quietly(conn)


def _close_quietly(conn: Optional[pymysql.Connection]) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass


@contextmanager
def get_db_connection() -> Generator[pymysql.Connection, None, None]:
    """
    MySQL 커넥션을 안전하게 빌려주고 돌려받는 컨텍스트 매니저.
    트랜잭션 커밋 및 예외 시 롤백을 수행하며, 정상 종료된 커넥션만 풀로 반환합니다.
    """
    conn = _acquire_connection()
    succeeded = False
    try:
        yield conn
        conn.commit()
        succeeded = True
        _mark_healthy()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        _mark_unhealthy(exc)
        logger.error(f"Database transaction error: {exc}", exc_info=True)
        raise
    finally:
        if succeeded:
            _release_connection(conn)
        else:
            _close_quietly(conn)


def _tolerant(fallback_factory: Callable[[], Any]):
    """
    DB 장애(서버 미기동, 네트워크 끊김)로 시스템 전체가 멈추지 않도록 하는 데코레이터.
    실패 시 예외 대신 안전한 기본값을 돌려주고, 과도한 로그를 막기 위해 경고는 30초에 한 번만 남깁니다.
    DB 상태는 get_db_status()와 /health 응답으로 확인할 수 있습니다.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (pymysql.Error, OSError) as exc:
                _mark_unhealthy(exc)
                now = time.time()
                if now - float(_db_status["last_warned_at"]) > _WARN_INTERVAL_SECONDS:
                    _db_status["last_warned_at"] = now
                    logger.warning(
                        f"DB 접근 실패로 '{func.__name__}'을(를) 건너뜁니다 "
                        f"(DB 없이도 동작하도록 폴백). 원인: {exc}"
                    )
                return fallback_factory()
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def _decode_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    PyMySQL이 문자열로 돌려주는 JSON 컬럼을 파이썬 객체로 되돌립니다.
    (이 처리가 없으면 대시보드에서 current_value.pressed 같은 접근이 전부 undefined가 됩니다.)
    """
    if not row:
        return row
    for key in _JSON_COLUMNS:
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                row[key] = json.loads(raw)
            except (ValueError, TypeError):
                pass  # 순수 문자열 값이면 그대로 둔다
    return row


def _decode_rows(rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    return [_decode_row(dict(r)) for r in (rows or [])]


def init_db() -> None:
    """
    서버 시작 시 데이터베이스 및 기본 테이블이 존재하는지 확인하고 생성합니다.
    AGENTS.md 팀 정보에 정의된 기본 디바이스 시드 데이터를 함께 삽입합니다.
    """
    # 1. 데이터베이스 존재 여부 확인 및 생성
    server_conn = pymysql.connect(**_get_connection_params(include_db=False))
    try:
        with server_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        server_conn.commit()
    finally:
        server_conn.close()

    # 2. 필수 테이블 5개 및 시드 데이터 적용
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # 1) devices
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    kind VARCHAR(30) NOT NULL,
                    desired_state VARCHAR(30) NULL,
                    current_state VARCHAR(30) NULL,
                    desired_value JSON NULL,
                    current_value JSON NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # 2) sensor_readings
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
                    device_id VARCHAR(50) NOT NULL,
                    value FLOAT NULL,
                    unit VARCHAR(20) NULL,
                    value_json JSON NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
                    INDEX idx_sensor_device_time (device_id, created_at)
                );
                """
            )
            # 3) control_log
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS control_log (
                    id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
                    device_id VARCHAR(50) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    value JSON NULL,
                    actor VARCHAR(50) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
                    INDEX idx_control_device_time (device_id, created_at)
                );
                """
            )

            # 4) vision_events
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vision_events (
                    id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
                    event_type VARCHAR(50) NOT NULL,
                    detected BOOLEAN NOT NULL,
                    count INT DEFAULT 0,
                    confidence FLOAT NULL,
                    label VARCHAR(50) NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_vision_time (created_at)
                );
                """
            )

            # 5) app_settings — 알람 예약처럼 서버 재시작 후에도 살아남아야 하는 설정 (부록A 제9장)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key VARCHAR(50) PRIMARY KEY,
                    setting_value JSON NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                );
                """
            )

            # 기존 DB에 label 컬럼이 없으면 추가 (1차 완성본에서 올라온 팀 호환)
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'vision_events' AND column_name = 'label'
                """,
                (DB_NAME,),
            )
            row = cursor.fetchone()
            if row and int(row["cnt"]) == 0:
                cursor.execute("ALTER TABLE vision_events ADD COLUMN label VARCHAR(50) NULL")

            # 시드 데이터 삽입 (원점 상태 덮어쓰기 방지: ON DUPLICATE KEY UPDATE name, kind만 갱신)
            seed_devices = [
                ("buzzer_1", "알람 출력 장치(피에조 부저)", "buzzer"),
                ("touch_pad_1", "패드 화면/터치 입력", "touch_pad"),
                ("camera_1", "기상 감지 카메라", "camera"),
            ]
            for dev_id, name, kind in seed_devices:
                cursor.execute(
                    """
                    INSERT INTO devices (id, name, kind)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        kind = VALUES(kind);
                    """,
                    (dev_id, name, kind),
                )
    logger.info("Database initialized successfully with default devices.")


# ==============================================================================
# 디바이스(Devices) 관련 헬퍼 함수
# ==============================================================================

@_tolerant(lambda: None)
def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    """특정 디바이스 정보를 조회합니다. (DB 장애 시 None)"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM devices WHERE id = %s", (device_id,))
            return _decode_row(cursor.fetchone())


@_tolerant(lambda: [])
def get_all_devices() -> List[Dict[str, Any]]:
    """등록된 모든 디바이스 목록을 조회합니다. (DB 장애 시 빈 목록)"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM devices ORDER BY created_at ASC")
            return _decode_rows(cursor.fetchall())


@_tolerant(lambda: False)
def update_desired_state(
    device_id: str,
    desired_state: str,
    desired_value: Optional[Any] = None
) -> bool:
    """
    대시보드 또는 트리거 로직에서 지정한 액추에이터의 목표 상태(desired_state)를 DB에 갱신합니다.
    """
    val_json = json.dumps(desired_value) if desired_value is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE devices
                SET desired_state = %s, desired_value = %s
                WHERE id = %s
                """,
                (desired_state, val_json, device_id),
            )
            return cursor.rowcount > 0


@_tolerant(lambda: False)
def update_current_state(
    device_id: str,
    current_state: str,
    current_value: Optional[Any] = None
) -> bool:
    """
    라즈베리파이(또는 Mock)가 보고한 실제 상태(current_state)를 DB에 갱신합니다.
    이 함수는 '기기가 실제로 반영한 결과'만 기록합니다 — 백엔드가 명령한 값은
    update_desired_state()에 기록해야 부록A의 desired/current 계약이 유지됩니다.
    """
    val_json = json.dumps(current_value) if current_value is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE devices
                SET current_state = %s, current_value = %s
                WHERE id = %s
                """,
                (current_state, val_json, device_id),
            )
            return cursor.rowcount > 0


# ==============================================================================
# 센서 측정값(Sensor Readings) 관련 헬퍼 함수
# ==============================================================================

@_tolerant(lambda: None)
def log_sensor_reading(
    device_id: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    value_json: Optional[Union[Dict[str, Any], List[Any]]] = None,
) -> None:
    """
    센서 측정값을 sensor_readings 테이블에 기록합니다.
    단일 수치는 value+unit을, 다중 센서 값은 value_json에 저장합니다.
    """
    v_json_str = json.dumps(value_json) if value_json is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sensor_readings (device_id, value, unit, value_json)
                VALUES (%s, %s, %s, %s)
                """,
                (device_id, value, unit, v_json_str),
            )


@_tolerant(lambda: [])
def get_sensor_history(device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """특정 센서의 최근 측정 이력을 반환합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM sensor_readings
                WHERE device_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (device_id, limit),
            )
            return _decode_rows(cursor.fetchall())


# ==============================================================================
# 제어 이력(Control Log) 관련 헬퍼 함수
# ==============================================================================

@_tolerant(lambda: None)
def log_control_action(
    device_id: str,
    action: str,
    value: Optional[Any] = None,
    actor: str = "user",
) -> None:
    """
    액추에이터 제어 명령 이력을 control_log 테이블에 기록합니다.
    actor는 'user'(대시보드), 'device'(라즈베리파이 보고), 'trigger'/'system'(자동 규칙)입니다.
    """
    val_json = json.dumps(value) if value is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO control_log (device_id, action, value, actor)
                VALUES (%s, %s, %s, %s)
                """,
                (device_id, action, val_json, actor),
            )


@_tolerant(lambda: [])
def get_control_log(device_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """디바이스 제어 이력 로그를 조회합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            if device_id:
                cursor.execute(
                    """
                    SELECT * FROM control_log
                    WHERE device_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (device_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM control_log
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return _decode_rows(cursor.fetchall())


# ==============================================================================
# 영상인식 이벤트(Vision Events) 관련 헬퍼 함수
# ==============================================================================

@_tolerant(lambda: None)
def log_vision_event(
    event_type: str,
    detected: bool,
    count: int = 0,
    confidence: Optional[float] = None,
    label: Optional[str] = None,
) -> Optional[int]:
    """
    웹캠 영상인식 감지 이벤트를 vision_events 테이블에 기록합니다.
    새로 생성된 이벤트 ID(PK)를 반환하며, DB 장애 시 None을 반환합니다.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vision_events (event_type, detected, count, confidence, label)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (event_type, detected, count, confidence, label),
            )
            return int(cursor.lastrowid)


@_tolerant(lambda: [])
def get_recent_vision_events(limit: int = 20) -> List[Dict[str, Any]]:
    """최근 영상인식 감지 이벤트 목록을 반환합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM vision_events
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return _decode_rows(cursor.fetchall())


# ==============================================================================
# 앱 설정(App Settings) — 알람 예약처럼 재시작 후에도 유지되어야 하는 값
# ==============================================================================

@_tolerant(lambda: None)
def get_app_setting(key: str) -> Optional[Any]:
    """저장된 앱 설정 값을 조회합니다. (없거나 DB 장애 시 None)"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = %s", (key,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row.get("setting_value")
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except (ValueError, TypeError):
                    return raw
            return raw


@_tolerant(lambda: False)
def set_app_setting(key: str, value: Optional[Any]) -> bool:
    """앱 설정 값을 저장합니다 (JSON 직렬화)."""
    val_json = json.dumps(value) if value is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                """,
                (key, val_json),
            )
            return True
