#!/usr/bin/env python3
"""
화면 파일 묶기 (tools/merge_ui.py) — 프론트엔드 화면 소스를 MD 파일 하나로 합칩니다.
=============================================================================
왜 필요한가
-----------
우리는 AI 에이전트 도구를 쓰지 않습니다. 채팅형 생성형 AI는 우리 폴더를 볼 수 없으므로
**AI가 볼 것을 우리가 골라서** 보여 줘야 합니다. 이것이 컨텍스트 엔지니어링입니다.

이 스크립트는 고칠 화면(`page.tsx`)에서 시작해 그 화면이 **실제로 import하는 파일**을
따라가며 MD 파일 하나로 묶습니다.

  · 우리가 고치는 화면 파일 → 전문      (화면, components/team/, globals.css, layout.tsx)
  · 호출만 하는 키트·로직   → 쓰는 법만 (타입은 전문, 함수는 이름과 매개변수)
  · 제약·설치된 패키지·디자인 토큰·답변 형식 → 자동으로 붙습니다
  · .env 같은 비밀 파일     → 절대 넣지 않습니다 (비밀값처럼 보이는 문자열도 지웁니다)

쓰는 방법 (저장소 최상위 폴더에서)
---------------------------------
    python tools/merge_ui.py                  # 우리 팀 화면 (/ = app/page.tsx)
    python tools/merge_ui.py --page study     # /study 화면
    python tools/merge_ui.py --add components/team/SeatCard.tsx   # 파일을 더 넣기
    python tools/merge_ui.py --list           # 묶지 않고 무엇이 들어갈지만 보기
    python tools/merge_ui.py --all            # 화면 파일 전부 (크니까 꼭 필요할 때만)

만들어진 파일은 `context_packs/ui_<화면>.md`입니다 (git에 올라가지 않습니다).
코드를 고친 뒤에는 **다시 실행해서 새로 만드세요** — 묶음은 만든 순간의 사진입니다.
AI의 답을 코드에 넣을 때는 `tools/apply_ui.py`를 씁니다 (docs/08 가이드).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
FRONTEND = ROOT / "frontend"
OUT_DIR = ROOT / "context_packs"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from context_pack import scrub_secrets  # noqa: E402 — 다른 팩과 같은 비밀값 거름망

#: 4팀 공통 키트 — 고치지 않습니다. 쓰는 법만 담습니다.
KIT_PREFIXES = ("lib/", "components/kit/", "app/kit/")
#: 설정 파일 — 고치지 않습니다.
CONFIG_FILES = frozenset({
    "package.json", "package-lock.json", "next.config.ts", "next.config.js",
    "next.config.mjs", "tsconfig.json", "eslint.config.mjs", "postcss.config.mjs",
    "next-env.d.ts",
})
#: 묶음에 담을 수 있는 파일 종류
CODE_SUFFIXES = (".tsx", ".ts", ".css")
#: 모든 화면에 영향을 주므로 언제나 전문을 담습니다.
ALWAYS_FULL = ("app/layout.tsx", "app/globals.css")
#: 묶음이 이보다 크면 경고합니다 (무료 채팅에서 뒷부분이 잘릴 수 있습니다).
WARN_KB = 120

ROLE_LABEL = {
    "ui": "★ 고치는 파일",
    "logic": "팀 로직",
    "kit": "키트 — 고치지 않음",
}

PACKAGE_NOTES = {
    "next": "Next.js 16 (App Router)",
    "react": "React 19",
    "react-dom": "React 19",
    "lucide-react": "아이콘 — https://lucide.dev 에서 이름을 찾아 import",
    "tailwindcss": "Tailwind CSS v4 — 설정은 app/globals.css의 @theme",
    "@tailwindcss/postcss": "Tailwind v4 빌드 도구",
    "typescript": "TypeScript",
    "eslint": "린트 (npx eslint .)",
    "eslint-config-next": "Next.js 린트 규칙 (React 19 규칙 포함)",
}


# ---------------------------------------------------------------------------
# 파일 분류
# ---------------------------------------------------------------------------

def rel_of(path: Path) -> str:
    """frontend/ 기준 경로 (예: app/page.tsx)."""
    return path.resolve().relative_to(FRONTEND.resolve()).as_posix()


def role_of(rel: str) -> str:
    """frontend/ 기준 경로의 역할: secret · config · build · test · kit · logic · ui"""
    name = rel.rsplit("/", 1)[-1]
    if name.startswith(".env"):
        return "secret"
    if rel.startswith(("node_modules/", ".next/")):
        return "build"
    if rel in CONFIG_FILES:
        return "config"
    if rel.endswith((".test.ts", ".test.tsx")):
        return "test"
    if rel.startswith(KIT_PREFIXES):
        return "kit"
    if rel.startswith("scenarios/"):
        return "logic"
    return "ui"


def find_pages() -> "OrderedDict[str, Path]":
    """app/ 아래의 page.tsx를 주소(route)별로 찾습니다. `/`가 맨 앞입니다."""
    app = FRONTEND / "app"
    found: List[Tuple[str, Path]] = []
    if app.exists():
        for page in app.rglob("page.tsx"):
            parts = [p for p in page.parent.relative_to(app).parts
                     if not (p.startswith("(") and p.endswith(")"))]   # (그룹) 폴더는 주소에 안 나옵니다
            found.append(("/" + "/".join(parts), page))
    found.sort(key=lambda item: (item[0] != "/", item[0]))
    return OrderedDict(found)


def page_kind(route: str) -> str:
    if route == "/":
        return "★ 우리 팀 화면 (4팀 공통 출발점)"
    if route == "/kit" or route.startswith("/kit/"):
        return "키트 제공 — 고치지 않음"
    return "팀 화면 (다른 팀 것이면 본보기)"


def pick_page(value: str, pages: "OrderedDict[str, Path]") -> Tuple[str, Path]:
    """`--page` 값(/, home, study, /study, app/study/page.tsx)을 주소로 바꿉니다."""
    text = value.strip().replace("\\", "/")
    if text.endswith("page.tsx"):
        wanted = (ROOT / text) if text.startswith("frontend/") else (FRONTEND / text)
        for route, page in pages.items():
            if page.resolve() == wanted.resolve():
                return route, page
        raise LookupError(text)
    route = "/" if text.lower() in ("", "/", "home", "main", "index") else "/" + text.strip("/")
    if route not in pages:
        raise LookupError(text)
    return route, pages[route]


def out_name(routes: Sequence[str], everything: bool) -> str:
    if everything:
        return "ui_all.md"
    route = routes[0]
    slug = "home" if route == "/" else re.sub(r"[^\w-]+", "_", route.strip("/"))
    return f"ui_{slug}.md"


# ---------------------------------------------------------------------------
# import 따라가기
# ---------------------------------------------------------------------------

#: 맨 앞 칸에서 시작하는 import 문 (주석 속 예시 코드는 들여쓰기가 있어 걸리지 않습니다)
IMPORT_FROM = re.compile(
    r"""^import\s+(?P<type>type\s+)?(?P<names>[^;"']*?)\s+from\s+["'](?P<src>[^"']+)["']""",
    re.M | re.S)
