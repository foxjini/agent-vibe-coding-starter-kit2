/**
 * YouTube IFrame Player API 래퍼
 *
 * 기존 구현은 <iframe src="youtube.com/embed/ID">를 그대로 박아 넣었기 때문에
 *   1) 영상 ID가 틀리거나 임베드가 막힌 영상이면 "동영상을 재생할 수 없음"만 뜨고
 *      코드 쪽에서는 그 사실을 알 방법이 없었고,
 *   2) 곡이 끝나도 앱이 알 수 없어 점수를 자동으로 띄우지 못했다.
 *
 * IFrame Player API를 쓰면 onError / onStateChange 이벤트를 받을 수 있어
 * 두 문제가 모두 해결된다. (공식 API이므로 유튜브 약관이 허용하는 재생 방식이다)
 *
 * 문서: https://developers.google.com/youtube/iframe_api_reference
 */

/** 플레이어 상태 (YT.PlayerState와 동일한 값) */
export const YT_STATE = {
  UNSTARTED: -1,
  ENDED: 0,
  PLAYING: 1,
  PAUSED: 2,
  BUFFERING: 3,
  CUED: 5,
} as const;

/** 유튜브가 돌려주는 오류 코드 → 학생이 읽을 수 있는 한국어 설명 */
export const YT_ERROR_MESSAGE: Record<number, string> = {
  2: "영상 ID 형식이 올바르지 않습니다. 링크를 다시 확인해 주세요.",
  5: "이 브라우저에서 재생할 수 없는 영상입니다.",
  100: "영상이 삭제되었거나 비공개로 바뀌었습니다.",
  101: "영상 소유자가 외부 사이트 재생(임베드)을 막아 두었습니다.",
  150: "영상 소유자가 외부 사이트 재생(임베드)을 막아 두었습니다.",
};

export interface YouTubePlayerHandle {
  play(): void;
  pause(): void;
  stop(): void;
  seekTo(seconds: number): void;
  setVolume(percent0to100: number): void;
  getCurrentTime(): number;
  getDuration(): number;
  destroy(): void;
}

export interface YouTubePlayerOptions {
  videoId: string;
  /** 재생 시작 시 자동 재생할지 */
  autoplay?: boolean;
  onReady?: (handle: YouTubePlayerHandle) => void;
  onStateChange?: (state: number) => void;
  /** 재생 불가(잘못된 ID·임베드 차단·삭제됨)일 때 호출 */
  onError?: (code: number, message: string) => void;
}

/* ── 내부: IFrame API 스크립트 1회 로딩 ─────────────────────────── */

interface YTNamespace {
  Player: new (el: HTMLElement | string, cfg: Record<string, unknown>) => YTPlayerInstance;
}
interface YTPlayerInstance {
  playVideo(): void;
  pauseVideo(): void;
  stopVideo(): void;
  seekTo(sec: number, allowSeekAhead: boolean): void;
  setVolume(v: number): void;
  getCurrentTime(): number;
  getDuration(): number;
  destroy(): void;
}
type WindowWithYT = Window & {
  YT?: YTNamespace;
  onYouTubeIframeAPIReady?: () => void;
};

let apiPromise: Promise<YTNamespace> | null = null;

/** youtube.com의 iframe_api 스크립트를 한 번만 로드한다 */
export function loadYouTubeApi(): Promise<YTNamespace> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("서버 환경에서는 사용할 수 없습니다"));
  }
  if (apiPromise) return apiPromise;

  apiPromise = new Promise<YTNamespace>((resolve, reject) => {
    const w = window as WindowWithYT;

    // 이미 로드돼 있으면 바로 사용
    if (w.YT && w.YT.Player) {
      resolve(w.YT);
      return;
    }

    // 유튜브가 스크립트 로드를 마치면 이 전역 콜백을 호출한다
    const prev = w.onYouTubeIframeAPIReady;
    w.onYouTubeIframeAPIReady = () => {
      if (prev) prev();
      if (w.YT && w.YT.Player) resolve(w.YT);
      else reject(new Error("YouTube API 로드 실패"));
    };

    const existing = document.getElementById("youtube-iframe-api");
    if (!existing) {
      const script = document.createElement("script");
      script.id = "youtube-iframe-api";
      script.src = "https://www.youtube.com/iframe_api";
      script.async = true;
      script.onerror = () =>
        reject(new Error("유튜브에 연결할 수 없습니다 (네트워크 또는 방화벽 확인)"));
      document.head.appendChild(script);
    }

    // 학교 방화벽 등으로 스크립트가 끝내 안 올라오는 경우를 대비한 타임아웃
    setTimeout(() => {
      if (!(window as WindowWithYT).YT?.Player) {
        reject(new Error("유튜브 연결이 지연되고 있습니다 (네트워크 확인)"));
      }
    }, 12000);
  });

  return apiPromise;
}

