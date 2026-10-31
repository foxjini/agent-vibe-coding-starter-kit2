"""
voiceover.py — 실습 영상에 한국어 해설 음성을 입힌다 (학교 PC에서 실행).

영상에는 자막만 있고 소리 해설은 없습니다. 이 스크립트는 같은 이름의 .srt 자막 대본을
Microsoft Edge 음성(edge-tts, 인터넷 필요)으로 읽어, 자막이 뜨는 시각에 맞춰 영상에 섞습니다.

준비 (한 번):
    pip install edge-tts
    ffmpeg 설치 (명령 프롬프트에서 ffmpeg -version 이 나와야 합니다)

사용:
    python voiceover.py 영상/1-라즈베리파이편.mp4
    python voiceover.py 영상/2-백엔드-프론트엔드편.mp4 --voice ko-KR-InJoonNeural
    → 영상/1-라즈베리파이편-해설.mp4 가 생깁니다.

    --voice    ko-KR-SunHiNeural(기본, 여성) / ko-KR-InJoonNeural(남성)
    --dry-run  음성 대신 짧은 신호음으로 시각만 맞춰 본다 (인터넷 없이 시험)

직접 녹음하고 싶다면 .srt 를 대본으로 읽으며 녹음해 영상 편집기에서 붙여도 됩니다.
"""

import argparse
import asyncio
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_srt(path: Path):
    cues = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            continue
        g = list(map(int, m.groups()))
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        cues.append({"start": start, "end": end, "text": " ".join(lines[2:]).strip()})
    return cues


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


async def tts(text: str, voice: str, rate: str, out: Path):
    import edge_tts  # pip install edge-tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def make_clip(cue, slot: float, voice: str, out: Path, dry: bool) -> float:
    if dry:
        # 글자 수만큼의 길이를 가진 작은 신호음 (실제 음성과 비슷한 길이)
        d = min(slot, 0.11 * len(cue["text"].replace(" ", "")) + 0.4)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={d:.2f}", "-af", "volume=0.3", str(out)], check=True)
        return d
    rate = 0
    for _ in range(3):
        asyncio.run(tts(cue["text"], voice, f"{rate:+d}%", out))
        d = duration(out)
        if d <= slot * 0.98 or rate >= 60:
            return d
        # 자막이 떠 있는 동안 다 읽도록 빠르게 읽힌다 (최대 +60%)
        rate = min(60, rate + math.ceil((d / slot - 1) * 100) + 5)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--srt")
    ap.add_argument("--voice", default="ko-KR-SunHiNeural")
    ap.add_argument("--duck", type=float, default=0.35, help="해설이 나오는 동안 원래 소리 크기 (0~1)")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg 가 없습니다. 먼저 설치해 주세요.")
    video = Path(a.video)
    srt = Path(a.srt) if a.srt else video.with_suffix(".srt")
    out = Path(a.out) if a.out else video.with_name(video.stem + "-해설.mp4")
    cues = parse_srt(srt)
    if not cues:
        sys.exit(f"{srt} 에서 자막을 읽지 못했습니다.")
    print(f"자막 {len(cues)}개를 읽습니다 ({'신호음 시험' if a.dry_run else a.voice})")

    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, c in enumerate(cues):
            nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + 1.0
            slot = max(1.0, nxt - c["start"] - 0.15)
            p = Path(tmp) / f"{i:03d}.{'wav' if a.dry_run else 'mp3'}"
            d = make_clip(c, slot, a.voice, p, a.dry_run)
            if d > slot + 0.3:
                print(f"  ⚠️ {i + 1}번 자막이 다음 자막과 {d - slot:.1f}초 겹칩니다: {c['text'][:30]}…")
            clips.append((c["start"], p))
            print(f"  {i + 1}/{len(cues)}", end="\r")
        print()

        # 해설 음성을 자막 시각에 놓고, 원래 소리(효과음·배경음)는 낮춰서 섞는다
        args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
        for _, p in clips:
            args += ["-i", str(p)]
        parts = [f"[0:a]volume={a.duck}[bg]"]
        for k, (at, _) in enumerate(clips, start=1):
            ms = int(at * 1000)
            parts.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
        mix_in = "[bg]" + "".join(f"[v{k}]" for k in range(1, len(clips) + 1))
        parts.append(f"{mix_in}amix=inputs={len(clips) + 1}:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5[a]")
        script = Path(tmp) / "filter.txt"
        script.write_text(";\n".join(parts), encoding="utf-8")
        args += ["-filter_complex_script", str(script), "-map", "0:v", "-map", "[a]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        subprocess.run(args, check=True)
    print(f"완성: {out}")


if __name__ == "__main__":
    main()
