"""사전 점검 도구 자체가 죽지 않는지 확인한다.

진단 도구가 중간에 터지면 남은 항목을 아예 못 본다 — 카메라나 백엔드를 보러
왔는데 GPIO 줄에서 멈춰 버리면 도구가 제 일을 못 한 것이다. 실제로 실기기에서
`gpiozero.__version__`이 없어 4번 항목에서 죽었고, 5·6번은 보지도 못했다.
"""
from types import SimpleNamespace

import pytest

import check_hardware as ch


@pytest.fixture(autouse=True)
def _clear_problems():
    """점검 결과는 모듈 전역에 쌓인다 — 테스트마다 비운다."""
    ch.problems.clear()
    yield
    ch.problems.clear()


def test_version_lookup_survives_a_module_without_version() -> None:
    """`__version__`을 내놓지 않는 패키지가 있다 (gpiozero가 그렇다)."""
    assert ch.module_version(SimpleNamespace(), "이-런-패키지는-없다") == "버전 확인 불가"


def test_version_lookup_uses_dunder_when_present() -> None:
    assert ch.module_version(SimpleNamespace(__version__="4.9.0"), "opencv-python") == "4.9.0"


def test_one_broken_check_does_not_stop_the_rest(capsys: pytest.CaptureFixture[str]) -> None:
    """점검 하나가 터져도 실패로 기록하고 계속 간다."""
    done: list[str] = []

    def explodes() -> None:
        raise AttributeError("module 'gpiozero' has no attribute '__version__'")

    ch.run_check("GPIO", explodes)
    ch.run_check("카메라", lambda: done.append("카메라"))

    assert done == ["카메라"], "앞 점검이 터져도 다음 점검은 돌아야 한다"
    assert len(ch.problems) == 1
    output = capsys.readouterr().out
    assert "예기치 못한 오류" in output
    assert "__version__" in output, "원인을 그대로 보여 줘야 팀에 공유할 수 있다"


def test_run_check_passes_arguments_through() -> None:
    """--servo 같은 인자가 점검 함수까지 전달되어야 한다."""
    seen: list[bool] = []

    ch.run_check("GPIO", lambda move: seen.append(move), True)

    assert seen == [True]
    assert not ch.problems
