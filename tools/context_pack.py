"""
컨텍스트 팩 생성기 (tools/context_pack.py) — 채팅형 AI에 붙여넣을 파일 하나를 만듭니다.
=============================================================================
왜 필요한가
-----------
우리 학생들은 학교에서 허용한 채팅형 생성형 AI로 바이브 코딩을 합니다.
채팅창에는 **폴더 구조를 유지한 채 수십 개 파일을 올릴 수 없습니다.**
그런데 AI가 우리 코드를 모르면 엉뚱한 답을 줍니다.

이 스크립트는 **지금 내 담당 일에 꼭 필요한 것만** 골라 마크다운 파일 하나로 묶습니다.
그 파일 하나만 채팅창에 올리면(또는 붙여넣으면) AI가 우리 프로젝트를 이해합니다.

  · 내가 고치는 파일    → 전문을 담습니다
  · 내가 호출만 하는 키트 → 사용법(타입·함수 이름)만 담습니다
  · 우리 팀 현재 배치표  → 지금 내 파일에서 직접 읽어 담습니다

쓰는 방법 (저장소 최상위 폴더에서)
---------------------------------
    python tools/context_pack.py pi          # 라즈베리파이 담당
    python tools/context_pack.py frontend    # 프론트엔드 담당
    python tools/context_pack.py vision      # 영상인식 담당
    python tools/context_pack.py all         # 셋 다

만들어진 파일은 `context_packs/` 폴더에 들어갑니다 (git에 올리지 않습니다).
코드를 고친 뒤에는 **다시 실행해서 새로 만드세요** — 팩은 만든 순간의 사진입니다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "context_packs"

ROLES = ("pi", "frontend", "vision")

#: 모든 팩 맨 앞에 붙는 규칙. AI가 이것을 어기면 4팀이 모두 깨집니다.
RULES = """\
## 지켜야 할 제약 (이것을 어기면 4개 팀이 모두 깨집니다)

우리는 고등학교 IoT 팀 프로젝트이고, 4개 팀(wakeup · classroom · study · subway)이
**공통 "IoT 개발 플랫폼 키트"** 위에서 각자 2차 개발을 하고 있습니다.

- 센서·액추에이터는 **고정 슬롯 20개**로만 부릅니다:
  `sensor_01`~`sensor_10`, `actuator_01`~`actuator_10`.
  팀 부품 이름(예: `servo_door`)을 코드에 넣지 않습니다 — 이름은 DB의 `label`로만 존재합니다.
- **다음 파일은 고치지 않습니다** (4팀 공통 코드):
  `backend/` 전체, `backend/db/` 스키마, `vision/main.py`, `vision/camera.py`,
  `vision/detectors/base.py`, `vision/detectors/__init__.py`, `vision/detectors/objects.py`
- 우리가 고치는 곳은 **다섯 군데뿐**입니다:
  1. `pi/slot_map.py` — 부품 배치표
  2. `frontend/` — 화면과 시나리오
  3. `vision/detectors/<우리팀>.py` — 감지 방법
  4. 대시보드 자동화 규칙 (코드 아님)
  5. 대시보드 영상인식 설정 (코드 아님)

### 계약
- 액추에이터: 백엔드는 `desired_state`만 씁니다. `current_state`는 **하드웨어가 보고할 때만** 바뀝니다.
- `desired_state`는 항상 문자열(`"on"` / `"off"` / `"move"`), 세부 값은 항상 `value` 객체(`{"angle": 90}`).
- 숫자 센서는 반드시 `{"value": 24.5}` 형식으로 보고합니다 (그래야 차트가 자동으로 그려집니다).
- 라운드·승수가 있는 게임 로직은 백엔드에 만들지 않고 `frontend/scenarios/`에 씁니다.
- 검출기는 "무엇이 보이는가"만 말하고 승패 판정은 하지 않습니다.
- DB가 꺼져 있어도 시스템은 동작해야 합니다 (기록만 저장되지 않음).

