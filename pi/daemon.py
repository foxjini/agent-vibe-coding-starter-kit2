"""
공통 데몬 (pi/daemon.py) — 키트 제공, **수정하지 마세요.**
=============================================================================
하드웨어를 고치려면 `slot_map.py`만 고치면 됩니다 (docs/부록F 8장).

실행 방법
    python daemon.py            # 배치표대로 실행
    python daemon.py --check    # 배선·설정만 확인하고 종료 (GPIO를 건드리지 않습니다)

하는 일
 1. 부팅 시 배치표를 `POST /api/v1/devices/register`로 등록 (exclusive: true)
 2. 1초 주기로 `GET /api/v1/devices/desired-states` → 드라이버에 반영
 3. 반영 결과와 센서값을 `POST /api/v1/devices/states`로 일괄 보고
 4. 보고 실패 시 다음 회차에 재시도, 30초마다 전체 재동기화
 5. GPIO가 없는 PC에서는 흉내내기 부품으로 자동 대체 — **프로그램이 죽지 않습니다**
"""
import argparse
import logging
import os
import signal
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# 윈도우 콘솔에서 한글이 깨지지 않도록
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] [pi] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pi.daemon")

from backend_client import BackendClient          # noqa: E402
from drivers import create_driver                 # noqa: E402
from drivers.base import DriverError, SensorDriver  # noqa: E402
from drivers.gpio import gpio_available, gpio_unavailable_reason  # noqa: E402
from slot_config import load_slot_map             # noqa: E402

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))
RESYNC_INTERVAL_SECONDS = float(os.getenv("RESYNC_INTERVAL_SECONDS", "30"))
REGISTER_RETRY_SECONDS = float(os.getenv("REGISTER_RETRY_SECONDS", "10"))


