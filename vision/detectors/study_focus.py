"""
★ study 팀 검출기 — 한 사람의 집중도를 봅니다.
=============================================================================
**이 파일은 study 팀이 고치는 파일입니다.** 다른 팀은 지워도 됩니다.

무엇을 하나
-----------
책상 앞 **한 사람**의 얼굴을 보고, 눈이 얼마나 떠 있는지·고개를 숙였는지·
시선이 화면을 벗어났는지를 잽니다. FHD 웹캠 한 대면 됩니다.

    label = "face_visible"                            ← 얼굴이 보인다
    extra = {"eyes_open": 0.86, "closed_run": 0.3,    ← 어떤 상태였나
             "look_away": 0.20, "face_px": 268}

**판정은 하지 않습니다.** "눈이 1.5초 감겨 있었다"까지만 말하고,
"졸고 있으니 방석을 울려라"는 프론트엔드 시나리오가 정합니다.

라벨 네 개를 내보내는 이유
--------------------------
자동화 규칙(`/kit`)은 **detected=True일 때만** 동작합니다. "얼굴이 안 보일 때"를
규칙으로 쓰려면 그것도 켜지는 라벨이어야 해서, 반대되는 것까지 라벨로 둡니다.

    face_visible   얼굴이 보임        → 측정값을 화면으로 보냅니다
    eyes_closed    눈이 오래 감겨 있음  → 규칙: 방석 진동
    look_away      시선·고개가 벗어남   → 규칙: 알림
    no_face        얼굴이 안 보임      → 규칙: 스탠드 끄기(절전)

설치
----
    pip install mediapipe          (requirements.txt에 이미 있습니다)
    vision/.env 에  CAMERA_WIDTH=1920  CAMERA_HEIGHT=1080

얼굴이 화면에서 **폭 192px 이상**으로 잡혀야 눈을 제대로 잽니다.
웹캠 창의 `face_px` 숫자를 보면서 카메라 거리를 맞추세요 (0.5~1.0m 권장).
MediaPipe가 없으면 이 검출기만 쉬고 나머지는 그대로 돌아갑니다.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import DetectionEvent, FrameDetector
from . import _focus_engine as fe

logger = logging.getLogger("vision.detectors.study_focus")

# =============================================================================
# ★ 여기를 고쳐서 맞춥니다
#   (눈·고개·시선의 임계값은 _focus_engine.py 맨 위에 있습니다)
# =============================================================================

#: 몇 초씩 모아서 요약할지. 전송 주기(`cooldown_seconds`, 기본 2.5초)보다 짧아야 합니다.
WINDOW_SECONDS = 2.0

#: 얼굴이 이만큼(초) 안 보이면 자리를 비운 것으로 봅니다.
AWAY_SECONDS = 3.0

#: 자리를 이만큼(초) 오래 비우면 **다른 사람이 앉았을 수 있으므로** 보정을 다시 합니다.
RECALIBRATE_AFTER_SECONDS = 60.0

#: 몇 프레임마다 얼굴을 찾을지. PC가 느리면 2~3으로 올리세요 (1 = 매 프레임).
PROCESS_EVERY_N_FRAMES = 1

#: 얼굴로 인정할 최소 확신도.
MIN_FACE_CONFIDENCE = 0.4


class Detector(FrameDetector):
    name = "study_focus"
    labels = ("face_visible", "eyes_closed", "look_away", "no_face")
    description = "한 사람 집중도 — 눈·고개·시선 (study 팀)"

    def __init__(self) -> None:
        super().__init__()
        # ⚠️ MediaPipe가 없어 아래에서 멈추더라도 status_text()·draw()가 불릴 수 있으므로
        #    쓰는 값은 **먼저 다 만들어 둡니다.** (없으면 AttributeError로 화면이 죽습니다)
        self._mesh = None
        self._frame_no = 0
        self._acc = fe.WindowAccumulator()
        self._window_started = time.time()
        self._summary: Dict[str, Any] = {"samples": 0, "face": False, "calibrated": False}
        self._last_face_at = 0.0
        self._last_points: Optional[Sequence[Tuple[float, float]]] = None

        try:
            import mediapipe as mp
            self._mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,          # 눈동자(시선)를 쓰려면 반드시 True
                min_detection_confidence=MIN_FACE_CONFIDENCE,
                min_tracking_confidence=MIN_FACE_CONFIDENCE,
            )
        except Exception as exc:
            self.disable(f"MediaPipe를 쓸 수 없습니다: {exc}")

    # ------------------------------------------------------------------
    def detect(self, frame_bgr, config: Dict[str, Any]) -> List[DetectionEvent]:
        if frame_bgr is None or self._mesh is None:
            return []

        now = time.time()
        self._frame_no += 1
        if self._frame_no % PROCESS_EVERY_N_FRAMES == 0:
            self._measure(frame_bgr, now)

        # 창이 찼으면 요약을 갱신합니다 (전송은 main.py가 알아서 조절합니다)
        if now - self._window_started >= WINDOW_SECONDS:
            self._summary = self._acc.drain(now)
            self._window_started = now

        return self._events(now)

    # ------------------------------------------------------------------
    def _measure(self, frame_bgr, now: float) -> None:
        """프레임 하나에서 얼굴을 찾아 측정값을 쌓습니다."""
        import cv2

        height, width = frame_bgr.shape[:2]
        try:
            result = self._mesh.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        except Exception as exc:
            logger.debug(f"얼굴 분석 실패(건너뜁니다): {exc}")
            return

        faces = getattr(result, "multi_face_landmarks", None)
        if not faces:
            self._acc.add_no_face()
            self._last_points = None
            # 오래 비었으면 다음 사람을 위해 기준을 새로 배웁니다
            if self._last_face_at and now - self._last_face_at > RECALIBRATE_AFTER_SECONDS:
                self._acc.reset()
                self._last_face_at = 0.0
                logger.info("자리가 오래 비어 보정을 다시 합니다.")
            return

        # MediaPipe는 0.0~1.0으로 주므로 픽셀로 바꿉니다 (엔진은 픽셀만 압니다)
        points = [(lm.x * width, lm.y * height) for lm in faces[0].landmark]
        self._acc.add(fe.read_face(points, now))
        self._last_points = points
        self._last_face_at = now

    # ------------------------------------------------------------------
    def _events(self, now: float) -> List[DetectionEvent]:
        """요약 하나를 라벨 네 개로 나눠 내보냅니다."""
        summary = self._summary
        confidence = fe.reading_confidence(summary)
        face = bool(summary.get("face"))
        away_for = now - self._last_face_at if self._last_face_at else None

        # 창을 넘어서 이어지고 있는 '눈 감은 시간'도 함께 봅니다 —
        # 창 경계에서 졸음이 끊겨 보이지 않도록.
        closed_run = max(float(summary.get("closed_run") or 0.0),
                         self._acc.closed_run_seconds)

        no_face = (not face) or (away_for is not None and away_for >= AWAY_SECONDS)

        def event(label: str, detected: bool, extra: Optional[Dict[str, Any]] = None
                  ) -> DetectionEvent:
            return DetectionEvent(
                label=label,
                detected=detected,
                confidence=confidence,
                count=1 if detected else 0,
                event_type="study_focus",
                extra=extra or {},
            )

        return [
            # 측정값 전부는 이 라벨에 실어 화면으로 보냅니다
            event("face_visible", face, dict(summary, closed_run=round(closed_run, 2))),
            # 아래 셋은 자동화 규칙이 바로 쓰는 신호입니다
            event("eyes_closed", face and closed_run >= fe.EYES_CLOSED_SECONDS),
            event("look_away", face and float(summary.get("look_away") or 0.0) >= 0.5),
            event("no_face", no_face),
        ]

    # ------------------------------------------------------------------
    def draw(self, frame_bgr, events) -> None:
        """무엇을 보고 있는지 화면에 그립니다 — 임계값을 맞출 때 이것을 봅니다."""
        if frame_bgr is None:
            return
        import cv2

        points = self._last_points
        if not points:
            return

        left = int(min(p[0] for p in points))
        right = int(max(p[0] for p in points))
        top = int(min(p[1] for p in points))
        bottom = int(max(p[1] for p in points))

        summary = self._summary
        closed = float(summary.get("closed_run") or 0.0) >= fe.EYES_CLOSED_SECONDS
        color = (0, 0, 255) if closed else (0, 200, 0)
        cv2.rectangle(frame_bgr, (left, top), (right, bottom), color, 2)

        # 눈 여섯 점을 찍어 두면 어디를 재는지 눈으로 확인됩니다
        for eye in (fe.EYE_IMAGE_LEFT, fe.EYE_IMAGE_RIGHT):
            for index in (eye["outer"], eye["inner"], *eye["up"], *eye["low"]):
                x, y = points[index]
                cv2.circle(frame_bgr, (int(x), int(y)), 1, (255, 200, 0), -1)

        face_px = fe.face_width_px(points)
        quality = "OK" if face_px >= fe.GOOD_FACE_PX else "TOO SMALL - move closer"
        lines = [
            f"face {int(face_px)}px  {quality}",
            f"EAR {fe.mean_ear(points):.2f}  open {fe.eyes_open_ratio(points):.2f}",
        ]
        if not self._acc.calibration.done:
            lines.append(f"calibrating {self._acc.calibration.progress(time.time()) * 100:.0f}%")

        for i, text in enumerate(lines):
            cv2.putText(frame_bgr, text, (left, max(18, top - 8 - i * 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 220, 255) if "TOO SMALL" in text else (220, 220, 220),
                        1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    def status_text(self) -> str:
        summary = self._summary
        if not summary.get("face"):
            return "집중도 — 얼굴이 보이지 않음"
        if not summary.get("calibrated"):
            return f"집중도 — 보정 중 {self._acc.calibration.progress(time.time()) * 100:.0f}%"
        return (f"집중도 — 눈 {summary.get('eyes_open', 0):.2f} · "
                f"감김 {summary.get('closed_run', 0):.1f}s · "
                f"이탈 {summary.get('look_away', 0):.0%} · "
                f"얼굴 {summary.get('face_px', 0)}px")

    def close(self) -> None:
        if self._mesh is not None:
            try:
                self._mesh.close()
            except Exception:
                pass
