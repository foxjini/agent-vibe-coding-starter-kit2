import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
import pymysql

from booth_time import today_utc_range
from pymysql.cursors import DictCursor

logger = logging.getLogger("backend.db")

# .env 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ==============================================================================
# 접속 대상 결정 — 로컬 MariaDB vs Supabase(PostgreSQL)
#
# DATABASE_URL이 채워져 있으면 Supabase(PostgreSQL)로 붙고, 없으면 기존처럼
# 로컬 MySQL/MariaDB로 붙는다. 학생 PC에서는 아무것도 안 바꿔도 그대로 돌아가고,
# Render/Vercel 배포 시에는 DATABASE_URL 하나만 넣으면 전환된다.
#
# 두 드라이버(pymysql / psycopg) 모두 %s 자리표시자를 쓰기 때문에 쿼리 본문은
# 대부분 그대로 쓸 수 있다. 방언이 갈리는 곳은 UPSERT와 DDL뿐이라 아래에서
# _upsert_clause() 와 init_db()가 나눠 처리한다.
# ==============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = bool(DATABASE_URL)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smart_control")


def _upsert_clause(conflict_columns: str, assignments: Dict[str, str]) -> str:
    """
    INSERT 뒤에 붙일 UPSERT 절을 현재 DB 방언에 맞춰 만듭니다.

    assignments의 값에는 `EXCLUDED`(새로 넣으려던 값)를 대문자 그대로 쓴다.
    MySQL에서는 VALUES(컬럼) 형태로, PostgreSQL에서는 EXCLUDED.컬럼 형태로
    자동 변환된다.

        _upsert_clause("id", {"name": "EXCLUDED.name"})
        MySQL      -> ON DUPLICATE KEY UPDATE name = VALUES(name)
        PostgreSQL -> ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
    """
    if IS_POSTGRES:
        sets = ", ".join(f"{col} = {expr}" for col, expr in assignments.items())
        return f"ON CONFLICT ({conflict_columns}) DO UPDATE SET {sets}"

    mysql_sets = []
    for col, expr in assignments.items():
        # EXCLUDED.name -> VALUES(name)
        converted = expr
        if expr.startswith("EXCLUDED."):
            converted = f"VALUES({expr.split('.', 1)[1]})"
        mysql_sets.append(f"{col} = {converted}")
    return "ON DUPLICATE KEY UPDATE " + ", ".join(mysql_sets)


def get_db_connection(include_database: bool = True):
    """
    데이터베이스 커넥션을 생성하여 반환합니다.
    DATABASE_URL이 있으면 PostgreSQL(Supabase), 없으면 MySQL/MariaDB.
    """
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        # Supabase는 항상 TLS를 요구한다. URL에 sslmode가 없으면 붙여 준다.
        dsn = DATABASE_URL
        if "sslmode=" not in dsn:
            dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
        return psycopg.connect(dsn, row_factory=dict_row, autocommit=True)

    # ⚠️ 접속할 때마다 세션 시간대를 UTC로 맞춘다.
    #    DATETIME 컬럼의 기본값(CURRENT_TIMESTAMP)은 "그 DB 서버의 시간대" 시각이다.
    #    한국 PC에 깐 XAMPP는 한국 시간이라, 그대로 두면 저장된 시각을 UTC로 읽는
    #    _format_row 와 9시간 어긋난다. 실제로 체험 대기열이 "9시간 뒤에 호출된
    #    사람"으로 보여 만료·종료가 9시간 동안 일어나지 않았다.
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME if include_database else None,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        init_command="SET time_zone = '+00:00'",
    )


