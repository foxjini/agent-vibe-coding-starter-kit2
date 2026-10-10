#!/usr/bin/env python3
"""
AI 답 적용하기 (tools/apply_ui.py) — 채팅형 AI가 준 코드를 안전하게 파일에 넣습니다.
=============================================================================
`merge_ui.py`로 묶은 파일을 AI에게 올리면, AI는 바꿀 파일마다 코드블록 하나를 줍니다.
코드블록의 첫 줄에는 경로 표시가 있습니다:   // 파일: frontend/app/page.tsx

이 스크립트는 그 답을 읽어서
  1) 무엇이 바뀌는지 먼저 보여 주고          (미리 보기 — 아무것도 바꾸지 않습니다)
  2) --write를 붙이면 바꾸기 전 파일을 백업한 뒤 적용하고
  3) --undo로 마지막 적용을 되돌립니다.

다음이 하나라도 있으면 **아무것도 쓰지 않습니다** (반쪽만 바뀌면 더 헷갈립니다)
  · 4팀 공통 파일 (lib/, components/kit/, app/kit/, 설정 파일, .env)
  · `...`·`// 기존 코드` 같은 생략이 든 코드, 줄 앞에 `+`/`-` diff 기호가 붙은 코드
  · 중간에 끊긴 답 (코드블록이 닫히지 않음)

쓰는 방법 (저장소 최상위 폴더에서)
---------------------------------
  1. AI의 답을 복사해 `context_packs/answer.md`에 붙여넣고 저장합니다.
     (답 전체를 복사해도 되고, 코드블록의 복사 버튼으로 블록만 차례로 붙여넣어도 됩니다)
  2. python tools/apply_ui.py              # 미리 보기
  3. python tools/apply_ui.py --write      # 적용 (바꾸기 전 파일을 백업합니다)
  4. python tools/apply_ui.py --undo       # 마음에 안 들면 되돌리기
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
PACKS = ROOT / "context_packs"
DEFAULT_ANSWER = PACKS / "answer.md"
BACKUPS = PACKS / "backups"

ALLOWED_SUFFIXES = (".tsx", ".ts", ".css")
#: 4팀 공통 — 이 도구로는 쓰지 않습니다
PROTECTED_PREFIXES = ("lib/", "components/kit/", "app/kit/", "node_modules/", ".next/")
PROTECTED_FILES = frozenset({
    "package.json", "package-lock.json", "next.config.ts", "next.config.js",
    "next.config.mjs", "tsconfig.json", "eslint.config.mjs", "postcss.config.mjs",
    "next-env.d.ts",
})
#: `frontend/`를 빼먹고 적어도 알아듣는 경로
SHORT_PREFIXES = ("app/", "components/", "scenarios/", "lib/", "styles/", "hooks/")
#: 한 번에 이보다 많이 바꾸면 경고합니다
MANY_FILES = 3

# ---------------------------------------------------------------------------
# 답 읽기
# ---------------------------------------------------------------------------

#: 코드블록 첫 줄의 경로 표시 —  // 파일: …   /* 파일: … */   {/* 파일: … */}
MARKER = re.compile(
    r"^\s*\{?\s*(?:/\*+|//+|<!--)\s*(?:파일\s*(?:명|경로)?|경로|file(?:\s*path)?|path)\s*[:：]\s*(?P<rest>.+?)\s*$",
    re.I)
#: 예전 형식 — 첫 줄 주석이 경로만 적혀 있는 경우  // frontend/app/page.tsx (전체)
MARKER_PATH_ONLY = re.compile(
    r"^\s*\{?\s*(?:/\*+|//+)\s*[`'\"]?(?P<rest>(?:frontend/)?(?:app|components|scenarios|lib|styles)/"
    r"[\w./\[\]()@-]+\.(?:tsx|ts|css)\b.*)$")
#: 제목에서 경로를 읽을 때, 코드블록 언어가 파일 종류와 맞아야 합니다 (명령어 블록을 코드로 착각하지 않게)
LANGS_FOR = {
    ".tsx": {"", "tsx", "ts", "typescript", "jsx", "js", "javascript", "react"},
    ".ts": {"", "ts", "typescript", "tsx", "js", "javascript"},
    ".css": {"", "css"},
}
#: 코드블록 바로 위 제목에 적힌 경로 —  ### 파일: frontend/app/page.tsx
TITLE_WITH_WORD = re.compile(r"(?:파일|file)\s*[:：]\s*\**\s*[`'\"]?(?P<path>[\w./\[\]()@-]+\.(?:tsx|ts|css))", re.I)
TITLE_PATH = re.compile(
    r"^\s*(?:#{1,6}\s+|\*\*|\d+[.)]\s+|[-*]\s+).*?[`'\"]?"
    r"(?P<path>(?:frontend/)?(?:app|components|scenarios|lib|styles)/[\w./\[\]()@-]+\.(?:tsx|ts|css))")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>[^`]*)$")


@dataclass
class Block:
    path_text: str                  # 답에 적힌 경로 그대로
    content: str                    # 경로 표시 줄을 뺀 파일 내용
    line_no: int                    # 답 파일에서 몇 번째 줄인가 (안내용)
    closed: bool = True             # 코드블록이 닫혔는가 (아니면 답이 끊긴 것)


def path_token(rest: str) -> Optional[str]:
    """경로 표시 뒤쪽에서 경로만 꺼냅니다 ('(전체)'·'*/' 같은 꼬리는 버림)."""
    rest = re.sub(r"(\*+/\s*\}?|-->)\s*$", "", rest).strip()
    match = re.match(r"[`'\"]?([^\s`'\"*]+)", rest)
    return match.group(1) if match else None


def _title_path(lines: List[str], fence_index: int) -> Optional[str]:
    """코드블록 바로 위(빈 줄 빼고 두 줄 안)의 제목에서 경로를 찾습니다."""
    seen = 0
    for index in range(fence_index - 1, -1, -1):
        text = lines[index].strip()
        if not text:
            continue
        seen += 1
        match = TITLE_WITH_WORD.search(text) or TITLE_PATH.match(text)
        if match:
            return match.group("path")
        if seen >= 2:
            return None
    return None


def _trim(body: List[str]) -> str:
    while body and not body[0].strip():
        body = body[1:]
    while body and not body[-1].strip():
        body = body[:-1]
    return "\n".join(body)


def parse_answer(text: str) -> Tuple[List[Block], List[Tuple[int, str]]]:
    """
    AI 답에서 '경로가 붙은 코드'를 꺼냅니다.

    돌려주는 것: (경로가 있는 블록들, 경로가 없어 건너뛴 블록들[(줄 번호, 첫 줄)])
    코드블록(```)이 하나도 없으면, 학생이 코드만 붙여넣은 것으로 보고
    경로 표시 줄을 기준으로 파일을 나눕니다.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not any(FENCE.match(line) for line in lines):
        return _parse_bare(lines), []

    blocks: List[Block] = []
    skipped: List[Tuple[int, str]] = []
    index = 0
    while index < len(lines):
        opening = FENCE.match(lines[index])
        if not opening:
            index += 1
            continue
        indent = len(opening.group("indent"))
        mark, size = opening.group("fence")[0], len(opening.group("fence"))
        end, closed = index + 1, False
        while end < len(lines):
            stripped = lines[end].strip()
            if stripped and set(stripped) == {mark} and len(stripped) >= size:
                closed = True
                break
            end += 1
        # 목록 안에 들여 쓴 코드블록이면 그만큼 들여쓰기를 걷어 냅니다
        body = [line[indent:] if line[:indent].strip() == "" else line
                for line in lines[index + 1:end]]

        first = next((k for k, line in enumerate(body) if line.strip()), None)
        path: Optional[str] = None
        if first is not None:
            marker = MARKER.match(body[first]) or MARKER_PATH_ONLY.match(body[first])
            if marker:
                path = path_token(marker.group("rest"))
                body = body[first + 1:]
        if path is None:
            titled = _title_path(lines, index)
            language = opening.group("info").strip().split(" ")[0].lower()
            if titled and language in LANGS_FOR.get(Path(titled).suffix, set()):
                path = titled
        if path:
            blocks.append(Block(path, _trim(body), index + 1, closed))
        else:
            preview = body[first].strip()[:50] if first is not None else "(빈 블록)"
            skipped.append((index + 1, preview))
        index = end + 1
    return blocks, skipped


def _parse_bare(lines: List[str]) -> List[Block]:
    blocks: List[Block] = []
    current: Optional[Tuple[str, int, List[str]]] = None
    for number, line in enumerate(lines, 1):
        marker = MARKER.match(line) or MARKER_PATH_ONLY.match(line)
        path = path_token(marker.group("rest")) if marker else None
        if path:
            if current:
                blocks.append(Block(current[0], _trim(current[2]), current[1]))
            current = (path, number, [])
        elif current is not None:
            current[2].append(line)
    if current:
        blocks.append(Block(current[0], _trim(current[2]), current[1]))
    return blocks


# ---------------------------------------------------------------------------
# 검사
# ---------------------------------------------------------------------------

#: 코드를 빼먹었다는 뜻의 말 — 주석 줄에 이것이 있으면 생략으로 봅니다
OMISSION_PHRASES = (
    "기존 코드", "기존과 동일", "기존과 같", "기존 내용", "이전과 동일", "이전과 같",
    "나머지 코드", "나머지는 그대로", "나머지는 동일", "나머지 생략", "중략",
    "이하 생략", "이하 동일", "코드 생략", "구현 생략", "(생략)", "생략)",
    "existing code", "rest of the code", "rest of the file", "rest of code",
    "rest of the component", "unchanged", "same as before", "remains the same",
    "omitted", "truncated", "keep the rest",
)
COMMENT_LINE = re.compile(r"^\s*(?://|/\*|\{\s*/\*|\*(?!/))")
COMMENT_STARTS_WITH_DOTS = re.compile(r"^\s*(?://+|/\*+|\{\s*/\*+|\*)\s*(?:\.\.\.|…)")
DOTS_ONLY = re.compile(r"^\s*(?:\.\.\.|…)+\s*[,;]?\s*$")
DIFF_HEADER = re.compile(r"^(?:@@ .* @@|\+\+\+ |--- [ab/])")
DIFF_LINE = re.compile(r"^[+-](?![+-])\S?")
USES_CLIENT = re.compile(r"\buse(State|Effect|Ref|Memo|Callback|Reducer|Scenario|Wakeup|Study)\b|\bon[A-Z]\w*=\{")


def omission_lines(content: str) -> List[Tuple[int, str]]:
    found = []
    for number, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if DOTS_ONLY.match(line) or stripped.startswith("…") or COMMENT_STARTS_WITH_DOTS.match(line):
            found.append((number, stripped))
        elif COMMENT_LINE.match(line) and any(p in stripped.lower() for p in OMISSION_PHRASES):
            found.append((number, stripped))
    return found


def diff_marks(content: str) -> int:
    lines = content.split("\n")
    if any(DIFF_HEADER.match(line) for line in lines):
        return max(2, sum(1 for line in lines if DIFF_LINE.match(line)))
    return sum(1 for line in lines if DIFF_LINE.match(line) and line.strip() not in ("-", "+"))


def normalize_path(path_text: str) -> Tuple[Optional[str], str]:
    """답에 적힌 경로 → frontend/ 기준 경로. 안 되면 (None, 이유)."""
    text = path_text.strip().strip("`'\"").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return None, "절대 경로입니다 — `frontend/…`처럼 저장소 기준 경로여야 합니다"
    if text.startswith("frontend/"):
        rel = text[len("frontend/"):]
    elif text.startswith(SHORT_PREFIXES):
        rel = text
    else:
        return None, "frontend/ 아래 경로가 아닙니다 — 이 도구는 화면 파일만 씁니다"
    target = (FRONTEND / rel).resolve()
    try:
        return target.relative_to(FRONTEND.resolve()).as_posix(), ""
    except ValueError:
        return None, "frontend 폴더 밖을 가리킵니다"


def read_current(path: Path) -> Tuple[Optional[str], bool]:
    """(지금 내용 — 줄바꿈은 \\n으로, 원래 CRLF였는가). 파일이 없으면 (None, False)."""
    if not path.exists():
        return None, False
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n"), b"\r\n" in raw


@dataclass
class Plan:
    rel: str
    block: Block
    current: Optional[str]
    crlf: bool
    errors: List[str] = field(default_factory=list)      # 학생에게 보여 줄 거부 이유
    asks: List[str] = field(default_factory=list)        # AI에게 다시 요청할 말
    warnings: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors:
            return "거부"
        if self.current is None:
            return "새로"
        if self.current.rstrip("\n") == self.block.content.rstrip("\n"):
            return "같음"
        return "바꿈"


def check(rel: str, block: Block, current: Optional[str]) -> Tuple[List[str], List[str], List[str]]:
    """(거부 이유, AI에게 다시 요청할 말, 경고)"""
    errors: List[str] = []
    asks: List[str] = []
    warnings: List[str] = []
    name = rel.rsplit("/", 1)[-1]
    content = block.content
    if current is not None and current.rstrip("\n") == content.rstrip("\n"):
        return errors, asks, warnings          # 바뀐 것이 없으면 쓰지 않으므로 검사할 것도 없습니다

    def fail(message: str, ask: str) -> None:
        errors.append(message)
        if ask not in asks:
            asks.append(ask)

    if name.startswith(".env"):
        fail("비밀값 파일(.env)은 이 도구로 쓰지 않습니다",
             ".env 파일은 내가 직접 관리해. 코드에서 값을 바꾸지 않는 방법으로 해 줘")
    elif rel in PROTECTED_FILES or rel.startswith(PROTECTED_PREFIXES):
        fail("4팀 공통 파일입니다 — 고치지 않습니다",
             "이 파일은 4팀 공통 파일이라 고칠 수 없어. 이 파일은 그대로 두고 "
             "우리 화면 파일이나 components/team/의 새 파일로 같은 결과를 내 줘")
    elif not rel.endswith(ALLOWED_SUFFIXES):
        fail(".tsx · .ts · .css 파일만 씁니다", ".tsx · .ts · .css 파일만 바꿀 수 있어")

    if not block.closed:
        fail("코드블록이 닫히지 않았습니다 — 답이 중간에 끊긴 것 같습니다",
             "답이 중간에 끊겼어. '이어서'가 아니라 이 파일 전체를 처음부터 다시 줘")
    if not content.strip():
        fail("내용이 비어 있습니다", "내용이 비어 있어. 파일 전체를 줘")
    for number, line in omission_lines(content)[:3]:
        fail(f"{number}번째 줄이 생략 표시로 보입니다: {line[:50]}",
             "생략(`...`, `// 기존 코드` 등) 없이 파일 전체를 다시 줘")
    if diff_marks(content) >= 2:
        fail("줄 앞에 diff 기호(+/-)가 붙어 있습니다 — 기호 없는 완성된 코드여야 합니다",
             "+/- 기호 없는 완성된 파일 전체로 다시 줘")
    if name in ("page.tsx", "layout.tsx") and "export default" not in content:
        fail("export default가 없습니다 — 화면 파일에는 꼭 있어야 합니다",
             "export default가 빠졌어. 파일 전체를 다시 줘")
    if rel == "app/layout.tsx" and re.search(r"""^\s*["']use client["']""", content, re.M) \
            and "metadata" in content:
        fail('layout.tsx에 "use client"가 들어갔습니다 — metadata를 쓰는 서버 컴포넌트라 빌드가 실패합니다',
             'layout.tsx는 metadata를 쓰는 서버 컴포넌트라 "use client"를 넣으면 안 돼')

    has_directive = re.search(r"""^\s*["']use client["'];?""", content, re.M) is not None
    if current is not None:
        old_lines, new_lines = current.count("\n") + 1, content.count("\n") + 1
        if old_lines >= 20 and new_lines < old_lines * 0.5:
            warnings.append(f"{old_lines}줄 → {new_lines}줄로 크게 줄었습니다. 일부만 받은 것은 아닌지 확인하세요")
        if re.search(r"""^\s*["']use client["']""", current, re.M) and not has_directive:
            if name == "page.tsx" and USES_CLIENT.search(content):
                fail('"use client";가 사라졌습니다 — 훅을 쓰는 화면이라 빌드가 실패합니다',
                     '맨 위의 "use client";가 빠졌어. 원래 있던 설명 주석과 함께 그대로 두고 다시 줘')
            else:
                warnings.append('"use client";가 사라졌습니다 — 훅이나 onClick을 쓰면 빌드가 실패합니다')
    elif rel.endswith(".tsx") and USES_CLIENT.search(content) and not has_directive \
            and rel != "app/layout.tsx":
        warnings.append('맨 위에 "use client";가 없습니다 — 이 프로젝트의 다른 컴포넌트처럼 넣어 두세요')
    return errors, asks, warnings


def make_plans(blocks: Sequence[Block]) -> Tuple[List[Plan], List[str]]:
    """블록마다 무엇을 할지 정합니다. 같은 파일이 두 번이면 뒤의 것을 씁니다."""
    notes: List[str] = []
    chosen: Dict[str, Plan] = {}
    for block in blocks:
        rel, why = normalize_path(block.path_text)
        if rel is None:
            chosen[f"?{block.line_no}"] = Plan(
                block.path_text, block, None, False, [why],
                ["경로는 `frontend/app/page.tsx`처럼 저장소 기준으로 적어 줘"])
            continue
        if rel in chosen:
            notes.append(f"frontend/{rel} 가 두 번 나와서 뒤의 것({block.line_no}번째 줄)을 씁니다")
        current, crlf = read_current(FRONTEND / rel)
        errors, asks, warnings = check(rel, block, current)
        chosen[rel] = Plan(rel, block, current, crlf, errors, asks, warnings)
    return list(chosen.values()), notes


# ---------------------------------------------------------------------------
# 보여 주기
# ---------------------------------------------------------------------------

def _count(text: Optional[str]) -> int:
    return 0 if text is None else text.rstrip("\n").count("\n") + 1


def diff_text(plan: Plan, limit: Optional[int]) -> List[str]:
    old = (plan.current or "").rstrip("\n").split("\n") if plan.current is not None else []
    new = plan.block.content.rstrip("\n").split("\n")
    lines = list(difflib.unified_diff(old, new, f"frontend/{plan.rel} (지금)",
                                      f"frontend/{plan.rel} (AI 답)", n=2, lineterm=""))
    if limit is not None and len(lines) > limit:
        rest = len(lines) - limit
        lines = lines[:limit] + [f"… 이하 {rest}줄 더 있습니다 (전부 보려면 --diff)"]
    return lines


def change_stat(plan: Plan) -> str:
    old = (plan.current or "").rstrip("\n").split("\n") if plan.current is not None else []
    new = plan.block.content.rstrip("\n").split("\n")
    added = removed = 0
    for line in difflib.ndiff(old, new):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return f"+{added} -{removed}"


def retry_request(plans: Sequence[Plan]) -> List[str]:
    """거부된 이유를 AI에게 그대로 붙여넣을 문장으로 만듭니다."""
    lines = ["답을 적용하다가 문제가 있었어. 아래를 고쳐서 다시 줘."]
    for plan in plans:
        if not plan.errors:
            continue
        shown = f"frontend/{plan.rel}" if not plan.rel.startswith("?") else plan.block.path_text
        lines.append(f"- {shown}: " + " / ".join(plan.asks or plan.errors))
    lines.append("형식은 묶음 파일 9장대로 — 바꾸는 파일마다 코드블록 하나, "
                 "첫 줄은 `// 파일: frontend/…`, 생략 없이 파일 전체.")
    return lines


# ---------------------------------------------------------------------------
# 쓰기 · 되돌리기
# ---------------------------------------------------------------------------

def _encoded(content: str, crlf: bool) -> bytes:
    text = content.rstrip("\n") + "\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def write_plans(plans: Sequence[Plan], answer: Path) -> Path:
    """바꾸기 전 파일을 백업하고 적용합니다. 백업 폴더를 돌려줍니다."""
    folder = unique_path(BACKUPS / datetime.now().strftime("%Y%m%d-%H%M%S"))
    (folder / "files").mkdir(parents=True)

    manifest = {"created": datetime.now().isoformat(timespec="seconds"),
                "answer": str(answer), "files": []}
    for plan in plans:
        target = FRONTEND / plan.rel
        existed = target.exists()
        if existed:
            saved = folder / "files" / plan.rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(target.read_bytes())
        data = _encoded(plan.block.content, plan.crlf)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["files"].append({"path": plan.rel, "existed": existed,
                                  "sha256": hashlib.sha256(data).hexdigest(), "undone": False})
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    return folder


def unique_path(path: Path) -> Path:
    """같은 이름이 이미 있으면 -2, -3 …을 붙입니다 (1초 안에 두 번 적용·되돌리기 해도 안전하게)."""
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}-{number}")
        number += 1
    return candidate


