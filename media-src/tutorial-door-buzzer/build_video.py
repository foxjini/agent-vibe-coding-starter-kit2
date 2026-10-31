"""
build_video.py — 실습 영상(문 열림 센서 + 경고 부저) 두 편을 만든다.

  python build_video.py pi        # ① 라즈베리파이 편
  python build_video.py web       # ② 백엔드·프론트엔드 편
  python build_video.py pi --check 12.5 40   # 그 시각들의 화면만 PNG 로 (검수용)

흐름: episodes.py 의 장면 대본 → 시각표(timeline.js) → player.html 을 프레임마다 그려
JPEG 로 ffmpeg 에 흘려 넣기 → 효과음·배경음 합성 → mp4 + 자막 대본(.srt).
화면 속 터미널 출력과 관리자 화면은 captured/ 에 기록한 실제 실행 결과만 쓴다 (cap.py, screen_rec.mjs).

준비물: ffmpeg, node + playwright-core, Chromium, numpy, pygments,
        Pretendard(frontend/node_modules/pretendard), D2Coding(npm i d2coding)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name
from pygments.token import Token

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CAPT = HERE / "captured"
OUT = HERE / "out"
FPS = 15
SR = 48000

# ── 자막 길이: 한국어 자막을 읽는 데 드는 시간 ─────────────────────────────
def cap_dur(text: str) -> float:
    n = len(re.sub(r"\s+", "", text))
    return max(3.0, min(9.0, 1.4 + n * 0.115))


# ── 구문 강조 ─────────────────────────────────────────────────────────────
def _cls(tok) -> str:
    if tok in Token.Comment:
        return "c"
    if tok in Token.Literal.String:
        return "s"
    if tok in Token.Literal.Number:
        return "n"
    if tok in Token.Keyword:
        return "k"
    if tok in Token.Name.Builtin:
        return "b"
    if tok in Token.Name.Function or tok in Token.Name.Decorator:
        return "f"
    if tok in Token.Name.Class:
        return "cl"
    if tok in Token.Name.Tag:
        return "tg"
    if tok in Token.Name.Attribute:
        return "at"
    if tok in Token.Operator.Word:
        return "k"
    return ""


def lexer_for(path: str):
    if path.endswith(".tsx"):
        try:
            return get_lexer_by_name("tsx")
        except Exception:
            return get_lexer_by_name("typescript")
    return get_lexer_for_filename(path)


def tokenize_block(path: str, lines):
    """여러 줄을 한꺼번에 강조해서(여러 줄 문자열이 깨지지 않게) 줄별 토큰으로 돌려준다."""
    if not lines:
        return []
    src = "\n".join(lines) + "\n"
    out, cur = [], []
    for tok, val in lexer_for(path).get_tokens(src):
        parts = val.split("\n")
        for i, part in enumerate(parts):
            if part:
                c = _cls(tok)
                if cur and cur[-1][0] == c:
                    cur[-1][1] += part
                else:
                    cur.append([c, part])
            if i < len(parts) - 1:
                out.append(cur)
                cur = []
    return out[: len(lines)]


# ── diff ──────────────────────────────────────────────────────────────────
def parse_patch(patch: str):
    """{파일: [hunk, ...]}  hunk = {"head", "ctx": 함수 이름, "lines": [(종류, 줄번호, 글)]}"""
    files, cur, hunk = {}, None, None
    for raw in patch.split("\n"):
        if raw.startswith("diff --git"):
            cur = None
        elif raw.startswith("+++ "):
            cur = raw[6:] if raw.startswith("+++ b/") else raw[4:]
            files.setdefault(cur, [])
        elif raw.startswith("@@") and cur:
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@ ?(.*)", raw)
            hunk = {"old": int(m.group(1)), "new": int(m.group(2)), "ctx": m.group(3), "lines": []}
            files[cur].append(hunk)
        elif hunk is not None and cur and raw[:1] in (" ", "+", "-") and not raw.startswith(("--- ", "+++ ")):
            hunk["lines"].append(raw)
    for hunks in files.values():
        for h in hunks:
            o, n, rows = h["old"], h["new"], []
            for raw in h["lines"]:
                kind = {" ": "ctx", "+": "add", "-": "del"}[raw[0]]
                if kind == "del":
                    rows.append([kind, o, raw[1:]]); o += 1
                elif kind == "add":
                    rows.append([kind, n, raw[1:]]); n += 1
                else:
                    rows.append([kind, n, raw[1:]]); o += 1; n += 1
            h["rows"] = rows
    return files


def edit_lines(diff_id: str, path: str, hunks, focus_text=None):
    patch = json.loads((CAPT / f"{diff_id}.json").read_text(encoding="utf-8"))["patch"]
    files = parse_patch(patch)
    if path not in files:
        raise SystemExit(f"{diff_id} 에 {path} 가 없습니다: {list(files)}")
    allh = files[path]
    sel = allh if hunks == "all" else [allh[i] for i in hunks]
    lines, is_new = [], all(h["old"] == 0 for h in allh)
    for hi, h in enumerate(sel):
        if hi or not is_new:
            where = f"⋯ {h['rows'][0][1]}번째 줄 근처" + (f" · {h['ctx'].strip()}" if h["ctx"].strip() else "")
            lines.append({"type": "sep", "text": where})
        newside = [r for r in h["rows"] if r[0] != "del"]
        toks = tokenize_block(path, [r[2] for r in newside])
        dels = [r for r in h["rows"] if r[0] == "del"]
        dtoks = tokenize_block(path, [r[2] for r in dels])
        ni = di = 0
        for kind, no, text in h["rows"]:
            if kind == "del":
                t = dtoks[di] if di < len(dtoks) else [["", text]]; di += 1
                lines.append({"type": "del", "no": None, "toks": t})
            else:
                t = toks[ni] if ni < len(toks) else [["", text]]; ni += 1
                ln = {"type": kind, "no": no, "toks": t}
                if focus_text and kind == "add" and any(f in text for f in focus_text):
                    ln["focus"] = True
                lines.append(ln)
    return lines, is_new


# ── 터미널 출력 ───────────────────────────────────────────────────────────
SCRATCH = re.compile(r"/tmp/claude-0/[^\s\"']*?/scratchpad/")


def tidy(text: str) -> str:
    """이 컴퓨터에만 있는 긴 경로를 줄여 보여 준다 (내용은 바꾸지 않는다)."""
    text = re.sub(r"[^\s\"']*/pivenv/lib/python3\.\d+/site-packages/", "…/site-packages/", text)
    text = SCRATCH.sub("~/", text)
    return text


def line_class(text: str) -> str:
    if re.search(r"Traceback|Error|❌|🚨|401\)|\b401\b|raise |GPIOPinInUse", text):
        return "err"
    if "🔍" in text or "⚠️" in text or "DEVICE_NOT_FOUND" in text:
        return "warn"
    if re.search(r"✅|📤|✓|🎉|recorded\":true|200 OK", text):
        return "ok"
    if text.startswith("INFO") or "💓" in text or text.startswith("  File ") or text.startswith("    "):
        return "dim"
    return ""


def load_run(cid: str):
    return json.loads((CAPT / f"{cid}.json").read_text(encoding="utf-8"))


def term_lines(cid: str, speed=1.0, only=None, drop=None, max_lines=None, gap=None):
    d = load_run(cid)
    rows = []
    for l in d["lines"]:
        text = tidy(l["text"])
        if only and not re.search(only, text):
            continue
        if drop and re.search(drop, text):
            continue
        if l.get("input"):
            rows.append({"at": l["t"] / speed, "text": f"⌨  {text[2:].strip()}  + Enter   (키보드 입력)", "cls": "in"})
            continue
        # 진행 표시(\r) 뒤에 이어 붙은 글은 따로 떼어 실제 화면처럼 보이게 한다
        rows.append({"at": l["t"] / speed, "text": text, "cls": line_class(text)})
    if gap is not None:  # 한꺼번에 쏟아지는 출력은 줄마다 gap 초씩 벌린다
        for i, r in enumerate(rows):
            r["at"] = max(r["at"], i * gap)
    if max_lines:
        rows = rows[:max_lines]
    return d, rows


# ── 장면 만들기 도구 ──────────────────────────────────────────────────────
class Ep:
    def __init__(self, ep_id, label, title, chapters, tree=None):
        self.id, self.label, self.title = ep_id, label, title
        self.chapters = [{"no": n, "short": s} for n, s in chapters]
        self.tree = tree or []
        self.scenes, self.captions, self.sfx = [], [], []
        self.t = 0.0
        self.chapter = -1
        self._carry = []   # 앞 IDE 장면의 대화·편집 기록 (이어 보이게)

    # 자막 여러 개를 t 부터 차례로 깐다. 걸린 시간을 돌려준다
    def _caps(self, caps, t0):
        t = t0
        for c in caps or []:
            d = cap_dur(c)
            self.captions.append({"start": round(t, 3), "end": round(t + d, 3), "text": c})
            t += d
        return t - t0

    def _scene(self, typ, dur, data=None, events=None, **kw):
        s = {"id": len(self.scenes), "type": typ, "start": round(self.t, 3), "end": round(self.t + dur, 3),
             "chapter": self.chapter, "data": data or {}, "events": events or []}
        s.update(kw)
        self.scenes.append(s)
        self.t += dur
        return s

    def title_card(self, kicker, title, sub, parts, caps):
        d = max(5.0, self._caps(caps, self.t + 0.6) + 1.0)
        self.sfx.append(("swell", self.t))
        self._scene("title", d, {"kicker": kicker, "title": title, "sub": sub, "parts": parts})

    def chapter_card(self, title, sub="", caps=None, no=None):
        self.chapter += 1
        no = no or self.chapters[self.chapter]["no"]
        d = max(3.2, self._caps(caps, self.t + 0.4) + 0.8)
        self.sfx.append(("swell", self.t))
        self._scene("chapter", d, {"no": no, "title": title, "sub": sub})

    def end_card(self, title, sub, caps):
        d = max(5.0, self._caps(caps, self.t + 0.4) + 1.5)
        self._scene("chapter", d, {"no": "끝", "title": title, "sub": sub})

    def card(self, title, items, caps_per_item, reveal=True):
        evs, t = [], self.t + 0.3
        for i, caps in enumerate(caps_per_item):
            d = max(2.4, self._caps(caps, t))
            evs.append({"id": i, "start": round(t, 3), "end": round(t + d, 3)})
            self.sfx.append(("tick", t))
            t += d
        self._scene("card", t - self.t + 0.6, {"title": title, "items": items, "reveal": reveal}, evs)

    def diagram(self, name, steps):
        evs, t = [], self.t + 0.3
        for i, (on, caps, *rest) in enumerate(steps):
            dim = rest[0] if rest else []
            d = max(2.8, self._caps(caps, t))
            evs.append({"id": i, "start": round(t, 3), "end": round(t + d, 3), "on": on, "dim": dim})
            t += d
        self._scene("diagram", t - self.t + 0.5, {"name": name}, evs)

    # ── IDE 장면: 이벤트를 차례로 쌓는다 ──
    def ide(self, role, events, keep=True):
        evs, t = [], self.t + 0.4
        carry = [dict(e, start=self.t - 1000 - i, end=self.t - 1000 - i + 1) for i, e in enumerate(self._carry)] if keep else []
        for i, e in enumerate(events):
            kind = e["kind"]
            ev = {"id": f"{len(self.scenes)}-{i}", "kind": kind, "start": round(t, 3)}
            anim = 0.0
            if kind == "prompt":
                ev.update(text=e["text"], cps=e.get("cps", 26))
                anim = len(e["text"]) / ev["cps"] + 0.8
                self.sfx.append(("type", t, len(e["text"]) / ev["cps"], ev["cps"]))
                self.sfx.append(("send", t + anim - 0.4))
            elif kind == "reply":
                ev.update(text=e["text"], cps=e.get("cps", 70), files=e.get("files"))
                anim = len(e["text"]) / ev["cps"] + 0.8
                self.sfx.append(("ping", t))
            elif kind == "edit":
                lines, is_new = edit_lines(e["diff"], e["file"], e.get("hunks", "all"), e.get("focus"))
                adds = sum(1 for l in lines if l["type"] == "add")
                ev.update(file=e["file"], lines=lines, isNew=is_new,
                          addChars=sum(max(1, sum(len(x[1]) for x in l["toks"])) for l in lines if l["type"] == "add"),
                          reveal=e.get("reveal", min(9.0, 0.6 + adds * 0.16)))
                if "scrollTo" in e:
                    ev["scrollTo"] = e["scrollTo"]
                anim = ev["reveal"] + 1.0
                self.sfx.append(("stream", t, ev["reveal"]))
            elif kind == "term":
                d, rows = term_lines(e["cap"], e.get("speed", 1.0), e.get("only"), e.get("drop"), e.get("max_lines"), e.get("gap"))
                cmd = e.get("cmd", d.get("command"))
                cps = e.get("cps", 32 if len(cmd) < 90 else 70)
                cwd = d.get("cwd") or ""
                ev.update(cmd=cmd, cps=cps, prompt=e.get("prompt", f"{cwd} $" if cwd else "$"), lines=rows,
                          cwdLabel=e.get("label", cwd))
                out = (rows[-1]["at"] if rows else 0) + 0.6
                anim = len(cmd) / cps + 0.35 + min(out, e.get("max_out", 60))
                self.sfx.append(("type", t, len(cmd) / cps, cps))
                for r in rows:
                    at = t + len(cmd) / cps + 0.35 + r["at"]
                    if r["cls"] == "err" and not any(s[0] == "err" and abs(s[1] - at) < 2 for s in self.sfx):
                        self.sfx.append(("err", at))
                    if "🔔 삐-" in r["text"]:
                        self.sfx.append(("beep", at))
            elif kind == "hold":
                anim = e.get("dur", 0.5)
            dur = max(anim, self._caps(e.get("caps"), t)) + e.get("pad", 0.4)
            ev["end"] = round(t + dur, 3)
            evs.append(ev)
            t += dur
        all_evs = carry + evs
        self._scene("ide", t - self.t + 0.3, {}, all_evs, tree=self.tree, role=role)
        chat = [e for e in all_evs if e["kind"] in ("prompt", "reply")][-4:]
        last_edit = {}
        for e in all_evs:
            if e["kind"] == "edit":
                last_edit[e["file"]] = e
        self._carry = sorted(list(last_edit.values()), key=lambda e: e["start"]) + chat

    def browser(self, rec, start, end, crop, caps, speed=1.0, term=None, highlights=None, url="localhost:3000/admin",
                beeps=True):
        fr = json.loads((CAPT / "screens" / rec / "frames.json").read_text(encoding="utf-8"))
        frames = [{"t": f["t"], "file": f["file"]} for f in fr["frames"] if "file" in f]
        data = {"dir": f"screens/{rec}", "frames": frames, "from": start, "speed": speed, "crop": crop, "url": url,
                "highlights": highlights or []}
        if term:
            d = load_run(term)
            off = d["started_at"] - fr["started_at"]
            rows = []
            for l in d["lines"]:
                text = tidy(l["text"])
                if l.get("input"):
                    rows.append({"t": l["t"] + off, "text": f"⌨  {text[2:].strip()}  + Enter", "cls": "in"})
                else:
                    rows.append({"t": l["t"] + off, "text": text, "cls": line_class(text)})
            data["term"] = {"command": d["command"], "lines": rows}
            if beeps:
                for r in rows:
                    if "🔔 삐-" in r["text"] and start <= r["t"] <= end:
                        self.sfx.append(("beep", self.t + (r["t"] - start) / speed))
        # 자막은 (녹화 속 시각, 글) — 화면에서 그 일이 일어나는 순간에 맞춰 띄운다
        timed = sorted(caps, key=lambda c: c[0])
        last_end = self.t
        for i, (at, text) in enumerate(timed):
            s0 = self.t + (at - start) / speed
            e0 = s0 + cap_dur(text)
            if i + 1 < len(timed):
                e0 = min(e0, self.t + (timed[i + 1][0] - start) / speed)
            self.captions.append({"start": round(s0, 3), "end": round(e0, 3), "text": text})
            last_end = max(last_end, e0)
        d = max((end - start) / speed, last_end - self.t + 0.4)
        self._scene("browser", d, data)

    def timeline(self):
        return {"ep": self.id, "ep_label": self.label, "title": self.title, "chapters": self.chapters,
                "duration": round(self.t, 3), "scenes": self.scenes, "captions": self.captions}


# ── 소리 ──────────────────────────────────────────────────────────────────
def synth_audio(ep: Ep, path: Path):
    n = int((ep.t + 1) * SR)
    sfx = np.zeros(n)
    rng = np.random.default_rng(7)

    def put(sig, at, gain):
        i = int(at * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        sfx[i:j] += sig[: j - i] * gain

    def env(L, a=0.002, r=0.05):
        t = np.arange(L) / SR
        return np.minimum(1, t / a) * np.exp(-t / r)

    def click():
        L = int(0.03 * SR)
        noise = rng.standard_normal(L)
        noise = np.convolve(noise, np.ones(6) / 6, mode="same")
        return noise * env(L, 0.0008, 0.008)

    def tone(freqs, dur, r=0.25, a=0.005):
        L = int(dur * SR)
        t = np.arange(L) / SR
        s = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
        return s * env(L, a, r)

    for ev in ep.sfx:
        kind = ev[0]
        if kind == "type":   # 자판 소리: 글자마다 한 번, 조금씩 불규칙하게
            _, at, dur, cps = ev
            k = 0.0
            while k < dur:
                put(click(), at + k, 0.10 * rng.uniform(0.6, 1.0))
                k += (1.0 / cps) * rng.uniform(1.4, 2.6)
        elif kind == "send":
            put(tone([880, 1320], 0.18, 0.06), ev[1], 0.05)
        elif kind == "ping":
            put(tone([1046.5], 0.5, 0.18), ev[1], 0.05)
            put(tone([1568], 0.5, 0.2), ev[1] + 0.09, 0.04)
        elif kind == "stream":
            _, at, dur = ev
            k = 0.0
            while k < dur:
                put(click(), at + k, 0.035)
                k += 0.07
        elif kind == "tick":
            put(tone([660], 0.15, 0.05), ev[1], 0.04)
        elif kind == "err":
            put(tone([196, 207.6], 0.45, 0.16), ev[1], 0.09)
        elif kind == "beep":   # 액티브 부저 소리 흉내 (0.2초 간격 세 번, 귀가 아프지 않게 낮춤)
            for k in range(3):
                put(tone([2700], 0.2, 0.5, 0.004) * 0.6 + tone([1350], 0.2, 0.5) * 0.4, ev[1] + k * 0.4, 0.07)
        elif kind == "swell":
            L = int(1.2 * SR)
            t = np.arange(L) / SR
            s = (np.sin(2 * np.pi * 523.25 * t) + np.sin(2 * np.pi * 659.25 * t) + np.sin(2 * np.pi * 783.99 * t)) / 3
            put(s * np.sin(np.pi * t / 1.2) ** 2, ev[1], 0.035)

    # 배경음: 아주 작은 화음 패드 (Cmaj7 → Am7 → Fmaj7 → G6, 마디당 4초)
    t = np.arange(n) / SR
    chords = [[261.6, 329.6, 392.0, 493.9], [220.0, 261.6, 329.6, 392.0], [174.6, 220.0, 261.6, 329.6], [196.0, 246.9, 293.7, 329.6]]
    pad = np.zeros(n)
    bar = 4.0
    for ci in range(int(ep.t / bar) + 2):
        a, b = int(ci * bar * SR), int((ci + 1) * bar * SR + 0.8 * SR)
        a, b = max(0, a), min(n, b)
        if a >= n:
            break
        tt = t[a:b] - ci * bar
        e = np.minimum(1, tt / 1.2) * np.minimum(1, np.maximum(0, (bar + 0.8 - tt)) / 0.8)
        for f in chords[ci % 4]:
            pad[a:b] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt)) * e
    pad *= 0.0045
    fade = np.minimum(1, t / 2) * np.minimum(1, np.maximum(0, ep.t + 0.5 - t) / 2)
    mix = (sfx + pad) * fade
    peak = np.max(np.abs(mix)) or 1
    if peak > 0.89:
        mix *= 0.89 / peak
    st = np.stack([mix, mix], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


def srt_time(x: float) -> str:
    ms = int(round(x * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(ep: Ep, path: Path):
    rows = []
    for i, c in enumerate(ep.captions, 1):
        rows.append(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text'].replace('`', '')}\n")
    path.write_text("\n".join(rows), encoding="utf-8")


# ── 작업 폴더 준비 ────────────────────────────────────────────────────────
def prepare_work(ep: Ep, work: Path):
    work.mkdir(parents=True, exist_ok=True)
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)
    pre = REPO / "frontend/node_modules/pretendard/dist/public/static"
    for w in ["Regular", "SemiBold", "Bold", "ExtraBold"]:
        shutil.copy(pre / f"Pretendard-{w}.otf", fonts / f"Pretendard-{w}.otf")
    d2 = Path(os.environ.get("D2CODING_DIR", "")) if os.environ.get("D2CODING_DIR") else None
    if not d2 or not (d2 / "d2coding.ttf").exists():
        raise SystemExit("D2CODING_DIR 에 d2coding 패키지의 src 폴더를 알려 주세요 (npm i d2coding)")
    shutil.copy(d2 / "d2coding.ttf", fonts / "D2Coding.ttf")
    shutil.copy(d2 / "d2coding-bold.ttf", fonts / "D2Coding-Bold.ttf")
    shutil.copy(HERE / "player.html", work / "player.html")
    shutil.copy(HERE / "diagrams.js", work / "diagrams.js")
    link = work / "screens"
    if not link.exists():
        link.symlink_to(CAPT / "screens")
    (work / "timeline.js").write_text("window.TL = " + json.dumps(ep.timeline(), ensure_ascii=False) + ";", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep", choices=["pi", "web"])
    ap.add_argument("--check", nargs="*", type=float, help="이 시각들의 화면만 PNG 로 저장")
    ap.add_argument("--plan", action="store_true", help="시각표만 출력")
    a = ap.parse_args()

    import episodes
    ep = episodes.build(a.ep, Ep)
    work = OUT / f"work-{a.ep}"
    prepare_work(ep, work)
    print(f"[{a.ep}] 길이 {ep.t / 60:.1f}분, 장면 {len(ep.scenes)}개, 자막 {len(ep.captions)}개")
    if a.plan:
        for s in ep.scenes:
            print(f"  {s['start']:7.1f}  {s['type']:8s} ch{s['chapter']}  {s['end'] - s['start']:5.1f}s")
        return
    node = ["node", str(HERE / "render_frames.mjs"), str(work)]
    if a.check is not None:
        subprocess.run(node + ["--check", *map(str, a.check)], check=True)
        return

    OUT.mkdir(exist_ok=True)
    name = {"pi": "1-라즈베리파이편", "web": "2-백엔드-프론트엔드편"}[a.ep]
    silent = work / "video.mp4"
    subprocess.run(node + ["--fps", str(FPS), "--out", str(silent), "--duration", str(ep.t)], check=True)
    wav = work / "audio.wav"
    synth_audio(ep, wav)
    final = OUT / f"{name}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        # 효과음만 있는 소리라 약 -23 LUFS 로 올리고, 부저·오류음이 튀지 않게 -3 dBFS 로 막는다
        "-af", "volume=17dB,alimiter=limit=0.7079:level=0", "-c:a", "aac", "-b:a", "96k",
        "-shortest", "-movflags", "+faststart", str(final)], check=True)
    write_srt(ep, OUT / f"{name}.srt")
    print(f"[{a.ep}] → {final}")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
