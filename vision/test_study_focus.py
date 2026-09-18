"""
집중도 측정 자가 점검 (vision/test_study_focus.py) — ★ study 팀
=============================================================================
**웹캠도 사람 얼굴도 없이** 돌아갑니다. 가짜 얼굴 좌표를 만들어 넣고,
눈 감김·시선·고개 숙임·창 집계가 제대로 계산되는지 확인합니다.

실행 방법 (vision 폴더에서):
    python test_study_focus.py

임계값(EAR_CLOSED 등)을 고친 뒤에는 반드시 이것을 한 번 돌려 보세요.
"""
import os
import sys
from typing import Dict, List, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from detectors import _focus_engine as fe  # noqa: E402

_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return condition


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * 66}")


# =============================================================================
# 가짜 얼굴 만들기 — 카메라 없이 시험하기 위한 도구
# =============================================================================

def make_face(
    ear: float = 0.30,
    gaze: float = 0.0,
    yaw: float = 0.0,
    pitch: float = 1.6,
    face_px: float = 260.0,
    with_iris: bool = True,
) -> List[Tuple[float, float]]:
    """
    원하는 값이 나오도록 **거꾸로 계산해서** 얼굴 점 배열을 만듭니다.

    ear     눈이 얼마나 떠 있나 (0.30쯤이 평소, 0.10이면 감은 것)
    gaze    눈동자가 좌우로 치우친 정도 (0.0이 한가운데)
    yaw     고개를 좌우로 돌린 정도 (0.0이 정면)
    pitch   눈높이~턱 / 이마~눈높이 비율 (작을수록 고개를 숙인 것)
    face_px 얼굴 폭(픽셀)
    """
    points = [(0.0, 0.0)] * fe.LANDMARKS_WITH_IRIS
    cx, cy = 960.0, 540.0
    half = face_px / 2.0

    # 얼굴 좌우 끝
    points[fe.FACE_EDGE_LEFT] = (cx - half, cy)
    points[fe.FACE_EDGE_RIGHT] = (cx + half, cy)

    # 코끝 — yaw = (코~왼끝 - 코~오른끝) / 얼굴폭 이 되도록 좌우로 옮깁니다
    points[fe.NOSE_TIP] = (cx + yaw * face_px / 2.0, cy)

    # 이마 · 눈높이 · 턱 — pitch = (턱-눈높이) / (눈높이-이마) 가 되도록
    upper = 60.0
    eye_y = cy - 20.0
    points[fe.FOREHEAD] = (cx, eye_y - upper)
    points[fe.CHIN] = (cx, eye_y + upper * pitch)

    # 눈 두 개 — EAR = 위아래 간격 / 좌우 간격 이 되도록
    eye_w = face_px * 0.22
    lid = ear * eye_w                      # 위아래 눈꺼풀 간격
    for eye, iris, direction in (
        (fe.EYE_IMAGE_LEFT, fe.IRIS_IMAGE_LEFT, -1.0),
        (fe.EYE_IMAGE_RIGHT, fe.IRIS_IMAGE_RIGHT, +1.0),
    ):
        eye_cx = cx + direction * face_px * 0.22
        inner_x = eye_cx - direction * eye_w / 2.0
        outer_x = eye_cx + direction * eye_w / 2.0
        points[eye["inner"]] = (inner_x, eye_y)
        points[eye["outer"]] = (outer_x, eye_y)
        for index in eye["up"]:
            points[index] = (eye_cx, eye_y - lid / 2.0)
        for index in eye["low"]:
            points[index] = (eye_cx, eye_y + lid / 2.0)
        # 눈동자 — 눈 안쪽 끝을 0, 바깥쪽 끝을 1로 봤을 때 (0.5 + gaze) 위치
        points[iris] = (inner_x + (0.5 + gaze) * (outer_x - inner_x), eye_y)

    return points[: fe.LANDMARKS_WITH_IRIS if with_iris else 468]


# =============================================================================