IMPORT_SIDE = re.compile(r"""^import\s+["'](?P<src>[^"']+)["']""", re.M)


def imported_names(names: str) -> List[str]:
    """`React, { useState, type X as Y }` → ['React', 'useState', 'Y']"""
    names = " ".join(names.split())
    head, _, rest = names.partition("{")
    picked: List[str] = []
    for token in head.split(","):
        token = token.strip().replace("* as ", "")
        if token and token != "type":
            picked.append(token)
    if rest:
        for token in rest.rsplit("}", 1)[0].split(","):
            token = re.sub(r"^type\s+", "", token.strip())
            if token:
                picked.append(token.split(" as ")[-1].strip())
    return picked


def imports_of(text: str) -> List[Tuple[str, List[str]]]:
    """파일 안의 import를 (가져오는 곳, 가져오는 이름들)로 돌려줍니다."""
    found = [(m.group("src"), imported_names(m.group("names"))) for m in IMPORT_FROM.finditer(text)]
    found += [(m.group("src"), []) for m in IMPORT_SIDE.finditer(text)]
    return found


def resolve_import(src: str, importer: Path) -> Optional[Path]:
    """`@/…`·`./…` import를 실제 파일로 바꿉니다. 외부 패키지면 None."""
    if src.startswith("@/"):
        base = FRONTEND / src[2:]
    elif src.startswith(("./", "../")):
        base = importer.parent / src
    else:
        return None
    candidates = [base] if base.suffix in CODE_SUFFIXES else []
    candidates += [Path(str(base) + ext) for ext in CODE_SUFFIXES]
    candidates += [base / "index.tsx", base / "index.ts"]
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            try:
                resolved.relative_to(FRONTEND.resolve())
            except ValueError:
                return None                     # frontend 밖은 담지 않습니다
            return resolved
    return None


@dataclass
class Entry:
    path: Path
    rel: str
    role: str
    mode: str                                   # "full"(전문) | "api"(쓰는 법만)
    reason: str
    used_by: List[str] = field(default_factory=list)


def collect(targets: Sequence[Path], extra: Sequence[Path]) -> "OrderedDict[str, Entry]":
    """
    묶음에 넣을 파일을 고릅니다.

    - 전문 파일이 import하는 **화면 파일**은 전문, **키트·로직**은 쓰는 법만 담습니다.
    - 쓰는 법만 담은 파일에서는 타입이 사는 `lib/`·`scenarios/`만 한 단계씩 더 따라갑니다.
      키트 카드의 속(ActuatorSlotCard 등)은 화면 작업에 필요 없으므로 따라가지 않습니다.
    """
    entries: "OrderedDict[str, Entry]" = OrderedDict()
    queue: "deque[Path]" = deque()

    def add(path: Path, mode: str, reason: str, by: Optional[str] = None) -> None:
        rel = rel_of(path)
        entry = entries.get(rel)
        if entry is None:
            entries[rel] = Entry(path, rel, role_of(rel), mode, reason, [by] if by else [])
            queue.append(path)
            return
        if by and by not in entry.used_by:
            entry.used_by.append(by)
        if mode == "full" and entry.mode == "api":
            entry.mode = "full"                 # 전문으로 올리면 import도 다시 따라갑니다
            queue.append(path)

    for page in targets:
        add(page, "full", "이번에 고칠 화면")
    for rel in ALWAYS_FULL:
        if (FRONTEND / rel).exists():
            add(FRONTEND / rel, "full", "모든 화면에 적용 (글꼴·디자인 토큰)")
    for path in extra:
        add(path, "full", "--add로 직접 넣음")

    while queue:
        current = queue.popleft()
        entry = entries[rel_of(current)]
        text = current.read_text(encoding="utf-8", errors="replace")
        for src, _names in imports_of(text):
            target = resolve_import(src, current)
            if target is None:
                continue
            target_rel = rel_of(target)
            role = role_of(target_rel)
            if role not in ("ui", "kit", "logic"):
                continue
            if entry.mode == "full":
                mode = "full" if role == "ui" else "api"
            elif target_rel.startswith(("lib/", "scenarios/")):
                mode = "api"
            else:
                continue
            add(target, mode, f"`frontend/{entry.rel}`가 씀", by=entry.rel)
    return entries