@contextmanager
def get_db_cursor(include_database: bool = True) -> Generator[Any, None, None]:
    """
    자동 리소스 관리를 위한 커서 컨텍스트 매니저.
    두 드라이버 모두 dict 형태의 행을 돌려주도록 맞춰져 있다.
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
            # MySQL DATETIME은 naive(오프셋 없음)라 "Z"만 붙이면 되지만,
            # Supabase(PostgreSQL) 전환 시 tz-aware 값이 오면 "+00:00Z"가 되어
            # ISO-8601이 깨진다. 두 경우를 모두 안전하게 처리한다.
            iso = val.isoformat()
            formatted[key] = iso.replace("+00:00", "Z") if val.tzinfo else iso + "Z"
        elif key in ("desired_value", "current_value", "value_json", "value"):
            formatted[key] = _deserialize_json(val)
    return formatted


def _seed_initial_rows() -> None:
    """
    디바이스·기본 애창곡 시드 데이터를 보장합니다 (MySQL / PostgreSQL 공용).
    UPSERT라 여러 번 실행해도 안전합니다.
    """
    seed_devices = [
        ("door_lock_1", "솔레노이드 도어락", "door_lock"),
        ("relay_1", "기기 전원 릴레이", "relay"),
        ("led_1", "부스 조명 LED", "led"),
        ("speaker_1", "스피커/오디오 모듈", "speaker"),
        ("keypad_1", "4x4 비밀번호 키패드", "keypad"),
        ("pir_1", "입장 감지 센서", "pir"),
    ]
    device_query = """
        INSERT INTO devices (id, name, kind)
        VALUES (%s, %s, %s)
    """ + _upsert_clause("id", {"name": "EXCLUDED.name", "kind": "EXCLUDED.kind"})

    seed_songs = [
        ("다시 만나", "더윈드", 5),
        ("첫 만남은 계획대로 되지 않아", "TWS", 4),
        ("Supernova", "aespa", 3),
        ("Love wins all", "아이유", 2),
        ("Hype Boy", "NewJeans", 1),
    ]
    song_query = """
        INSERT INTO song_history (title, singer, sing_count)
        VALUES (%s, %s, %s)
    """ + _upsert_clause("title, singer", {"sing_count": "EXCLUDED.sing_count"})

    with get_db_cursor() as cursor:
        for dev in seed_devices:
            cursor.execute(device_query, dev)
        for song in seed_songs:
            cursor.execute(song_query, song)


def init_db() -> None:
    """
    서버 시작 시 데이터베이스 및 필수 테이블 존재 여부를 확인하고 생성합니다.
    시드 디바이스 데이터도 함께 보장합니다.

    PostgreSQL(Supabase)에서는 DB·테이블을 코드가 만들지 않는다.
    Supabase 대시보드의 SQL Editor에서 `backend/db/init_supabase.sql`을
    한 번 실행해 스키마를 만들어 두고, 여기서는 시드 데이터만 보장한다.
    (Supabase는 CREATE DATABASE 권한을 주지 않고, 스키마 변경은 대시보드에서
     이력이 남게 관리하는 편이 안전하다)
    """
    try:
        if IS_POSTGRES:
            logger.info("PostgreSQL(Supabase) 모드 — DDL은 건너뛰고 시드만 확인합니다.")
            _seed_initial_rows()
            logger.info("Supabase seed data verified.")
            return

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

            # 6. 노래방 영상 등록 테이블 (F-06)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS song_videos (
                  song_id    VARCHAR(64) PRIMARY KEY,
                  video_id   VARCHAR(32) NOT NULL,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. 전시 체험 대기열 (부록G §2-③)
            # 8. 점수 기록 (부록G §2-④)
            #
            # init.sql 에도 같은 정의가 있지만, 1주차에 이미 DB를 만들어 둔 학생은
            # init.sql 을 다시 돌리지 않는다. 서버가 켜질 때 여기서 만들어 줘야
            # git pull 만 하고도 순위·체험 모드가 동작한다.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS queue_tickets (
                  id         INT AUTO_INCREMENT PRIMARY KEY,
                  ticket_no  INT NOT NULL,
                  issued_on  DATE NOT NULL,
                  nickname   VARCHAR(20) NOT NULL DEFAULT '관람객',
                  pin_code   VARCHAR(4) NOT NULL,
                  status     VARCHAR(20) NOT NULL DEFAULT 'waiting',
                  issued_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                  called_at  DATETIME NULL,
                  started_at DATETIME NULL,
                  ended_at   DATETIME NULL,
                  UNIQUE KEY uq_ticket_day (issued_on, ticket_no),
                  INDEX idx_queue_status (issued_on, status)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS score_records (
                  id         INT AUTO_INCREMENT PRIMARY KEY,
                  nickname   VARCHAR(20) NOT NULL DEFAULT '익명',
                  title      VARCHAR(100) NOT NULL,
                  singer     VARCHAR(100) NOT NULL,
                  score      INT NOT NULL,
                  rank_label VARCHAR(20),
                  pitch      INT,
                  timing     INT,
                  volume     INT,
                  expression INT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_score (score DESC),
                  INDEX idx_created (created_at DESC)
                );
            """)

        # 9. 시드 데이터 등록 (MySQL/PostgreSQL 공용)
        _seed_initial_rows()

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
        # execute()의 반환값은 드라이버마다 다르다 (pymysql: 행 수, psycopg: 커서).
        # 두 드라이버 모두에서 같은 뜻인 rowcount 를 쓴다.
        cursor.execute(
            """
            UPDATE devices
            SET desired_state = %s, desired_value = %s
            WHERE id = %s
            """,
            (desired_state, serialized_val, device_id)
        )
        return cursor.rowcount > 0


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
        cursor.execute(
            """
            UPDATE devices
            SET current_state = %s, current_value = %s
            WHERE id = %s
            """,
            (current_state, serialized_val, device_id)
        )
        return cursor.rowcount > 0


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
            """ + (" RETURNING id" if IS_POSTGRES else ""),
            (grade, department, student_name, user_count, reservation_date, time_slot, pin_code)
        )
        # cursor.lastrowid는 MySQL 전용이라 PostgreSQL에서는 RETURNING으로 받는다
        new_id = cursor.fetchone()["id"] if IS_POSTGRES else cursor.lastrowid
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


def get_reservations_by_pin(pin_code: str) -> List[Dict[str, Any]]:
    """
    4자리 PIN 코드로 **아직 사용하지 않은** 예약을 모두 찾습니다.

    PIN은 일회성이므로 status='reserved'인 예약만 찾는다.
    인증에 성공하면 곧바로 'active'로 바뀌므로 같은 PIN을 다시 넣어도
    여기서 걸리지 않아 재사용이 차단된다.

    한 건이 아니라 목록을 돌려주는 이유: 날짜가 다른 두 예약이 우연히 같은
    PIN을 받았다면, 그중 **지금 이용 시간인 예약**을 골라야 하기 때문이다
    (고르는 일은 BoothService 가 한다).
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM reservations
            WHERE pin_code = %s AND status = 'reserved'
            ORDER BY reservation_date ASC, id ASC
            """,
            (pin_code,)
        )
        return [_format_row(r) for r in (cursor.fetchall() or [])]  # type: ignore


def get_reservations_on(reservation_date: str) -> List[Dict[str, Any]]:
    """그날의 예약만 조회합니다 (스케줄러가 씁니다).

    get_reservations() 는 최근 50건만 돌려주므로, 몇 주 뒤 예약이 많이 쌓이면
    정작 오늘 예약이 목록에서 잘려 자동 종료·노쇼 처리가 빠질 수 있다.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM reservations WHERE reservation_date = %s ORDER BY time_slot ASC",
            (reservation_date,),
        )
        return [_format_row(r) for r in (cursor.fetchall() or [])]  # type: ignore


