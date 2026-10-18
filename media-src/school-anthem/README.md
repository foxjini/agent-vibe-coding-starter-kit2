# 교가 노래방 영상 만들기 (`media-src/school-anthem`)

축제 **교가 부르기 대회**용 노래방 영상입니다. 학교 교가 악보를 채보한 데이터(`score.py`)
하나로 반주 음원·가사 자막·1080p 영상을 모두 만듭니다. 음 하나를 고쳐도 `build.py`를 다시
돌리면 영상까지 그대로 따라 바뀝니다.

| 파일 | 하는 일 |
|------|---------|
| `score.py` | **채보 원본** — 멜로디·가사 음절·박마다 화음 (24마디). 고칠 곳은 여기뿐 |
| `build.py` | 편곡 → 음원 녹음 → 잔향·마스터링 → 가사 타이밍 → 자막 → 배경 영상 → mp4/webm |
| `build.sh` | 준비물 확인 후 `build.py` 실행 |
| `out/` | 중간 산출물과 **검수용 파일** (커밋하지 않음) |

만들어지는 것

| 파일 | 내용 |
|------|------|
| `frontend/public/media/karaoke/school-anthem.mp4` | 1080p30 H.264 + AAC 256k, 가사 자막이 들어간 노래방 영상 (약 1분 29초) |
| `frontend/public/media/karaoke/school-anthem.webm` | 같은 영상 VP9·Opus — H.264를 못 트는 리눅스·라즈베리파이 Chromium용 |
| `frontend/public/media/karaoke/school-anthem.vtt` | 줄 단위 가사 + 음절 시각 (앱 자막 트랙) |
| `frontend/data/schoolAnthem.generated.ts` | 곡 길이·구간 안내 — 앱이 읽는다 (직접 고치지 말 것) |

## 구성

- **전주 4마디** (마지막 단 "백만년 무궁토록…" 선율, 트럼펫) → **본곡 24마디** → **후주 2마디** (팀파니 롤 + 종지)
- F장조 4/4, ♩=84 (`build.py`의 `BPM`)
- 악기: 현악, 첼로, 피아노, 콘트라베이스, 호른(4단·6단·전주·후주), 팀파니·심벌, 마지막 단 트럼펫
- **가이드 멜로디**: 클라리넷, 반주보다 약 9 dB 작게 — 처음 부르는 학생도 따라올 수 있을 만큼만
- 단마다 셈여림 (`score.py`의 `DYNAMICS`), 콘서트홀 잔향, −14 LUFS · 최대 −1.5 dBFS
- 영상: 타이틀(교가 · 학교명 · 작사), 첫 소절 전 ●●●● 카운트, 두 줄 교대 가사(부를 때 금색으로 채워짐),
  서해 물결 배경, 하단 진행 막대, 끝 화면 "수고하셨습니다"

## 준비 (처음 한 번)

```bash
pip install numpy Pillow mido
pip install --no-deps tinysoundfont        # pyaudio 를 빼고 설치 (렌더링에는 필요 없다)
git clone --depth 1 https://github.com/mrbumpy409/GeneralUser-GS ~/generaluser-gs
export SOUNDFONT=~/generaluser-gs/GeneralUser-GS.sf2
(cd ../../frontend && npm ci)              # 자막 글꼴 Pretendard
```

ffmpeg 는 libass(자막)·libx264·libvpx-vp9·libopus 가 들어 있어야 합니다 (`ffmpeg -filters | grep ass`).

## 만들기

```bash
./build.sh               # 전부 (약 2분)
./build.sh --review      # 검수용 파일만 (몇 초)
./build.sh --audio       # 음원·자막까지만
```

## 검수 — 반드시 사람이 귀로 확인

채보는 해상도가 낮은 악보 이미지를 **사람이 보고 옮긴 것**입니다. 교가를 아는 선생님·학생이 확인해 주세요.

1. `out/review_score.png` — 마디별 음 이름·가사·화음 대조표. 원본 악보와 한 마디씩 비교
2. `out/review_melody.wav` — 멜로디만 피아노로. 교가를 아는 사람이 들으면 틀린 음이 바로 들린다
3. `out/anthem_mix.wav` — 완성 반주

특히 확인할 곳

- 3단 가사 **"참운의 뜻을 모아"** — 악보에 "참 - 운"으로 적혀 있어 그대로 옮겼습니다. 실제 가사가 다르면 `score.py`의 `LINES`와 `MELODY` 가사를 함께 고칩니다
- 11마디 "운"(F4로 읽음), 21마디 "년"(C5로 읽음) — 악보 이미지에서 가장 흐릿했던 음
- 화음(코드)은 4부 합창의 소프라노·알토·베이스를 보고 정했습니다. 원곡 반주 화성과 다를 수 있습니다

틀린 곳은 `score.py`에서 고치고 `python3 score.py`(마디·가사 수 자동 확인) → `./build.sh` 를 다시 돌립니다.

## 권리

- 교가 가사·선율: 학교 저작물 (작사 이인수). 작곡자 표기가 악보에 없어 영상에 넣지 않았습니다 — 확인되면 `build.py`의 타이틀에 추가하세요
- 반주·영상: 학교(학생)가 직접 제작 — `LICENSE-LEDGER.md` 기록, 라이선스 표기 `self-produced`
- 악기 음색: GeneralUser GS 사운드폰트 (상업 음악 제작까지 허용하는 무료 라이선스)
- 글꼴: Pretendard (SIL Open Font License)
