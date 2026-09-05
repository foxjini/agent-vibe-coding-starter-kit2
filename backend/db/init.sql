-- MySQL-only (db-migration 스킬에서 Supabase 전환 시 이 두 줄은 제거한다)
CREATE DATABASE IF NOT EXISTS smart_control
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_control;

-- 1. 디바이스 메타데이터 및 목표/현재 상태 관리 테이블
CREATE TABLE IF NOT EXISTS devices (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  kind VARCHAR(30) NOT NULL,
  desired_state VARCHAR(30) NULL,   -- 대시보드/트리거가 지정한 목표 상태
  current_state VARCHAR(30) NULL,   -- 파이(또는 Mock)가 보고한 실제 상태
  desired_value JSON NULL,          -- on/off로 안 되는 값 (부저 주파수, 볼륨 등)
  current_value JSON NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 센서 측정치 기록 테이블
CREATE TABLE IF NOT EXISTS sensor_readings (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  value FLOAT NULL,
  unit VARCHAR(20) NULL,
  value_json JSON NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- 3. 디바이스 제어 이력 로그 테이블
CREATE TABLE IF NOT EXISTS control_log (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  action VARCHAR(50) NOT NULL,
  value JSON NULL,
  actor VARCHAR(50) NOT NULL, -- 'user' or 'device' or 'system' or 'trigger'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);


-- 4. 영상인식 이벤트 로그 테이블
CREATE TABLE IF NOT EXISTS vision_events (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  event_type VARCHAR(50) NOT NULL,
  detected BOOLEAN NOT NULL,
  count INT DEFAULT 0,
  confidence FLOAT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 시드 데이터 (AGENTS.md 팀 정보: 스마트 기상 시스템 센서 및 액추에이터)
-- 주의: 시드 INSERT에는 desired_state/current_state를 넣지 않는다 (재실행 시 상태 보존)
-- ==============================================================================
INSERT INTO devices (id, name, kind) VALUES
  ('buzzer_1', '알람 출력 장치(피에조 부저)', 'buzzer'),
  ('touch_pad_1', '패드 화면/터치 입력', 'touch_pad'),
  ('camera_1', '기상 감지 카메라', 'camera')
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  kind = VALUES(kind);
