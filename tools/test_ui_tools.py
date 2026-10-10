#!/usr/bin/env python3
"""
화면 작업 도구 자가 점검 (tools/test_ui_tools.py)
=============================================================================
`merge_ui.py`(화면 파일 묶기)와 `apply_ui.py`(AI 답 적용하기)가 약속대로 동작하는지
확인합니다. 임시 폴더에 작은 가짜 frontend를 만들어 시험하므로 **진짜 코드는 건드리지
않습니다.** 서버·DB·브라우저도 필요 없습니다.

실행 방법 (tools 폴더에서):
    python test_ui_tools.py

확인하는 것:
 1) 묶기 — 고칠 파일은 전문, 키트·로직은 쓰는 법만, 비밀은 절대 안 들어감
 2) 쓰는 법 뽑기 — 여러 줄 props·기본값·유니온 타입이 잘리지 않음
 3) 답 읽기 — 경로 표시·제목·코드만 붙여넣기·들여 쓴 블록·끊긴 답
 4) 거부 — 공통 파일·생략·diff 기호를 막고, 하나라도 거부면 아무것도 안 씀
 5) 쓰기·되돌리기 — 백업, 줄바꿈 유지, 새 파일 지우기, 나중에 고친 파일 보호
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import apply_ui  # noqa: E402
import merge_ui  # noqa: E402

REAL_FRONTEND = merge_ui.FRONTEND
_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return bool(condition)


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * 68)


def quiet(func, *args):
    """도구의 출력은 숨기고 (돌려준 값, 출력)을 받습니다."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = func(*args)
    return result, buffer.getvalue()


# ---------------------------------------------------------------------------
# 가짜 프로젝트
# ---------------------------------------------------------------------------

FAKE: Dict[str, str] = {
    "package.json": """{
  "dependencies": {"lucide-react": "^1.0.0", "next": "16.0.0", "react": "19.0.0"},
  "devDependencies": {"tailwindcss": "^4", "@types/react": "^19"}
}
""",
    ".env.local": "NEXT_PUBLIC_TEAM_NAME=비밀팀이름\nDEVICE_API_KEY=supersecretvalue123456\n",
    "app/globals.css": """@import "tailwindcss";

@theme inline {
  --color-brand: var(--ui-brand);          /* bg-brand 강조 */
  --radius-card: var(--ui-radius-card);
}

:root,
[data-style="minimal"] { --ui-brand: #2563eb; --ui-radius-card: 12px; }
[data-style="soft"] { --ui-brand: #b44d18; }

.card { background: white; }

@keyframes kit-pulse { from { opacity: 1 } to { opacity: 0.5 } }
""",
    "app/layout.tsx": """import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "테스트" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="ko"><body>{children}</body></html>);
}
""",
    "app/page.tsx": """/**
 * 테스트 화면
 *
 * 예시 (따라가면 안 됩니다):
 * import Ghost from "@/components/team/Ghost";
 */
"use client";

import { Bell } from "lucide-react";
import React, { useState } from "react";

import KitCard from "@/components/kit/KitCard";
import Panel from "@/components/team/Panel";
import { useThing } from "@/scenarios/useThing";

export default function Page() {
  const [open, setOpen] = useState(false);
  const thing = useThing();
  return (
    <main>
      <Bell />
      <KitCard title="a" onPick={() => setOpen(!open)} />
      <Panel value={thing.value} />
    </main>
  );
}
""",
    "app/study/page.tsx": """"use client";

export default function StudyPage() {
  return <main>study</main>;
}
""",
    "app/kit/page.tsx": """"use client";

export default function KitPage() {
  return <main>kit</main>;
}
""",
    "components/kit/KitCard.tsx": """/** 키트 카드 (테스트) */
"use client";

import React from "react";

import KitInner from "@/components/kit/KitInner";
import type { Thing } from "@/lib/types";

export interface KitCardProps {
  title: string;
  /** 고를 때 부릅니다 */
  onPick: (
    id: string,
  ) => void;
  thing?: Thing;
}

export default function KitCard({
  title,
  onPick,
}: KitCardProps) {
  const hiddenImplementation = 42;
  return <div onClick={() => onPick(title)}><KitInner />{hiddenImplementation}</div>;
}
""",
    "components/kit/KitInner.tsx": """export default function KitInner() {
  return <span />;
}
""",
    "components/team/Panel.tsx": """"use client";

import React from "react";

import Badge from "./Badge";

export const API_KEY = "abcdefghijklmnop123456";

export default function Panel({ value }: { value: number }) {
  return <div><Badge />{value}</div>;
}
""",
    "components/team/Badge.tsx": """"use client";

export const FENCE_EXAMPLE = "```";

export default function Badge() {
  return <span>badge</span>;
}
""",
    "components/team/Ghost.tsx": """export default function Ghost() {
  return null;
}
""",
    "lib/types.ts": """export interface Thing {
  value: number;
}

export type Mode =
  | "a"
  | "b";
""",
    "scenarios/useThing.ts": """import { useState } from "react";

import type { Thing } from "@/lib/types";

export interface ThingApi {
  value: number;
  reset: () => void;
}

export function useThing(): ThingApi {
  const [value] = useState(1);
  return { value, reset: () => {} };
}
""",
}