/**
 * 컨테이너 엘리먼트 안에 유튜브 플레이어를 만든다.
 * 실패(잘못된 ID·임베드 차단·네트워크)는 반드시 onError로 통보되므로
 * 호출한 쪽에서 로컬 파일이나 내장 반주로 폴백할 수 있다.
 */
export async function createYouTubePlayer(
  container: HTMLElement,
  options: YouTubePlayerOptions
): Promise<YouTubePlayerHandle> {
  const YT = await loadYouTubeApi();

  return new Promise<YouTubePlayerHandle>((resolve, reject) => {
    let settled = false;

    const player = new YT.Player(container, {
      videoId: options.videoId,
      playerVars: {
        autoplay: options.autoplay ? 1 : 0,
        // 노래방 화면이므로 관련 영상·주석 등 방해 요소를 줄인다
        rel: 0,
        modestbranding: 1,
        playsinline: 1,
        // origin을 넘겨야 브라우저가 postMessage를 차단하지 않는다 (기존 오류 원인 중 하나)
        origin: window.location.origin,
        enablejsapi: 1,
      },
      events: {
        onReady: () => {
          const handle: YouTubePlayerHandle = {
            play: () => player.playVideo(),
            pause: () => player.pauseVideo(),
            stop: () => player.stopVideo(),
            seekTo: (s: number) => player.seekTo(s, true),
            setVolume: (v: number) => player.setVolume(Math.round(Math.max(0, Math.min(100, v)))),
            getCurrentTime: () => player.getCurrentTime() || 0,
            getDuration: () => player.getDuration() || 0,
            destroy: () => {
              try {
                player.destroy();
              } catch {
                /* 이미 정리된 경우 무시 */
              }
            },
          };
          if (options.onReady) options.onReady(handle);
          if (!settled) {
            settled = true;
            resolve(handle);
          }
        },
        onStateChange: (e: { data: number }) => {
          if (options.onStateChange) options.onStateChange(e.data);
        },
        onError: (e: { data: number }) => {
          const msg = YT_ERROR_MESSAGE[e.data] ?? `재생할 수 없는 영상입니다 (코드 ${e.data})`;
          if (options.onError) options.onError(e.data, msg);
          if (!settled) {
            settled = true;
            reject(new Error(msg));
          }
        },
      },
    });
  });
}

/* ── 임베드 가능 여부 점검 ──────────────────────────────────────
 *
 * 유튜브 영상이 "우리 페이지 안에서 재생되는가"는 겉으로 봐서는 알 수 없다.
 * 영상 주인이 [다른 사이트에서 재생 금지]를 걸어 두면 유튜브에서는 잘 보이지만
 * 우리 화면에서는 오류 코드 150으로 막힌다.
 *
 * 확실한 확인 방법은 하나뿐이다 — 실제로 플레이어를 만들어 보는 것.
 * 그래서 화면 밖(off-screen)에 아주 작은 플레이어를 잠깐 띄웠다가 지운다.
 * 소리는 나지 않는다 (재생 명령을 내리지 않는다).
 */

export type ProbeStatus =
  | "ok"        // 우리 화면에서 재생 가능
  | "blocked"   // 영상은 있으나 퍼가기 금지 (101·150)
  | "missing"   // 삭제·비공개 (100)
  | "invalid"   // ID 형식 오류 (2)
  | "unplayable" // 브라우저 재생 불가 (5)
  | "timeout"   // 응답 없음 (네트워크·방화벽)
  | "error";    // 그 밖의 실패

export interface ProbeResult {
  videoId: string;
  status: ProbeStatus;
  code?: number;
  message: string;
}

function classifyProbe(videoId: string, code: number): ProbeResult {
  const message = YT_ERROR_MESSAGE[code] ?? `재생할 수 없는 영상입니다 (코드 ${code})`;
  const status: ProbeStatus =
    code === 101 || code === 150
      ? "blocked"
      : code === 100
      ? "missing"
      : code === 2
      ? "invalid"
      : code === 5
      ? "unplayable"
      : "error";
  return { videoId, status, code, message };
}