### 기술 스택
- 백엔드 FastAPI(Python 3.12) + WebSocket · DB MariaDB
- 프론트엔드 Next.js 16 (React 19, TypeScript, **Tailwind CSS v4**)
  ⚠️ **v4입니다. v3 방식은 조용히 실패합니다** (빌드는 되는데 스타일이 안 먹습니다):
    · `tailwind.config.js`를 쓰지 않습니다 — 설정은 `app/globals.css`의 `@theme`에 씁니다
    · 색·모서리 토큰을 `:root`에 적으면 유틸리티 클래스가 **만들어지지 않습니다**.
      반드시 `@theme { --color-brand: ... }` 안에 적어야 `bg-brand`가 생깁니다
    · 실행 중에 값을 바꾸려면 `@theme inline { --color-brand: var(--ui-brand); }` 로 쓰고
      `--ui-brand`를 `:root` / `[data-style="..."]`에서 바꿉니다
- 영상인식 YOLOv8 ONNX(onnxruntime, ultralytics 미사용) + MediaPipe, OpenCV, Pillow(한글)
  ⛔ `dlib` · `face_recognition`은 쓰지 않습니다 (Windows 컴파일 오류)
- 하드웨어 라즈베리파이 5 (gpiozero + lgpio). PC에서는 자동으로 흉내내기로 대체됩니다.
"""

#: 모든 팩 맨 뒤에 붙는 답변 형식 요구. 학생이 손으로 붙여넣어야 하므로 중요합니다.
HOW_TO_ANSWER = """\
## 답변은 이렇게 해 주세요 (저는 손으로 복사해서 붙여넣습니다)

저는 AI 에이전트 도구를 쓰지 않습니다. **제가 직접 파일을 열어 붙여넣습니다.**
그래서 아래 형식을 꼭 지켜 주세요.

1. **바꿀 파일이 적을 때**: 파일마다 코드블록 하나를 주고, 맨 첫 줄에 경로를 주석으로 적어 주세요.
   ```python
   # pi/slot_map.py  (파일 전체를 이 내용으로 바꾸세요)
   ...
   ```
2. **파일이 길어서 전체를 주기 어려울 때**: "어느 함수/블록을 무엇으로 바꾸는지"를
   **바꾸기 전 코드 → 바꾼 뒤 코드** 순서로 보여 주세요. diff 기호(`+`/`-`)는 쓰지 마세요
   (그대로 붙여넣으면 문법 오류가 납니다).
3. 새 파일을 만들어야 하면 **경로와 파일명을 분명히** 말해 주세요.
4. 한 번에 **파일 3개 이하**만 바꿔 주세요. 많으면 제가 붙여넣다가 틀립니다.
5. 마지막에 **제가 확인할 명령**을 알려 주세요 (아래 중 해당되는 것).
   ```
   cd backend  && python smoke_test.py            # 32항목
   cd backend  && python conformance_test.py      # 75항목
   cd pi       && python daemon.py --check
   cd pi       && python test_slot_daemon.py      # 39항목
   cd vision   && python test_vision_config.py    # 45항목
   cd vision   && python test_study_focus.py      # 63항목 (study 집중도)
   cd frontend && npx eslint . && npm run build
   cd frontend && grep -o '\.bg-brand{[^}]*}' .next/static/chunks/*.css   # 토큰이 살아 있는지
   ```
6. 위 "지켜야 할 제약"의 **고치지 않는 파일을 고쳐야 한다면, 고치지 말고 먼저 이유를 설명**해 주세요.
   거의 항상 다른 방법이 있습니다.
