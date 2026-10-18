"""
교가 노래방 영상 만들기 — score.py 한 파일에서 반주·자막·영상까지

    python3 build.py              # 전부 (약 3~5분)
    python3 build.py --audio      # 반주와 검수용 음원만
    python3 build.py --review     # 검수용 (멜로디 피아노 + 악보 대조표 PNG)만

필요한 것 (README.md 참고)
  - ffmpeg (libass 포함), Python 패키지: numpy Pillow mido tinysoundfont
  - 사운드폰트: GeneralUser GS (무료, 상업 음악 제작까지 허용)
      환경변수 SOUNDFONT 로 경로를 지정한다
  - 글꼴: Pretendard (frontend/node_modules/pretendard, OFL)

만드는 것
  frontend/public/media/karaoke/school-anthem.mp4   1080p30 · AAC 256k · 자막 포함
  frontend/public/media/karaoke/school-anthem.webm  같은 영상 (VP9·Opus — H.264 를 못 트는 브라우저용)
  frontend/public/media/karaoke/school-anthem.vtt   앱에서 쓰는 줄 단위 자막
  frontend/data/schoolAnthem.generated.ts           곡 길이·구간 안내(guideCues)
  out/                                              중간 산출물 (커밋하지 않는다)
"""

import argparse
import itertools
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import score as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "out"
MEDIA_DIR = ROOT / "frontend" / "public" / "media" / "karaoke"
GENERATED_TS = ROOT / "frontend" / "data" / "schoolAnthem.generated.ts"
FONT_DIR = ROOT / "frontend" / "node_modules" / "pretendard" / "dist" / "public" / "static"
SOUNDFONT = Path(os.getenv("SOUNDFONT", "/home/user/mrbumpy409/generaluser-gs/GeneralUser-GS.sf2"))

SR = 48000
FPS = 30
W, H = 1920, 1080

# ── 시간 ──────────────────────────────────────────────────────────────
BPM = 84                       # 교가 행진 빠르기. 바꾸면 자막·영상이 함께 따라간다
BEAT = 60.0 / BPM
BAR = 4 * BEAT
PRE = 0.6                      # 맨 앞 여백 (첫 소리가 잘리지 않게)
INTRO_BARS = 4                 # 전주: 마지막 단(21~24마디) 선율
OUTRO_BARS = 2
TAIL = 3.0                     # 마지막 화음의 울림


def bar_start(global_bar: float) -> float:
    return PRE + global_bar * BAR


SONG0 = INTRO_BARS             # 본곡 1마디의 전체 마디 번호
TOTAL_BARS = INTRO_BARS + 24 + OUTRO_BARS
DURATION = bar_start(TOTAL_BARS) + TAIL


