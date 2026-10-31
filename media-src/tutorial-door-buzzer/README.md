# 실습 영상 만들기 (`media-src/tutorial-door-buzzer`)

`docs/실습-문센서-부저/영상/`의 실습 영상 두 편을 만드는 소스입니다.
**영상 속 코드 변경, 터미널 출력, 관리자 화면은 모두 실제로 실행해 기록한 것**이고, 이 폴더의
렌더러는 그 기록을 IDE 모양의 화면에 다시 그려 줄 뿐입니다. 출력을 손으로 지어내지 않습니다.

| 파일 | 하는 일 |
|------|---------|
| `cap.py` | 명령을 실행하고 출력 줄마다 시각을 붙여 `captured/<id>.json`에 저장 · `git diff` 저장 |
| `screen_rec.mjs` | 관리자 화면(`/admin`)을 Playwright로 열어 프레임마다 저장 (`captured/screens/`) |
| `episodes.py` | **장면 대본** — 자막(=내레이션), 프롬프트, 어느 diff·출력을 보여 줄지 |
| `build_video.py` | 대본 → 시각표 → 프레임 렌더 → 효과음·배경음 → mp4 + `.srt` |
| `player.html` · `diagrams.js` | 한 시각의 화면을 그리는 무대 (IDE · 브라우저 · 도해 · 카드 · 자막) |
| `render_frames.mjs` | `player.html`을 프레임마다 찍어 ffmpeg로 흘려 넣는다 |
| `captured/` | 실제 실행 기록 (JSON). `screens/`는 용량 때문에 커밋하지 않는다 |

## 기록을 만든 방법

1. karaoke 브랜치에서 작업용 worktree를 만들고 단계마다 실제로 코드를 고쳤다 (그 결과가 `docs/실습-문센서-부저/patches/`).
2. 단계마다 `python cap.py diff <id> --repo <worktree> -- <파일>`로 변경을, `python cap.py run <id> --show "화면에 보일 명령" -- <명령>`으로 출력을 기록했다.
   - 파이 쪽은 `GPIOZERO_PIN_FACTORY=mock`(gpiozero 가짜 핀)으로 실행했다. 실물 라즈베리파이 화면은 담지 않았다.
   - 시행착오 장면(핀 겹침, 404, 401, 재시작 직후 404, 빈 DB에서 규칙이 안 도는 문제, 새로고침해야 바뀌는 화면)은 실제로 재현하거나 실제로 겪은 그대로다.
3. 관리자 화면은 백엔드(8000)·프론트(3000)·`pi/mock_door.py`를 함께 띄우고 `screen_rec.mjs`로 녹화했다. 두 기록은 시계 시각(`started_at`)으로 맞춘다.

## 다시 만들기

```bash
pip install numpy pygments
npm i d2coding playwright-core            # 코드 글꼴과 브라우저 조종
export D2CODING_DIR=$PWD/node_modules/d2coding/src
export PW_CORE=$PWD/node_modules/playwright-core/index.mjs
export PW_CHROME=<크롬 실행 파일 경로>
python build_video.py pi --plan           # 장면 시각표만
python build_video.py pi --check 40 200   # 그 시각의 화면 PNG (out/work-pi/)
python build_video.py pi                  # → out/1-라즈베리파이편.mp4, .srt
python build_video.py web                 # → out/2-백엔드-프론트엔드편.mp4, .srt
```

자막 문장만 고칠 때는 `episodes.py`만 고치면 됩니다. 브라우저 장면(`captured/screens/`)은 커밋되어
있지 않으므로, 처음 다시 만드는 컴퓨터에서는 위 3번처럼 서버를 띄우고 `screen_rec.mjs`로 다시 녹화합니다.

## 소리

자막만 있고 해설 음성은 없습니다. 효과음(자판, 알림, 오류음, 부저 흉내)과 아주 작은 배경 화음은
`build_video.py`가 숫자로 합성합니다. 해설 음성은 `docs/실습-문센서-부저/voiceover.py`로 학교 PC에서 입힙니다.
