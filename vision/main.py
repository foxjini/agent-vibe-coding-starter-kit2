"""
영상인식 클라이언트 (vision/main.py) — 키트 제공 공통 루프, 수정하지 마세요.
=============================================================================
이 파일은 **무엇을 감지할지도, 그게 무슨 의미인지도 모릅니다.**

  무엇을 감지할지   서버 설정에서 받아옵니다 (대시보드 /kit → 영상인식 설정)
  어떻게 감지할지   `detectors/`의 검출기들이 합니다 (팀이 파일을 추가할 수 있습니다)
  무슨 의미인지     프론트엔드 시나리오가 판정합니다 (승패·혼잡도·졸음 등)

하는 일은 네 가지뿐입니다.
  1. 카메라 열기 (USB 웹캠 / Pi Camera 자동 선택 — camera.py)
  2. `detectors/`의 검출기를 모두 불러와 프레임마다 돌리기
  3. 결과를 백엔드로 보내기 (비동기 — 영상이 끊기지 않게)
  4. 화면에 보여 주기

새 감지를 추가하려면 이 파일이 아니라 **`detectors/`에 파일 하나**를 넣으세요
(pi에서 새 부품이 `drivers/`에 파일 하나인 것과 같습니다 — docs/부록F 10장).

실행 방법 (vision 폴더에서):
    python main.py
"""
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from camera import open_camera
from detectors import DetectionEvent, load_detectors
from detectors.objects import label_ko

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("vision.main")

# 1. 환경 변수 로드 (.env)
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
# auto(기본) / usb / picamera — 라즈베리파이 Pi Camera를 쓰면 picamera
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "auto")
# 감지 설정을 몇 초마다 다시 받아올지 (대시보드에서 바꾼 대상이 반영되는 주기)
CONFIG_POLL_SECONDS = float(os.getenv("CONFIG_POLL_SECONDS", "5"))

#: 사물 탐지 검출기의 이름. 공통층이 아는 유일한 검출기 이름입니다 —
#: `object_labels` 설정을 받는 주인이기 때문입니다(부록F 10장).
OBJECT_DETECTOR = "objects"

# 2. 서버에 연결되지 않았을 때 쓸 기본값 (수업이 멈추지 않도록)
FALLBACK_CONFIG: Dict[str, Any] = {
    "object_labels": ["person", "bottle", "cup", "book", "cell phone"],
    # 비워 두면 `detectors/` 폴더에 있는 것을 모두 돌립니다 —
    # 그래서 이 파일에 검출기 이름을 하나도 적지 않습니다 (팀마다 다르니까요).
    "detectors": [],
    "min_confidence": 0.6,
    "cooldown_seconds": 2.5,
}

# 4. 한글 폰트 로드 유틸리티
_FONT_CACHE: Dict[int, ImageFont.ImageFont] = {}