# ── 편곡 재료: 전체 마디 목록 (전주 + 본곡 + 후주) ─────────────────────
def arrangement_bars():
    """[(마디 종류, 멜로디 or None, 화음, 셈여림)] 30마디"""
    bars = []
    for i in range(20, 24):                          # 전주 = 마지막 단
        chords = S.CHORDS[i]
        if i == 23:
            chords = [(0, "F", "F"), (3, "C7", "C")]  # 본곡으로 이어지게
        bars.append(("intro", S.MELODY[i], chords, 0.72))
    for i in range(24):
        bars.append(("song", S.MELODY[i], S.CHORDS[i], S.DYNAMICS[i // 4]))
    bars.append(("outro", None, [(0, "Bb", "Bb"), (2, "C7", "C")], 0.85))
    bars.append(("outro", None, [(0, "F", "F")], 0.95))
    return bars


def chord_segments(bars):
    """[(시작초, 끝초, 코드, 베이스, 셈여림, 마디종류, 전체마디번호)]"""
    segs = []
    for gi, (kind, _, chords, dyn) in enumerate(bars):
        for j, (b, ch, bass) in enumerate(chords):
            nb = chords[j + 1][0] if j + 1 < len(chords) else 4
            segs.append([bar_start(gi) + b * BEAT, bar_start(gi) + nb * BEAT, ch, bass, dyn, kind, gi, b])
    # 마지막 화음은 울림 끝까지
    segs[-1][1] = DURATION - 0.8
    return segs


def voicing(pcs, lo, hi, n, prev, span=16, gap=2):
    """코드 구성음으로 n성 화음을 고른다. 앞 화음에서 가장 적게 움직이는 자리를 고른다."""
    # 3화음을 4성으로 쓸 때는 근음 → 5음 → 3음 순서로 겹쳐 본다 (음역에 따라 근음을 못 겹칠 수 있다)
    tries = [list(pcs)] if len(pcs) >= n else [list(pcs) + [pcs[i]] for i in (0, 2, 1)]
    for p in tries:
        for sp, gp in ((span, gap), (24, 1)):
            best = _voicing(p, lo, hi, n, prev, sp, gp)
            if best:
                return best
    raise ValueError(f"화음을 쌓을 수 없다: {pcs} {lo}-{hi} {n}성")


def _voicing(pcs, lo, hi, n, prev, span, gap):
    pcs = list(pcs)
    while len(pcs) < n:
        pcs.append(pcs[0])           # 근음을 겹친다
    pcs = pcs[:n]
    options = [[k for k in range(lo, hi + 1) if k % 12 == pc] for pc in pcs]
    best, best_cost = None, 1e9
    for combo in itertools.product(*options):
        notes = sorted(combo)
        if len(set(notes)) < n or notes[-1] - notes[0] > span:
            continue
        if any(b - a < gap for a, b in zip(notes, notes[1:])):
            continue
        center = sum(notes) / n
        cost = abs(center - (lo + hi) / 2) * 0.35
        if prev:
            cost += sum(abs(a - b) for a, b in zip(notes, prev))
        if cost < best_cost:
            best, best_cost = notes, cost
    return best


def vel(dyn, base=46, span=62, accent=0):
    return int(max(18, min(124, base + dyn * span + accent)))


def build_events():
    """악기별 음표 [(시작초, 길이초, 건반, 세기)]"""
    bars = arrangement_bars()
    segs = chord_segments(bars)
    ev = {k: [] for k in ("guide", "lead", "strings", "cello", "horns", "piano", "bass", "timpani", "perc")}

    # 멜로디 — 가이드(클라리넷)는 본곡 내내, 전주는 트럼펫·호른이 노래한다
    for gi, (kind, melody, _, dyn) in enumerate(bars):
        if not melody:
            continue
        t = bar_start(gi)
        for pitch, beats, _syl in melody:
            dur = beats * BEAT
            if pitch is not None:
                if kind == "song":
                    ev["guide"].append((t, dur * 0.93, pitch, vel(dyn, 52, 50)))
                    if gi >= SONG0 + 20:             # 마지막 단은 트럼펫이 살짝 받쳐 준다
                        ev["lead"].append((t, dur * 0.9, pitch, vel(dyn, 30, 40)))
                else:
                    ev["lead"].append((t, dur * 0.92, pitch, vel(dyn, 48, 50)))
            t += dur

    prev_str = prev_hrn = prev_pno = None
    for (t0, t1, ch, bass, dyn, kind, gi, b) in segs:
        pcs = S.CHORD_TONES[ch]
        song_bar = gi - SONG0
        unison = kind == "song" and 16 <= song_bar <= 17 and b < 2    # "비바람 몰아쳐도"는 가볍게

        # 현악 패드 (공통음은 이어 붙인다)
        v = voicing(pcs, 53, 72, 4, prev_str)
        ev["strings"].append((t0, t1 - t0 + 0.05, v, vel(dyn, 34, 48) - (12 if unison else 0)))
        prev_str = v
        # 첼로 — 베이스 한 옥타브 위에서 길게
        bk = 36 + (S.NOTE_PC[bass] - 36) % 12
        ev["cello"].append((t0, t1 - t0 + 0.03, [bk + 12 if bk < 41 else bk], vel(dyn, 32, 40)))

        # 호른 — 전주·4단·6단·후주에서 화성을 두껍게
        if kind in ("intro", "outro") or (kind == "song" and (12 <= song_bar <= 15 or song_bar >= 20)):
            hv = voicing(pcs[:3], 53, 67, 3, prev_hrn)
            ev["horns"].append((t0, t1 - t0, hv, vel(dyn, 36, 46)))
            prev_hrn = hv

        # 피아노 — 박마다 화음, 1·3박에 왼손 베이스
        pv = voicing(pcs, 57, 72, 3, prev_pno)
        prev_pno = pv
        beat_t = t0
        while beat_t < t1 - 1e-6:
            pos = round((beat_t - bar_start(gi)) / BEAT, 3)
            strong = abs(pos - round(pos)) < 1e-3 and int(round(pos)) % 2 == 0
            nxt = min(t1, beat_t + BEAT)
            if kind == "outro" and gi == TOTAL_BARS - 1:
                ev["piano"].append((beat_t, t1 - beat_t, pv + [pv[0] + 12], vel(dyn, 40, 40)))
                ev["piano"].append((beat_t, t1 - beat_t, [bk, bk - 12], vel(dyn, 40, 40)))
                break
            ev["piano"].append((beat_t, (nxt - beat_t) * 0.85, pv, vel(dyn, 30 if not strong else 38, 40) - (10 if unison else 0)))
            if strong or abs(beat_t - t0) < 1e-6:
                ev["piano"].append((beat_t, min(2 * BEAT, t1 - beat_t) * 0.95, [bk, bk - 12 if bk - 12 >= 28 else bk + 12], vel(dyn, 36, 40)))
            beat_t = nxt

        # 콘트라베이스 — 2박마다 다시 긋는다
        beat_t = t0
        while beat_t < t1 - 1e-6:
            nxt = min(t1, beat_t + 2 * BEAT)
            ev["bass"].append((beat_t, (nxt - beat_t) * 0.96, [bk], vel(dyn, 44, 44)))
            beat_t = nxt

    # 팀파니·심벌 — 단이 바뀌는 곳과 절정에만
    F2, C3 = 41, 48
    hits = [(0, F2, .8), (SONG0, F2, .7), (SONG0 + 4, F2, .6), (SONG0 + 8, C3, .55),
            (SONG0 + 12, F2, .8), (SONG0 + 16, C3, .6), (SONG0 + 20, F2, .95), (SONG0 + 21, F2, .9),
            (SONG0 + 23, F2, .9)]
    for gb, key, d in hits:
        ev["timpani"].append((bar_start(gb), BEAT * 1.5, [key], vel(d, 50, 60)))
    # 후주: 팀파니 롤 (16분음표 크레셴도) → 마지막 일격
    roll_start = bar_start(TOTAL_BARS - 2) + 2 * BEAT
    n = int((bar_start(TOTAL_BARS - 1) - roll_start) / (BEAT / 4))
    for k in range(n):
        ev["timpani"].append((roll_start + k * BEAT / 4, BEAT / 4, [C3], 40 + int(60 * k / n)))
    ev["timpani"].append((bar_start(TOTAL_BARS - 1), BEAT * 3, [F2], 120))
    for gb, d in [(SONG0 + 12, .7), (SONG0 + 20, .9), (TOTAL_BARS - 1, 1.0)]:
        ev["perc"].append((bar_start(gb), BEAT * 4, [57 if gb != TOTAL_BARS - 1 else 49], vel(d, 50, 60)))
    return ev


# 악기: (뱅크, 프리셋, 드럼?, 음량dB, 좌우(-1~1), 리버브 보내기)
INSTRUMENTS = {
    "strings": (0, 49, False, -1.0, 0.0, 0.55),
    "cello":   (0, 48, False, -6.0, -0.35, 0.45),
    "horns":   (0, 60, False, -4.0, 0.35, 0.55),
    "piano":   (0, 0, False, -2.0, -0.15, 0.35),
    "bass":    (0, 43, False, -2.0, 0.1, 0.25),
    "lead":    (0, 56, False, -4.5, -0.1, 0.5),
    "timpani": (0, 47, False, -3.0, 0.0, 0.5),
    "perc":    (128, 48, True, -9.0, 0.2, 0.6),
    "guide":   (0, 71, False, 0.0, 0.0, 0.35),
}


def render_stem(name, notes):
    import tinysoundfont

    bank, preset, drums, *_ = INSTRUMENTS[name]
    synth = tinysoundfont.Synth(samplerate=SR)
    sfid = synth.sfload(str(SOUNDFONT))
    synth.program_select(0, sfid, bank, preset, is_drums=drums)
    events = []
    for (t, dur, keys, v) in notes:
        keys = keys if isinstance(keys, list) else [keys]
        for k in keys:
            events.append((t, 1, k, v))
            events.append((t + dur, 0, k, 0))
    events.sort(key=lambda e: (e[0], e[1]))      # 같은 시각이면 끄기를 먼저
    total = int(DURATION * SR)
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    for (t, on, k, v) in events:
        target = min(total, int(t * SR))
        if target > pos:
            buf = np.frombuffer(synth.generate(target - pos), dtype=np.float32).reshape(-1, 2)
            out[pos:target] = buf
            pos = target
        if on:
            synth.noteon(0, k, v)
        else:
            synth.noteoff(0, k)
    if pos < total:
        out[pos:] = np.frombuffer(synth.generate(total - pos), dtype=np.float32).reshape(-1, 2)
    return out


def hall_ir(seconds=2.4, rt60=2.1):
    """간단한 콘서트홀 잔향 (지수 감쇠 잡음 + 초기 반사). 좌우를 다르게 만들어 넓게 들린다."""
    rng = np.random.default_rng(7)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    env = np.exp(-6.91 * t / rt60)
    ir = rng.standard_normal((n, 2)) * env[:, None]
    # 높은 소리는 더 빨리 줄어든다 — 이동평균으로 부드럽게
    k = 6
    ir = np.stack([np.convolve(ir[:, c], np.ones(k) / k, mode="same") for c in range(2)], axis=1)
    pre = int(0.018 * SR)
    ir = np.concatenate([np.zeros((pre, 2)), ir])
    for d, g in [(0.011, 0.5), (0.019, 0.38), (0.027, 0.3), (0.041, 0.22)]:
        i = int(d * SR)
        ir[i, 0] += g
        ir[i + 37, 1] += g
    return (ir / np.sqrt((ir ** 2).sum(axis=0))).astype(np.float32)


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.zeros((n, 2), dtype=np.float32)
    for c in range(2):
        X = np.fft.rfft(x[:, c], nfft)
        Hf = np.fft.rfft(ir[:, c], nfft)
        y[:, c] = np.fft.irfft(X * Hf, nfft)[:n]
    return y[: len(x)]


def db(x):
    return 10 ** (x / 20)


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-12)


def write_wav(path, x):
    import wave

    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def build_audio():
    print("▶ 반주 편곡·녹음 (사운드폰트)")
    ev = build_events()
    stems = {}
    for name in INSTRUMENTS:
        stems[name] = render_stem(name, ev[name])
        print(f"   {name:8s} {len(ev[name]):4d}개 음표")

    accomp = [k for k in INSTRUMENTS if k != "guide"]
    dry = np.zeros_like(stems["strings"])
    send = np.zeros_like(dry)
    for name in accomp:
        _, _, _, gdb, pan, rev = INSTRUMENTS[name]
        a = (pan + 1) * math.pi / 4
        g = np.array([math.cos(a), math.sin(a)], dtype=np.float32) * math.sqrt(2) * db(gdb)
        s = stems[name] * g
        dry += s
        send += s * rev
    # 가이드 멜로디: 반주보다 확실히 작게 (따라 부를 수 있을 만큼만)
    target = rms(dry) * db(-9.0)
    guide = stems["guide"] * (target / rms(stems["guide"]))
    send += guide * INSTRUMENTS["guide"][5]
    dry += guide

    print("▶ 잔향(홀) 입히기")
    wet = convolve(send, hall_ir())
    mix = (dry + wet * 0.42) * dynamics_envelope()[:, None]
    mix /= np.abs(mix).max() * 1.12
    raw = OUT / "anthem_raw.wav"
    write_wav(raw, mix)

    print("▶ 마스터링 (−14 LUFS, 셈여림은 살린다)")
    # 정규화기(loudnorm)를 그대로 쓰면 셈여림이 납작해진다. 음량을 재서 그만큼만
    # 올리고, 넘치는 순간만 리미터가 잡게 한다.
    chain = ("highpass=f=32,equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1:g=1.5,"
             "acompressor=threshold=-16dB:ratio=1.6:attack=30:release=350")
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(raw), "-af", chain + ",ebur128",
                           "-f", "null", "-"], capture_output=True, text=True).stderr
    integrated = float(meas[meas.rindex("I:"):].split()[1])
    gain = -14.0 - integrated
    master = OUT / "anthem_mix.wav"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-af",
                    f"{chain},volume={gain:.2f}dB,alimiter=limit=0.84:attack=3:release=60:level=false,"
                    f"afade=t=out:st={DURATION - 1.3:.2f}:d=1.2",
                    "-ar", str(SR), str(master)], check=True)
    return master


