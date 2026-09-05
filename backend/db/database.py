import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Union

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
    }
    if include_db:
        params["database"] = DB_NAME
    return params


@contextmanager
def get_db_connection() -> Generator[pymysql.Connection, None, None]:
    """
    MySQL 커넥션을 안전하게 열고 닫는 컨텍스트 매니저.
    트랜잭션 커밋 및 예외 시 롤백을 수행합니다.
    """
    connection = pymysql.connect(**_get_connection_params(include_db=True))
    try:
        yield connection
        connection.commit()
    except Exception as exc:
        connection.rollback()
        logger.error(f"Database transaction error: {exc}", exc_info=True)
        raise
    finally:
        connection.close()


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

    # 2. 필수 테이블 4개 및 시드 데이터 적용
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
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
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
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
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
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

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

def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    """특정 디바이스 정보를 조회합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM devices WHERE id = %s", (device_id,))
            return cursor.fetchone()


def get_all_devices() -> List[Dict[str, Any]]:
    """등록된 모든 디바이스 목록을 조회합니다."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM devices ORDER BY created_at ASC")
            return cursor.fetchall()


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


def update_current_state(
    device_id: str,
    current_state: str,
    current_value: Optional[Any] = None
) -> bool:
    """
    라즈베리파이(또는 Mock)가 보고한 실제 상태(current_state)를 DB에 갱신합니다.
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
            return cursor.fetchall()


# ==============================================================================
# 제어 이력(Control Log) 관련 헬퍼 함수
# ==============================================================================

def log_control_action(
    device_id: str,
    action: str,
    value: Optional[Any] = None,
    actor: str = "user",
) -> None:
    """
    액추에이터 제어 명령 이력을 control_log 테이블에 기록합니다.
    actor는 'user' 또는 'device'입니다.
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
            return cursor.fetchall()


# ==============================================================================
# 영상인식 이벤트(Vision Events) 관련 헬퍼 함수
# ==============================================================================

def log_vision_event(
    event_type: str,
    detected: bool,
    count: int = 0,
    confidence: Optional[float] = None,
) -> int:
    """
    웹캠 영상인식 감지 이벤트를 vision_events 테이블에 기록합니다.
    새로 생성된 이벤트 ID(PK)를 반환합니다.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vision_events (event_type, detected, count, confidence)
                VALUES (%s, %s, %s, %s)
                """,
                (event_type, detected, count, confidence),
            )
            return int(cursor.lastrowid)


def get_recent_vision_events(limit: int = 20) -> List[Dict[str, Any]]:
    """최근 영상인식 감지 이벤트 목록을 조회합니다."""
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
            return cursor.fetchall()
