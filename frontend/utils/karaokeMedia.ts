/**
 * 노래방 재생 소스 결정 로직
 *
 * 우선순위
 *   1) 로컬 미디어 파일  (public/media/karaoke/<id>.<ext>)
 *      → 학교가 구매했거나 학생이 만든 음원. 음질이 가장 좋고 인터넷이 끊겨도 재생된다.
 *   2) 유튜브 공식 임베드 (IFrame Player API)
 *      → 원곡 음질 + 영상에 가사가 함께 나온다. 복제하지 않으므로 합법.
 *   3) 내장 신스 자동 반주
 *      → 위 둘 다 없을 때만. 원곡이 아니라 장르 스타일 반주다.
 *
 * 전시회장 Wi-Fi가 불안정한 상황을 대비해 1번을 최우선으로 둔다.
 */

import { KaraokeSong, localMediaPath } from "@/data/karaokeSongs";

export type PlaybackSource = "local" | "youtube" | "synth";

export interface ResolvedMedia {
  source: PlaybackSource;
  /** source === "local" 일 때의 파일 경로 */
  localUrl?: string;
  /** source === "youtube" 일 때의 영상 ID */
  youtubeId?: string;
  /** 화면에 띄울 한 줄 설명 (어떤 권리로 재생 중인지) */
  reason: string;
}

/* ── 등록된 유튜브 영상 ID 저장소 ─────────────────────────────────
 * 선생님/학생이 앱에서 등록한 영상 ID를 브라우저에 저장한다.
 * 저장소(GitHub)에 검증 안 된 ID를 박아두면 깨진 플레이어가 뜨기 때문에,
 * 실제로 재생되는 것을 확인한 ID만 이렇게 남긴다.
 */

const STORAGE_KEY = "karaoke.videoIds.v1";

type VideoIdMap = Record<string, string>;

function readMap(): VideoIdMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as VideoIdMap) : {};
  } catch {
    return {};
  }
}

function writeMap(map: VideoIdMap) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* 시크릿 모드 등 저장 실패는 무시 — 이번 세션에서는 메모리로만 동작 */
  }
}

/** 곡에 등록된 유튜브 영상 ID (등록본 우선, 없으면 manifest 기본값) */
export function getVideoId(song: KaraokeSong): string | null {
  return readMap()[song.id] ?? song.youtubeId;
}

/** 재생이 확인된 영상 ID를 저장한다 */
export function saveVideoId(songId: string, videoId: string) {
  const map = readMap();
  map[songId] = videoId;
  writeMap(map);
}

/** 재생 실패한 영상 ID를 지운다 (임베드 차단·삭제된 영상) */
export function clearVideoId(songId: string) {
  const map = readMap();
  delete map[songId];
  writeMap(map);
}

/** 영상 ID가 등록된 곡 수 — 설정 화면 안내용 */
export function registeredVideoCount(songs: KaraokeSong[]): number {
  const map = readMap();
  return songs.filter((s) => map[s.id] ?? s.youtubeId).length;
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

/** 이 곡을 지금 어떤 소스로 재생할지 결정한다 */
export async function resolveMedia(song: KaraokeSong): Promise<ResolvedMedia> {
  const path = localMediaPath(song);
  if (path && (await probeLocalMedia(song))) {
    return {
      source: "local",
      localUrl: path,
      reason:
        song.license === "self-produced"
          ? "학생이 직접 만든 반주 파일로 재생 중"
          : song.license === "cc-or-public-domain"
          ? "CC/퍼블릭 도메인 음원으로 재생 중"
          : "학교가 정식 확보한 반주 파일로 재생 중",
    };
  }

  const videoId = getVideoId(song);
  if (videoId) {
    return {
      source: "youtube",
      youtubeId: videoId,
      reason: "유튜브 공식 임베드 플레이어로 스트리밍 중 (복제 없음)",
    };
  }

  return {
    source: "synth",
    reason: "내장 자동 반주 — 원곡이 아닌 장르 스타일 반주입니다",
  };
}