def dynamics_envelope():
    """단마다의 셈여림을 반주 전체 음량에 입힌다 (1단 mf … 6단 ff, 후주는 더 크게)"""
    bars = arrangement_bars()
    pts_t, pts_g = [0.0], [None]
    for gi, (_, _, _, dyn) in enumerate(bars):
        g = 10 ** ((dyn - 0.75) * 16 / 20)
        pts_t += [bar_start(gi), bar_start(gi) + BEAT]   # 한 박에 걸쳐 바뀐다
        pts_g += [None, g]
    pts_g[0] = pts_g[2]
    for i, g in enumerate(pts_g):
        if g is None:
            pts_g[i] = pts_g[i - 1]
    t = np.arange(int(DURATION * SR)) / SR
    return np.interp(t, pts_t, pts_g).astype(np.float32)


# ── 검수용 ────────────────────────────────────────────────────────────
def build_review():
    """멜로디만 피아노로 + 악보 대조표 PNG — 원본 악보와 비교해 채보를 확인한다."""
    import tinysoundfont  # noqa: F401
    notes = []
    for i, bar in enumerate(S.MELODY):
        t = bar_start(SONG0 + i)
        for pitch, beats, _ in bar:
            if pitch is not None:
                notes.append((t, beats * BEAT * 0.95, [pitch], 92))
            t += beats * BEAT
    saved = INSTRUMENTS["guide"]
    INSTRUMENTS["guide"] = (0, 0, False, 0, 0, 0)
    x = render_stem("guide", notes)
    INSTRUMENTS["guide"] = saved
    write_wav(OUT / "review_melody.wav", x / (np.abs(x).max() * 1.1))
    review_png()
    print("▶ 검수용: out/review_melody.wav, out/review_score.png")