def make_fake(root: Path) -> None:
    for rel, text in FAKE.items():
        target = root / "frontend" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def point_tools_at(root: Path) -> None:
    merge_ui.ROOT, merge_ui.FRONTEND, merge_ui.OUT_DIR = root, root / "frontend", root / "context_packs"
    apply_ui.ROOT, apply_ui.FRONTEND = root, root / "frontend"
    apply_ui.PACKS = root / "context_packs"
    apply_ui.DEFAULT_ANSWER = apply_ui.PACKS / "answer.md"
    apply_ui.BACKUPS = apply_ui.PACKS / "backups"


def write_answer(root: Path, text: str, name: str = "answer.md") -> Path:
    path = root / "context_packs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def block(path: str, body: str, lang: str = "tsx") -> str:
    marker = f"/* 파일: {path} */" if path.endswith(".css") else f"// 파일: {path}"
    return f"```{lang}\n{marker}\n{body.rstrip()}\n```\n"


# ---------------------------------------------------------------------------
# 1. 묶기
# ---------------------------------------------------------------------------

def test_merge(root: Path) -> None:
    section("1. 묶기 — 고칠 파일은 전문, 키트·로직은 쓰는 법만")
    out = root / "context_packs"

    code, _ = quiet(merge_ui.main, ["--list"])
    check("--list 는 파일을 만들지 않음", code == 0 and not (out / "ui_home.md").exists())

    code, _ = quiet(merge_ui.main, ["--add", ".env.local", "--add", "../outside.txt",
                                    "--add", "package.json"])
    pack = (out / "ui_home.md").read_text(encoding="utf-8") if code == 0 else ""
    check("기본 묶음은 ui_home.md", code == 0 and bool(pack))

    def section_of(rel: str) -> str:
        match = re.search(rf"### `frontend/{re.escape(rel)}` — (.*)", pack)
        return match.group(1) if match else ""

    check("고칠 화면(app/page.tsx)은 전문", "전문" in section_of("app/page.tsx"))
    check("layout.tsx · globals.css는 언제나 전문",
          "전문" in section_of("app/layout.tsx") and "전문" in section_of("app/globals.css"))
    check("화면이 쓰는 팀 컴포넌트는 전문 (상대 경로 import까지)",
          "전문" in section_of("components/team/Panel.tsx")
          and "전문" in section_of("components/team/Badge.tsx"))
    kit = section_of("components/kit/KitCard.tsx")
    check("키트 컴포넌트는 쓰는 법만 — props 타입은 있고 구현은 없음",
          "쓰는 법만" in kit and "export interface KitCardProps" in pack
          and "onPick: (" in pack and "hiddenImplementation" not in pack)
    check("키트 카드의 속(KitInner)은 따라가지 않음", "KitInner.tsx" not in pack)
    check("키트가 쓰는 타입 파일(lib/types.ts)은 한 단계 더 따라감",
          "쓰는 법만" in section_of("lib/types.ts") and '| "b";' in pack)
    check("시나리오 훅은 쓰는 법만 — 돌려주는 타입은 전문",
          "쓰는 법만" in section_of("scenarios/useThing.ts")
          and "export interface ThingApi" in pack and "useState(1)" not in pack)
    check("주석 속 예시 import(Ghost)는 따라가지 않음", "components/team/Ghost.tsx" not in pack)
    check(".env.local은 --add로도 들어가지 않음",
          "비밀팀이름" not in pack and "supersecretvalue" not in pack)
    check("frontend 밖 · 설정 파일은 --add로도 들어가지 않음",
          "outside.txt" not in pack and '"devDependencies"' not in pack)
    check("코드에 적어 둔 비밀값처럼 보이는 문자열은 지워짐",
          "abcdefghijklmnop123456" not in pack and "<비밀값이라 지웠습니다>" in pack)
    check("코드 안에 ```가 있어도 더 긴 울타리로 감쌈", "````tsx" in pack)
    check("디자인 토큰 → 클래스 이름 표 (bg-brand · rounded-card)",
          "`bg-brand`" in pack and "`rounded-card`" in pack)
    check("스타일 묶음 · 직접 만든 클래스 · 애니메이션 이름",
          "`minimal`" in pack and "`soft`" in pack and "`.card`" in pack and "`kit-pulse`" in pack)
    check("설치된 패키지 표 (@types는 뺌)", "`lucide-react`" in pack and "@types/react" not in pack)
    check("제약 · 답변 형식(경로 표시 규칙)이 들어 있음",
          "## 2. 지켜야 할 제약" in pack and "// 파일: frontend/app/page.tsx" in pack
          and "여기까지가 묶음입니다" in pack)

    code, _ = quiet(merge_ui.main, ["--page", "study"])
    check("--page study → ui_study.md", code == 0 and (out / "ui_study.md").exists())
    code, _ = quiet(merge_ui.main, ["--all"])
    every = (out / "ui_all.md").read_text(encoding="utf-8") if code == 0 else ""
    check("--all → 키트 화면만 빼고 전부",
          "`frontend/app/study/page.tsx` — ★ 고치는 파일 · 전문" in every
          and "`frontend/app/kit/page.tsx` — " not in every)
    code_missing, _ = quiet(merge_ui.main, ["--page", "nope"])
    code_kit, _ = quiet(merge_ui.main, ["--page", "kit"])
    check("없는 화면 · 키트 화면은 거부 (코드 2)", code_missing == 2 and code_kit == 2)