def find_live_reservation(reservation_date: str, time_slot: str) -> Optional[Dict[str, Any]]:
    """같은 날짜·시간대에 살아 있는(예약됨/이용 중) 예약이 있으면 돌려줍니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM reservations
            WHERE reservation_date = %s AND time_slot = %s
              AND status IN ('reserved', 'active')
            LIMIT 1
            """,
            (reservation_date, time_slot),
        )
        return _format_row(cursor.fetchone())


def update_reservation_status(reservation_id: int, status: str) -> bool:
    """예약 상태를 갱신합니다 ('active', 'completed', 'cancelled')"""
    with get_db_cursor() as cursor:
        cursor.execute(
            "UPDATE reservations SET status = %s WHERE id = %s",
            (status, reservation_id)
        )
        return cursor.rowcount > 0


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
            """ + _upsert_clause(
                "title, singer",
                {"sing_count": "song_history.sing_count + 1"}
            ),
            (title, singer)
        )
        cursor.execute(
            "SELECT * FROM song_history WHERE title = %s AND singer = %s",
            (title, singer)
        )
        row = cursor.fetchone()
        return _format_row(row) or {}


# ==============================================================================
# 전시 체험 대기열 (부록G §2-③)
#
# 전시장 관람객에게는 예약 PIN이 없다. QR을 찍어 그 자리에서 체험권을 받고,
# 차례가 오면 그 체험권의 PIN으로 부스에 들어간다.
#
# 번호는 날마다 1부터 다시 센다 — 전시 둘째 날에 137번이 불리면 이상하다.
# ==============================================================================

def issue_queue_ticket(nickname: str, pin_code: str, issued_on: str) -> Dict[str, Any]:
    """체험권을 발급하고 그날의 다음 대기 번호를 매깁니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(MAX(ticket_no), 0) AS last_no FROM queue_tickets WHERE issued_on = %s",
            (issued_on,),
        )
        row = cursor.fetchone() or {}
        next_no = int(row.get("last_no") or 0) + 1

        cursor.execute(
            """
            INSERT INTO queue_tickets (ticket_no, issued_on, nickname, pin_code, status)
            VALUES (%s, %s, %s, %s, 'waiting')
            """ + (" RETURNING id" if IS_POSTGRES else ""),
            (next_no, issued_on, nickname, pin_code),
        )
        new_id = cursor.fetchone()["id"] if IS_POSTGRES else cursor.lastrowid

        cursor.execute("SELECT * FROM queue_tickets WHERE id = %s", (new_id,))
        return _format_row(cursor.fetchone()) or {}


