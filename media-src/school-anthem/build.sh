#!/bin/sh
# 교가 노래방 영상 만들기 — 준비물을 확인하고 build.py 를 돌린다 (README.md 참고)
set -e
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || { echo "ffmpeg 가 없습니다."; exit 1; }
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " ass " || { echo "ffmpeg 에 libass(자막)가 없습니다."; exit 1; }
python3 -c "import numpy, PIL, tinysoundfont" 2>/dev/null || {
  echo "파이썬 패키지가 없습니다: pip install numpy Pillow mido && pip install --no-deps tinysoundfont"; exit 1; }
[ -f "${SOUNDFONT:-/home/user/mrbumpy409/generaluser-gs/GeneralUser-GS.sf2}" ] || {
  echo "사운드폰트가 없습니다. README.md 의 준비 단계대로 받고 SOUNDFONT 를 지정하세요."; exit 1; }
[ -d ../../frontend/node_modules/pretendard ] || { echo "글꼴이 없습니다: (cd ../../frontend && npm ci)"; exit 1; }

python3 score.py
python3 build.py "$@"
