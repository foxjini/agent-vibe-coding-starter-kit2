"""
cap.py — 실습 영상에 넣을 '진짜' 실행 결과를 기록한다.

영상 속 터미널에 나오는 글자는 모두 여기서 실제로 실행해 받은 출력이다.
지어낸 출력을 쓰지 않으려고 만든 도구다.

  python cap.py run  <id> [--cwd DIR] [--show "화면에 보일 명령"] [--timeout 초]
                     [--stdin "초:글자;초:글자"] [--env K=V ...] -- 명령 인자...
  python cap.py diff <id> --repo DIR [-- 경로...]     # 지금 작업 트리의 git diff
  python cap.py note <id> --text "..."                # 손으로 적는 메모(브라우저 응답 등)

결과는 captured/<id>.json 에 줄마다 나온 시각(초)과 함께 저장한다.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "captured"


def save(cid: str, data: dict) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / f"{cid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[cap] captured/{cid}.json 저장 ({len(data.get('lines', []))}줄)", file=sys.stderr)


def cmd_run(a: argparse.Namespace) -> None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    for kv in a.env or []:
        k, _, v = kv.partition("=")
        env[k] = v
    t0 = time.monotonic()
    started_at = time.time()  # 브라우저 화면 녹화와 시각을 맞출 때 쓴다
    proc = subprocess.Popen(
        a.cmd, cwd=a.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE if a.stdin else subprocess.DEVNULL, text=True, bufsize=1,
    )
    lines = []

    def reader():
        for raw in proc.stdout:  # type: ignore[union-attr]
            text = raw.rstrip("\n")
            # 진행 표시(\r)는 마지막 상태만 남긴다
            if "\r" in text:
                text = text.split("\r")[-1]
            lines.append({"t": round(time.monotonic() - t0, 2), "text": text})
            print(text)

    th = threading.Thread(target=reader, daemon=True)
    th.start()

    if a.stdin:
        def feeder():
            for part in a.stdin.split(";"):
                at, _, txt = part.partition(":")
                delay = float(at) - (time.monotonic() - t0)
                if delay > 0:
                    time.sleep(delay)
                try:
                    proc.stdin.write(txt + "\n")  # type: ignore[union-attr]
                    proc.stdin.flush()  # type: ignore[union-attr]
                    lines.append({"t": round(time.monotonic() - t0, 2), "text": f"⌨ {txt}", "input": True})
                except (BrokenPipeError, ValueError):
                    return
        threading.Thread(target=feeder, daemon=True).start()

    timed_out = False
    try:
        proc.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.send_signal(2)  # Ctrl+C 와 같은 신호 — 프로그램의 정리 출력도 담는다
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    th.join(timeout=3)
    lines.sort(key=lambda x: x["t"])
    save(a.id, {
        "id": a.id, "kind": "run", "cwd": a.show_cwd or a.cwd, "command": a.show or " ".join(a.cmd),
        "exit": proc.returncode, "stopped_by_ctrl_c": timed_out, "started_at": started_at, "lines": lines,
    })


def cmd_diff(a: argparse.Namespace) -> None:
    args = ["git", "diff", "--no-color", "-U3", "HEAD", "--", *(a.paths or [])]
    out = subprocess.run(args, cwd=a.repo, capture_output=True, text=True, check=True).stdout
    save(a.id, {"id": a.id, "kind": "diff", "patch": out})


def cmd_note(a: argparse.Namespace) -> None:
    save(a.id, {"id": a.id, "kind": "note", "lines": [{"t": 0, "text": x} for x in a.text.split("\n")]})


def main() -> None:
    argv = sys.argv[1:]
    tail = []
    if "--" in argv:  # '--' 뒤는 그대로 실행할 명령(또는 diff 경로)이다
        i = argv.index("--")
        argv, tail = argv[:i], argv[i + 1:]
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="what", required=True)
    r = sub.add_parser("run")
    r.add_argument("id")
    r.add_argument("--cwd", default=".")
    r.add_argument("--show-cwd")
    r.add_argument("--show")
    r.add_argument("--timeout", type=float, default=60)
    r.add_argument("--stdin")
    r.add_argument("--env", action="append")
    d = sub.add_parser("diff")
    d.add_argument("id")
    d.add_argument("--repo", required=True)
    n = sub.add_parser("note")
    n.add_argument("id")
    n.add_argument("--text", required=True)
    a = p.parse_args(argv)
    a.cmd = a.paths = tail
    {"run": cmd_run, "diff": cmd_diff, "note": cmd_note}[a.what](a)


if __name__ == "__main__":
    main()