def get_queue_tickets(issued_on: str, statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """그날의 체험권 목록 (번호 순)."""
    sql = "SELECT * FROM queue_tickets WHERE issued_on = %s"
    params: List[Any] = [issued_on]
    if statuses:
        sql += " AND status IN (" + ", ".join(["%s"] * len(statuses)) + ")"
        params.extend(statuses)
    sql += " ORDER BY ticket_no ASC"

    with get_db_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return [_format_row(r) for r in (cursor.fetchall() or [])]


def get_queue_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    """체험권 한 장 (관람객 폰이 자기 순번을 확인할 때)."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM queue_tickets WHERE id = %s", (ticket_id,))
        return _format_row(cursor.fetchone())


def get_called_ticket_by_pin(pin_code: str) -> Optional[Dict[str, Any]]:
    """
    PIN으로 체험권을 찾습니다.

    status='called' 인 것만 찾는다 — 차례가 오지 않은 사람의 PIN으로는 문이 열리면
    안 된다. 예약 PIN을 'reserved' 로 제한하는 것과 같은 이유다.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM queue_tickets WHERE pin_code = %s AND status = 'called' "
            "ORDER BY ticket_no ASC LIMIT 1",
            (pin_code,),
        )
        return _format_row(cursor.fetchone())


def update_ticket_status(ticket_id: int, status: str) -> bool:
    """
    체험권 상태를 바꾸고 해당 시각을 함께 기록합니다.
    called → called_at, active → started_at, done/expired → ended_at
    """
    stamp = {"called": "called_at", "active": "started_at"}.get(status)
    if status in ("done", "expired"):
        stamp = "ended_at"

    now_fn = "NOW()" if IS_POSTGRES else "CURRENT_TIMESTAMP"
    extra = f", {stamp} = {now_fn}" if stamp else ""

    with get_db_cursor() as cursor:
        cursor.execute(
            f"UPDATE queue_tickets SET status = %s{extra} WHERE id = %s",
            (status, ticket_id),
        )
        return cursor.rowcount > 0


def pins_in_use(issued_on: str) -> List[str]:
    """지금 살아 있는 PIN 목록 — 새 체험권 번호가 겹치지 않게 하려고 본다."""
    used: List[str] = []
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT pin_code FROM queue_tickets WHERE issued_on = %s "
            "AND status IN ('waiting', 'called', 'active')",
            (issued_on,),
        )
        used.extend(str(r["pin_code"]) for r in (cursor.fetchall() or []))
        cursor.execute("SELECT pin_code FROM reservations WHERE status IN ('reserved', 'active')")
        used.extend(str(r["pin_code"]) for r in (cursor.fetchall() or []))
    return used