"""


# ---------------------------------------------------------------------------
# 파일을 읽어 코드블록으로 만드는 도구들
# ---------------------------------------------------------------------------

LANG_OF = {".py": "python", ".ts": "typescript", ".tsx": "tsx",
           ".json": "json", ".sql": "sql", ".md": "markdown"}


def read_lines(path: Path) -> Optional[List[str]]:
    """파일을 줄 목록으로 읽습니다. 없으면 None (팀마다 없는 파일이 있습니다)."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def code_block(path: Path, lines: List[str], note: str = "",
               line_range: Optional[Tuple[int, int]] = None) -> str:
    """파일 하나를 제목 + 코드블록으로 만듭니다."""
    relative = path.relative_to(ROOT).as_posix()
    lang = LANG_OF.get(path.suffix, "")
    if line_range:
        start, end = line_range
        body = "\n".join(lines[start - 1:end])
        head = f"### `{relative}` ({start}~{end}번째 줄)"
    else:
        body = "\n".join(lines)
        head = f"### `{relative}` (전문 {len(lines)}줄)"
    parts = [head]
    if note:
        parts.append(f"> {note}")
    parts.append(f"```{lang}\n{body}\n```")
    return "\n\n".join(parts)


def _block_end(lines: List[str], start: int) -> int:
    """
    `start`번째 줄에서 시작하는 선언이 끝나는 줄 번호를 돌려줍니다 (0-기준, 포함).

    중괄호·대괄호 개수를 세어 균형이 맞는 곳까지 갑니다. 타입 선언을 중간에서
    자르면 AI가 구조를 알 수 없으므로(예: `interface Slot {`만 보이면 쓸모없음)
    타입은 꼭 전문으로 담아야 합니다.
    """
    opener = lines[start]
    if not re.search(r"[{\[]", opener):
        # 중괄호가 없는 선언 — 유니온 타입처럼 여러 줄에 걸칠 수 있습니다.
        #   export type ControlType =
        #     | "onoff"
        #     | "pulse";
        if opener.rstrip().endswith(";"):
            return start
        for index in range(start + 1, len(lines)):
            if lines[index].rstrip().endswith(";"):
                return index
            if not lines[index].strip():          # 빈 줄이면 선언이 끝난 것으로 봅니다
                return index - 1
        return len(lines) - 1

    depth = 0
    for index in range(start, len(lines)):
        depth += lines[index].count("{") + lines[index].count("[")
        depth -= lines[index].count("}") + lines[index].count("]")
        if depth <= 0:
            return index
    return len(lines) - 1


def signatures_only(path: Path, lines: List[str], note: str = "") -> str:
    """
    **타입은 전문, 함수는 첫 줄만** 담습니다.

    키트가 주는 파일은 고치지 않으므로 구현 수백 줄은 필요 없습니다. 다만 타입은
    "무엇을 넘기고 무엇을 돌려받는가"이므로 반드시 전문이 있어야 합니다.
    """
    relative = path.relative_to(ROOT).as_posix()
    picked: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        is_type = re.match(r"\s*export (interface|type|const|enum)\b", line)
        is_func = re.match(r"\s*export (default )?(function|async function)\b", line)
        is_py = re.match(r"\s*(def|class) \w+", line)

        if is_type:
            end = _block_end(lines, index)
            picked.extend(l.rstrip() for l in lines[index:end + 1])
            picked.append("")
            index = end + 1
            continue
        if is_func or is_py:
            # 여러 줄에 걸친 매개변수 목록도 한 덩어리로 담고, 본문은 생략합니다.
            signature = [line]
            cursor = index
            while cursor < len(lines) - 1 and not re.search(r"[{:]\s*$", lines[cursor].rstrip()):
                cursor += 1
                signature.append(lines[cursor].rstrip())
            picked.extend(signature)
            picked.append("    … 구현 생략 …" if is_py else "  // … 구현 생략 …")
            picked.append("}" if not is_py else "")
            picked.append("")
            index = cursor + 1
            continue
        index += 1

    body = "\n".join(picked).rstrip() if picked else "(공개된 이름이 없습니다)"
    parts = [f"### `{relative}` — 타입은 전문, 함수는 이름만 "
             f"(전체 {len(lines)}줄 중 필요한 것만 · 고치지 않습니다)"]
    if note:
        parts.append(f"> {note}")
    parts.append(f"```{LANG_OF.get(path.suffix, '')}\n{body}\n```")
    return "\n\n".join(parts)