def get_korean_font(size: int = 18) -> ImageFont.ImageFont:
    """시스템 한글 폰트를 로드합니다 (윈도우 맑은 고딕 우선, 없으면 리눅스 폰트)."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    font_paths = [
        "C:/Windows/Fonts/malgun.ttf",   # 맑은 고딕
        "C:/Windows/Fonts/malgunbd.ttf",  # 맑은 고딕 볼드
        "C:/Windows/Fonts/gulim.ttc",    # 굴림
        "C:/Windows/Fonts/batang.ttc",   # 바탕
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # 리눅스
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",       # macOS
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue

    # 폴백: 기본 비트맵 폰트 (한글은 깨질 수 있음)
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def put_korean_text(
    img: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_size: int = 18,
    color: Tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """OpenCV 이미지(BGR) 위에 깨짐 없는 한글 텍스트를 오버레이합니다."""
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    font = get_korean_font(font_size)

    # PIL 색상은 RGB 기준
    rgb_color = (color[2], color[1], color[0])
    draw.text(position, text, font=font, fill=rgb_color)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

# ==============================================================================
# 5. 백엔드 통신 (영상 루프를 절대 멈추지 않도록 별도 스레드에서 처리)
# ==============================================================================

class BackendClient:
    """
    이벤트 전송과 감지 설정 조회를 백그라운드 스레드에서 처리합니다.

    예전에는 영상 루프 안에서 곧바로 requests.post를 호출해서,
    백엔드가 꺼져 있으면 매 프레임 최대 2.5초씩 멈추고 화면이 얼어붙었습니다.
    이제 큐에 넣기만 하므로 영상은 끊기지 않습니다.
    """

    def __init__(self, backend_url: str, api_key: str):
        self.backend_url = backend_url
        self.headers = {
            "X-Device-Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=32)
        self._running = True
        self._session = requests.Session()

        self.last_send_ok: Optional[bool] = None
        #: 서버가 내려준 감지 설정 (부록F 10장). 연결 전에는 기본값을 씁니다.
        self.config: Dict[str, Any] = dict(FALLBACK_CONFIG)
        self._detectors: List[Dict[str, Any]] = []
        self.config_source: str = "기본값(서버 연결 전)"

        self._sender = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender.start()
        self._poller = threading.Thread(target=self._config_loop, daemon=True)
        self._poller.start()

    def send_event(
        self,
        event_type: str,
        detected: bool,
        label: Optional[str] = None,
        count: int = 0,
        confidence: Optional[float] = None,
    ) -> None:
        """이벤트를 큐에 넣습니다 (즉시 반환 — 영상 루프를 막지 않음)."""
        payload = {
            "event_type": event_type,
            "detected": detected,
            "count": count,
            "confidence": round(float(confidence), 2) if confidence is not None else None,
            "label": label,
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.debug("전송 큐가 가득 차 이벤트를 건너뜁니다 (백엔드 응답 지연).")

    def _sender_loop(self) -> None:
        url = f"{self.backend_url}/api/v1/vision/events"
        while self._running:
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                res = self._session.post(url, json=payload, headers=self.headers, timeout=2.5)
                if res.status_code == 200:
                    self.last_send_ok = True
                    logger.info(
                        f"[이벤트 전송] {payload['event_type']} "
                        f"label={payload['label']} conf={payload['confidence']}"
                    )
                else:
                    self.last_send_ok = False
                    logger.warning(f"[이벤트 응답 오류] {res.status_code} - {res.text[:120]}")
            except requests.exceptions.RequestException as exc:
                self.last_send_ok = False
                logger.warning(f"[백엔드 통신 실패] {url}: {exc}")

    def _config_loop(self) -> None:
        """
        감지 설정을 주기적으로 받아옵니다 (부록F 10장).

        대시보드에서 감지 대상을 바꾸면 **프로그램을 다시 켜지 않아도** 몇 초 안에 반영됩니다.
        서버에 연결되지 않으면 기본값을 유지합니다 — 설정을 못 읽었다고 감지를 멈추면
        수업이 멈춥니다.
        """
        url = f"{self.backend_url}/api/v1/vision/config"
        while self._running:
            try:
                res = self._session.get(url, headers=self.headers, timeout=2.0)
                if res.status_code == 200:
                    data = res.json().get("data") or {}
                    labels = [str(x).strip().lower() for x in (data.get("object_labels") or []) if x]
                    if labels != self.config.get("object_labels"):
                        logger.info(f"[감지 설정] 대상이 바뀌었습니다: {labels}")

                    # 어떤 검출기를 돌릴지. 빈 목록은 "폴더에 있는 것 전부"라는 뜻입니다.
                    # 구버전 서버는 gesture_enabled 불린만 주므로 그것도 같은 뜻으로 읽습니다.
                    enabled = [str(x).strip() for x in (data.get("detectors") or []) if x]
                    if not enabled and data.get("gesture_enabled") is False:
                        enabled = [OBJECT_DETECTOR]     # 사물 탐지만
                    if enabled != self.config.get("detectors"):
                        logger.info(f"[감지 설정] 검출기가 바뀌었습니다: {enabled}")

                    self.config = {
                        "object_labels": labels or list(FALLBACK_CONFIG["object_labels"]),
                        "detectors": enabled,
                        "min_confidence": float(data.get("min_confidence") or 0.6),
                        "cooldown_seconds": float(data.get("cooldown_seconds") or 2.5),
                    }
                    self.config_source = "서버 설정" if data.get("source") == "saved" else "서버 기본값"
                elif res.status_code in (401, 403):
                    logger.error("인증 실패! vision/.env의 DEVICE_API_KEY를 확인하세요.")
            except requests.exceptions.RequestException:
                pass    # 다음 주기에 다시 시도 — 그동안은 마지막 설정을 그대로 씁니다
            time.sleep(CONFIG_POLL_SECONDS)

    def report_detectors(self, detectors: List[Dict[str, Any]]) -> None:
        """
        내가 어떤 검출기를 갖고 있고 어떤 라벨을 내보내는지 백엔드에 알립니다.

        백엔드는 이 신고를 보고 규칙 편집기에 고를 수 있는 라벨을 채웁니다 —
        그래서 공통 계층(백엔드·이 파일)에는 팀 고유 라벨을 둘 필요가 없습니다.
        실패해도 감지는 그대로 동작합니다.
        """
        self._detectors = detectors
        url = f"{self.backend_url}/api/v1/vision/detectors"
        try:
            res = self._session.post(url, json={"detectors": detectors},
                                     headers=self.headers, timeout=3.0)
            if res.status_code == 200:
                names = [d.get("name") for d in detectors if d.get("available")]
                body = res.json().get("data", {}) if res.content else {}
                if body.get("persisted") is False:
                    logger.warning(f"[검출기 신고] {names} — 서버 DB가 꺼져 있어 "
                                   "대시보드가 라벨 목록을 기억하지 못합니다.")
                else:
                    logger.info(f"[검출기 신고] {names}")
            elif res.status_code == 404:
                logger.debug("구버전 백엔드라 검출기 신고를 건너뜁니다.")
            else:
                logger.warning(f"[검출기 신고 실패] {res.status_code} {res.text[:120]}")
        except requests.exceptions.RequestException:
            logger.debug("백엔드에 검출기를 신고하지 못했습니다 (감지는 계속 동작합니다).")

    def close(self) -> None:
        self._running = False

# ==============================================================================
# 6. 메인 루프 — 검출기를 돌리고, 보내고, 보여 줍니다
# ==============================================================================

class EventThrottle:
    """
    같은 내용을 계속 보내지 않도록 거릅니다.

    상태가 바뀌었을 때(보임 ↔ 안 보임)는 즉시, 같은 상태가 이어질 때는
    서버가 정한 쿨다운이 지난 뒤에만 보냅니다.
    """

    def __init__(self) -> None:
        self._last_state: Dict[str, bool] = {}
        self._last_sent_at: Dict[str, float] = {}

    def should_send(self, event: DetectionEvent, now: float, cooldown: float) -> bool:
        key = f"{event.event_type or ''}:{event.label}"
        changed = self._last_state.get(key) != event.detected
        overdue = now - self._last_sent_at.get(key, 0.0) >= cooldown
        if changed or overdue:
            self._last_state[key] = event.detected
            self._last_sent_at[key] = now
            return True
        return False

    def reset(self) -> None:
        self._last_state.clear()
        self._last_sent_at.clear()


def main() -> int:
    if not DEVICE_API_KEY:
        print("[안내] DEVICE_API_KEY가 설정되어 있지 않습니다. vision/.env에 백엔드와 같은 키를 넣어 주세요.\n")

    # 검출기 불러오기 — 하나가 준비되지 않아도 나머지는 그대로 동작합니다
    detectors = load_detectors()
    if not detectors:
        logger.error("검출기를 하나도 불러오지 못했습니다. vision/detectors/ 폴더를 확인하세요.")
        return 1

    backend = BackendClient(BACKEND_URL, DEVICE_API_KEY)
    backend.report_detectors([d.describe() for d in detectors.values()])

    camera = open_camera(index=CAMERA_INDEX, source=CAMERA_SOURCE)
    if camera is None:
        backend.close()
        return 1

    throttle = EventThrottle()
    #: 숫자키로 대상 하나만 보기. -1이면 설정된 대상 전체.
    focus_index = -1
    #: 검출기 켜고 끄기 (화면에서 임시로 — 영구 설정은 대시보드에서)
    muted: set = set()

    print("\n" + "=" * 70)
    print(" [IoT 플랫폼 키트 - 영상인식 클라이언트]")
    print(f" * 카메라   : {camera.description}")
    print(f" * 백엔드   : {BACKEND_URL}")
    print(f" * 감지 대상: {backend.config['object_labels']}  ({backend.config_source})")
    print("   └ 대상을 바꾸려면 코드가 아니라 대시보드 /kit → 영상인식 설정에서 바꾸세요.")
    print(" * 검출기:")
    for name, detector in detectors.items():
        mark = "O" if detector.available else "X"
        reason = f"  ({detector.unavailable_reason})" if not detector.available else ""
        print(f"     [{mark}] {name:12} {detector.description}{reason}")
    print(" * 키보드 단축키:")
    print("   - [1]~[9]: 설정된 대상 중 하나만 집중해서 보기   [A]: 전체")
    print("   - [D]: 검출기 켜기/끄기 순환                     [Q]: 종료")
    print("=" * 70 + "\n")

    fps_time = time.time()
    fps_count = 0
    fps_display = 0.0

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                logger.warning("프레임을 읽지 못했습니다. 카메라 연결을 확인하세요.")
                time.sleep(0.5)
                continue

            frame = cv2.flip(frame, 1)      # 거울처럼 보이게 (손동작이 자연스러움)
            h, w = frame.shape[:2]
            now = time.time()

            # ---- 서버 설정 적용 (대시보드에서 바꾸면 몇 초 안에 반영됩니다) ----
            config = dict(backend.config)
            all_labels = config.get("object_labels") or []
            if focus_index >= len(all_labels):
                focus_index = -1
            if focus_index >= 0:
                config["object_labels"] = [all_labels[focus_index]]

            enabled = set(config.get("detectors") or detectors.keys())

            # ---- 검출기 실행 ----
            events: List[DetectionEvent] = []
            status_lines: List[str] = []
            for name, detector in detectors.items():
                if not detector.available or name in muted or name not in enabled:
                    continue
                try:
                    found = detector.detect(frame, config)
                except Exception as exc:
                    logger.warning(f"검출기 '{name}' 실행 중 오류 (건너뜁니다): {exc}")
                    continue
                try:
                    detector.draw(frame, found)
                except Exception:
                    pass
                text = detector.status_text()
                if text:
                    status_lines.append(text)
                events.extend(found)

            # ---- 백엔드로 전송 ----
            cooldown = float(config.get("cooldown_seconds") or 2.5)
            for event in events:
                if throttle.should_send(event, now, cooldown):
                    backend.send_event(
                        event_type=event.event_type or "object_detected",
                        detected=event.detected,
                        label=event.label,
                        count=event.count,
                        confidence=event.confidence,
                    )

            # ---- 화면 ----
            fps_count += 1
            if now - fps_time >= 1.0:
                fps_display = fps_count / (now - fps_time)
                fps_count = 0
                fps_time = now

            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 74), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

            watching = config.get("object_labels") or []
            watching_ko = ", ".join(label_ko(label) for label in watching) or "설정된 대상 없음"
            if focus_index >= 0:
                watching_ko += " (하나만 보기 — [A]로 전체)"
            frame = put_korean_text(frame, f"감지 대상: {watching_ko}", (14, 4),
                                    font_size=17, color=(255, 255, 255))
            if status_lines:
                frame = put_korean_text(frame, "  ·  ".join(status_lines[:2]), (14, 26),
                                        font_size=15, color=(120, 220, 255))

            conn = ("백엔드 OK" if backend.last_send_ok
                    else ("백엔드 응답없음" if backend.last_send_ok is False else "대기"))
            cv2.putText(frame, f"{fps_display:.1f} FPS", (w - 250, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
            frame = put_korean_text(
                frame, conn, (w - 250, 34), font_size=14,
                color=(120, 255, 120) if backend.last_send_ok else (150, 150, 255)
            )

            cv2.rectangle(frame, (0, h - 26), (w, h), (15, 15, 15), -1)
            shortcuts = " ".join(f"[{i + 1}]{label_ko(label)}"
                                 for i, label in enumerate(all_labels[:9]))
            active = [n for n, d in detectors.items()
                      if d.available and n not in muted and n in enabled]
            frame = put_korean_text(
                frame,
                f"단축키: {shortcuts} [A]전체 [D]검출기({','.join(active) or '없음'}) [Q]종료",
                (10, h - 22), font_size=13, color=(210, 210, 210)
            )

            cv2.imshow("IoT Kit Vision", frame)

            # ---- 키보드 ----
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("사용자가 종료(q)했습니다.")
                break
            elif ord("1") <= key <= ord("9"):
                index = key - ord("1")
                if index < len(all_labels):
                    focus_index = index
                    throttle.reset()
                    logger.info(f"감지 대상 집중: {label_ko(all_labels[index])}")
                else:
                    logger.info(f"{index + 1}번 대상이 없습니다 (설정된 대상 {len(all_labels)}개).")
            elif key == ord("a"):
                focus_index = -1
                throttle.reset()
                logger.info(f"설정된 대상 전체 감지: {all_labels}")
            elif key == ord("d"):
                # 켜져 있는 검출기를 하나씩 잠시 꺼 봅니다 (영구 설정은 대시보드에서)
                switchable = [n for n, d in detectors.items() if d.available]
                if switchable:
                    target = next((n for n in switchable if n not in muted), None)
                    if target:
                        muted.add(target)
                    else:
                        muted.clear()
                    throttle.reset()
                    logger.info(f"검출기 끔: {sorted(muted) or '없음'}")

    except KeyboardInterrupt:
        logger.info("Ctrl+C로 종료합니다.")
    finally:
        for detector in detectors.values():
            try:
                detector.close()
            except Exception:
                pass
        camera.release()
        cv2.destroyAllWindows()
        backend.close()
        logger.info("영상인식 클라이언트를 종료했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