def usage_rows(page: Path) -> List[Tuple[str, str, str]]:
    """화면 파일이 가져다 쓰는 것: (이름들, 어디서, 구분)"""
    rows = []
    text = page.read_text(encoding="utf-8", errors="replace")
    for src, names in imports_of(text):
        shown = ", ".join(f"`{n}`" for n in names) if names else "(불러오기만)"
        target = resolve_import(src, page)
        if target is None:
            where, kind = f"`{src}`", "외부 패키지"
        else:
            rel = rel_of(target)
            where = f"`frontend/{rel}`"
            role = role_of(rel)
            kind = {"ui": "★ 고치는 파일 (전문)", "kit": "키트 (쓰는 법만)",
                    "logic": "팀 로직 (쓰는 법만)"}.get(role, role)
        rows.append((shown, where, kind))
    return rows


# ---------------------------------------------------------------------------
# 쓰는 법만 뽑기 — 타입은 전문, 함수는 이름과 매개변수
# ---------------------------------------------------------------------------

def _sanitize(text: str) -> str:
    """
    주석과 문자열을 공백으로 지운 사본을 만듭니다 (줄 수·글자 위치는 그대로).
    괄호를 셀 때 주석 속 `{`나 문자열 속 `)`에 속지 않기 위해서입니다.
    """
    out: List[str] = []
    i, n = 0, len(text)
    state: Optional[str] = None                 # None · line · block · ' · " · `
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state is None:
            if ch == "/" and nxt == "/":
                state, i = "line", i + 2
                out.append("  ")
            elif ch == "/" and nxt == "*":
                state, i = "block", i + 2
                out.append("  ")
            elif ch in "'\"`":
                state, i = ch, i + 1
                out.append(" ")
            else:
                out.append(ch)
                i += 1
        elif state == "line":
            if ch == "\n":
                state = None
            out.append("\n" if ch == "\n" else " ")
            i += 1
        elif state == "block":
            if ch == "*" and nxt == "/":
                state, i = None, i + 2
                out.append("  ")
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        else:                                   # 문자열 안
            if ch == "\\" and nxt:
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == state:
                state = None
                out.append(" ")
                i += 1
            elif ch == "\n":
                out.append("\n")
                if state != "`":                # 따옴표 문자열은 한 줄에서 끝납니다
                    state = None
                i += 1
            else:
                out.append(" ")
                i += 1
    return "".join(out)


def _depth_change(code: str) -> int:
    return sum(code.count(c) for c in "({[") - sum(code.count(c) for c in ")}]")


def _next_code(clean: List[str], index: int) -> Optional[str]:
    for line in clean[index + 1:]:
        if line.strip():
            return line
    return None


def _statement_end(clean: List[str], start: int) -> int:
    """`start`에서 시작한 선언(타입·상수)이 끝나는 줄."""
    depth, opened = 0, False
    for index in range(start, len(clean)):
        code = clean[index]
        if any(c in code for c in "({["):
            opened = True
        depth += _depth_change(code)
        stripped = code.strip()
        if depth > 0:
            continue
        if stripped.endswith(";"):
            return index
        if opened and stripped.endswith(("}", ")", "]")):
            following = _next_code(clean, index)
            if following is None or not re.match(r"\s*[|&.?:=]", following):
                return index
        if not opened and not stripped and index > start:
            return index - 1
    return len(clean) - 1


def _signature_end(clean: List[str], start: int) -> int:
    """함수 선언에서 본문 `{`이 열리는 줄 (매개변수가 여러 줄이어도)."""
    depth, seen, closed = 0, False, False
    for index in range(start, len(clean)):
        code = clean[index]
        for ch in code:
            if ch == "(":
                depth, seen = depth + 1, True
            elif ch == ")":
                depth -= 1
        if seen and depth <= 0:
            closed = True
        if closed and ("{" in code or code.strip().endswith(";")):
            return index
    return start


def _block_close(clean: List[str], start: int, body_line: int) -> int:
    """함수 본문이 닫히는 줄."""
    depth = 0
    for index in range(start, len(clean)):
        depth += clean[index].count("{") - clean[index].count("}")
        if index >= body_line and depth <= 0:
            return index
    return len(clean) - 1


