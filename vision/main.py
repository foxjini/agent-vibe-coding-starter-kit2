import logging
import os
import sys
import time
from typing import Dict, Optional

import cv2
import requests
from dotenv import load_dotenv
from ultralytics import YOLO

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

# 2. 기상 미션 감지 대상 COCO 클래스 매핑
# (YOLOv8n 기본 80종 중 기상 미션 연관 클래스)
MISSION_TARGETS: Dict[int, str] = {
    0: "person",       # 1번: 사람 감지 (침대에서 일어남 확인)
    39: "bottle",      # 2번: 물병 (아침 기상 물 한잔 미션)
    41: "cup",         # 3번: 컵/양치컵
    73: "book",        # 4번: 책 (독서/두뇌 깨우기 미션)
    67: "cell phone",  # 5번: 휴대폰 (기상 알람 터치/해제 연계)
}

# 현재 활성 미션 대상 (기본: person)
current_target_id = 0
current_target_name = MISSION_TARGETS[0]

# 이벤트 전송 상태 관리 (불필요한 중복 전송 방지)
last_detected_state: Optional[bool] = None
last_event_time: float = 0.0
EVENT_COOLDOWN_SECONDS = 2.5  # 동일 상태 최소 전송 간격 (초)


def send_vision_event(
    event_type: str,
    detected: bool,
    count: int = 0,
    confidence: Optional[float] = None
) -> None:
    """
    백엔드로 영상인식 감지 이벤트를 전송합니다 (POST /api/v1/vision/events).
    영상 프레임 자체는 전송하지 않고 감지 수치 메타데이터만 전송합니다.
    """
    url = f"{BACKEND_URL}/api/v1/vision/events"
    headers = {
        "X-Device-Api-Key": DEVICE_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "event_type": event_type,
        "detected": detected,
        "count": count,
        "confidence": round(float(confidence), 2) if confidence is not None else None,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=2.5)
        if response.status_code == 200:
            logger.info(
                f"[이벤트 전송 성공] {event_type} (detected={detected}, count={count}, conf={payload['confidence']})"
            )
        else:
            logger.warning(
                f"[이벤트 전송 응답 오류] {response.status_code} - {response.text}"
            )
    except requests.exceptions.RequestException as exc:
        logger.warning(f"[백엔드 통신 실패] {url} 연결 불가: {exc}")


