import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger("backend.db")

# .env 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smart_control")


def get_db_connection(include_database: bool = True) -> pymysql.Connection:
    """
    MySQL/MariaDB 데이터베이스 커넥션을 생성하여 반환합니다.
    """
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME if include_database else None,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True
    )


@contextmanager
def get_db_cursor(include_database: bool = True) -> Generator[DictCursor, None, None]:
    """
    자동 리소스 관리를 위한 커서 컨텍스트 매니저.
    """
    conn = get_db_connection(include_database=include_database)
    try:
        with conn.cursor() as cursor:
            yield cursor
    finally:
        conn.close()


def _serialize_json(value: Any) -> Optional[str]:
    """값 객체를 JSON 문자열로 직렬화합니다."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _deserialize_json(value: Any) -> Any:
    """JSON 문자열을 파이썬 객체로 역직렬화합니다."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _format_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """DB 행의 날짜 및 JSON 필드를 정제합니다."""
    if not row:
        return None
    formatted = dict(row)
    for key, val in formatted.items():
        if isinstance(val, datetime):
            formatted[key] = val.isoformat() + "Z"
        elif key in ("desired_value", "current_value", "value_json", "value"):
            formatted[key] = _deserialize_json(val)
    return formatted


def init_db() -> None:
    """
    서버 시작 시 데이터베이스 및 필수 테이블 존재 여부를 확인하고 생성합니다.
    시드 디바이스 데이터도 함께 보장합니다.
    """
    try:
        # 1. DB 생성 확인
        with get_db_cursor(include_database=False) as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )

        # 2. 테이블 생성 확인
        with get_db_cursor(include_database=True) as cursor:
            cursor.execute("""
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
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  device_id VARCHAR(50) NOT NULL,
                  value DOUBLE NULL,
                  unit VARCHAR(30) NULL,
                  value_json JSON NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS control_log (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  device_id VARCHAR(50) NOT NULL,
                  action VARCHAR(50) NOT NULL,
                  value JSON NULL,
                  actor VARCHAR(20) NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vision_events (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  event_type VARCHAR(50) NOT NULL,
                  detected BOOLEAN NOT NULL DEFAULT FALSE,
                  count INT DEFAULT 0,
                  confidence FLOAT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. 예약 테이블 (F-01, F-02)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  grade INT NOT NULL,
                  department VARCHAR(50) NOT NULL,
                  student_name VARCHAR(50) NOT NULL,
                  user_count INT NOT NULL DEFAULT 1,
                  reservation_date DATE NOT NULL,
                  time_slot VARCHAR(20) NOT NULL,
                  pin_code VARCHAR(4) NOT NULL,
                  status VARCHAR(20) NOT NULL DEFAULT 'reserved',
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_date_slot (reservation_date, time_slot)
                );
            """)

            # 5. 노래 기록 및 나의 18번 테이블 (F-05)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS song_history (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  title VARCHAR(100) NOT NULL,
                  singer VARCHAR(100) NOT NULL,
                  sing_count INT NOT NULL DEFAULT 1,
                  last_sung_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_title_singer (title, singer)
                );
            """)

            # 6. 디바이스 시드 데이터 등록 (ON DUPLICATE KEY UPDATE)
            seed_devices = [
                ("door_lock_1", "솔레노이드 도어락", "door_lock"),
                ("relay_1", "기기 전원 릴레이", "relay"),
                ("led_1", "부스 조명 LED", "led"),
                ("speaker_1", "스피커/오디오 모듈", "speaker"),
                ("keypad_1", "4x4 비밀번호 키패드", "keypad"),
                ("pir_1", "입장 감지 센서", "pir"),
            ]

            insert_query = """
                INSERT INTO devices (id, name, kind)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  name = VALUES(name),
                  kind = VALUES(kind);
            """
            for dev in seed_devices:
                cursor.execute(insert_query, dev)

            # 7. 기본 노래 시드 데이터 등록
            seed_songs = [
                ("다시 만나", "더윈드", 5),
                ("첫 만남은 계획대로 되지 않아", "TWS", 4),
                ("Supernova", "aespa", 3),
                ("Love wins all", "아이유", 2),
                ("Hype Boy", "NewJeans", 1)
            ]
            song_insert_query = """
                INSERT INTO song_history (title, singer, sing_count)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  sing_count = VALUES(sing_count);
            """
            for song in seed_songs:
                cursor.execute(song_insert_query, song)

        logger.info(f"Database '{DB_NAME}' initialized successfully with devices, reservations, and songs.")
    except Exception as exc:
        logger.error(f"Failed to initialize database: {exc}")
        raise exc


# ==============================================================================
# 디바이스 조회 및 상태 관리 헬퍼 함수
# ==============================================================================

def get_all_devices() -> List[Dict[str, Any]]:
    """모든 디바이스 목록과 현재 상태를 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM devices ORDER BY id ASC")
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    """단일 디바이스 정보를 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM devices WHERE id = %s", (device_id,))
        row = cursor.fetchone()
        return _format_row(row)


def update_desired_state(
    device_id: str,
    desired_state: str,
    desired_value: Optional[Any] = None
) -> bool:
    """
    액추에이터의 목표 상태(desired_state) 및 추가 값(desired_value)을 DB에 저장합니다.
    """
    serialized_val = _serialize_json(desired_value)
    with get_db_cursor() as cursor:
        affected = cursor.execute(
            """
            UPDATE devices
            SET desired_state = %s, desired_value = %s
            WHERE id = %s
            """,
            (desired_state, serialized_val, device_id)
        )
        return affected > 0