def missing_note(relative: str, why: str) -> str:
    return f"### `{relative}` — 파일이 없습니다\n\n> {why}"


# ---------------------------------------------------------------------------
# 우리 팀 현재 상태 (학생이 고친 내용을 그대로 읽습니다)
# ---------------------------------------------------------------------------

def current_slots() -> str:
    """`pi/slot_map.py`의 SLOTS를 읽어 사람이 읽는 표로 만듭니다."""
    slot_map = ROOT / "pi" / "slot_map.py"
    if not slot_map.exists():
        return ("> `pi/slot_map.py`가 아직 없습니다. "
                "`pi/examples/`에서 우리 팀 예시를 복사하세요.")

    sys.path.insert(0, str(ROOT / "pi"))
    try:
        import importlib
        module = importlib.import_module("slot_map")
        importlib.reload(module)            # 고친 내용이 바로 반영되도록
        slots = getattr(module, "SLOTS", {})
    except Exception as exc:                # 오타가 있어도 팩 생성은 계속되어야 합니다
        return f"> 배치표를 읽지 못했습니다 ({exc}). `python pi/daemon.py --check`로 확인하세요."
    finally:
        sys.path.pop(0)

    if not isinstance(slots, dict) or not slots:
        return "> 배치표가 비어 있습니다."

    rows = ["| 슬롯 | 라벨 | 종류 | 드라이버 | 제어 방식 | 핀 |",
            "|---|---|---|---|---|---|"]
    for slot_id in sorted(slots, key=lambda s: (s.split("_")[0], s)):
        config = slots[slot_id] if isinstance(slots[slot_id], dict) else {}
        pin = config.get("pin", config.get("pins", config.get("trigger_pin", "—")))
        rows.append(
            f"| `{slot_id}` | {config.get('label', '—')} | {config.get('kind', '—')} "
            f"| `{config.get('driver', '—')}` | {config.get('control_type', '—')} | {pin} |"
        )
    return "\n".join(rows)


def team_detectors() -> List[Path]:
    """`vision/detectors/`에서 팀이 추가한 검출기 파일만 고릅니다."""
    kit_files = {"base.py", "__init__.py", "objects.py"}
    folder = ROOT / "vision" / "detectors"
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.py")
                  if p.name not in kit_files and not p.name.startswith("_"))


def driver_names() -> str:
    """쓸 수 있는 드라이버 목록을 실제 폴더에서 읽습니다."""
    folder = ROOT / "pi" / "drivers"
    if not folder.exists():
        return "(drivers 폴더를 찾지 못했습니다)"
    names = sorted(p.stem for p in folder.glob("*.py")
                   if p.stem not in {"base", "gpio", "__init__"})
    return ", ".join(f"`{n}`" for n in names)


def coco_labels() -> str:
    """사물 탐지가 아는 이름 목록 (감지 대상을 고를 때 씁니다)."""
    objects = ROOT / "vision" / "detectors" / "objects.py"
    lines = read_lines(objects)
    if not lines:
        return "(objects.py를 찾지 못했습니다)"
    text = "\n".join(lines)
    match = re.search(r"COCO_CLASSES\s*=\s*\[(.*?)\]", text, re.S)
    if not match:
        return "(목록을 찾지 못했습니다)"
    names = re.findall(r'"([^"]+)"', match.group(1))
    return ", ".join(names)


# ---------------------------------------------------------------------------
# 역할별 팩
# ---------------------------------------------------------------------------