# ---------------------------------------------------------------------------
# 2. 쓰는 법 뽑기
# ---------------------------------------------------------------------------

def test_api_view() -> None:
    section("2. 쓰는 법 뽑기 — 타입은 전문, 함수는 이름과 매개변수")
    view = merge_ui.api_view(
        "export default function X({\n  a,\n  b = 2,\n}: {\n  a: string;\n  b?: number;\n}) {\n"
        "  const hidden = 1;\n  return null;\n}\n")
    check("여러 줄 props 구조분해가 통째로 남음", "b?: number;" in view and "}) {" in view
          and "hidden" not in view)
    view = merge_ui.api_view(
        "export function f(\n  pick: (c: string[]) => string = (c) =>\n    c[0],\n): { ok: boolean } {\n"
        "  return { ok: true };\n}\n")
    check("기본값에 화살표 함수가 든 매개변수 · 객체 반환 타입",
          "): { ok: boolean } {" in view and "return { ok: true }" not in view)
    view = merge_ui.api_view('export type U =\n  | "a"\n  | "b";\n\nconst x = 1;\n')
    check("여러 줄 유니온 타입은 전문", '| "b";' in view and "const x" not in view)
    view = merge_ui.api_view("export function one() { return 1; }\nexport const Z = 3;\n")
    check("한 줄 함수 다음 선언도 놓치지 않음", "export const Z = 3;" in view)

    missing: List[str] = []
    for folder in ("app", "components", "lib", "scenarios"):
        for path in (REAL_FRONTEND / folder).rglob("*.ts*"):
            text = path.read_text(encoding="utf-8")
            shown = merge_ui.api_view(text)
            missing += [f"{path.name}: {line[:40]}" for line in text.split("\n")
                        if line.startswith("export") and line.rstrip() not in shown]
    check("실제 저장소의 모든 export가 쓰는 법에 남음", not missing, "; ".join(missing[:3]))


