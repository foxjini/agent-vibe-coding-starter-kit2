-- ==============================================================================
-- Supabase (PostgreSQL) 초기 스키마
-- 프로젝트: 웹 예약 연동 자동화 학교 노래방 부스 관리 시스템
--
-- 사용법: Supabase 대시보드 → SQL Editor → 이 파일 전체를 붙여넣고 Run
--         (로컬 MariaDB용은 init.sql, 이 파일은 클라우드 배포용)
--
-- init.sql과 테이블·컬럼 이름이 같아야 백엔드 코드가 그대로 돌아간다.
-- 바꿀 일이 생기면 두 파일을 함께 고칠 것.
-- ==============================================================================

-- 1. 디바이스 테이블 (상태 동기화 및 메타데이터)
CREATE TABLE IF NOT EXISTS devices (
  id            VARCHAR(50) PRIMARY KEY,
  name          VARCHAR(100) NOT NULL,
  kind          VARCHAR(30)  NOT NULL,
  desired_state VARCHAR(30),              -- 대시보드/트리거가 지정한 목표 상태
  current_state VARCHAR(30),              -- 파이(또는 Mock)가 보고한 실제 상태
  desired_value JSONB,                    -- on/off로 안 되는 값 (밝기 등)
  current_value JSONB,
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 센서 측정값
CREATE TABLE IF NOT EXISTS sensor_readings (
  id         SERIAL PRIMARY KEY,
  device_id  VARCHAR(50) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  value      DOUBLE PRECISION,
  unit       VARCHAR(30),
  value_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 제어 이력
CREATE TABLE IF NOT EXISTS control_log (
  id         SERIAL PRIMARY KEY,
  device_id  VARCHAR(50) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  action     VARCHAR(50) NOT NULL,
  value      JSONB,
  actor      VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 영상인식 이벤트
CREATE TABLE IF NOT EXISTS vision_events (
  id         SERIAL PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,
  detected   BOOLEAN NOT NULL DEFAULT FALSE,
  count      INTEGER DEFAULT 0,
  confidence REAL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 예약 (F-01, F-02)
--    같은 날짜의 같은 시간대는 한 팀만 — UNIQUE 제약으로 중복 예약을 막는다
CREATE TABLE IF NOT EXISTS reservations (
  id               SERIAL PRIMARY KEY,
  grade            INTEGER NOT NULL,
  department       VARCHAR(50) NOT NULL,
  student_name     VARCHAR(50) NOT NULL,
  user_count       INTEGER NOT NULL DEFAULT 1,
  reservation_date DATE NOT NULL,
  time_slot        VARCHAR(20) NOT NULL,
  pin_code         VARCHAR(4)  NOT NULL,
  status           VARCHAR(20) NOT NULL DEFAULT 'reserved',
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_date_slot UNIQUE (reservation_date, time_slot)
);

-- 6. 노래 기록 및 나의 18번 (F-05)
CREATE TABLE IF NOT EXISTS song_history (
  id           SERIAL PRIMARY KEY,
  title        VARCHAR(100) NOT NULL,
  singer       VARCHAR(100) NOT NULL,
  sing_count   INTEGER NOT NULL DEFAULT 1,
  last_sung_at TIMESTAMPTZ DEFAULT NOW(),
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_title_singer UNIQUE (title, singer)
);

-- ==============================================================================
-- MySQL의 ON UPDATE CURRENT_TIMESTAMP 대체
-- PostgreSQL에는 같은 기능이 없어 트리거로 만든다.
-- ==============================================================================
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_devices_updated_at ON devices;
CREATE TRIGGER trg_devices_updated_at
  BEFORE UPDATE ON devices
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE OR REPLACE FUNCTION touch_last_sung_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.last_sung_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_song_last_sung_at ON song_history;
CREATE TRIGGER trg_song_last_sung_at
  BEFORE UPDATE ON song_history
  FOR EACH ROW EXECUTE FUNCTION touch_last_sung_at();

-- 7. 노래방 영상 등록 (F-06)
--    곡별 기본 후보는 프론트엔드 코드에 있고, 이 테이블은 관리자가 직접 지정한
--    영상만 담는다. 모든 기기가 같은 영상을 보게 하려고 서버에 저장한다.
CREATE TABLE IF NOT EXISTS song_videos (
  song_id    VARCHAR(64) PRIMARY KEY,
  video_id   VARCHAR(32) NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_song_videos_updated_at ON song_videos;
CREATE TRIGGER trg_song_videos_updated_at
  BEFORE UPDATE ON song_videos
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ==============================================================================
-- 시드 데이터
-- 백엔드가 시작할 때도 같은 내용을 UPSERT하므로 여기서 빠뜨려도 채워진다.
-- ==============================================================================
INSERT INTO devices (id, name, kind) VALUES
  ('door_lock_1', '솔레노이드 도어락',   'door_lock'),
  ('relay_1',     '기기 전원 릴레이',     'relay'),
  ('led_1',       '부스 조명 LED',        'led'),
  ('speaker_1',   '스피커/오디오 모듈',   'speaker'),
  ('keypad_1',    '4x4 비밀번호 키패드',  'keypad'),
  ('pir_1',       '입장 감지 센서',       'pir')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  kind = EXCLUDED.kind;

INSERT INTO song_history (title, singer, sing_count) VALUES
  ('다시 만나',                     '더윈드',   5),
  ('첫 만남은 계획대로 되지 않아',  'TWS',      4),
  ('Supernova',                     'aespa',    3),
  ('Love wins all',                 '아이유',   2),
  ('Hype Boy',                      'NewJeans', 1)
ON CONFLICT (title, singer) DO UPDATE SET
  sing_count = EXCLUDED.sing_count;

-- ==============================================================================
-- ⚠️ RLS(Row Level Security) 안내
--
-- 백엔드(Render)는 service_role 키로 붙으므로 RLS를 우회한다.
-- 하지만 프론트엔드에서 anon 키로 직접 테이블을 읽는 코드를 나중에 추가한다면,
-- 반드시 RLS를 켜고 정책을 만들어야 한다. 켜지 않으면 예약자 이름·PIN이
-- 브라우저에서 그대로 조회된다.
--
-- 지금 구조(프론트 → 백엔드 REST → DB)에서는 프론트가 DB에 직접 붙지 않으므로
-- 아래를 켜 두는 편이 안전하다.
-- ==============================================================================
ALTER TABLE devices        ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_log    ENABLE ROW LEVEL SECURITY;
ALTER TABLE vision_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE song_history   ENABLE ROW LEVEL SECURITY;
ALTER TABLE song_videos    ENABLE ROW LEVEL SECURITY;
