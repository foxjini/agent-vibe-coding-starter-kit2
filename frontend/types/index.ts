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
  /** 신청 응답과 관리자 화면에만 실린다 — 공개 목록에서는 서버가 뺀다 */
  pin_code?: string;
  status: "reserved" | "active" | "completed" | "cancelled" | "no_show" | string;
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
  // queue_called / queue_updated (부록G §2-③)
  ticket_no?: number;
  success?: boolean;
  /** 부스 화면이 소리 내어 읽을 안내 문장 (파이 스피커와 같은 문장) */
  speech?: string;
  /** 키패드 인증 실패 이유 — invalid(틀림) / not_now(예약 시간 아님) */
  reason?: string;
  timestamp?: string;
  created_at?: string;
}

/** 지금 부스를 쓰는 사람 — GET /api/booth/session (부스 화면 표시용) */
export interface BoothSession {
  /** reservation(예약) · experience(전시 체험) · null(관리자가 직접 켰거나 비어 있음) */
  kind: "reservation" | "experience" | null;
  user_name?: string;
  /** 순위에 올릴 이름의 기본값 */
  nickname?: string;
  /** 끝나는 시각 (부스 시간대, 예: 2026-10-06T13:20+09:00) */
  ends_at?: string;
  /** 서버 시계로 잰 남은 시간(초) — 부스 PC 시계가 틀려도 맞게 나온다 */
  remaining_sec?: number;
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

/** 전시 체험권 한 장 (부록G §2-③) */
export interface QueueTicket {
  id: number;
  ticket_no: number;
  issued_on?: string;
  nickname: string;
  /** 발급 직후, 또는 자기 비밀번호를 같이 보낸 조회에서만 내려온다 */
  pin_code?: string;
  status: "waiting" | "called" | "active" | "done" | "expired" | string;
  issued_at?: string | null;
  called_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  /** 앞에 남은 사람 수 (0이면 내 차례) */
  position?: number;
  estimated_wait_min?: number;
}

/** 대기열 현황 — 부스 화면·관람객 폰·관리자 화면이 같은 것을 본다 */
export interface QueueSnapshot {
  enabled: boolean;
  /** 예약한 학생의 이용 시간이라 잠시 부르지 않을 때 그 이유 */
  paused_reason?: string | null;
  experience_minutes: number;
  call_grace_minutes: number;
  now?: string;
  now_serving: { id: number; ticket_no: number; nickname: string; status: string } | null;
  waiting_count: number;
  waiting: { id: number; ticket_no: number; nickname: string }[];
  estimated_wait_min: number;
}