def mark_undone(folder: Path) -> None:
    """다 되돌린 백업은 이름 끝에 -undone을 붙여 다음 --undo가 건너뛰게 합니다."""
    folder.rename(unique_path(folder.with_name(folder.name + "-undone")))


def latest_backup() -> Optional[Path]:
    if not BACKUPS.exists():
        return None
    folders = sorted(d for d in BACKUPS.iterdir()
                     if d.is_dir() and "-undone" not in d.name and (d / "manifest.json").exists())
    return folders[-1] if folders else None


def undo() -> int:
    folder = latest_backup()
    if folder is None:
        print("  되돌릴 적용 기록이 없습니다 (context_packs/backups/).")
        return 1
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    print(f"  {folder.name}에 적용한 것을 되돌립니다")
    kept = 0
    for item in manifest["files"]:
        if item.get("undone"):
            continue
        target = FRONTEND / item["path"]
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            kept += 1
            print(f"  [그대로] frontend/{item['path']} — 적용한 뒤에 또 바뀌었습니다. 되돌리지 않았습니다")
            if item["existed"]:
                print(f"           원래 파일: {(folder / 'files' / item['path']).relative_to(ROOT).as_posix()}")
            continue
        if item["existed"]:
            target.write_bytes((folder / "files" / item["path"]).read_bytes())
            print(f"  [되돌림] frontend/{item['path']}")
        elif target.exists():
            target.unlink()
            print(f"  [지움]   frontend/{item['path']} (AI 답으로 새로 만들었던 파일)")
        item["undone"] = True
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    if kept:
        print("\n  일부는 되돌리지 않았습니다. `git diff`로 보고 직접 정리하세요.")
        return 1
    mark_undone(folder)
    print("\n  다 되돌렸습니다. 브라우저를 새로 고쳐 확인하세요.")
    return 0


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def read_answer(path: Path) -> Tuple[Optional[str], str]:
    if not path.exists():
        return None, (f"{path} 파일이 없습니다. AI의 답을 복사해서 이 파일에 붙여넣고 저장하세요.")
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        try:
            return raw.decode("cp949"), "⚠ UTF-8이 아니라서 cp949로 읽었습니다 (다음에는 UTF-8로 저장하세요)"
        except UnicodeDecodeError:
            return None, "파일 글자 인코딩을 읽을 수 없습니다. UTF-8로 다시 저장하세요."


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")    # 어떤 터미널에서도 글자 때문에 멈추지 않게
    parser = argparse.ArgumentParser(description="채팅형 AI의 답을 화면 파일에 적용합니다.")
    parser.add_argument("answer", nargs="?", default=str(DEFAULT_ANSWER),
                        help="AI 답을 저장한 파일 (기본: context_packs/answer.md)")
    parser.add_argument("--write", action="store_true", help="실제로 적용합니다 (백업을 남깁니다)")
    parser.add_argument("--undo", action="store_true", help="마지막 적용을 되돌립니다")
    parser.add_argument("--diff", action="store_true", help="바뀌는 곳을 전부 보여 줍니다")
    args = parser.parse_args(argv)

    print("=" * 68)
    print(" AI 답 적용하기" + (" — 되돌리기" if args.undo else
                            " — 적용" if args.write else " — 미리 보기 (아직 아무것도 바꾸지 않습니다)"))
    print("=" * 68)
    if args.undo:
        return undo()

    answer = Path(args.answer)
    if not answer.is_absolute():
        answer = (Path.cwd() / answer) if (Path.cwd() / answer).exists() else (ROOT / answer)
    text, note = read_answer(answer)
    if text is None:
        print(f"  {note}")
        return 1
    if note:
        print(f"  {note}")
    if text.lstrip().startswith("# 화면 수정 컨텍스트") or "여기까지가 묶음입니다" in text:
        print("  이 파일은 merge_ui.py가 만든 '묶음'입니다. AI에게 올리는 파일이지 적용할 답이 아닙니다.")
        print("  AI의 답을 복사해 context_packs/answer.md에 저장한 뒤 그 파일로 실행하세요.")
        return 1

    blocks, skipped = parse_answer(text)
    shown_name = answer.relative_to(ROOT).as_posix() if answer.is_relative_to(ROOT) else str(answer)
    print(f"  읽은 파일: {shown_name}  (경로가 붙은 코드 {len(blocks)}개)")
    if not blocks:
        print()
        print("  경로 표시가 붙은 코드를 찾지 못했습니다.")
        print("  코드블록 첫 줄이 `// 파일: frontend/app/page.tsx` 처럼 되어 있어야 합니다.")
        print("  AI에게 '묶음 파일 9장 형식대로, 첫 줄에 경로를 붙여서 다시 줘'라고 요청하세요.")
        return 1

    plans, notes = make_plans(blocks)
    print()
    for plan in plans:
        shown = f"frontend/{plan.rel}" if not plan.rel.startswith("?") else plan.block.path_text
        status = plan.status
        if status == "바꿈":
            detail = f"{_count(plan.current)}줄 → {_count(plan.block.content)}줄  ({change_stat(plan)})"
        elif status == "새로":
            detail = f"{_count(plan.block.content)}줄 (새 파일)"
        elif status == "같음":
            detail = "지금 파일과 똑같아서 건너뜁니다"
        else:
            detail = ""
        print(f"  [{status}] {shown}  {detail}".rstrip())
        for message in plan.errors:
            print(f"      ✖ {message}")
        for message in ([] if plan.errors else plan.warnings):
            print(f"      ⚠ {message}")
    for message in notes:
        print(f"  ⚠ {message}")
    if skipped:
        print(f"\n  [건너뜀] 경로 표시가 없는 코드블록 {len(skipped)}개 (명령어·예시일 수 있습니다)")
        for line_no, first in skipped[:5]:
            print(f"           {line_no}번째 줄: {first}")

    rejected = [p for p in plans if p.errors]
    to_write = [p for p in plans if p.status in ("바꿈", "새로")]
    if rejected:
        request = "\n".join(retry_request(plans))
        PACKS.mkdir(exist_ok=True)
        (PACKS / "retry.md").write_text(request + "\n", encoding="utf-8")
        print("\n  ✖ 거부된 파일이 있어서 아무것도 쓰지 않습니다 (반쪽만 바뀌면 더 헷갈립니다).")
        print("    AI에게 아래를 복사해서 보내세요 (context_packs/retry.md에도 저장했습니다)")
        print("  ───────────── 여기부터 복사 ─────────────")
        print(request)
        print("  ───────────── 여기까지 ─────────────")
        return 1
    if not to_write:
        print("\n  바뀌는 파일이 없습니다.")
        return 0
    if len(to_write) > MANY_FILES:
        print(f"\n  ⚠ 한 번에 {len(to_write)}개 파일이 바뀝니다. 빌드가 깨지면 원인을 찾기 어렵습니다.")

    if not args.write:
        for plan in to_write:
            print(f"\n  ── 바뀌는 곳: frontend/{plan.rel}")
            for line in diff_text(plan, None if args.diff else 60):
                print(f"  {line}")
        print("\n  → 적용하려면:  python tools/apply_ui.py --write"
              + ("" if answer == DEFAULT_ANSWER else f" {args.answer}"))
        return 0

    folder = write_plans(to_write, answer)
    print(f"\n  적용했습니다. 바꾸기 전 파일은 {folder.relative_to(ROOT).as_posix()}/ 에 있습니다.")
    print()
    print("  이제 직접 확인하세요 (docs/08 5장)")
    print("    cd frontend")
    print("    npx eslint .        # 오류가 나면 그 출력을 그대로 AI에게 붙여넣기")
    print("    npx next build")
    print("    npm run dev         # 브라우저에서 바뀐 화면을 눈으로 확인")
    print()
    print("  마음에 안 들면:  python tools/apply_ui.py --undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