# ---------------------------------------------------------------------------
# 3. 답 읽기
# ---------------------------------------------------------------------------

def test_parse() -> None:
    section("3. 답 읽기 — 경로 표시가 붙은 코드만 꺼냄")
    blocks, _ = apply_ui.parse_answer(block("frontend/app/page.tsx", '"use client";\nX'))
    check("// 파일: 경로를 읽고, 그 줄은 내용에서 뺌",
          len(blocks) == 1 and blocks[0].path_text == "frontend/app/page.tsx"
          and blocks[0].content.startswith('"use client";'))
    blocks, _ = apply_ui.parse_answer(block("frontend/app/globals.css", '@import "tailwindcss";', "css"))
    check("CSS 경로 표시 /* 파일: … */", len(blocks) == 1
          and blocks[0].path_text == "frontend/app/globals.css")
    check("frontend/를 빼먹은 경로도 알아들음",
          apply_ui.normalize_path("app/page.tsx")[0] == "app/page.tsx")
    blocks, _ = apply_ui.parse_answer(
        "### 파일: frontend/components/team/Panel.tsx\n\n```tsx\nexport default function P() {}\n```\n")
    check("제목(### 파일: …)에 적힌 경로도 읽음",
          len(blocks) == 1 and blocks[0].path_text == "frontend/components/team/Panel.tsx")
    blocks, skipped = apply_ui.parse_answer(
        "1. `frontend/app/page.tsx`를 저장한 뒤 실행하세요:\n\n```bash\ncd frontend\n```\n")
    check("경로가 적힌 제목 아래의 명령어 블록은 코드로 착각하지 않음",
          not blocks and len(skipped) == 1)
    blocks, _ = apply_ui.parse_answer(
        "// 파일: frontend/app/page.tsx\nA\n// 파일: frontend/components/team/New.tsx\nB\n")
    check("코드만 붙여넣어도 경로 표시로 파일을 나눔",
          [b.content for b in blocks] == ["A", "B"])
    blocks, _ = apply_ui.parse_answer(
        "1. 이렇게 바꿉니다:\n\n   ```tsx\n   // 파일: frontend/components/team/New.tsx\n"
        "   export const A = 1;\n   ```\n")
    check("목록 안에 들여 쓴 코드블록은 들여쓰기를 걷어 냄",
          len(blocks) == 1 and blocks[0].content == "export const A = 1;")
    blocks, _ = apply_ui.parse_answer("```tsx\n// 파일: frontend/app/page.tsx\nexport default 1\n")
    check("닫히지 않은 코드블록은 끊긴 답으로 표시", len(blocks) == 1 and not blocks[0].closed)
    blocks, _ = apply_ui.parse_answer("```tsx\n// frontend/app/page.tsx (파일 전체)\nX\n```\n")
    check("예전 형식(첫 줄이 경로만 적힌 주석)도 읽음",
          len(blocks) == 1 and blocks[0].path_text == "frontend/app/page.tsx")


# ---------------------------------------------------------------------------
# 4. 거부
# ---------------------------------------------------------------------------

def plan_for(path: str, body: str) -> "apply_ui.Plan":
    plans, _ = apply_ui.make_plans(apply_ui.parse_answer(block(path, body))[0])
    return plans[0]