def pack_pi() -> str:
    sections = [
        "# 컨텍스트 팩 — 라즈베리파이 담당",
        "",
        "이 파일은 제 프로젝트에서 **라즈베리파이 담당이 필요한 부분만** 묶은 것입니다.",
        "폴더 전체가 아니라 제가 고치는 파일과 계약만 담겨 있습니다.",
        "", RULES, "",
        "## 우리 팀 현재 배치표 (`pi/slot_map.py`에서 읽었습니다)",
        "", current_slots(), "",
        f"쓸 수 있는 드라이버: {driver_names()}",
        "",
        "## 제가 고치는 파일",
    ]

    slot_map = ROOT / "pi" / "slot_map.py"
    lines = read_lines(slot_map)
    if lines:
        sections.append(code_block(
            slot_map, lines,
            "★ 제가 고치는 유일한 파일입니다. 부품을 추가하면 줄을 추가, 떼면 줄을 지웁니다."))
    else:
        sections.append(missing_note(
            "pi/slot_map.py",
            "아직 없습니다. `pi/examples/`에서 우리 팀 예시를 복사해 만듭니다."))

    sections += ["", "## 참고 — 키트가 주는 계약 (고치지 않습니다)"]

    base = ROOT / "pi" / "drivers" / "base.py"
    base_lines = read_lines(base)
    if base_lines:
        sections.append(code_block(
            base, base_lines,
            "새 드라이버를 만들 때 지켜야 하는 계약입니다. 이 파일 자체는 고치지 않습니다."))

    example = ROOT / "pi" / "drivers" / "digital_out.py"
    example_lines = read_lines(example)
    if example_lines:
        sections.append(code_block(
            example, example_lines,
            "가장 단순한 드라이버 본보기입니다. 새 드라이버는 이 구조를 따릅니다."))

    sections += ["", HOW_TO_ANSWER]
    return "\n".join(sections)


