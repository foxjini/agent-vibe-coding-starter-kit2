-- ==============================================================================
-- Smart Control Database Initialization Script (MySQL / MariaDB)
-- 프로젝트: 웹 예약 연동 자동화 학교 노래방 부스 관리 시스템
-- ==============================================================================

-- MySQL-only (db-migration 스킬에서 Supabase 전환 시 이 두 줄은 제거한다)
CREATE DATABASE IF NOT EXISTS smart_control
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_control;

-- 이 스크립트를 파이프로 넣을 때(mysql < init.sql) 클라이언트 기본 문자셋이
-- latin1/cp949면 아래 시드 데이터의 한글이 깨져서 저장된다.
-- 접속 문자셋을 스크립트 안에서 직접 못박아 실행 환경과 무관하게 만든다.
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 1. 디바이스 테이블 (상태 동기화 및 메타데이터)
CREATE TABLE IF NOT EXISTS devices (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  kind VARCHAR(30) NOT NULL,
  desired_state VARCHAR(30) NULL,   -- 대시보드/트리거가 지정한 목표 상태
  current_state VARCHAR(30) NULL,   -- 파이(또는 Mock)가 보고한 실제 상태
  desired_value JSON NULL,          -- on/off로 안 되는 값 (서보 각도, LED 밝기 등)
  current_value JSON NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 센서 측정치 기록 테이블
CREATE TABLE IF NOT EXISTS sensor_readings (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  value DOUBLE NULL,
  unit VARCHAR(30) NULL,
  value_json JSON NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- 3. 제어 이력 로그 테이블 (actor: 'user' 또는 'device')
CREATE TABLE IF NOT EXISTS control_log (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  action VARCHAR(50) NOT NULL,
  value JSON NULL,
  actor VARCHAR(20) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- 4. 비전 감지 이벤트 테이블
CREATE TABLE IF NOT EXISTS vision_events (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  event_type VARCHAR(50) NOT NULL,
  detected BOOLEAN NOT NULL DEFAULT FALSE,
  count INT DEFAULT 0,
  confidence FLOAT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. 노래방 예약 테이블 (F-01, F-02: 당일 예약 불가, 중복 방지, 4자리 일회성 PIN)
CREATE TABLE IF NOT EXISTS reservations (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  grade INT NOT NULL,                  -- 학년 (1, 2, 3)
  department VARCHAR(50) NOT NULL,     -- 학과 (정보통신과 등)
  student_name VARCHAR(50) NOT NULL,   -- 신청자 이름
  user_count INT NOT NULL DEFAULT 1,   -- 인원수 (최대 10명)
  reservation_date DATE NOT NULL,      -- 예약 일자
  time_slot VARCHAR(20) NOT NULL,      -- 타임슬롯 ('lunch', 'dinner')
  pin_code VARCHAR(4) NOT NULL,        -- 일회성 4자리 비밀번호
  status VARCHAR(20) NOT NULL DEFAULT 'reserved', -- 'reserved', 'active', 'completed', 'cancelled'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_date_slot (reservation_date, time_slot) -- 동일 날짜/시간대 중복 예약 차단
);

-- 6. 노래 기록 및 나의 18번 관리 테이블 (F-05)
CREATE TABLE IF NOT EXISTS song_history (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  title VARCHAR(100) NOT NULL,
  singer VARCHAR(100) NOT NULL,
  sing_count INT NOT NULL DEFAULT 1,
  last_sung_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_title_singer (title, singer)
);

-- ==============================================================================
-- 시드 데이터 (AGENTS.md 팀 정보 기준 디바이스 등록)
-- 재실행해도 기존 상태값을 덮어쓰지 않도록 desired_state/current_state는 제외

-- 7. 노래방 영상 등록 (F-06)
--    곡마다 기본 후보 목록은 프론트엔드 코드에 있고, 이 테이블은 그 위에 덮어쓰는
--    "관리자가 직접 지정한 영상"만 담는다. 부스 화면·관람객 폰·관리자 노트북이
--    같은 영상을 보게 하려고 브라우저가 아닌 서버에 저장한다.
CREATE TABLE IF NOT EXISTS song_videos (
  song_id    VARCHAR(64) PRIMARY KEY,
  video_id   VARCHAR(32) NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
INSERT INTO devices (id, name, kind) VALUES
  -- 액추에이터 목록
  ('door_lock_1', '솔레노이드 도어락', 'door_lock'),
  ('relay_1', '기기 전원 릴레이', 'relay'),
  ('led_1', '부스 조명 LED', 'led'),
  ('speaker_1', '스피커/오디오 모듈', 'speaker'),
  -- 센서 목록
  ('keypad_1', '4x4 비밀번호 키패드', 'keypad'),
  ('pir_1', '입장 감지 센서', 'pir')
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  kind = VALUES(kind);

-- 노래 기록 초기 시드 데이터 (나의 18번 3회 이상 곡 포함)
INSERT INTO song_history (title, singer, sing_count) VALUES
  ('다시 만나', '더윈드', 5),
  ('첫 만남은 계획대로 되지 않아', 'TWS', 4),
  ('Supernova', 'aespa', 3),
  ('Love wins all', '아이유', 2),
  ('Hype Boy', 'NewJeans', 1)
ON DUPLICATE KEY UPDATE
  sing_count = VALUES(sing_count);

