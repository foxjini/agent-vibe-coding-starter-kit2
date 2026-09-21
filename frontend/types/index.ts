export interface Device {
  id: string;
  name: string;
  kind: "door_lock" | "relay" | "led" | "speaker" | "keypad" | "pir" | string;
  desired_state: string | null;
  current_state: string | null;
  desired_value: unknown;
  current_value: unknown;
  updated_at: string | null;
  created_at?: string;
}

export interface Reservation {
  id: number;
  grade: number;
  department: string;
  student_name: string;
  user_count: number;
  reservation_date: string;
  time_slot: "lunch" | "dinner" | string;
  pin_code: string;
  status: "reserved" | "active" | "completed" | "cancelled" | string;
  created_at: string;
}

export interface Song {
  id: number;
  title: string;
  singer: string;
  sing_count: number;
  last_sung_at: string;
}

export interface WebSocketMessage {
  type: string;
  device_id?: string;
  kind?: string;
  state?: string;
  value?: unknown;
  actor?: string;
  mode?: string;
  user_name?: string;
  message?: string;
  event?: string;
  event_type?: string;
  detected?: boolean;
  count?: number;
  confidence?: number;
  // score_recorded (부록G §2-④)
  nickname?: string;
  title?: string;
  score?: number;
  success?: boolean;
  timestamp?: string;
  created_at?: string;
}

/** 채점 결과 한 건 (부록G §2-④ 점수 저장 + 실시간 랭킹) */
export interface ScoreRecord {
  id: number;
  nickname: string;
  title: string;
  singer: string;
  score: number;
  rank_label?: string | null;
  pitch?: number | null;
  timing?: number | null;
  volume?: number | null;
  expression?: number | null;
  created_at?: string | null;
}