# ==============================================================================
# 점수 기록과 랭킹 (부록G §2-④)
#
# song_history 는 "어떤 곡을 몇 번 불렀나"의 누적이고, 여기는 "누가 언제 몇 점을
# 받았나"의 낱개 기록이다. 질문이 다르므로 테이블도 따로 둔다.
#
# 다른 조회 함수와 마찬가지로, DB가 꺼져 있어도 부스 화면은 떠야 하므로
# 호출하는 쪽에서 빈 목록으로 degrade 한다.
# ==============================================================================

def record_score(
    nickname: str,
    title: str,
    singer: str,
    score: int,
    rank_label: Optional[str] = None,
    pitch: Optional[int] = None,
    timing: Optional[int] = None,
    volume: Optional[int] = None,
    expression: Optional[int] = None,
) -> Dict[str, Any]:
    """한 번의 채점 결과를 남깁니다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO score_records
              (nickname, title, singer, score, rank_label, pitch, timing, volume, expression)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """ + (" RETURNING id" if IS_POSTGRES else ""),
            (nickname, title, singer, score, rank_label, pitch, timing, volume, expression),
        )
        new_id = cursor.fetchone()["id"] if IS_POSTGRES else cursor.lastrowid

        cursor.execute("SELECT * FROM score_records WHERE id = %s", (new_id,))
        return _format_row(cursor.fetchone()) or {}


def get_top_scores(period: str = "today", limit: int = 5) -> List[Dict[str, Any]]:
    """
    점수 순위.

    period="today" 는 오늘 기록만 본다 — 전시장에서는 "오늘의 1등"이라야
    관람객이 순위를 깨러 다시 온다. "all" 은 명예의 전당이다.
    """
    # "오늘"은 부스 시간 기준이다. DB의 CURDATE()/CURRENT_DATE 는 UTC 날짜라
    # 한국에서는 오전 9시에야 하루가 바뀐다. 그래서 부스 기준 하루를 UTC 구간으로
    # 바꿔서 자른다 — 두 DB 모두 같은 문법으로 쓸 수 있다는 장점도 있다.
    where, params = "", []
    if period == "today":
        start, end = today_utc_range()
        if not IS_POSTGRES:
            # MySQL DATETIME 에는 시간대가 없다 (세션을 UTC로 맞춰 두었다)
            start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)
        where, params = "WHERE created_at >= %s AND created_at < %s", [start, end]

    with get_db_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT * FROM score_records
            {where}
            ORDER BY score DESC, created_at ASC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )
        return [_format_row(r) for r in (cursor.fetchall() or [])]


def get_recent_scores(limit: int = 10) -> List[Dict[str, Any]]:
    """최근 기록 순 — 어트랙트 화면에서 '방금 이 점수가 나왔다'를 보여 줄 때 쓴다."""
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM score_records ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        return [_format_row(r) for r in (cursor.fetchall() or [])]


# ==============================================================================
# 노래방 영상 등록 (F-06)
#
# 곡별 기본 후보 목록은 프론트엔드 코드(data/karaokeSongs.ts)에 있다.
# 이 테이블은 그 위에 덮어쓰는 "관리자가 직접 지정한 영상"만 담는다.
# 브라우저 localStorage가 아니라 서버에 두는 이유는, 부스 화면·관람객 폰·
# 관리자 노트북이 모두 같은 영상을 보게 하기 위해서다.
# ==============================================================================

def get_song_videos() -> Dict[str, str]:
    """등록된 곡별 영상 ID를 {song_id: video_id} 형태로 반환합니다."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT song_id, video_id FROM song_videos")
        rows = cursor.fetchall() or []
        return {row["song_id"]: row["video_id"] for row in rows}


def set_song_video(song_id: str, video_id: str) -> Dict[str, Any]:
    """곡의 영상 ID를 등록하거나 갱신합니다."""
    query = """
        INSERT INTO song_videos (song_id, video_id)
        VALUES (%s, %s)
    """ + _upsert_clause("song_id", {"video_id": "EXCLUDED.video_id"})

    with get_db_cursor() as cursor:
        cursor.execute(query, (song_id, video_id))
    return {"song_id": song_id, "video_id": video_id}


def delete_song_video(song_id: str) -> bool:
    """등록된 영상을 지웁니다 (곡의 기본 후보 목록으로 되돌아간다)."""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM song_videos WHERE song_id = %s", (song_id,))
    return True