def pack_frontend() -> str:
    sections = [
        "# 컨텍스트 팩 — 프론트엔드 담당",
        "",
        "이 파일은 제 프로젝트에서 **프론트엔드 담당이 필요한 부분만** 묶은 것입니다.",
        "키트가 주는 SDK는 구현을 빼고 **쓰는 법만** 담았습니다 (고치지 않으니까요).",
        "화면 디자인·배치만 고칠 때는 이 팩 대신 `python tools/merge_ui.py`로 만든 "
        "화면 묶음을 씁니다 (docs/08).",
        "", RULES, "",
        "## 화면은 셋입니다",
        "",
        "| 파일 | 주소 | 무엇 |",
        "|---|---|---|",
        "| `app/page.tsx` | `/` | ★ 우리 팀 화면 — 4팀 공통 출발점, 제가 고치는 곳 |",
        "| `app/kit/page.tsx` | `/kit` | 키트 제공 (하드웨어 구성·자동화 규칙·영상인식 설정) |",
        "| `app/wakeup/page.tsx` | `/wakeup` | wakeup 팀 완성 화면 — 본보기 |",
        "",
        "화면 제목은 코드가 아니라 `frontend/.env.local`의 `NEXT_PUBLIC_TEAM_NAME`에서 옵니다.",
        "",
        "## 우리 팀 현재 배치표 (화면에 이 슬롯들이 카드로 나옵니다)",
        "", current_slots(), "",
        "## 제가 고치는 파일",
    ]

    page = ROOT / "frontend" / "app" / "page.tsx"
    page_lines = read_lines(page)
    if page_lines:
        sections.append(code_block(
            page, page_lines,
            "★ 우리 팀 화면(`/`)입니다. 4팀 공통 출발점이며, 여기를 우리 팀 화면으로 바꿉니다. "
            "`ScenarioPlaceholder`는 시나리오를 만들면 지우는 안내 카드입니다."))

    # 팀이 이미 만든 시나리오가 있으면 함께 담습니다 (wakeup 본보기는 제외)
    scenario_dir = ROOT / "frontend" / "scenarios"
    mine = sorted(f for f in scenario_dir.glob("*.ts")
                  if scenario_dir.exists()
                  and not f.name.startswith("wakeup")
                  and not f.name.startswith("useWakeup")
                  and not f.name.endswith(".test.ts")) if scenario_dir.exists() else []
    for path in mine:
        lines = read_lines(path)
        if lines:
            sections.append(code_block(path, lines, "★ 우리 팀이 만든 시나리오입니다."))

    sections += ["", "## 제가 호출하는 키트 SDK (쓰는 법만 — 고치지 않습니다)"]

    scenario = ROOT / "frontend" / "lib" / "scenario.ts"
    scenario_lines = read_lines(scenario)
    if scenario_lines:
        # 이벤트 타입과 ScenarioApi 선언부까지만 담으면 쓰는 법이 전부 드러납니다.
        # useScenario() 선언 줄 '앞'에서 끊어야 열린 중괄호로 끝나지 않습니다.
        hook_line = next((i for i, line in enumerate(scenario_lines, start=1)
                          if line.startswith("export function useScenario")), 127)
        sections.append(code_block(
            scenario, scenario_lines,
            "useScenario()가 돌려주는 것 전부입니다. 아래 구현 부분은 생략했습니다.",
            line_range=(1, max(1, hook_line - 1))))

    slots_lib = ROOT / "frontend" / "lib" / "slots.ts"
    slots_lines = read_lines(slots_lib)
    if slots_lines:
        sections.append(signatures_only(
            slots_lib, slots_lines,
            "슬롯 타입과 도움 함수들입니다. Slot 구조와 함수 이름만 알면 됩니다."))

    sections += ["", "## 본보기 — wakeup 팀 완성 화면 (우리 팀 것이 아니면 구조만 참고)",
                 "",
                 "`/wakeup` 주소에서 직접 볼 수 있는 화면입니다. 시나리오가 있는 화면이 "
                 "어떻게 생겼는지 보여 주는 본보기이고, 베껴 쓰는 것이 아닙니다."]

    engine = ROOT / "frontend" / "scenarios" / "wakeupEngine.ts"
    engine_lines = read_lines(engine)
    if engine_lines:
        sections.append(signatures_only(
            engine, engine_lines,
            "판정 규칙을 React 없는 순수 함수로 쓰면 브라우저 없이 테스트할 수 있습니다. "
            "우리 팀 시나리오도 이 구조로 만듭니다 (전문이 필요하면 따로 올리겠습니다)."))

    wakeup_page = ROOT / "frontend" / "app" / "wakeup" / "page.tsx"
    wakeup_lines = read_lines(wakeup_page)
    if wakeup_lines:
        # 화면 컴포넌트는 '구조'가 핵심이라 시그니처만 담으면 쓸모없습니다.
        sections.append(code_block(
            wakeup_page, wakeup_lines,
            "시나리오 훅을 받아 화면에 그리는 방법을 보세요 — `useWakeup()` 한 줄로 상태를 받고, "
            "`<SlotGrid>`는 그대로 두고, 팀 카드만 얹었습니다. 우리 팀 화면도 이 모양이 됩니다."))

    sections += [
        "",
        "## 기억할 것",
        "",
        "- 슬롯 카드는 `<SlotGrid slots={slots} onControl={setActuator} />` 한 줄이면 자동으로 그려집니다.",
        "  부품이 바뀌어도 이 줄은 고치지 않습니다 (위젯은 `control_type`이 결정합니다).",
        "- `onSensor` · `onVision` · `onSlotChange`는 **구독 해지 함수**를 돌려줍니다.",
        "  `useEffect`에서 등록했으면 정리 함수로 해지하세요.",
        "- 브라우저 탭을 닫으면 시나리오가 멈춥니다. 화면 없이 동작해야 하는 것은",
        "  `serverTimer()`나 대시보드 자동화 규칙으로 백엔드에 맡깁니다.",
        "", HOW_TO_ANSWER,
    ]
    return "\n".join(sections)


