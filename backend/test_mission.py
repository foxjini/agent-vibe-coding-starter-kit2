"""
기상 미션 엔진 단위 테스트 (test_mission.py)
=============================================================================
가위바위보 미션 판정 로직만 따로 떼어내 확인하는 스크립트입니다.
백엔드 서버도, DB도, 웹캠도 필요 없습니다.

실행 방법 (backend 폴더에서, 가상환경 활성화 후):
    python test_mission.py

미션 규칙을 바꾼 뒤(예: 필요 승수, 제한 시간) 이 스크립트를 돌려서
규칙이 여전히 의도대로 동작하는지 확인하세요.
"""
import asyncio, os, sys, warnings
warnings.filterwarnings("ignore")
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.environ["MISSION_ROUND_GRACE_SECONDS"] = "0"
os.environ["MISSION_EVENT_DEBOUNCE_SECONDS"] = "0"
os.environ["MISSION_ROUND_TIMEOUT_SECONDS"] = "3"
os.environ["MISSION_REQUIRED_WINS"] = "3"

import importlib
ts = importlib.import_module("services.trigger_service")

# 부저 제어와 WS 브로드캐스트를 가짜로 대체 (미션 판정 로직만 검증)
sent = []
async def fake_set_actuator(*a, **k): return {"id": "buzzer_1", "desired_state": a[1] if len(a) > 1 else "off"}
async def fake_broadcast(msg): sent.append(msg)
ts.set_actuator = fake_set_actuator
ts.ws_manager.broadcast = fake_broadcast

BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}  # key가 value를 이긴다
WINS_AGAINST = {v: k for k, v in BEATS.items()}  # ai -> 이기는 손
LOSES_TO = dict(BEATS)                           # ai -> 지는 손 (ai가 이기는 손)

async def main():
    svc = ts.TriggerService()
    fails = []

    def check(label, cond, extra=""):
        print(("  [PASS] " if cond else "  [FAIL] ") + label + ("" if cond else f" — {extra}"))
        if not cond: fails.append(label)

    # --- 1) 라운드 전환 시 AI 손패가 연속으로 같지 않은지 (30회) ---
    await svc.start_mission("test")
    hands = [svc._session.ai_hand]
    for _ in range(30):
        async with svc._lock:
            await svc._begin_round()
        hands.append(svc._session.ai_hand)
    repeats = [i for i in range(1, len(hands)) if hands[i] == hands[i-1]]
    check("라운드 전환 시 AI 손패가 연속 반복되지 않음", not repeats, f"반복 위치={repeats}")
    check("AI 손패가 3종을 모두 사용", len(set(hands)) == 3, str(set(hands)))

    # --- 2) 이기는 손 -> 승수 증가 & 라운드 전진 ---
    svc2 = ts.TriggerService()
    await svc2.start_mission("test")
    for i in range(1, 4):
        s = svc2._session
        if s is None: break
        expected, before_round, before_wins = s.expected_hand, s.round_index, s.wins
        await svc2.handle_vision_event("gesture_detected", True, 1, 0.9, expected)
        if svc2._session:
            check(f"{i}번째 승리 후 승수 증가", svc2._session.wins == before_wins + 1,
                  f"{before_wins} -> {svc2._session.wins}")
            check(f"{i}번째 승리 후 새 라운드 시작", svc2._session.round_index == before_round + 1,
                  f"{before_round} -> {svc2._session.round_index}")
    check("3승 후 미션 종료", svc2._session is None, str(svc2.get_mission_status()))
    check("미션 성공 메시지 브로드캐스트", any(m["type"] == "mission_success" for m in sent))

    # --- 3) 지는 손 -> 승수 유지 & 재시도 ---
    svc3 = ts.TriggerService()
    await svc3.start_mission("test")
    s = svc3._session
    losing = LOSES_TO[s.ai_hand]
    before_round, before_wins = s.round_index, s.wins
    await svc3.handle_vision_event("gesture_detected", True, 1, 0.9, losing)
    check("오답 시 승수 유지", svc3._session.wins == before_wins)
    check("오답 시 재시도 라운드 시작", svc3._session.round_index == before_round + 1)

    # --- 4) 비긴 경우도 재시도 ---
    s = svc3._session
    before_round = s.round_index
    await svc3.handle_vision_event("gesture_detected", True, 1, 0.9, s.ai_hand)
    check("무승부 시 재시도", svc3._session.round_index == before_round + 1)

    # --- 5) 신뢰도 미달은 무시 ---
    s = svc3._session
    before_round = s.round_index
    await svc3.handle_vision_event("gesture_detected", True, 1, 0.2, s.expected_hand)
    check("신뢰도 미달 이벤트는 판정하지 않음", svc3._session.round_index == before_round)

    # --- 6) 시간 초과 시 자동 재시도 ---
    svc4 = ts.TriggerService()
    await svc4.start_mission("test")
    before_round = svc4._session.round_index
    await asyncio.sleep(3.4)
    check("시간 초과 시 자동 재시도", svc4._session and svc4._session.round_index == before_round + 1,
          str(svc4.get_mission_status()))
    check("시간 초과 결과가 브로드캐스트됨",
          any(m.get("type") == "mission_result" and m.get("result") == "timeout" for m in sent))
    await svc4.cancel_mission("test_end")

    # --- 7) 라운드 직후 유예: 직전 손이 재전송돼도 오답 처리하지 않음 ---
    os.environ["MISSION_ROUND_GRACE_SECONDS"] = "2"
    svc5 = ts.TriggerService()
    await svc5.start_mission("test")
    s = svc5._session
    before_round = s.round_index
    await svc5.handle_vision_event("gesture_detected", True, 1, 0.9, WINS_AGAINST[s.ai_hand])
    check("유예 시간 안의 이벤트는 무시됨(직전 손 재전송 보호)",
          svc5._session.round_index == before_round and svc5._session.wins == 0)
    await svc5.cancel_mission("test_end")

    # --- 8) 사물 미션: 연속 감지 횟수를 채워야 통과 ---
    os.environ["MISSION_ROUND_GRACE_SECONDS"] = "0"
    os.environ["MISSION_OBJECT_REQUIRED_HITS"] = "2"
    svc6 = ts.TriggerService()
    await svc6.start_mission("test")
    before_wins = svc6._session.wins
    await svc6.handle_vision_event("object_detected", True, 1, 0.9, "person")
    check("사물 1회 감지로는 통과하지 않음", svc6._session.wins == before_wins)
    await svc6.handle_vision_event("object_detected", True, 1, 0.9, "person")
    check("사물 2회 연속 감지로 라운드 통과", svc6._session.wins == before_wins + 1)
    before_wins = svc6._session.wins
    await svc6.handle_vision_event("object_detected", True, 1, 0.9, "airplane")
    check("미지정 사물은 통과시키지 않음", svc6._session.wins == before_wins)
    await svc6.cancel_mission("test_end")

    print(f"\n결과: 성공 {18 - len(fails)}건 / 실패 {len(fails)}건")
    return 1 if fails else 0

sys.exit(asyncio.run(main()))