def test_refuse(root: Path) -> None:
    section("4. 거부 — 공통 파일·생략·diff 기호")
    check("키트 파일은 거부", plan_for("frontend/components/kit/KitCard.tsx", "export const A = 1;").errors)
    check("설정 파일 · .env는 거부",
          plan_for("frontend/package.json", "{}").errors and plan_for("frontend/.env.local", "X=1").errors)
    check("frontend 밖을 가리키는 경로는 거부",
          apply_ui.normalize_path("frontend/../backend/main.py")[0] is None
          and apply_ui.normalize_path("/etc/passwd")[0] is None)
    samples = ["  // ... 기존 코드 ...", "  ...", "      {/* ... */}", "  // 나머지는 그대로",
               "  /* 이하 생략 */", "  // ... existing code ..."]
    caught = [s for s in samples if apply_ui.omission_lines(f"const a = 1;\n{s}\nconst b = 2;")]
    check("생략 표시 6가지를 모두 잡음", len(caught) == len(samples),
          f"놓친 것: {[s for s in samples if s not in caught]}")
    check("생략 표시가 든 답은 실제로 거부됨",
          plan_for("frontend/components/team/Panel.tsx",
                   "export const A = 1;\n// ... 기존 코드 ...\nexport const B = 2;").errors)
    legit = "const a = { ...rest };\nconst b = [...items];\n// 다른 팀 화면은 그대로 둡니다\n"
    check("펼침 연산자(...rest)와 보통 주석은 생략으로 보지 않음", not apply_ui.omission_lines(legit))

    false_alarms: List[str] = []
    for folder in ("app", "components", "lib", "scenarios"):
        for path in (REAL_FRONTEND / folder).rglob("*.ts*"):
            text = path.read_text(encoding="utf-8")
            if apply_ui.omission_lines(text) or apply_ui.diff_marks(text) >= 2:
                false_alarms.append(path.name)
    check("지금 저장소의 파일 전체에서 생략·diff 오탐 0개", not false_alarms, ", ".join(false_alarms))

    check("diff 기호(+/-)가 붙은 코드는 거부",
          plan_for("frontend/components/team/Panel.tsx", "+import x\n-import y\n const z = 1;").errors)
    check("page.tsx에 export default가 없으면 거부",
          plan_for("frontend/app/page.tsx", '"use client";\nconst x = 1;').errors)
    check('layout.tsx에 "use client"를 넣으면 거부',
          plan_for("frontend/app/layout.tsx",
                   '"use client";\nexport const metadata = {};\nexport default function L() {}').errors)

    page = root / "frontend" / "app" / "page.tsx"
    before = page.read_bytes()
    answer = write_answer(root, block("frontend/app/page.tsx", FAKE["app/page.tsx"].replace("main", "section"))
                          + block("frontend/lib/types.ts", "export const X = 1;", "ts"))
    code, _ = quiet(apply_ui.main, [str(answer), "--write"])
    check("하나라도 거부면 아무것도 쓰지 않음 (멀쩡한 파일도 그대로)",
          code == 1 and page.read_bytes() == before)
    retry = root / "context_packs" / "retry.md"
    check("AI에게 보낼 다시 요청 문장을 retry.md에 남김",
          retry.exists() and "4팀 공통 파일이라 고칠 수 없어" in retry.read_text(encoding="utf-8"))
    pack = write_answer(root, "# 화면 수정 컨텍스트 — `/` 화면\n\n" + block("frontend/app/page.tsx", "x"),
                        "ui_home_copy.md")
    code, out = quiet(apply_ui.main, [str(pack), "--write"])
    check("묶음 파일을 답으로 잘못 주면 거부", code == 1 and "묶음" in out and page.read_bytes() == before)


# ---------------------------------------------------------------------------
# 5. 쓰기·되돌리기
# ---------------------------------------------------------------------------