def pack_vision() -> str:
    sections = [
        "# 컨텍스트 팩 — 영상인식 담당",
        "",
        "이 파일은 제 프로젝트에서 **영상인식 담당이 필요한 부분만** 묶은 것입니다.",
        "vision은 공통 루프 + 검출기 플러그인 구조이고, 제가 고치는 것은 검출기 파일뿐입니다.",
        "", RULES, "",
        "## vision 폴더 구조",
        "",
        "```",
        "vision/",
        "  main.py                  공통 — 카메라를 열고, 검출기를 돌리고, 보내고, 보여 줌 (고치지 않음)",
        "  camera.py                공통 — USB 웹캠 / Pi Camera 자동 선택 (고치지 않음)",
        "  detectors/",
        "    base.py                공통 — 검출기 계약 (고치지 않음)",
        "    __init__.py            공통 — 폴더를 훑어 자동으로 찾는 로더 (고치지 않음)",
        "    objects.py             공통 — 사물 탐지(YOLO). 4팀이 같이 씀 (고치지 않음)",
        "    <우리팀>.py             ★ 제가 만드는 파일 — 파일 하나 = 검출기 하나",
        "    _<보조>.py              `_`로 시작하면 로더가 검출기로 세지 않음",
        "```",
        "",
        "검출기를 추가하면 **백엔드와 대시보드는 고치지 않습니다.** 검출기가 부팅할 때",
        "자기 이름과 라벨을 서버에 신고하고(`POST /api/v1/vision/detectors`),",
        "설정 화면과 규칙 편집기가 그 신고를 보고 자동으로 채워집니다.",
        "",
        "## 제가 지켜야 하는 계약 (고치지 않습니다)",
    ]

    base = ROOT / "vision" / "detectors" / "base.py"
    base_lines = read_lines(base)
    if base_lines:
        sections.append(code_block(
            base, base_lines,
            "새 검출기는 이 파일의 FrameDetector를 상속한 `Detector` 클래스를 둡니다."))

    sections += ["", "## 본보기 — 이미 있는 검출기"]

    example = ROOT / "vision" / "detectors" / "hands_rps.py"
    example_lines = read_lines(example)
    if example_lines:
        sections.append(code_block(
            example, example_lines,
            "wakeup 팀 손동작 검출기입니다. 라이브러리가 없을 때 disable()로 "
            "자기만 꺼지는 부분을 보세요 — 사물 감지는 계속 돌아야 합니다."))

    mine = [f for f in team_detectors() if f.name != "hands_rps.py"]
    if mine:
        # 폴더에 있는 팀 검출기를 담습니다. 우리 팀 것이면 고칠 파일이고,
        # 다른 팀 것이면 본보기입니다(지워도 됩니다) — AI가 헷갈리지 않게 그대로 적습니다.
        sections += ["", "## 폴더에 있는 팀 검출기",
                     "",
                     "우리 팀 것이면 **제가 고치는 파일**이고, 다른 팀 것이면 **본보기**입니다",
                     "(지워도 되지만 구조를 볼 때 편해서 남겨 둡니다)."]
        for path in mine:
            lines = read_lines(path)
            if lines:
                sections.append(code_block(path, lines))

    sections += [
        "",
        "## 사물 탐지가 아는 이름 (감지 대상을 고를 때)",
        "",
        "이 이름들은 대시보드 `/kit` → 영상인식 설정에서 고릅니다. **코드로 적지 않습니다.**",
        "",
        f"```\n{coco_labels()}\n```",
        "",
        "이 목록에 없는 것(손동작·자세·표정 등)을 감지하려면 **검출기를 새로 만듭니다.**",
        "", HOW_TO_ANSWER,
    ]
    return "\n".join(sections)


BUILDERS = {"pi": pack_pi, "frontend": pack_frontend, "vision": pack_vision}


# ---------------------------------------------------------------------------
# 안전장치 — 팩은 외부 AI 서비스에 올라갑니다
# ---------------------------------------------------------------------------

