/**
 * 노래방 재생 소스 결정 로직
 *
 * 우선순위
 *   1) 로컬 미디어 파일  (public/media/karaoke/<id>.<ext>)
 *   2) 유튜브 영상 — ① 관리자가 등록한 영상 → ② 곡의 기본 후보 목록 순서대로
 *   3) 내장 신스 자동 반주
 *
 * ── 후보 목록이 필요한 이유 ─────────────────────────────────────
 * 영상 ID를 하나만 박아 두면 그 영상이 삭제되거나 임베드가 막히는 순간
 * 곡이 통째로 죽는다. 같은 곡의 다른 버전을 여러 개 넣어 두고 실패하면
 * 다음 후보로 넘어가면 그런 일이 없다.
 *
 * ── 등록본을 서버에 두는 이유 ───────────────────────────────────
 * 예전에는 localStorage에 저장해서 부스 화면·관람객 폰·관리자 노트북이
 * 각각 따로 등록해야 했다. 전시회에서는 치명적이라 서버로 옮겼다.
 */

import { KaraokeSong, localMediaPath } from "@/data/karaokeSongs";
import { apiUrl } from "@/utils/apiConfig";
import { adminFetch } from "@/utils/adminSession";

export type PlaybackSource = "local" | "youtube" | "synth";

export interface ResolvedMedia {
  source: PlaybackSource;
  /** source === "local" 일 때의 파일 경로 */
  localUrl?: string;
  /** source === "youtube" 일 때의 영상 ID */
  youtubeId?: string;
  /** 시도 목록에서 몇 번째를 쓰고 있는지 (실패 시 +1 해서 다음 후보로) */
  attemptIndex?: number;
  /** 화면에 띄울 한 줄 설명 (어떤 권리로 재생 중인지) */
  reason: string;
}

/* ── 관리자 등록본 (서버 저장) ──────────────────────────────────
 * 앱이 뜰 때 한 번 받아 와 메모리에 캐시한다. 없거나 서버가 꺼져 있어도
 * 곡의 기본 후보 목록으로 재생되므로 노래방 자체는 멈추지 않는다.
 */

type VideoIdMap = Record<string, string>;

let overrides: VideoIdMap = {};
let overridesLoaded = false;
let inflight: Promise<VideoIdMap> | null = null;

/** 서버에서 관리자 등록본을 받아 온다 (앱 시작 시 1회) */
export async function loadVideoOverrides(): Promise<VideoIdMap> {
  if (overridesLoaded) return overrides;
  if (inflight) return inflight;

  inflight = (async () => {
    try {
      const res = await fetch(apiUrl("/api/song-videos"));
      if (res.ok) {
        const json = await res.json();
        overrides = (json?.data as VideoIdMap) ?? {};
      }
    } catch {
      // 백엔드가 꺼져 있어도 기본 후보로 재생된다
    }
    overridesLoaded = true;
    inflight = null;
    return overrides;
  })();

  return inflight;
}

/** 캐시된 등록본에서 이 곡의 영상 ID (없으면 null) */
export function getRegisteredVideoId(songId: string): string | null {
  return overrides[songId] ?? null;
}

/**
 * 곡에 영상을 등록한다 (관리자 전용).
 * 서버에 저장해 모든 기기가 같은 영상을 보게 한다.
 */