def test_write_undo(root: Path) -> None:
    section("5. 쓰기·되돌리기 — 백업, 줄바꿈, 새 파일, 나중에 고친 파일")
    front = root / "frontend"
    page = front / "app" / "page.tsx"
    crlf = front / "components" / "team" / "Crlf.tsx"
    crlf.write_bytes(b'"use client";\r\nexport default function C() {\r\n  return null;\r\n}\r\n')
    original_page, original_crlf = page.read_bytes(), crlf.read_bytes()

    new_page = FAKE["app/page.tsx"].replace("<main>", "<main className=\"card\">")
    new_crlf = '"use client";\nexport default function C() {\n  return <b>crlf</b>;\n}\n'
    answer = write_answer(root, "계획: 두 파일을 바꿉니다.\n\n"
                          + block("frontend/app/page.tsx", new_page)
                          + block("frontend/components/team/Crlf.tsx", new_crlf)
                          + block("frontend/components/team/Fresh.tsx",
                                  '"use client";\nexport default function F() { return null; }'))

    code, out = quiet(apply_ui.main, [str(answer)])
    check("미리 보기는 아무것도 바꾸지 않음",
          code == 0 and page.read_bytes() == original_page and not (front / "components/team/Fresh.tsx").exists()
          and "--write" in out)

    code, _ = quiet(apply_ui.main, [str(answer), "--write"])
    fresh = front / "components" / "team" / "Fresh.tsx"
    backups = sorted((root / "context_packs" / "backups").iterdir())
    check("--write: 바뀐 파일 · 새 파일 · 백업",
          code == 0 and 'className="card"' in page.read_text(encoding="utf-8") and fresh.exists()
          and len(backups) == 1 and (backups[0] / "files" / "app" / "page.tsx").read_bytes() == original_page)
    data = crlf.read_bytes()
    check("원래 CRLF였던 파일은 CRLF를 유지", b"crlf" in data and data.count(b"\r\n") == data.count(b"\n"))

    code, out = quiet(apply_ui.main, [str(answer)])
    check("이미 적용한 답을 다시 보면 '같음'으로 건너뜀", code == 0 and "바뀌는 파일이 없습니다" in out)

    twice = write_answer(root, block("frontend/components/team/Fresh.tsx", "export const A = 1;")
                         + block("frontend/components/team/Fresh.tsx", "export const A = 2;"), "twice.md")
    plans, notes = apply_ui.make_plans(apply_ui.parse_answer(twice.read_text(encoding="utf-8"))[0])
    check("같은 파일이 두 번 나오면 뒤의 것을 씀",
          len(plans) == 1 and plans[0].block.content == "export const A = 2;" and notes)

    code, _ = quiet(apply_ui.main, ["--undo"])
    check("--undo: 원래 파일로 돌아가고 새 파일은 지움",
          code == 0 and page.read_bytes() == original_page and crlf.read_bytes() == original_crlf
          and not fresh.exists())
    check("되돌린 기록은 -undone으로 표시", backups[0].with_name(backups[0].name + "-undone").exists())

    quiet(apply_ui.main, [str(answer), "--write"])
    page.write_text(page.read_text(encoding="utf-8") + "\n// 학생이 나중에 고침\n", encoding="utf-8")
    code, out = quiet(apply_ui.main, ["--undo"])
    check("적용한 뒤 학생이 또 고친 파일은 되돌리지 않음",
          code == 1 and "학생이 나중에 고침" in page.read_text(encoding="utf-8")
          and crlf.read_bytes() == original_crlf)

    for folder in list((root / "context_packs" / "backups").iterdir()):
        if "-undone" not in folder.name:
            apply_ui.mark_undone(folder)          # 같은 이름이 이미 있어도 겹치지 않아야 합니다
    code, out = quiet(apply_ui.main, ["--undo"])
    check("되돌릴 것이 없으면 그렇게 알려 줌", code == 1 and "없습니다" in out)


def main() -> int:
    print("=" * 68)
    print(" 화면 작업 도구 자가 점검 (merge_ui · apply_ui)")
    print("=" * 68)
    saved = {name: getattr(merge_ui, name) for name in ("ROOT", "FRONTEND", "OUT_DIR")}
    saved_apply = {name: getattr(apply_ui, name)
                   for name in ("ROOT", "FRONTEND", "PACKS", "DEFAULT_ANSWER", "BACKUPS")}
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_fake(root)
            point_tools_at(root)
            test_merge(root)
            test_api_view()
            test_parse()
            test_refuse(root)
            test_write_undo(root)
    finally:
        for name, value in saved.items():
            setattr(merge_ui, name, value)
        for name, value in saved_apply.items():
            setattr(apply_ui, name, value)

    print("\n" + "=" * 68)
    print(f" 결과: 성공 {_passed}건 / 실패 {_failed}건")
    print("=" * 68)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