def _comment_block_above(lines: List[str], index: int) -> Tuple[int, List[str]]:
    """선언 바로 위의 설명 주석 (없으면 빈 목록). 너무 길면 앞부분만."""
    end = index - 1
    if end < 0 or not lines[end].strip().startswith(("*/", "*", "//", "/**", "/*")):
        return index, []
    begin = end
    while begin > 0 and lines[begin - 1].strip().startswith(("*", "//", "/**", "/*")) \
            and not lines[begin].strip().startswith(("/**", "/*")):
        begin -= 1
    block = lines[begin:end + 1]
    if len(block) > 15:
        block = block[:10] + ["   * … (설명 이하 생략)", "   */"] if block[0].strip().startswith("/*") \
            else block[:10] + ["  // … (설명 이하 생략)"]
    return begin, block


def _leading_comment(lines: List[str]) -> Tuple[int, List[str]]:
    """파일 맨 위 설명 주석 (그 파일이 무엇인지 알려 줍니다)."""
    if not lines or not lines[0].lstrip().startswith(("/*", "//")):
        return 0, []
    if lines[0].lstrip().startswith("//"):
        end = 0
        while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("//"):
            end += 1
    else:
        end = next((i for i, line in enumerate(lines) if "*/" in line), 0)
    block = lines[:end + 1]
    if len(block) > 30:
        block = block[:26] + [" * … (설명 이하 생략 — 전체 파일에 있습니다)", " */"]
    return end + 1, block


TYPE_DECL = re.compile(r"^(export\s+)?(declare\s+)?(interface|type|enum)\s+\w+")
FUNC_DECL = re.compile(r"^export\s+(default\s+)?(async\s+)?function\b")
CONST_DECL = re.compile(r"^export\s+(const|let)\s+\w+")
REEXPORT = re.compile(r"^export\s+(default\s+[\w.]+\s*;?\s*$|\{|\*)")


def api_view(text: str) -> str:
    """
    키트·로직 파일에서 **쓰는 법**만 남깁니다.

    타입(interface·type)은 "무엇을 넘기고 무엇을 받는가"이므로 전문을,
    함수·컴포넌트는 이름과 매개변수(props)까지만 담고 구현은 생략합니다.
    """
    lines = text.split("\n")
    clean = _sanitize(text).split("\n")
    picked: List[str] = []
    used_until = 0                              # 이미 담은 줄 (설명 주석이 두 번 들어가지 않게)

    body_start, header = _leading_comment(lines)
    if header:
        picked += header + [""]
        used_until = body_start

    def take_doc(index: int) -> None:
        begin, doc = _comment_block_above(lines, index)
        if doc and begin >= used_until:
            picked.extend(doc)

    index = 0
    while index < len(lines):
        line = lines[index]
        if TYPE_DECL.match(line):
            end = _statement_end(clean, index)
            take_doc(index)
            picked += lines[index:end + 1] + [""]
            used_until = index = end + 1
            continue
        if FUNC_DECL.match(line):
            body = _signature_end(clean, index)
            take_doc(index)
            picked += lines[index:body + 1]
            if clean[body].strip().endswith("{"):
                picked += ["  // … 구현 생략 …", "}"]
                close = _block_close(clean, index, body)
            else:
                close = body
            picked.append("")
            used_until = index = close + 1
            continue
        if CONST_DECL.match(line):
            end = _statement_end(clean, index)
            take_doc(index)
            block = lines[index:end + 1]
            arrow = next((k for k in range(index, end + 1) if "=>" in clean[k]), None)
            if arrow is not None and re.search(r"=\s*(async\s*)?(\(|<|\w+\s*=>)", clean[index]):
                picked += lines[index:arrow + 1] + ["  // … 구현 생략 …"]
            elif len(block) > 30:
                picked += block[:30] + [f"  // … 이하 {len(block) - 30}줄 생략 …"]
            else:
                picked += block
            picked.append("")
            used_until = index = end + 1
            continue
        if REEXPORT.match(line):
            picked.append(line)
        index += 1
    return "\n".join(picked).rstrip() or "(밖으로 내보내는 이름이 없습니다)"


# ---------------------------------------------------------------------------
# 디자인 토큰 · 패키지 · git
# ---------------------------------------------------------------------------

UTILITIES = (
    ("color-", ("bg-{}", "text-{}", "border-{}")),
    ("radius-", ("rounded-{}",)),
    ("font-", ("font-{}",)),
    ("shadow-", ("shadow-{}",)),
    ("text-", ("text-{}",)),
    ("animate-", ("animate-{}",)),
    ("breakpoint-", ("{}:",)),
)


def _theme_blocks(css: str) -> List[str]:
    blocks = []
    for match in re.finditer(r"@theme\b[^{]*\{", css):
        depth, start = 1, match.end()
        for index in range(start, len(css)):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(css[start:index])
                    break
    return blocks


