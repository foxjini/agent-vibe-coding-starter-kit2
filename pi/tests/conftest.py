"""pi 테스트 공통 설정 — pi/와 backend/를 임포트 경로에 넣는다."""
import sys
from pathlib import Path

import pytest

PI_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PI_DIR.parent / "backend"
for path in (PI_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def _silent_beeps(monkeypatch: pytest.MonkeyPatch) -> None:
    """경고음을 실제로 기다리지 않는다.

    DANGER 스캔마다 0.6초씩 붙으면 테스트 전체가 두 배 넘게 느려진다. 부저가
    제대로 꺼지는지는 이 값을 직접 켜는 전용 테스트에서 확인한다.
    """
    import atm_controller

    monkeypatch.setattr(atm_controller, "WARN_BEEP_SECONDS", 0.0, raising=False)