class SlotDaemon:
    """배치표를 읽어 드라이버를 만들고, 백엔드와 계속 주고받습니다."""

    def __init__(self, client: BackendClient, slots: Dict[str, Dict[str, Any]]) -> None:
        self.client = client
        self.slot_configs = slots
        self.drivers: Dict[str, Any] = {}
        self.running = False

        #: 마지막으로 반영한 목표 상태 (같은 명령을 반복해서 GPIO에 쓰지 않도록)
        self._applied: Dict[str, Any] = {}
        #: 마지막으로 보고한 상태 (재동기화 때 다시 올립니다)
        self._reported_states: Dict[str, str] = {}
        self._registered = False
        self._last_register_attempt = 0.0
        self._last_resync = 0.0

    # ------------------------------------------------------------------
    # 준비
    # ------------------------------------------------------------------

    def build_drivers(self) -> List[str]:
        """배치표 한 줄마다 드라이버를 만듭니다. 실패한 줄은 건너뜁니다."""
        failures: List[str] = []
        for slot_id, config in self.slot_configs.items():
            try:
                self.drivers[slot_id] = create_driver(slot_id, config)
            except DriverError as exc:
                failures.append(str(exc))
            except Exception as exc:
                failures.append(f"{slot_id}: {type(exc).__name__} — {exc}")
        return failures

    def describe_all(self) -> List[Dict[str, Any]]:
        return [driver.describe() for driver in self.drivers.values()]

    def try_register(self, now: float) -> None:
        """배치표를 백엔드에 등록합니다 (실패하면 주기적으로 다시 시도)."""
        if self._registered or (now - self._last_register_attempt) < REGISTER_RETRY_SECONDS:
            return
        self._last_register_attempt = now

        result = self.client.register(self.describe_all(), exclusive=True)
        if result is None:
            return

        self._registered = True
        registered = result.get("registered", [])
        disabled = result.get("disabled", [])
        logger.info(
            f"[배치표 등록] 사용 슬롯 {len(registered)}개"
            + (f", 자동으로 끈 슬롯 {len(disabled)}개 {disabled}" if disabled else "")
        )
        if result.get("rejected"):
            logger.warning(f"백엔드가 거부한 슬롯: {result['rejected']}")
        if result.get("persisted") is False:
            logger.warning(
                "백엔드 DB가 꺼져 있어 이 등록은 저장되지 않았습니다 "
                "(백엔드를 다시 켜면 자동으로 다시 등록합니다)."
            )
            self._registered = False

    # ------------------------------------------------------------------
    # 한 회차
    # ------------------------------------------------------------------

    def apply_desired_states(self, desired: Dict[str, Any], force: bool) -> List[Dict[str, Any]]:
        """백엔드 목표 상태를 드라이버에 반영하고, 반영 결과를 보고 목록으로 만듭니다."""
        reports: List[Dict[str, Any]] = []

        for slot_id, wanted in desired.items():
            driver = self.drivers.get(slot_id)
            if driver is None:
                # 대시보드에서 켰지만 배치표에 없는 슬롯 — 다음 등록에서 자동으로 정리됩니다.
                continue

            state = wanted.get("desired_state")
            value = wanted.get("value")
            signature = (state, repr(value))
            if not force and self._applied.get(slot_id) == signature:
                continue

            try:
                reflected = driver.apply(state, value)
            except Exception as exc:
                logger.warning(f"[{slot_id}] 반영 실패: {exc}")
                continue

            self._applied[slot_id] = signature
            self._reported_states[slot_id] = reflected
            reports.append({"slot_id": slot_id, "state": reflected, "value": value})

        return reports

    def read_sensors(self, now: float, force: bool) -> List[Dict[str, Any]]:
        """읽을 차례가 된 센서만 읽어 보고 목록으로 만듭니다."""
        reports: List[Dict[str, Any]] = []

        for slot_id, driver in self.drivers.items():
            if not isinstance(driver, SensorDriver) or not (force or driver.due(now)):
                continue
            try:
                measured = driver.read()
            except Exception as exc:
                logger.warning(f"[{slot_id}] 센서 읽기 실패: {exc}")
                continue
            driver.mark_read(now)

            if measured is None:
                continue
            report: Dict[str, Any] = {"slot_id": slot_id, "value": measured}
            unit = driver.config.get("unit")
            if unit:
                report["unit"] = unit
            reports.append(report)

        return reports

    def resync_reports(self) -> List[Dict[str, Any]]:
        """
        백엔드가 재시작되어 상태가 초기화돼도 어긋나지 않도록,
        30초마다 액추에이터의 현재 상태를 다시 올립니다.
        """
        return [
            {"slot_id": slot_id, "state": state}
            for slot_id, state in self._reported_states.items()
        ]

    def tick(self, now: float) -> None:
        self.try_register(now)

        resync = (now - self._last_resync) >= RESYNC_INTERVAL_SECONDS
        if resync:
            self._last_resync = now

        desired = self.client.poll_desired_states()
        if desired is None:
            # 백엔드가 끊겼습니다 — 다음 회차에 다시 등록하고 전체를 다시 반영합니다.
            self._registered = False
            self._applied.clear()
            return

        reports = self.apply_desired_states(desired, force=resync)
        reports += self.read_sensors(now, force=False)
        if resync:
            known = {r["slot_id"] for r in reports}
            reports += [r for r in self.resync_reports() if r["slot_id"] not in known]

        if not reports:
            return

        result = self.client.report_states(reports)
        if result is None:
            # 보고가 실패했으면 다음 회차에 다시 보내도록 반영 기록을 비웁니다.
            self._applied.clear()
            return
        for rejected in result.get("rejected") or []:
            logger.warning(
                f"백엔드가 보고를 거부했습니다: {rejected.get('slot_id')} — {rejected.get('reason')}"
            )
            if rejected.get("reason") in ("UNKNOWN_SLOT", "SLOT_DISABLED"):
                self._registered = False   # 배치표를 다시 등록해 맞춥니다

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.running = True
        logger.info(
            f"데몬을 시작합니다 — 슬롯 {len(self.drivers)}개, "
            f"폴링 {POLL_INTERVAL_SECONDS}초, 재동기화 {RESYNC_INTERVAL_SECONDS}초"
        )
        while self.running:
            started = time.time()
            try:
                self.tick(started)
            except Exception as exc:
                logger.error(f"회차 처리 중 오류 (계속 진행합니다): {exc}", exc_info=True)

            # 처리에 걸린 시간을 빼서 주기를 일정하게 유지합니다.
            time.sleep(max(0.05, POLL_INTERVAL_SECONDS - (time.time() - started)))

    def stop(self) -> None:
        self.running = False

    def close(self) -> None:
        """부저를 끄고 GPIO를 해제합니다 (켜 둔 채로 끝나지 않도록)."""
        for slot_id, driver in self.drivers.items():
            try:
                driver.close()
            except Exception as exc:
                logger.debug(f"[{slot_id}] 정리 중 예외: {exc}")