def main():
    global current_target_id, current_target_name
    global last_detected_state, last_event_time

    # 모델 파일 경로 확인
    model_path = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
    if not os.path.exists(model_path):
        logger.error(f"yolov8n.pt 모델을 찾을 수 없습니다: {model_path}")
        return

    logger.info(f"YOLOv8 모델 로드 중... ({model_path})")
    model = YOLO(model_path)
    logger.info("YOLOv8 모델 로드 완료.")

    # 웹캠 초기화 (Windows에서는 DirectShow 백엔드로 열어야 안정적)
    logger.info(f"카메라 인덱스 {CAMERA_INDEX} 초기화 시도...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        logger.warning("CAP_DSHOW로 카메라 열기 실패, 기본 백엔드로 재시도합니다.")
        cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        logger.error(f"카메라(인덱스 {CAMERA_INDEX})를 열 수 없습니다. 웹캠 연결을 확인하세요.")
        return

    # 해상도 설정
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\n" + "=" * 65)
    print(" [스마트 기상 시스템 - YOLOv8 기상 미션 비전 클라이언트]")
    print(f" * 백엔드 URL: {BACKEND_URL}")
    print(f" * 현재 미션 대상: [{current_target_name}]")
    print(" * 키보드 단축키:")
    print("   - [1]: 사람(person) 기상 감지 모드")
    print("   - [2]: 물병(bottle) 기상 미션 모드")
    print("   - [3]: 컵(cup) 양치/물 기상 미션 모드")
    print("   - [4]: 책(book) 독서 기상 미션 모드")
    print("   - [5]: 휴대폰(cell phone) 기상 미션 모드")
    print("   - [A]: 전체 사물 자동 감지 모드 (All)")
    print("   - [Q]: 프로그램 종료")
    print("=" * 65 + "\n")

    detect_all_mode = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("프레임을 읽을 수 없습니다.")
                time.sleep(0.1)
                continue

            # 좌우 반전 (거울 효과)
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # YOLO 객체 감지 추론
            target_classes = list(MISSION_TARGETS.keys()) if detect_all_mode else [current_target_id]
            results = model(frame, classes=target_classes, conf=0.5, verbose=False)

            detected_boxes = results[0].boxes
            detected_count = len(detected_boxes)
            is_detected = detected_count > 0

            max_confidence = 0.0
            primary_label = current_target_name

            # 감지된 객체 바운딩 박스 렌더링
            for box in detected_boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                if conf > max_confidence:
                    max_confidence = conf
                    primary_label = MISSION_TARGETS.get(cls_id, "object")

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # 박스 및 라벨 색상 (초록색)
                color = (0, 220, 0) if is_detected else (200, 200, 200)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                label_text = f"{MISSION_TARGETS.get(cls_id, 'object')} {conf * 100:.1f}%"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
                cv2.putText(
                    frame,
                    label_text,
                    (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0),
                    1,
                    cv2.LINE_AA,
                )

            now = time.time()
            # 상태 변경 시 즉시 전송 or 쿨다운 경과 시 상태 유지 전송
            should_send = False
            if last_detected_state is None or is_detected != last_detected_state:
                should_send = True
            elif now - last_event_time >= EVENT_COOLDOWN_SECONDS:
                should_send = True

            if should_send:
                event_type = f"{primary_label}_detected" if is_detected else f"{current_target_name}_cleared"
                send_vision_event(
                    event_type=event_type,
                    detected=is_detected,
                    count=detected_count,
                    confidence=max_confidence if is_detected else 0.0,
                )
                last_detected_state = is_detected
                last_event_time = now

            # ==================================================================
            # 화면 상단 HUD 정보 오버레이 (디자인 가이드라인 준수)
            # ==================================================================
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 48), (25, 25, 25), -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            # 타깃 정보 텍스트
            mode_str = "ALL" if detect_all_mode else current_target_name.upper()
            status_str = f"DETECTED ({detected_count})" if is_detected else "SEARCHING..."
            status_color = (0, 255, 100) if is_detected else (180, 180, 180)

            cv2.putText(
                frame,
                f"MISSION TARGET: [{mode_str}]",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                status_str,
                (w - 200, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                status_color,
                2,
                cv2.LINE_AA,
            )

            # 하단 조작 단축키 안내 띠
            cv2.putText(
                frame,
                "Keys: [1]Person [2]Bottle [3]Cup [4]Book [5]Phone [A]All [Q]Quit",
                (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )

            # 윈도우 창 표시
            cv2.imshow("Wakeup Vision Mission (YOLOv8)", frame)

            # 키보드 입력 처리
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("사용자에 의해 종료 명령(q)이 입력되었습니다.")
                break
            elif key == ord("1"):
                current_target_id = 0
                current_target_name = MISSION_TARGETS[0]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_name}")
            elif key == ord("2"):
                current_target_id = 39
                current_target_name = MISSION_TARGETS[39]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_name}")
            elif key == ord("3"):
                current_target_id = 41
                current_target_name = MISSION_TARGETS[41]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_name}")
            elif key == ord("4"):
                current_target_id = 73
                current_target_name = MISSION_TARGETS[73]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_name}")
            elif key == ord("5"):
                current_target_id = 67
                current_target_name = MISSION_TARGETS[67]
                detect_all_mode = False
                logger.info(f"미션 대상 변경: {current_target_name}")
            elif key == ord("a"):
                detect_all_mode = not detect_all_mode
                logger.info(f"전체 감지 모드 토글: {detect_all_mode}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        logger.info("웹캠 및 OpenCV 리소스가 안전하게 해제되었습니다.")


if __name__ == "__main__":
    main()