#: 비밀값처럼 보이는 것. 실수로 코드에 키를 적어 둔 경우를 잡습니다.
SECRET_PATTERNS = [
    # KEY = "긴 문자열" 꼴 (환경변수 이름에 KEY·SECRET·TOKEN·PASSWORD가 들어간 것)
    re.compile(r"""(?ix)
        \b([A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD)[A-Z0-9_]*)
        \s*[:=]\s*
        (['"]?)([^\s'"#]{12,})\2
    """),
]

#: 예시·빈 값은 비밀이 아닙니다 (.env.example에 들어 있는 안내 문구)
SAFE_VALUES = re.compile(
    r"(?i)(your_|여기에|example|changeme|placeholder|xxx+|\.\.\.|<[^>]+>)")


def scrub_secrets(text: str, role: str) -> Tuple[str, List[str]]:
    """
    비밀값처럼 보이는 것을 지우고, 무엇을 지웠는지 알려 줍니다.

    학생이 이 팩을 외부 채팅형 AI 서비스에 올립니다. 한 번 올라간 것은
    되돌릴 수 없으므로, 키가 섞여 있으면 **올리기 전에** 여기서 걸러야 합니다.
    """
    found: List[str] = []
    for pattern in SECRET_PATTERNS:
        def replace(match: "re.Match[str]") -> str:
            name, quote, value = match.group(1), match.group(2), match.group(3)
            if SAFE_VALUES.search(value):
                return match.group(0)          # 예시 문구는 그대로 둡니다
            found.append(name)
            return f"{name} = {quote}<비밀값이라 지웠습니다>{quote}"
        text = pattern.sub(replace, text)
    return text, found


def build(role: str) -> Tuple[Path, List[str]]:
    text = BUILDERS[role]()
    text, scrubbed = scrub_secrets(text, role)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"context_pack_{role}.md"
    out.write_text(text, encoding="utf-8")
    return out, scrubbed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="채팅형 AI에 올릴 컨텍스트 팩을 만듭니다.")
    parser.add_argument("role", nargs="?", default="all",
                        choices=(*ROLES, "all"),
                        help="pi | frontend | vision | all (기본: all)")
    args = parser.parse_args()

    roles = ROLES if args.role == "all" else (args.role,)

    print("=" * 68)
    print(" 컨텍스트 팩 만들기 — 채팅형 AI에 올릴 파일 하나")
    print("=" * 68)

    warned = False
    for role in roles:
        out, scrubbed = build(role)
        text = out.read_text(encoding="utf-8")
        lines = len(text.splitlines())
        kb = len(text.encode("utf-8")) / 1024
        print(f"  [완료] {out.relative_to(ROOT).as_posix()}  "
              f"({lines}줄, {kb:.0f}KB)")
        if scrubbed:
            warned = True
            print(f"     ⚠ 비밀값처럼 보이는 것을 지웠습니다: {', '.join(sorted(set(scrubbed)))}")
            print("       코드에 키를 직접 적어 두었다면 .env로 옮기세요.")

    print()
    if warned:
        print(" ⚠ 위 경고를 먼저 해결하세요. 팩은 외부 AI 서비스에 올라갑니다.")
        print()
    print(" 쓰는 방법")
    print("  1. 위 파일을 학교에서 허용한 채팅형 AI에 올리거나 붙여넣습니다.")
    print("  2. 그 아래에 하고 싶은 일을 한 문단으로 적습니다.")
    print("  3. AI가 준 코드를 직접 파일에 붙여넣습니다.")
    print("  4. 팩 맨 끝에 적힌 자가 점검 명령을 돌려 확인합니다.")
    print()
    print(" 🎨 화면(UI)을 고칠 때는 python tools/merge_ui.py 로 화면 묶음을 만드세요 (docs/08).")
    print(" ⚠️ 코드를 고친 뒤에는 이 명령을 다시 실행해서 팩을 새로 만드세요.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