# ==============================================================================
# 시작 점검 및 진입점
# ==============================================================================

def print_startup_report(slots: Dict[str, Dict[str, Any]], problems: List[str]) -> None:
    print("=" * 68)
    print(" 라즈베리파이 슬롯 데몬 — 시작 점검")
    print("=" * 68)
    print(f" 백엔드      : {BACKEND_URL}")
    print(f" 디바이스 키 : {'설정됨' if DEVICE_API_KEY else '없음 (pi/.env의 DEVICE_API_KEY를 채우세요)'}")
    if gpio_available():
        print(" 하드웨어    : 실기기 GPIO")
    else:
        print(f" 하드웨어    : 흉내내기 모드 — {gpio_unavailable_reason()}")
        print("               (PC에서는 정상입니다. 파이에서 이 메시지가 보이면 배선·권한을 확인하세요)")

    print(f"\n 배치표 슬롯 {len(slots)}개")
    for slot_id, config in sorted(slots.items()):
        pin = config.get("pin") or config.get("pins") or config.get("channel")
        pin_text = f"GPIO {pin}" if pin is not None else "-"
        print(f"   {slot_id:<13} {str(config.get('label') or ''):<16} "
              f"{str(config.get('driver')):<14} {pin_text}")

    if problems:
        print(f"\n ⚠ 고쳐야 할 것 {len(problems)}개 (이 줄만 빼고 나머지는 동작합니다)")
        for problem in problems:
            print(f"   · {problem}")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description="플랫폼 키트 라즈베리파이 데몬")
    parser.add_argument("--check", action="store_true",
                        help="배선·설정만 확인하고 종료합니다 (GPIO를 건드리지 않습니다)")
    args = parser.parse_args()

    slots, problems = load_slot_map()
    print_startup_report(slots, problems)

    if not slots:
        logger.error("쓸 수 있는 슬롯이 없습니다. pi/slot_map.py의 SLOTS를 확인하세요.")
        return 1
    if args.check:
        return 1 if problems else 0
    if not DEVICE_API_KEY:
        logger.error("pi/.env의 DEVICE_API_KEY가 비어 있습니다. 백엔드와 같은 값을 넣어 주세요.")
        return 1

    daemon = SlotDaemon(BackendClient(BACKEND_URL, DEVICE_API_KEY), slots)
    failures = daemon.build_drivers()
    for failure in failures:
        logger.error(failure)
    if not daemon.drivers:
        logger.error("드라이버를 하나도 만들지 못했습니다.")
        return 1

    def shutdown(signum: Any = None, frame: Any = None) -> None:
        logger.info("종료 신호를 받았습니다. 부품을 끄고 정리합니다...")
        daemon.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        daemon.run()
    except KeyboardInterrupt:
        pass
    finally:
        daemon.close()
        logger.info("데몬을 종료했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