def review_png():
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(FONT_DIR / "Pretendard-SemiBold.otf"), 22)
    small = ImageFont.truetype(str(FONT_DIR / "Pretendard-Regular.otf"), 16)
    names = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}
    rowh, lo, hi, bw = 230, 58, 76, 420
    img = Image.new("RGB", (60 + 4 * bw, 6 * rowh + 20), "white")
    d = ImageDraw.Draw(img)
    for r in range(6):
        y0 = 10 + r * rowh
        for p in range(lo, hi + 1):
            y = y0 + 150 - (p - lo) * 7
            if p % 12 in (0, 5):
                d.line([(60, y), (60 + 4 * bw, y)], fill=(225, 225, 235))
                d.text((8, y - 9), names[p % 12] + str(p // 12 - 1), font=small, fill=(120, 120, 140))
        for c in range(4):
            i = r * 4 + c
            x0 = 60 + c * bw
            d.line([(x0, y0), (x0, y0 + 200)], fill=(80, 80, 80), width=2)
            d.text((x0 + 4, y0), f"{i + 1}", font=small, fill=(150, 0, 0))
            chords = " ".join(ch for _, ch, _ in S.CHORDS[i])
            d.text((x0 + 4, y0 + 182), chords, font=small, fill=(0, 90, 160))
            pos = 0.0
            for pitch, beats, syl in S.MELODY[i]:
                x = x0 + 8 + pos / 4 * (bw - 16)
                xe = x0 + 8 + (pos + beats) / 4 * (bw - 16)
                if pitch is not None:
                    y = y0 + 150 - (pitch - lo) * 7
                    d.rectangle([x, y - 5, xe - 3, y + 5], fill=(30, 60, 120))
                    d.text((x, y - 32), names[pitch % 12], font=small, fill=(30, 60, 120))
                    d.text((x, y0 + 158), syl, font=font, fill=(0, 0, 0))
                pos += beats
    img.save(OUT / "review_score.png")


# ── 가사 타이밍 ───────────────────────────────────────────────────────
def syllable_timing():
    """[(줄번호, 화면글자, 시작초, 끝초)] — '-' 는 앞 음절에 붙인다"""
    syls = []
    for i, bar in enumerate(S.MELODY):
        t = bar_start(SONG0 + i)
        for pitch, beats, syl in bar:
            dur = beats * BEAT
            if syl == "-":
                syls[-1][2] = t + dur
            elif syl:
                syls.append([syl, t, t + dur])
            t += dur
    out, k = [], 0
    for li, line in enumerate(S.LINES):
        for wi, word in enumerate(line.split()):
            for ci, ch in enumerate(word):
                s = syls[k]
                assert s[0] == ch, (s, ch)
                text = ch + (" " if ci == len(word) - 1 and wi < len(line.split()) - 1 else "")
                out.append({"line": li, "text": text, "start": round(s[1], 3), "end": round(s[2], 3)})
                k += 1
    return out


def display_rows(syls, max_syl=14):
    """화면 한 줄에 너무 많으면 띄어쓰기 자리에서 둘로 나눈다"""
    rows = []
    for li in range(len(S.LINES)):
        items = [s for s in syls if s["line"] == li]
        if len(items) <= max_syl:
            rows.append(items)
            continue
        cuts = [i + 1 for i, s in enumerate(items[:-1]) if s["text"].endswith(" ")]
        mid = min(cuts, key=lambda c: abs(c - len(items) / 2))
        rows.append(items[:mid])
        rows.append(items[mid:])
    return rows


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_subtitles(syls):
    rows = display_rows(syls)
    first = rows[0][0]["start"]
    shows = []
    for k, row in enumerate(rows):
        if k < 2:
            show = bar_start(SONG0 - 1)                       # 전주 마지막 마디부터
        else:
            show = max(row[0]["start"] - 5.0, rows[k - 2][-1]["end"] + 0.2)
        shows.append(show)
    hides = []
    for k, row in enumerate(rows):
        hide = row[-1]["end"] + 0.5
        if k + 2 < len(rows):
            hide = min(hide, shows[k + 2] - 0.05)
        if k >= len(rows) - 2:
            hide = max(hide, row[-1]["end"] + 1.2)
        hides.append(hide)

    gold, white, navy = "&H004AD2FF", "&H00FFFFFF", "&H00401A08"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Top,Pretendard ExtraBold,88,{gold},{white},{navy},&H96000000,0,0,0,0,100,100,2,0,1,6,3,1,170,170,250,1
Style: Bottom,Pretendard ExtraBold,88,{gold},{white},{navy},&H96000000,0,0,0,0,100,100,2,0,1,6,3,3,170,170,120,1
Style: Count,Pretendard ExtraBold,54,{gold},{gold},{navy},&H96000000,0,0,0,0,100,100,14,0,1,4,2,1,175,170,370,1
Style: Title,Pretendard ExtraBold,150,{white},{white},{navy},&H96000000,0,0,0,0,100,100,6,0,1,7,4,5,0,0,0,1
Style: Sub,Pretendard ExtraBold,62,{gold},{gold},{navy},&H96000000,0,0,0,0,100,100,2,0,1,5,3,5,0,0,0,1
Style: Small,Pretendard ExtraBold,40,{white},{white},{navy},&H96000000,0,0,0,0,100,100,1,0,1,3,2,5,0,0,0,1
Style: Header,Pretendard ExtraBold,36,&H00F0E6D8,&H00F0E6D8,{navy},&H96000000,0,0,0,0,100,100,1,0,1,3,1,7,70,70,50,1
Style: HeaderR,Pretendard ExtraBold,32,&H00C8B4A0,&H00C8B4A0,{navy},&H96000000,0,0,0,0,100,100,1,0,1,3,1,9,70,70,54,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    title_end = bar_start(SONG0 - 1) - 0.2
    lines.append(f"Dialogue: 1,{ass_time(0.4)},{ass_time(title_end)},Title,,0,0,0,,{{\\fad(700,600)\\pos(960,430)}}교  가")
    lines.append(f"Dialogue: 1,{ass_time(0.9)},{ass_time(title_end)},Sub,,0,0,0,,{{\\fad(700,600)\\pos(960,580)}}인천전자마이스터고등학교")
    lines.append(f"Dialogue: 1,{ass_time(1.4)},{ass_time(title_end)},Small,,0,0,0,,{{\\fad(700,600)\\pos(960,670)}}작사  {S.LYRICIST}   ·   {S.KEY_NAME} 4/4   ·   ♩ = {BPM}")
    lines.append(f"Dialogue: 0,{ass_time(title_end)},{ass_time(DURATION)},Header,,0,0,0,,{{\\fad(500,0)}}인천전자마이스터고등학교 교가")
    lines.append(f"Dialogue: 0,{ass_time(title_end)},{ass_time(DURATION)},HeaderR,,0,0,0,,{{\\fad(500,0)}}작사 {S.LYRICIST}")
    # 첫 소절 카운트 (●●●● 하나씩 꺼진다)
    c0 = first - 4 * BEAT
    for j in range(4):
        dots = "● " * (4 - j)
        lines.append(f"Dialogue: 2,{ass_time(c0 + j * BEAT)},{ass_time(c0 + (j + 1) * BEAT)},Count,,0,0,0,,{dots.strip()}")
    for k, row in enumerate(rows):
        style = "Top" if k % 2 == 0 else "Bottom"
        parts = [f"{{\\fad(250,200)\\k{int(round((row[0]['start'] - shows[k]) * 100))}}}"]
        for i, s in enumerate(row):
            dur = int(round((s["end"] - s["start"]) * 100))
            parts.append(f"{{\\kf{dur}}}{s['text']}")
            if i + 1 < len(row):
                gap = int(round((row[i + 1]["start"] - s["end"]) * 100))
                if gap > 0:
                    parts.append(f"{{\\k{gap}}}")
        lines.append(f"Dialogue: 3,{ass_time(shows[k])},{ass_time(hides[k])},{style},,0,0,0,,{''.join(parts)}")
    end_t = syls[-1]["end"]
    lines.append(f"Dialogue: 1,{ass_time(end_t + 1.6)},{ass_time(DURATION)},Sub,,0,0,0,,{{\\fad(600,800)\\pos(960,470)}}수고하셨습니다!")
    lines.append(f"Dialogue: 1,{ass_time(end_t + 2.0)},{ass_time(DURATION)},Small,,0,0,0,,{{\\fad(600,800)\\pos(960,560)}}곧 점수가 나옵니다")
    ass = OUT / "school-anthem.ass"
    ass.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")

    # 앱용 WebVTT — 줄 단위 + 음절 시각 (<00:00:01.000> 형식, 노래방 표시에 쓸 수 있다)
    def vt(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"
    cues = ["WEBVTT", "", "NOTE 인천전자마이스터고등학교 교가 (작사 이인수) — media-src/school-anthem/build.py 가 만든다", ""]
    for k, row in enumerate(rows):
        body = row[0]["text"] + "".join(f"<{vt(s['start'])}>{s['text']}" for s in row[1:])
        cues += [f"{k + 1}", f"{vt(row[0]['start'] - 0.4)} --> {vt(row[-1]['end'] + 0.3)}", body.strip(), ""]
    (OUT / "school-anthem.vtt").write_text("\n".join(cues), encoding="utf-8")
    json.dump({"bpm": BPM, "duration": round(DURATION, 3), "songStart": round(first, 3),
               "rows": [[s for s in r] for r in rows]},
              open(OUT / "timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rows


# ── 배경 영상 ─────────────────────────────────────────────────────────
def frame_source():
    """1080p 배경: 남색→청록 그라데이션 + 서해 물결 3겹 + 떠오르는 빛 + 진행 막대"""
    from PIL import Image, ImageDraw, ImageFilter

    yy = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([10, 24, 52]), np.array([12, 78, 104])
    grad = (top * (1 - yy[..., None]) + bot * yy[..., None]).repeat(W, axis=1)
    # 가운데를 살짝 밝게 (비네트)
    xx = np.linspace(-1, 1, W)[None, :]
    vig = 1 - 0.28 * (xx ** 2 + (np.linspace(-1, 1, H)[:, None] * 0.8) ** 2)
    base = Image.fromarray(np.clip(grad * vig[..., None], 0, 255).astype(np.uint8))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.2, -H * 0.35, W * 0.8, H * 0.45], fill=(255, 210, 120, 38))
    base = Image.alpha_composite(base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(120)))

    rng = np.random.default_rng(3)
    parts = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.5, 4.5), rng.uniform(10, 34), rng.uniform(0, 6.28))
             for _ in range(70)]
    waves = [  # (기준 높이, 진폭, 파장, 속도, 색)
        (H * 0.80, 22, 610, 38, (40, 140, 190, 70)),
        (H * 0.85, 26, 830, -26, (30, 110, 170, 90)),
        (H * 0.90, 18, 470, 52, (20, 70, 130, 140)),
    ]
    n = int(math.ceil(DURATION * FPS))
    song_start, song_end = bar_start(SONG0), bar_start(SONG0 + 24)
    xs = np.arange(0, W + 41, 40)
    for f in range(n):
        t = f / FPS
        im = base.copy()
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for (px, py, r, sp, ph) in parts:
            y = (py - sp * t) % H
            x = px + 18 * math.sin(t * 0.6 + ph)
            a = int(60 + 50 * math.sin(t * 1.3 + ph))
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 230, 170, max(0, a)))
        for (yb, amp, wl, sp, col) in waves:
            ys = yb + amp * np.sin((xs + sp * t) / wl * 2 * math.pi) + amp * 0.4 * np.sin((xs - sp * 0.7 * t) / (wl * 0.53) * 2 * math.pi)
            pts = [(float(x), float(y)) for x, y in zip(xs, ys)] + [(W, H), (0, H)]
            d.polygon(pts, fill=col)
        # 진행 막대 (본곡 구간)
        prog = min(1, max(0, (t - song_start) / (song_end - song_start)))
        d.rectangle([0, H - 10, W, H], fill=(255, 255, 255, 40))
        d.rectangle([0, H - 10, int(W * prog), H], fill=(255, 210, 74, 230))
        im = Image.alpha_composite(im, ov)
        yield im.convert("RGB").tobytes()