def design_tokens(css: str) -> Dict[str, List]:
    """globals.css의 @theme에서 '쓸 수 있는 클래스 이름'을 뽑습니다."""
    tokens = []
    for block in _theme_blocks(css):
        for match in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);[ \t]*(?:/\*\s*(.*?)\s*\*/)?", block):
            name, value, note = match.group(1), " ".join(match.group(2).split()), match.group(3) or ""
            classes = next((tuple(t.format(name[len(p):]) for t in templates)
                            for p, templates in UTILITIES if name.startswith(p)), ())
            tokens.append((name, classes, value, note))
    plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return {
        "tokens": tokens,
        "styles": sorted(set(re.findall(r"""\[data-style=["']?([\w-]+)""", plain))),
        "classes": sorted(set(re.findall(r"^\.([A-Za-z][\w-]*)\s*[,{:]", plain, re.M))),
        "keyframes": sorted(set(re.findall(r"@keyframes\s+([\w-]+)", plain))),
    }


def installed_packages() -> List[Tuple[str, str, str]]:
    path = FRONTEND / "package.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = []
    for group in ("dependencies", "devDependencies"):
        for name, version in (data.get(group) or {}).items():
            if name.startswith("@types/"):
                continue
            rows.append((name, str(version), PACKAGE_NOTES.get(name, "")))
    return rows