def update_current_state(
    device_id: str,
    current_state: str,
    current_value: Optional[Any] = None
) -> bool:
    """
    라즈베리파이 또는 Mock이 보고한 실제 상태(current_state)를 DB에 반영합니다.
    """
    serialized_val = _serialize_json(current_value)
    with get_db_cursor() as cursor:
        affected = cursor.execute(
            """
            UPDATE devices
            SET current_state = %s, current_value = %s
            WHERE id = %s
            """,
            (current_state, serialized_val, device_id)
        )
        return affected > 0


# ==============================================================================
# 로그 기록 및 히스토리 조회 헬퍼 함수
# ==============================================================================

def log_sensor_reading(
    device_id: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    value_json: Optional[Dict[str, Any]] = None
) -> None:
    """
    센서 측정값을 sensor_readings 테이블에 기록합니다.
    """
    serialized_json = _serialize_json(value_json)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sensor_readings (device_id, value, unit, value_json)
            VALUES (%s, %s, %s, %s)
            """,
            (device_id, value, unit, serialized_json)
        )


def log_control_action(
    device_id: str,
    action: str,
    value: Optional[Any] = None,
    actor: str = "user"
) -> None:
    """
    제어 명령 또는 상태 반영 내역을 control_log 테이블에 기록합니다.
    actor는 'user' 또는 'device'입니다.
    """
    serialized_val = _serialize_json(value)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO control_log (device_id, action, value, actor)
            VALUES (%s, %s, %s, %s)
            """,
            (device_id, action, serialized_val, actor)
        )


def get_sensor_history(device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """특정 센서의 최근 측정치 히스토리를 반환합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM sensor_readings
            WHERE device_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (device_id, limit)
        )
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def get_control_history(
    device_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """제어 로그 히스토리를 반환합니다. device_id가 주어지면 해당 디바이스로 한정합니다."""
    with get_db_cursor() as cursor:
        if device_id:
            cursor.execute(
                """
                SELECT * FROM control_log
                WHERE device_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (device_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM control_log
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,)
            )
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def log_vision_event(
    event_type: str,
    detected: bool = False,
    count: int = 0,
    confidence: Optional[float] = None
) -> None:
    """비전 이벤트 감지 내역을 vision_events 테이블에 기록합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO vision_events (event_type, detected, count, confidence)
            VALUES (%s, %s, %s, %s)
            """,
            (event_type, detected, count, confidence)
        )


def get_recent_vision_events(limit: int = 20) -> List[Dict[str, Any]]:
    """최근 비전 감지 이벤트 목록을 반환합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM vision_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


# ==============================================================================
# 예약(F-01, F-02) 헬퍼 함수
# ==============================================================================

def create_reservation(
    grade: int,
    department: str,
    student_name: str,
    user_count: int,
    reservation_date: str,
    time_slot: str,
    pin_code: str
) -> Dict[str, Any]:
    """신규 예약을 등록합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
              grade, department, student_name, user_count,
              reservation_date, time_slot, pin_code, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'reserved')
            """,
            (grade, department, student_name, user_count, reservation_date, time_slot, pin_code)
        )
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM reservations WHERE id = %s", (new_id,))
        row = cursor.fetchone()
        return _format_row(row) or {}


def get_reservations(limit: int = 50) -> List[Dict[str, Any]]:
    """전체 예약 목록을 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM reservations
            ORDER BY reservation_date DESC, time_slot ASC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def get_reservation_by_pin(pin_code: str) -> Optional[Dict[str, Any]]:
    """4자리 PIN 코드로 유효한 예약을 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM reservations
            WHERE pin_code = %s AND status IN ('reserved', 'active')
            ORDER BY id DESC LIMIT 1
            """,
            (pin_code,)
        )
        row = cursor.fetchone()
        return _format_row(row)


def update_reservation_status(reservation_id: int, status: str) -> bool:
    """예약 상태를 갱신합니다 ('active', 'completed', 'cancelled')"""
    with get_db_cursor() as cursor:
        affected = cursor.execute(
            "UPDATE reservations SET status = %s WHERE id = %s",
            (status, reservation_id)
        )
        return affected > 0


# ==============================================================================
# 노래 기록 및 나의 18번(F-05) 헬퍼 함수
# ==============================================================================

def get_all_songs() -> List[Dict[str, Any]]:
    """모든 노래 목록을 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM song_history ORDER BY last_sung_at DESC")
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def get_favorite_songs(min_count: int = 3) -> List[Dict[str, Any]]:
    """나의 18번(3회 이상 부른 곡) 목록을 조회합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM song_history
            WHERE sing_count >= %s
            ORDER BY sing_count DESC, last_sung_at DESC
            """,
            (min_count,)
        )
        rows = cursor.fetchall()
        return [_format_row(row) for row in rows]  # type: ignore


def record_song(title: str, singer: str) -> Dict[str, Any]:
    """노래를 부른 내역을 기록(카운트 1 증가)합니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO song_history (title, singer, sing_count)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE
              sing_count = sing_count + 1
            """,
            (title, singer)
        )
        cursor.execute(
            "SELECT * FROM song_history WHERE title = %s AND singer = %s",
            (title, singer)
        )
        row = cursor.fetchone()
        return _format_row(row) or {}