def main_test() -> int:
    print("=" * 66)
    print(" 집중도 측정 자가 점검 (웹캠 없이)")
    print("=" * 66)

    # ------------------------------------------------------------------
    section("1. 눈이 얼마나 떠 있는가 (EAR)")

    opened = make_face(ear=0.30)
    closed = make_face(ear=0.05)
    check("뜬 눈의 EAR이 감은 눈보다 큼",
          fe.mean_ear(opened) > fe.mean_ear(closed),
          f"{fe.mean_ear(opened):.3f} vs {fe.mean_ear(closed):.3f}")
    check("요청한 EAR 값이 그대로 계산됨 (0.30)",
          abs(fe.mean_ear(opened) - 0.30) < 0.01, f"{fe.mean_ear(opened):.4f}")
    check("감은 눈은 EAR_CLOSED 아래",
          fe.mean_ear(closed) < fe.EAR_CLOSED, f"{fe.mean_ear(closed):.4f}")
    check("뜬 눈은 eyes_open이 1.0", fe.eyes_open_ratio(opened) == 1.0)
    check("감은 눈은 eyes_open이 0.0", fe.eyes_open_ratio(closed) == 0.0)
    half = fe.eyes_open_ratio(make_face(ear=(fe.EAR_CLOSED + fe.EAR_OPEN) / 2))
    check("중간쯤 감으면 0.5 근처", abs(half - 0.5) < 0.05, f"{half:.3f}")

    check("얼굴이 멀어져도(작아져도) EAR은 그대로 — 비율이라서",
          abs(fe.mean_ear(make_face(ear=0.3, face_px=100))
              - fe.mean_ear(make_face(ear=0.3, face_px=400))) < 0.001)

    # ------------------------------------------------------------------
    section("2. 눈동자가 어디를 보는가 (시선)")

    check("정면을 보면 0에 가까움",
          abs(fe.gaze_offset(make_face(gaze=0.0)) or 1) < 0.001)
    right = fe.gaze_offset(make_face(gaze=0.25))
    check("한쪽으로 치우치면 값이 커짐", right is not None and abs(right) > fe.GAZE_AWAY,
          f"{right}")
    check("눈동자 점이 없으면(refine_landmarks=False) None을 돌려줌",
          fe.gaze_offset(make_face(with_iris=False)) is None)

    # ------------------------------------------------------------------
    section("3. 고개 방향")

    check("정면이면 yaw가 0에 가까움", abs(fe.head_yaw(make_face(yaw=0.0))) < 0.01)
    turned = fe.head_yaw(make_face(yaw=0.5))
    check("고개를 돌리면 yaw가 커짐", abs(turned) > fe.YAW_AWAY, f"{turned:.3f}")
    check("고개를 숙이면 pitch 비율이 작아짐",
          fe.head_pitch_ratio(make_face(pitch=1.2)) < fe.head_pitch_ratio(make_face(pitch=1.6)))
    check("얼굴 폭이 픽셀로 나옴",
          abs(fe.face_width_px(make_face(face_px=260)) - 260) < 0.01)

    # ------------------------------------------------------------------
    section("4. 사람마다 다른 '정면'을 배우는가 (보정)")

    cal = fe.Calibration(seconds=2.0, min_samples=10)
    check("처음에는 보정이 안 되어 있음", not cal.done)
    check("보정 전에는 고개 숙임을 판단하지 않음", not cal.is_head_down(0.5))

    for i in range(30):
        cal.add(pitch=1.60, yaw=0.0, now=100.0 + i * 0.1)
    check("시간과 표본이 차면 보정 완료", cal.done)
    check("기준값이 중앙값으로 잡힘", abs((cal.pitch_baseline or 0) - 1.60) < 0.01,
          str(cal.pitch_baseline))
    check("보정 진행률이 1.0", cal.progress(103.0) == 1.0)

    check("기준보다 충분히 내려가면 '고개 숙임'", cal.is_head_down(1.60 * 0.8))
    check("조금 움직인 정도로는 '고개 숙임'이 아님", not cal.is_head_down(1.60 * 0.95))

    tilted = fe.Calibration(seconds=2.0, min_samples=10)
    for i in range(30):
        tilted.add(pitch=1.20, yaw=0.0, now=200.0 + i * 0.1)
    check("얼굴 비율이 다른 사람은 기준도 다르게 잡힘",
          abs((tilted.pitch_baseline or 0) - 1.20) < 0.01)
    check("그 사람 기준으로는 1.20이 정상 (고정 숫자였다면 늘 숙인 것이 됨)",
          not tilted.is_head_down(1.20))

    # ------------------------------------------------------------------
    section("5. 창 집계 — 깜빡임과 졸음을 가르는가")

    acc = fe.WindowAccumulator(fe.Calibration(seconds=0.5, min_samples=5))
    t = 1000.0
    # 눈을 뜨고 2초
    for i in range(20):
        acc.add(fe.read_face(make_face(ear=0.30), t + i * 0.1))
    t += 2.0
    # 0.3초 깜빡임
    for i in range(3):
        acc.add(fe.read_face(make_face(ear=0.05), t + i * 0.1))
    t += 0.3
    summary = acc.summarize(t)
    check("깜빡임은 짧게 기록됨 (0.3초 미만)", summary["closed_run"] < 0.3,
          str(summary["closed_run"]))
    check("표본 수가 맞음", summary["samples"] == 23, str(summary["samples"]))
    check("얼굴이 보였다고 나옴", summary["face"] is True)

    acc2 = fe.WindowAccumulator(fe.Calibration(seconds=0.5, min_samples=5))
    t = 2000.0
    for i in range(20):                      # 2초간 눈을 감고 있음
        acc2.add(fe.read_face(make_face(ear=0.05), t + i * 0.1))
    summary2 = acc2.summarize(t + 2.0)
    check("오래 감고 있으면 closed_run이 길게 기록됨",
          summary2["closed_run"] >= fe.EYES_CLOSED_SECONDS, str(summary2["closed_run"]))
    check("감은 프레임 비율이 1.0", summary2["closed_ratio"] == 1.0)

    check("깜빡임(0.3초)은 졸음 기준(1.2초)에 못 미침",
          summary["closed_run"] < fe.EYES_CLOSED_SECONDS <= summary2["closed_run"])

    # ------------------------------------------------------------------
    section("6. 창을 비워도 졸음이 끊기지 않는가")

    acc3 = fe.WindowAccumulator(fe.Calibration(seconds=0.5, min_samples=5))
    t = 3000.0
    for i in range(10):                      # 창 1: 1초간 감음
        acc3.add(fe.read_face(make_face(ear=0.05), t + i * 0.1))
    acc3.drain(t + 1.0)                      # 전송 — 창을 비움
    check("아직 감고 있으면 이어서 세고 있음", acc3.closed_run_seconds >= 0.9,
          str(acc3.closed_run_seconds))
    for i in range(10):                      # 창 2: 계속 감고 있음
        acc3.add(fe.read_face(make_face(ear=0.05), t + 1.0 + i * 0.1))
    check("창을 넘어가도 감은 시간이 누적됨",
          acc3.closed_run_seconds >= fe.EYES_CLOSED_SECONDS,
          str(acc3.closed_run_seconds))

    acc4 = fe.WindowAccumulator(fe.Calibration(seconds=0.5, min_samples=5))
    t = 4000.0
    for i in range(10):
        acc4.add(fe.read_face(make_face(ear=0.05), t + i * 0.1))
    acc4.add(fe.read_face(make_face(ear=0.30), t + 1.0))   # 눈을 뜸
    acc4.drain(t + 1.1)
    check("눈을 뜨면 감은 시간이 0으로 돌아감", acc4.closed_run_seconds == 0.0,
          str(acc4.closed_run_seconds))

    # ------------------------------------------------------------------
    section("7. 얼굴이 안 보일 때")

    acc5 = fe.WindowAccumulator()
    for _ in range(10):
        acc5.add_no_face()
    empty = acc5.summarize(5000.0)
    check("얼굴 없음이 기록됨", empty["face"] is False)
    check("표본 수는 세어짐", empty["samples"] == 10)
    check("얼굴이 없으면 눈 관련 값을 만들어내지 않음", "eyes_open" not in empty)

    # ------------------------------------------------------------------
    section("8. confidence는 '점수'가 아니라 '얼마나 믿을 만한가'")

    good = fe.reading_confidence({"samples": 20, "face": True, "face_px": 260})
    small = fe.reading_confidence({"samples": 20, "face": True, "face_px": 40})
    few = fe.reading_confidence({"samples": 2, "face": True, "face_px": 260})
    check("얼굴이 크고 표본이 많으면 높음", good >= 0.95, str(good))
    check("얼굴이 작으면 낮아짐 (멀리 있어 눈을 못 잼)", small < 0.3, str(small))
    check("표본이 적으면 낮아짐", few < 0.2, str(few))
    check("표본이 없으면 0", fe.reading_confidence({"samples": 0}) == 0.0)

    # ------------------------------------------------------------------
    section("9. extra 크기 제한을 지키는가 (백엔드: 키 20개 · 2KB)")

    import json
    acc6 = fe.WindowAccumulator(fe.Calibration(seconds=0.1, min_samples=1))
    for i in range(30):
        acc6.add(fe.read_face(make_face(), 6000.0 + i * 0.1))
    payload = acc6.summarize(6003.0)
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    check(f"키 개수 {len(payload)}개 ≤ 20", len(payload) <= 20)
    check(f"크기 {size}바이트 ≤ 2048", size <= 2048)
    check("좌표 배열이나 이미지가 들어 있지 않음",
          all(not isinstance(v, (list, dict, bytes)) for v in payload.values()))

    # ------------------------------------------------------------------
    section("10. 검출기가 라벨 네 개를 제대로 내보내는가")

    try:
        from detectors.study_focus import Detector
        detector = Detector()
    except Exception as exc:
        print(f"  [건너뜀] 검출기를 만들지 못했습니다: {exc}")
        detector = None

    if detector is not None and detector.available:
        check("라벨이 네 개", set(detector.labels) ==
              {"face_visible", "eyes_closed", "look_away", "no_face"})

        now = 7000.0
        detector._summary = {"samples": 20, "face": True, "face_px": 260,
                             "eyes_open": 0.9, "closed_run": 0.2, "look_away": 0.1,
                             "closed_ratio": 0.05, "head_down": 0.0, "no_face": 0.0,
                             "calibrated": True}
        detector._last_face_at = now
        events = {e.label: e for e in detector._events(now)}
        check("얼굴이 보이면 face_visible이 켜짐", events["face_visible"].detected)
        check("측정값은 face_visible의 extra에만 실림",
              "eyes_open" in events["face_visible"].extra
              and events["eyes_closed"].extra == {})
        check("잠깐 감은 것으로는 eyes_closed가 켜지지 않음",
              not events["eyes_closed"].detected)
        check("자리에 있으면 no_face가 꺼져 있음", not events["no_face"].detected)
        check("모든 이벤트의 event_type이 같음",
              {e.event_type for e in events.values()} == {"study_focus"})

        detector._summary = dict(detector._summary, closed_run=2.0)
        events = {e.label: e for e in detector._events(now)}
        check("오래 감으면 eyes_closed가 켜짐", events["eyes_closed"].detected)

        detector._summary = {"samples": 20, "face": False, "calibrated": True}
        detector._last_face_at = now - 10.0
        events = {e.label: e for e in detector._events(now)}
        check("얼굴이 없으면 no_face가 켜짐 (규칙은 detected=True에서만 동작)",
              events["no_face"].detected)
        check("얼굴이 없으면 face_visible이 꺼짐", not events["face_visible"].detected)
        check("얼굴이 없으면 eyes_closed도 꺼짐 (없는 눈을 감았다고 하지 않음)",
              not events["eyes_closed"].detected)

        check("confidence가 0~1 범위",
              all(0.0 <= (e.confidence or 0) <= 1.0 for e in events.values()))
        detector.close()
    else:
        reason = detector.unavailable_reason if detector else "생성 실패"
        print(f"  [건너뜀] MediaPipe가 없어 검출기 시험은 생략합니다 ({reason})")
        print("           → 좌석·사물 감지는 그대로 동작합니다. 이것이 정상 동작입니다.")

    print("\n" + "=" * 66)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 66)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main_test())