/**
 * 영상 하나가 우리 페이지에서 재생 가능한지 실제로 확인한다.
 *
 * 임베드가 막힌 영상은 onReady가 먼저 오고 곧이어 onError가 오는 경우가 있어,
 * onReady를 받아도 바로 "가능"이라고 단정하지 않고 잠시(graceMs) 기다린다.
 */
export async function probeVideoId(
  videoId: string,
  { timeoutMs = 9000, graceMs = 1800 }: { timeoutMs?: number; graceMs?: number } = {}
): Promise<ProbeResult> {
  if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
    return { videoId, status: "invalid", code: 2, message: YT_ERROR_MESSAGE[2] };
  }

  let YT: YTNamespace;
  try {
    YT = await loadYouTubeApi();
  } catch (err) {
    return { videoId, status: "error", message: (err as Error).message };
  }

  return new Promise<ProbeResult>((resolve) => {
    const host = document.createElement("div");
    // 화면 밖에 두되 display:none은 쓰지 않는다 — 숨기면 플레이어가 초기화되지 않는다
    host.style.cssText =
      "position:fixed;left:-10000px;top:0;width:200px;height:120px;opacity:0;pointer-events:none;";
    document.body.appendChild(host);
    const mount = document.createElement("div");
    host.appendChild(mount);

    let done = false;
    let player: YTPlayerInstance | null = null;
    let graceTimer: ReturnType<typeof setTimeout> | null = null;

    const finish = (result: ProbeResult) => {
      if (done) return;
      done = true;
      if (graceTimer) clearTimeout(graceTimer);
      clearTimeout(hardTimer);
      try {
        player?.destroy();
      } catch {
        /* 이미 정리된 경우 무시 */
      }
      host.remove();
      resolve(result);
    };

    const hardTimer = setTimeout(
      () =>
        finish({
          videoId,
          status: "timeout",
          message: "유튜브가 응답하지 않습니다 (네트워크·방화벽 확인)",
        }),
      timeoutMs
    );

    try {
      player = new YT.Player(mount, {
        videoId,
        playerVars: {
          autoplay: 0,
          origin: window.location.origin,
          enablejsapi: 1,
          playsinline: 1,
        },
        events: {
          onReady: () => {
            graceTimer = setTimeout(
              () => finish({ videoId, status: "ok", message: "이 화면에서 재생 가능합니다" }),
              graceMs
            );
          },
          onError: (e: { data: number }) => finish(classifyProbe(videoId, e.data)),
        },
      });
    } catch (err) {
      finish({ videoId, status: "error", message: (err as Error).message });
    }
  });
}

/**
 * 여러 영상을 한꺼번에 점검한다.
 * 유튜브가 한 번에 많은 플레이어를 만들면 느려지므로 동시 실행 수를 제한한다.
 * 결과가 하나 나올 때마다 onResult로 알려 주므로 화면을 즉시 갱신할 수 있다.
 */
export async function probeVideoIds(
  videoIds: string[],
  onResult: (result: ProbeResult) => void,
  concurrency = 3
): Promise<void> {
  let cursor = 0;
  const worker = async () => {
    while (cursor < videoIds.length) {
      const id = videoIds[cursor++];
      onResult(await probeVideoId(id));
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(concurrency, videoIds.length) }, () => worker())
  );
}

/**
 * 사용자가 붙여넣은 문자열에서 유튜브 영상 ID만 뽑아낸다.
 * watch?v=, youtu.be/, /embed/, /shorts/, /live/ 형식과 순수 ID를 모두 받는다.
 * 형식이 맞지 않으면 null (조용히 잘못된 ID를 만들어 내지 않는다).
 */
export function parseYouTubeId(input: string): string | null {
  const raw = input.trim();
  if (!raw) return null;

  // 11자리 순수 ID
  if (/^[A-Za-z0-9_-]{11}$/.test(raw)) return raw;

  const patterns = [
    /[?&]v=([A-Za-z0-9_-]{11})/,
    /youtu\.be\/([A-Za-z0-9_-]{11})/,
    /\/embed\/([A-Za-z0-9_-]{11})/,
    /\/shorts\/([A-Za-z0-9_-]{11})/,
    /\/live\/([A-Za-z0-9_-]{11})/,
  ];
  for (const re of patterns) {
    const m = raw.match(re);
    if (m) return m[1];
  }
  return null;
}

/** 임베드가 막힌 영상은 새 탭에서 여는 것이 유일한 합법 우회 경로다 */
export function youtubeWatchUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}
