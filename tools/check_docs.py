#!/usr/bin/env python3
"""
문서 정합성 검사 (tools/check_docs.py) — 키트 제공

문서에 적힌 것과 **실제**가 어긋나지 않는지 확인합니다.

  1) "(NN항목)"이라고 적어 둔 자가 점검 개수가 실제 실행 결과와 같은지
  2) 문서끼리 거는 링크가 실제 존재하는 파일을 가리키는지
  3) 문서가 가리키는 파일·명령이 실제로 있는지

사람이 손으로 맞추면 반드시 어긋납니다. 커밋 전에 한 번 돌리세요.

    python tools/check_docs.py           # 링크·경로만 (빠름)
    python tools/check_docs.py --run     # 테스트를 실제로 돌려 개수까지 대조 (느림)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

#: 자가 점검 스크립트 — (문서에 적히는 이름, 실행 위치, 실행 명령)
SUITES: List[Tuple[str, str, List[str]]] = [
    ("smoke_test.py",        "backend",  [sys.executable, "smoke_test.py"]),
    ("conformance_test.py",  "backend",  [sys.executable, "conformance_test.py"]),
    ("test_slot_daemon.py",  "pi",       [sys.executable, "test_slot_daemon.py"]),
    ("test_team_examples.py", "pi",      [sys.executable, "test_team_examples.py"]),
    ("test_vision_config.py", "vision",  [sys.executable, "test_vision_config.py"]),
    ("test_study_focus.py",  "vision",   [sys.executable, "test_study_focus.py"]),
    ("wakeupEngine.test.ts", "frontend",
     ["node", "--experimental-strip-types", "scenarios/wakeupEngine.test.ts"]),
    ("studyEngine.test.ts",  "frontend",
     ["node", "--experimental-strip-types", "scenarios/studyEngine.test.ts"]),
]

#: 지워진 파일의 '옛 기록'이라 고치지 않는 곳 (파일, 그 줄에 들어 있는 이름)
HISTORICAL = {("PLATFORM.md", "test_mission.py")}

#: 검사할 문서
def documents() -> List[Path]:
    found = [p for p in ROOT.rglob("*.md")
             if "node_modules" not in p.parts and ".git" not in p.parts
             and "context_packs" not in p.parts]
    extra = ROOT / "tools" / "context_pack.py"
    if extra.exists():
        found.append(extra)
    return found


def run_suite(cwd: str, command: List[str]) -> int | None:
    """자가 점검을 돌려 '성공 N건'의 N을 돌려줍니다. 못 돌리면 None."""
    try:
        result = subprocess.run(command, cwd=ROOT / cwd, capture_output=True,
                                text=True, timeout=600)
    except Exception:
        return None
    match = None
    for match in re.finditer(r"성공 (\d+)건", result.stdout + result.stderr):
        pass                                    # 마지막 것이 총계입니다
    return int(match.group(1)) if match else None


def check_counts(actual: Dict[str, int]) -> List[str]:
    problems: List[str] = []
    for doc in documents():
        try:
            text = doc.read_text(encoding="utf-8")
        except Exception:
            continue
        relative = doc.relative_to(ROOT)
        for line_no, line in enumerate(text.split("\n"), 1):
            if any(name in line for file_name, name in HISTORICAL
                   if file_name in str(relative)):
                continue
            for name, count in actual.items():
                if name not in line:
                    continue
                written = [int(found.group(1)) for found in re.finditer(r"(\d+)\s*항목", line)]
                # 표에서는 마지막 칸에 숫자만 적습니다 (| … | 32 |)
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if line.lstrip().startswith("|") and cells[-1].isdigit():
                    written.append(int(cells[-1]))
                for number in written:
                    if number != count:
                        problems.append(
                            f"{relative}:{line_no}  {name} — 문서 {number}항목 / "
                            f"실제 {count}항목")
    return problems


def check_links() -> List[str]:
    problems: List[str] = []
    for doc in documents():
        if doc.suffix != ".md":
            continue
        try:
            text = doc.read_text(encoding="utf-8")
        except Exception:
            continue
        for link in re.findall(r"\]\((?!https?:|mailto:)([^)#]+)", text):
            target = (doc.parent / link.strip()).resolve()
            if not target.exists():
                problems.append(f"{doc.relative_to(ROOT)} → {link.strip()} (없는 파일)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="문서와 실제가 맞는지 검사합니다.")
    parser.add_argument("--run", action="store_true",
                        help="자가 점검을 실제로 돌려 개수까지 대조합니다 (몇 분 걸립니다)")
    args = parser.parse_args()

    print("=" * 68)
    print(" 문서 정합성 검사")
    print("=" * 68)

    problems: List[str] = []

    print("\n1. 문서끼리 거는 링크")
    print("-" * 68)
    link_problems = check_links()
    if link_problems:
        for item in link_problems:
            print(f"  [FAIL] {item}")
        problems += link_problems
    else:
        print("  [PASS] 모든 내부 링크가 실제 파일을 가리킵니다")

    print("\n2. 문서에 적힌 자가 점검 항목 수")
    print("-" * 68)
    if not args.run:
        print("  [건너뜀] --run 을 붙이면 실제로 돌려서 대조합니다")
    else:
        actual: Dict[str, int] = {}
        for name, cwd, command in SUITES:
            count = run_suite(cwd, command)
            if count is None:
                print(f"  [건너뜀] {name} — 실행할 수 없습니다 (환경 미설치)")
                continue
            actual[name] = count
            print(f"           {name:24} 실제 {count}항목")
        count_problems = check_counts(actual)
        if count_problems:
            print()
            for item in count_problems:
                print(f"  [FAIL] {item}")
            problems += count_problems
        else:
            print("  [PASS] 문서의 모든 항목 수가 실제와 일치합니다")

    print("\n" + "=" * 68)
    if problems:
        print(f" 어긋난 곳 {len(problems)}군데 — 문서를 고치세요")
        print("=" * 68)
        return 1
    print(" 문서와 실제가 일치합니다")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