def git_snapshot() -> str:
    def run(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                                text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ""
    try:
        branch = run("rev-parse", "--abbrev-ref", "HEAD")
        commit = run("rev-parse", "--short", "HEAD")
        dirty = [line for line in run("status", "--porcelain", "--", "frontend").splitlines() if line]
    except Exception:
        return ""
    if not commit:
        return ""
    text = f"브랜치 `{branch}` · 커밋 `{commit}`"
    if dirty:
        text += f" · 아직 커밋하지 않은 frontend 변경 {len(dirty)}개 포함"
    return text


# ---------------------------------------------------------------------------
# 묶음 만들기
# ---------------------------------------------------------------------------

LANG = {".tsx": "tsx", ".ts": "ts", ".css": "css"}

TO_THE_AI = """\
## 1. 이 파일을 읽는 AI에게

- 당신은 **시니어 프론트엔드 개발자이자 UI/UX 디자이너**입니다. 상대는 마이스터고 2학년
  학생입니다 — 설명은 짧고 쉽게, 전문 용어는 처음 나올 때 한 번 풀어 주세요.
- 학생은 AI 에이전트 도구를 쓰지 않습니다. 당신은 학생의 폴더를 볼 수 없고
  **이 파일에 담긴 것이 전부**입니다. 이 파일은 학생이 방금 만든 '지금 코드의 사진'입니다.
- 이 파일에 없는 파일의 내용을 **추측해서 쓰지 마세요.** 필요하면
  "`python tools/merge_ui.py --add <경로>`로 그 파일을 넣어 다시 올려 달라"고 말해 주세요.
- 학생의 요청이 아직 없으면 코드를 쓰지 말고, **이 화면이 무엇으로 이루어졌는지 3줄로
  요약**한 뒤 무엇을 바꿀지 물어보세요.
- 요청을 받으면 이 순서로 답합니다:
  ① 요청을 한 문장으로 다시 말하기 → ② 바꿀 파일과 계획 3~5줄 → ③ 코드 → ④ 확인 방법.
  요청이 크면 ②에서 "두 번에 나눠서 하자"고 제안하고 첫 번째만 합니다.
"""

CONSTRAINTS = """\
## 2. 지켜야 할 제약

이 프로젝트는 4개 팀(wakeup · classroom · study · subway)이 함께 쓰는 **IoT 개발 플랫폼 키트**
위에 있습니다. 공통 파일을 고치면 다른 팀 화면까지 깨집니다.

| 구분 | 경로 | 이번 작업에서 |
|---|---|---|
| ★ 고치는 곳 | 화면(`app/…/page.tsx`), `components/team/`, `app/globals.css`, `app/layout.tsx` | 고칩니다. 새 파일은 `frontend/components/team/`에 만듭니다 |
| 팀 로직 | `scenarios/` | 화면 작업에서는 고치지 않습니다. 동작을 바꿔야 하면 코드 대신 먼저 말해 주세요 |
| 🚫 키트 | `lib/`, `components/kit/`, `app/kit/` | 고치지 않습니다 — 쓰는 법만 담았습니다 |
| 🚫 설정 | `package.json`, `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs` | 고치지 않습니다 |
| 🚫 비밀 | `.env.local` | 이 파일에 없습니다. 키·비밀번호 값을 묻지도 마세요 |

- 키트 카드(`SlotGrid` 등)의 모양은 키트 파일이 아니라 **우리 화면의 배치·감싸는 요소·
  디자인 토큰**으로 바꿉니다. 키트 컴포넌트에는 8장에 적힌 props만 넘깁니다.
- **새 npm 패키지를 쓰지 않습니다.** 4장 표에 있는 것만 씁니다.
- 데이터 구조, API 주소, 화면 주소(라우팅)는 바꾸지 않습니다.
"""

FACTS = """\
## 3. 이 프로젝트의 사실 (AI가 자주 틀리는 곳)

- **Next.js 16 (App Router) · React 19 · TypeScript(strict)**. import의 `@/`는 `frontend/` 폴더입니다.
- 화면 파일(`page.tsx`)과 팀 컴포넌트는 클라이언트 컴포넌트입니다. 훅(`useState` 등)이나
  `onClick`을 쓰는 파일은 맨 위 설명 주석 바로 다음 줄에 `"use client";`가 있어야 합니다.
  단 **`app/layout.tsx`는 서버 컴포넌트**입니다 — `metadata`를 내보내므로 `"use client"`를 넣으면 안 됩니다.
- **Tailwind CSS v4**입니다. `tailwind.config.js`는 없고 만들지도 않습니다.
  ⚠️ v3 방식은 빌드는 되는데 **스타일이 조용히 안 먹습니다.**
  - 색·모서리 토큰은 `app/globals.css`의 `@theme` 안에 적어야 `bg-brand` 같은 클래스가 생깁니다.
    `:root`에만 적으면 클래스가 만들어지지 않습니다.
  - 실행 중에 바꾸는 값은 `@theme inline { --color-brand: var(--ui-brand); }` 로 이름을 만들고
    실제 값은 `:root { --ui-brand: …; }`에 둡니다.
- 아이콘은 설치된 **lucide-react**에서 이름으로 import 합니다 (`import { Bell } from "lucide-react";`).
- React 19 린트 규칙 — 어기면 `npx eslint .`가 오류를 냅니다:
  - 렌더링 중에 `Date.now()`·`Math.random()`을 부르지 않습니다 (`useState` 초기값·이벤트·타이머 안에서).
  - 렌더링 중에 `ref.current`를 읽지 않습니다.
  - `useEffect` 본문에서 곧바로 `setState` 하지 않습니다 (타이머·구독 콜백 안에서).
  - 컴포넌트 **안에서** 또 다른 컴포넌트를 정의하지 않습니다 (파일 맨 바깥에 정의).
- `useScenario()`는 화면 하나에서 **한 번만** 부릅니다. 시나리오 훅(`useWakeup` 등)이 있으면
  그 훅이 돌려주는 `scenario`를 꺼내 씁니다.
- 화면 제목은 `.env.local`의 `NEXT_PUBLIC_TEAM_NAME`에서 옵니다. `NEXT_PUBLIC_*` 값은 서버를 다시 켜야 바뀝니다.
- 확인 명령은 `cd frontend` → `npx eslint .` → `npx next build`입니다 (Next.js 16에는 `next lint`가 없습니다).
"""

ANSWER_FORMAT = """\
## 9. 답변 형식 — 꼭 지켜 주세요

학생은 답을 `python tools/apply_ui.py`로 적용하거나 손으로 붙여넣습니다.
도구가 읽을 수 있도록 **아래 형식을 정확히** 지켜 주세요.

1. 먼저 **계획**을 3~5줄로 씁니다: 무엇을, 어느 파일에서, 왜.
2. 바꾸는 파일마다 **코드블록 하나에 파일 전체**를 줍니다.
   코드블록의 **첫 줄은 경로 표시**입니다 (저장소 기준 경로, `frontend/`부터).

   ```tsx
   // 파일: frontend/app/page.tsx
   /**
    * (원래 있던 설명 주석)
    */
   "use client";
   …파일의 마지막 줄까지 전부…
   ```

   CSS 파일은 `/* 파일: frontend/app/globals.css */` 로 시작합니다.
3. **금지**: `...`·`// 기존 코드`·`(생략)`·`// 나머지는 그대로` 같은 생략,
   줄 앞의 `+`/`-` diff 기호, 함수 하나만 따로 주기. 파일이 길어도 **전체**를 줍니다.
4. 한 번에 **파일 3개 이하**만 바꿉니다. 더 필요하면 나눠서 진행하자고 말해 주세요.
5. 새 파일은 `frontend/components/team/` 아래에 만듭니다 (경로 표시는 똑같이).
6. 2장의 🚫 파일을 바꿔야 할 것 같으면 **코드 대신 이유와 다른 방법**을 설명해 주세요.
7. 원래 파일의 설명 주석과 `"use client";`는 지우지 말고 그대로 둡니다.
8. 마지막에 **확인 방법**을 씁니다: 실행할 명령, 그리고 브라우저 어느 주소에서 무엇을 보면 되는지.
"""

CLOSING = """\
---

여기까지가 묶음입니다. **학생의 요청은 이 파일 다음에 옵니다.**
요청이 없으면 1장의 안내대로 화면 구성을 3줄로 요약하고 무엇을 바꿀지 물어봐 주세요.
"""


def fence_for(body: str) -> str:
    """내용 안에 ```가 있어도 깨지지 않도록 더 긴 울타리를 씁니다."""
    longest = max((len(m.group(0)) for m in re.finditer(r"`{3,}", body)), default=0)
    return "`" * max(3, longest + 1)


def file_section(entry: Entry) -> str:
    text = entry.path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
    lines = text.count("\n") + 1
    lang = LANG.get(entry.path.suffix, "")
    used_by = (" · 쓰는 곳: " + ", ".join(f"`frontend/{u}`" for u in entry.used_by)) if entry.used_by else ""
    if entry.mode == "full":
        head = f"### `frontend/{entry.rel}` — {ROLE_LABEL.get(entry.role, entry.role)} · 전문 {lines}줄"
        body = text
    else:
        head = (f"### `frontend/{entry.rel}` — {ROLE_LABEL.get(entry.role, entry.role)} · "
                f"쓰는 법만 (전체 {lines}줄 중 타입·이름)")
        body = api_view(text)
    fence = fence_for(body)
    return f"{head}\n\n> {entry.reason}{used_by}\n\n{fence}{lang}\n{body}\n{fence}"


def token_section(entries: "OrderedDict[str, Entry]") -> str:
    css_path = FRONTEND / "app" / "globals.css"
    if not css_path.exists():
        return "## 6. 디자인 토큰\n\n> `app/globals.css`가 없습니다."
    info = design_tokens(css_path.read_text(encoding="utf-8", errors="replace"))
    parts = ["## 6. 지금 쓸 수 있는 디자인 토큰 (`frontend/app/globals.css`에서 읽었습니다)", ""]
    if info["tokens"]:
        parts += ["| 토큰 | 만들어지는 클래스 | 값 | 메모 |", "|---|---|---|---|"]
        for name, classes, value, note in info["tokens"]:
            shown = " ".join(f"`{c}`" for c in classes) or "—"
            parts.append(f"| `--{name}` | {shown} | `{value}` | {note} |")
    else:
        parts.append("> `@theme`에 토큰이 없습니다.")
    extra = []
    if info["styles"]:
        extra.append("- 스타일 묶음(`<html data-style=\"…\">`): " + ", ".join(f"`{s}`" for s in info["styles"]))
    if info["classes"]:
        extra.append("- 직접 만든 클래스: " + ", ".join(f"`.{c}`" for c in info["classes"]))
    if info["keyframes"]:
        extra.append("- 애니메이션(@keyframes): " + ", ".join(f"`{k}`" for k in info["keyframes"]))
    if extra:
        parts += [""] + extra
    if len(info["tokens"]) <= 4:
        parts += ["", "> 아직 Next.js 기본 토큰뿐입니다. 팀 디자인 스타일을 정했다면 "
                  "06 교재 7장의 구조(`@theme inline` + `:root`/`[data-style]`)로 바꾸는 것부터 하세요."]
    return "\n".join(parts)


def build_pack(routes: Sequence[str], pages: "OrderedDict[str, Path]",
               entries: "OrderedDict[str, Entry]", everything: bool) -> str:
    full = [e for e in entries.values() if e.mode == "full"]
    api = [e for e in entries.values() if e.mode == "api"]
    title = "화면 파일 전부" if everything else f"`{routes[0]}` 화면"
    snapshot = git_snapshot()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [
        f"# 화면 수정 컨텍스트 — {title}",
        "",
        f"> 이 파일은 `python tools/merge_ui.py`로 만든 **지금 코드의 사진**입니다 ({stamp}"
        + (f" · {snapshot}" if snapshot else "") + ").",
        f"> 고치는 파일 {len(full)}개는 전문, 키트·로직 {len(api)}개는 쓰는 법만 담았습니다. "
        "`.env` 같은 비밀 파일은 넣지 않았습니다.",
        "",
        TO_THE_AI, CONSTRAINTS, FACTS,
        "## 4. 설치된 패키지 (이것만 씁니다)",
        "",
        "| 패키지 | 버전 | 메모 |",
        "|---|---|---|",
    ]
    parts += [f"| `{name}` | `{version}` | {note} |" for name, version, note in installed_packages()]

    parts += ["", "## 5. 화면 지도", "", "| 주소 | 파일 | 구분 |", "|---|---|---|"]
    for route, page in pages.items():
        mark = " ← **이번에 고칠 화면**" if route in routes else ""
        parts.append(f"| `{route}` | `frontend/{rel_of(page)}` | {page_kind(route)}{mark} |")

    for route in routes:
        parts += ["", f"### `{route}` 화면이 가져다 쓰는 것 (`frontend/{rel_of(pages[route])}`의 import)",
                  "", "| 가져오는 것 | 어디서 | 구분 |", "|---|---|---|"]
        parts += [f"| {names} | {where} | {kind} |" for names, where, kind in usage_rows(pages[route])]

    parts += ["", "### 이 묶음에 담긴 파일", "", "| 파일 | 담은 방식 | 왜 들어왔나 |", "|---|---|---|"]
    for entry in entries.values():
        how = "전문" if entry.mode == "full" else "쓰는 법만"
        parts.append(f"| `frontend/{entry.rel}` | {how} · {ROLE_LABEL.get(entry.role, entry.role)} | {entry.reason} |")

    parts += ["", token_section(entries), "",
              "## 7. 고치는 파일 — 전문", "",
              "아래 파일은 학생이 고칠 수 있는 파일입니다. 지금 내용 그대로입니다."]
    for entry in full:
        parts += ["", file_section(entry)]

    parts += ["", "## 8. 참고 — 쓰는 법만 (고치지 않습니다)", "",
              "구현은 생략하고 **타입은 전문, 함수·컴포넌트는 이름과 매개변수(props)**만 담았습니다."]
    if not api:
        parts += ["", "> (이 화면은 키트·로직 파일을 쓰지 않습니다)"]
    for entry in api:
        parts += ["", file_section(entry)]

    parts += ["", ANSWER_FORMAT, CLOSING]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def check_extra(values: Sequence[str]) -> Tuple[List[Path], List[str]]:
    """`--add`로 받은 경로를 확인합니다. 비밀·설정·frontend 밖은 넣지 않습니다."""
    accepted: List[Path] = []
    refused: List[str] = []
    for value in values:
        text = value.strip().replace("\\", "/")
        path = (ROOT / text) if text.startswith("frontend/") else (FRONTEND / text)
        try:
            rel = rel_of(path)
        except ValueError:
            refused.append(f"{value} — frontend 폴더 밖의 파일은 화면 묶음에 넣지 않습니다")
            continue
        role = role_of(rel)
        if role == "secret":
            refused.append(f"{value} — 비밀값 파일은 절대 넣지 않습니다")
        elif role in ("config", "build"):
            refused.append(f"{value} — 설정·빌드 파일은 넣지 않습니다 (패키지 목록은 이미 들어 있습니다)")
        elif path.suffix not in CODE_SUFFIXES:
            refused.append(f"{value} — .tsx · .ts · .css 파일만 넣을 수 있습니다")
        elif not path.is_file():
            refused.append(f"{value} — 파일이 없습니다 (경로를 확인하세요)")
        else:
            accepted.append(path.resolve())
    return accepted, refused


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")    # 어떤 터미널에서도 글자 때문에 멈추지 않게
    parser = argparse.ArgumentParser(
        description="프론트엔드 화면 파일을 채팅형 AI에 올릴 MD 파일 하나로 묶습니다.")
    parser.add_argument("--page", default="/",
                        help="고칠 화면: / (기본) · study · wakeup · app/study/page.tsx")
    parser.add_argument("--add", action="append", default=[], metavar="경로",
                        help="더 넣을 파일 (여러 번 쓸 수 있음). 예: components/team/SeatCard.tsx")
    parser.add_argument("--all", action="store_true", help="키트를 뺀 화면 전부를 묶습니다 (큽니다)")
    parser.add_argument("--list", action="store_true", help="묶지 않고 무엇이 들어갈지만 봅니다")
    args = parser.parse_args(argv)

    pages = find_pages()
    if not pages:
        print("frontend/app 아래에서 page.tsx를 찾지 못했습니다. 저장소 최상위 폴더에서 실행했나요?")
        return 2

    if args.all:
        routes = [r for r in pages if page_kind(r) != page_kind("/kit")]
    else:
        try:
            route, _page = pick_page(args.page, pages)
        except LookupError:
            print(f"'{args.page}' 화면을 찾지 못했습니다. 있는 화면:")
            for route, page in pages.items():
                print(f"  {route:10}  frontend/{rel_of(page)}")
            return 2
        if route == "/kit" or route.startswith("/kit/"):
            print("/kit 은 키트가 주는 화면이라 고치지 않습니다. 우리 팀 화면(/)을 묶으세요.")
            return 2
        routes = [route]

    extra, refused = check_extra(args.add)
    for line in refused:
        print(f"  [넣지 않음] {line}")

    entries = collect([pages[r] for r in routes], extra)

    print("=" * 68)
    print(" 화면 파일 묶기 — 채팅형 AI에 올릴 MD 파일 하나")
    print("=" * 68)
    for entry in entries.values():
        how = "전문    " if entry.mode == "full" else "쓰는 법만"
        lines = entry.path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        print(f"  {how}  frontend/{entry.rel}  ({lines}줄)")

    if args.list:
        print("\n (--list: 파일은 만들지 않았습니다)")
        return 0

    text = build_pack(routes, pages, entries, args.all)
    text, scrubbed = scrub_secrets(text, "ui")
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / out_name(routes, args.all)
    out.write_text(text, encoding="utf-8")

    size_kb = len(text.encode("utf-8")) / 1024
    print()
    print(f"  [완료] {out.relative_to(ROOT).as_posix()}  ({len(text.splitlines())}줄, {size_kb:.0f}KB)")
    if scrubbed:
        print(f"     ⚠ 비밀값처럼 보이는 것을 지웠습니다: {', '.join(sorted(set(scrubbed)))}")
        print("       코드에 키를 직접 적어 두었다면 .env.local로 옮기세요.")
    if size_kb > WARN_KB:
        print(f"     ⚠ {size_kb:.0f}KB로 큽니다. 무료 채팅에서는 뒷부분이 잘릴 수 있습니다.")
        print("       --all 대신 --page로 화면 하나만, 또는 필요 없는 --add를 빼세요.")
    print()
    print(" 다음 할 일 (docs/08 가이드)")
    print("  1. 채팅형 AI에서 새 대화를 열고 위 파일을 올립니다 (안 되면 내용을 붙여넣기).")
    print("  2. 그 아래에 요청을 씁니다 — 목표 · 바꿀 곳 · 바꾸지 말 것 · 완료 기준.")
    print("  3. 답을 context_packs/answer.md에 저장하고:  python tools/apply_ui.py")
    print()
    print(" ⚠️ 코드를 고친 뒤 다음 요청을 할 때는 이 명령을 다시 실행해서 새로 묶으세요.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