export async function registerVideoId(
  songId: string,
  videoId: string
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const res = await adminFetch(`/api/song-videos/${encodeURIComponent(songId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId }),
    });

    if (res.status === 401) {
      return { ok: false, message: "영상 등록은 관리자만 할 수 있습니다. 첫 번째 탭에서 관리자 인증을 먼저 해 주세요." };
    }
    if (!res.ok) {
      const json = await res.json().catch(() => null);
      return { ok: false, message: json?.error?.message ?? "영상 등록에 실패했습니다." };
    }

    overrides[songId] = videoId;
    return { ok: true };
  } catch {
    return { ok: false, message: "백엔드에 연결할 수 없습니다. 서버가 켜져 있는지 확인해 주세요." };
  }
}

/** 등록을 지우고 기본 후보 목록으로 되돌린다 (관리자 전용) */
export async function unregisterVideoId(songId: string): Promise<boolean> {
  try {
    const res = await adminFetch(`/api/song-videos/${encodeURIComponent(songId)}`, {
      method: "DELETE",
    });
    if (res.ok) {
      delete overrides[songId];
      return true;
    }
  } catch {
    /* 무시 */
  }
  return false;
}

/** 영상이 준비된 곡 수 — 목록 배지에 쓴다 */
export function hasPlayableVideo(song: KaraokeSong): boolean {
  return Boolean(overrides[song.id]) || song.youtubeCandidates.length > 0;
}

/* ── 로컬 파일 존재 확인 ───────────────────────────────────────── */

const localProbeCache = new Map<string, boolean>();

/**
 * public/media/karaoke/ 에 실제로 파일이 있는지 HEAD 요청으로 확인한다.
 * 파일은 커밋되지 않으므로 "manifest에 적혀 있다 = 파일이 있다"가 아니다.
 */
export async function probeLocalMedia(song: KaraokeSong): Promise<boolean> {
  const path = localMediaPath(song);
  if (!path) return false;

  const cached = localProbeCache.get(path);
  if (cached !== undefined) return cached;

  try {
    const res = await fetch(path, { method: "HEAD" });
    // dev 서버가 404에 HTML을 돌려주는 경우가 있어 content-type도 함께 본다
    const type = res.headers.get("content-type") ?? "";
    const ok = res.ok && !type.includes("text/html");
    localProbeCache.set(path, ok);
    return ok;
  } catch {
    localProbeCache.set(path, false);
    return false;
  }
}

/* ── 재생 소스 결정 ──────────────────────────────────────────── */

function localReason(song: KaraokeSong): string {
  if (song.license === "self-produced") return "학생이 직접 만든 반주 파일로 재생 중";
  if (song.license === "cc-or-public-domain") return "CC/퍼블릭 도메인 음원으로 재생 중";
  return "학교가 정식 확보한 반주 파일로 재생 중";
}

const YT_REASON = "유튜브 공식 임베드 플레이어로 스트리밍 중 (복제 없음)";
const SYNTH_REASON = "내장 자동 반주 — 원곡이 아닌 장르 스타일 반주입니다";

/**
 * 이 곡에 시도할 영상 ID 목록을 순서대로 만든다.
 * 관리자 등록본이 있으면 맨 앞에 오고, 그 뒤로 코드에 적힌 기본 후보가 붙는다.
 * 중복은 제거한다 (등록본이 후보 중 하나와 같은 경우).
 */
export function videoAttempts(song: KaraokeSong): string[] {
  const registered = getRegisteredVideoId(song.id);
  const list = registered ? [registered, ...song.youtubeCandidates] : [...song.youtubeCandidates];
  return list.filter((id, i) => list.indexOf(id) === i);
}

/**
 * 이 곡을 지금 어떤 소스로 재생할지 결정한다.
 *
 * @param attemptIndex 시도 목록에서 몇 번째를 쓸지. 재생에 실패하면 호출한 쪽이
 *                     +1 해서 다시 부르고, 목록을 다 쓰면 내장 반주로 떨어진다.
 */
export async function resolveMedia(
  song: KaraokeSong,
  attemptIndex = 0
): Promise<ResolvedMedia> {
  // 1) 로컬 파일이 있으면 최우선 (전시장 Wi-Fi가 끊겨도 재생된다)
  const path = localMediaPath(song);
  if (path && (await probeLocalMedia(song))) {
    return { source: "local", localUrl: path, reason: localReason(song) };
  }

  // 2) 유튜브 — 등록본 → 기본 후보 순서
  const attempts = videoAttempts(song);
  const videoId = attempts[attemptIndex];
  if (videoId) {
    const isRegistered = attemptIndex === 0 && getRegisteredVideoId(song.id) === videoId;
    const suffix = isRegistered
      ? " · 관리자 등록 영상"
      : attempts.length > 1
      ? ` · 후보 ${attemptIndex + 1}/${attempts.length}`
      : "";
    return {
      source: "youtube",
      youtubeId: videoId,
      attemptIndex,
      reason: YT_REASON + suffix,
    };
  }

  // 3) 다 막혔으면 내장 반주
  return { source: "synth", reason: SYNTH_REASON };
}

/** 실패했을 때 시도해 볼 다음 후보가 남아 있는가 */
export function hasNextAttempt(song: KaraokeSong, attemptIndex: number): boolean {
  return attemptIndex + 1 < videoAttempts(song).length;
}