def build_video(master):
    print("▶ 영상 만들기 (1080p30, 약 1~3분)")
    out = MEDIA_DIR / "school-anthem.mp4"
    ass = OUT / "school-anthem.ass"
    vf = f"ass={ass}:fontsdir={FONT_DIR}"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(master), "-vf", vf,
           "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-movflags", "+faststart", "-shortest", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k, fr in enumerate(frame_source()):
        p.stdin.write(fr)
        if k % 300 == 0:
            print(f"   {k / FPS:5.1f}s / {DURATION:.1f}s", flush=True)
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg 인코딩 실패")

    # 같은 영상을 WebM(VP9·Opus)으로도 만든다. 리눅스·라즈베리파이용 Chromium 처럼
    # H.264 를 못 트는 브라우저가 있어서, 앱은 mp4 를 못 틀면 이 파일을 튼다.
    print("▶ WebM 사본 만들기 (H.264 를 못 트는 브라우저용)")
    webm = MEDIA_DIR / "school-anthem.webm"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(out),
                    "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1", "-deadline", "good",
                    "-cpu-used", "4", "-c:a", "libopus", "-b:a", "192k", str(webm)], check=True)
    return out


def write_generated_ts(rows):
    first = rows[0][0]["start"]
    cues = [{"t": 0, "kind": "intro", "label": "🎵 전주 — 교가가 시작됩니다", "hint": "화면의 ●●●● 가 꺼지면 시작!"}]
    labels = ["1단 — 제물포", "2단 — 푸른 물결", "3단 — 슬기로운 배움", "4단 — 마음을 닦는 터전",
              "5단 — 비바람 몰아쳐도", "⭐ 6단 — 백만년 무궁토록"]
    kinds = ["verse", "verse", "pre", "chorus", "bridge", "high"]
    for i in range(6):
        t = bar_start(SONG0 + i * 4)
        cues.append({"t": round(t, 1), "kind": kinds[i], "label": labels[i],
                     "hint": "마지막 '만만세'는 힘차게!" if i == 5 else "가사를 또박또박"})
    cues.append({"t": round(bar_start(SONG0 + 24), 1), "kind": "outro", "label": "후주 — 수고했어요", "hint": "곧 점수가 나옵니다"})
    ts = f"""// 자동 생성 파일 — media-src/school-anthem/build.py 가 만든다. 직접 고치지 말 것.
import type {{ GuideCue }} from "@/data/karaokeSongs";

export const SCHOOL_ANTHEM_DURATION_SEC = {round(DURATION, 1)};
export const SCHOOL_ANTHEM_BPM = {BPM};
/** 첫 가사가 시작되는 시각(초) */
export const SCHOOL_ANTHEM_FIRST_LYRIC_SEC = {round(first, 2)};
export const SCHOOL_ANTHEM_CUES: GuideCue[] = {json.dumps(cues, ensure_ascii=False, indent=2)};
"""
    GENERATED_TS.write_text(ts, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", action="store_true", help="반주와 검수용 음원만")
    ap.add_argument("--review", action="store_true", help="검수용 파일만")
    args = ap.parse_args()
    S.check()
    OUT.mkdir(exist_ok=True)
    if not SOUNDFONT.exists():
        sys.exit(f"사운드폰트가 없습니다: {SOUNDFONT}  (README.md 의 준비 단계 참고)")
    build_review()
    if args.review:
        return
    master = build_audio()
    syls = syllable_timing()
    rows = build_subtitles(syls)
    write_generated_ts(rows)
    if args.audio:
        return
    out = build_video(master)
    import shutil
    shutil.copy(OUT / "school-anthem.vtt", MEDIA_DIR / "school-anthem.vtt")
    print(f"✅ {out.relative_to(ROOT)}  ({out.stat().st_size / 1e6:.1f} MB, {DURATION:.1f}초)")


if __name__ == "__main__":
    main()
