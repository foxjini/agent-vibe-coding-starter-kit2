/**
 * 학교 노래방 부스 — 선곡 목록 (2026년 9월 기준)
 *
 * 선정 기준: 중·고등학생이 실제로 노래방에서 자주 부르는 곡
 *   ① 2026년 상반기 국내 차트 상위곡 (멜론 장기 1위 / 빌보드 상반기 K-POP 25선)
 *   ② 발매 후 몇 년이 지나도 노래방 차트에 남아 있는 "떼창 스테디셀러"
 *   ③ 반주에 맞춰 부르기 쉬운 음역·템포 (중고생 평균 음역 고려)
 *
 * ⚠️ 가사 텍스트는 이 파일에 넣지 않는다.
 *    가사는 저작물이라 저장소에 그대로 복제하면 그 자체가 침해가 된다.
 *    → 가사는 "노래방 영상"이 화면에 직접 표시하고,
 *      이 파일은 저작권과 무관한 `guideCues`(구간 안내)만 갖는다.
 *    자세한 근거: docs/부록F-노래방-미디어-저작권-검토-및-구현계획.md
 */

/** 이 곡을 어떤 권리로 재생하는가 */
export type MediaLicense =
  /** 유튜브 공식 임베드 플레이어로 스트리밍 (복제 없음 · 기본값) */
  | "youtube-embed"
  /** 학교가 정식 구매·구독한 반주 음원 파일 */
  | "school-licensed"
  /** 학생이 직접 연주·편곡해 만든 반주 */
  | "self-produced"
  /** CC 라이선스 또는 퍼블릭 도메인 음원 */
  | "cc-or-public-domain"
  /** 위 어느 것도 없을 때 앱이 실시간 합성하는 내장 자동 반주 */
  | "synth-fallback";

/** 곡 구간 안내 큐 — 가사가 아니라 "지금 어느 구간인가"를 알려주는 정보 */
export interface GuideCue {
  /** 곡 시작 기준 초 */
  t: number;
  kind: "intro" | "verse" | "pre" | "chorus" | "bridge" | "high" | "outro";
  /** 화면에 크게 뜨는 안내 문구 */
  label: string;
  /** 작은 글씨 팁 (호흡·고음 준비 등) */
  hint?: string;
}

export interface KaraokeSong {
  /** 미디어 파일명·DOM key로 쓰이는 고유 ID (영문 소문자 + 하이픈) */
  id: string;
  title: string;
  singer: string;
  genre: string;
  /** 목록에 붙는 짧은 배지 */
  tag: string;
  /** 발매 연도 */
  year: number;
  /** 선정 근거 — 전시회에서 "왜 이 곡인가" 설명용 */
  pickReason: string;

  /**
   * 유튜브 노래방 영상 ID.
   * null이면 화면에 "영상 등록" 카드가 뜬다. 잘못된 ID를 박아두고
   * 깨진 플레이어를 보여주는 것보다 낫기 때문에 기본값을 null로 둔다.
   * 등록 방법: 앱 화면의 [노래방 영상 등록] 버튼 또는
   *            `node scripts/resolve-karaoke-videos.mjs` (YouTube Data API)
   */
  youtubeId: string | null;
  /** 위 ID를 찾을 때 쓸 유튜브 검색어 */
  youtubeSearchQuery: string;

  /**
   * 로컬 미디어 파일 확장자. 파일이 있으면 유튜브보다 우선 재생한다.
   * 실제 파일은 public/media/karaoke/<id>.<ext> 에 두며 커밋되지 않는다.
   * 파일을 준비하지 않았으면 null.
   */
  localMediaExt: "mp3" | "m4a" | "wav" | "ogg" | "mp4" | "webm" | null;

  /** 현재 이 곡을 재생하는 권리 근거 */
  license: MediaLicense;

  /** 내장 신스 폴백 반주가 참고하는 값 (원곡과 정확히 같지 않은 근사치) */
  mr: {
    bpm: number;
    style: "rock" | "dance" | "acoustic" | "ballad";
    /** 코드 진행 — 대중적으로 널리 쓰이는 진행 템플릿 (원곡 채보가 아님) */
    progression: "I-V-vi-IV" | "vi-IV-I-V" | "I-vi-IV-V" | "i-VI-III-VII";
    /** 기준 조성의 으뜸음 주파수(Hz) */
    tonic: number;
  };

  /** 대략적인 곡 길이(초) — 진행률 표시에만 쓰이며 실제 재생 길이가 우선한다 */
  approxDurationSec: number;

  guideCues: GuideCue[];
}

/** 어느 곡에나 쓸 수 있는 표준 구간 큐 (곡 길이에 맞춰 스케일링해서 사용) */
function standardCues(durationSec: number, highHint: string): GuideCue[] {
  const d = durationSec;
  return [
    { t: 0, kind: "intro", label: "🎵 전주 — 호흡 가다듬기", hint: "마이크 잡고 준비!" },
    { t: Math.round(d * 0.12), kind: "verse", label: "1절 시작", hint: "편하게, 작게 시작해도 좋아요" },
    { t: Math.round(d * 0.28), kind: "pre", label: "프리코러스 — 힘 모으기", hint: "숨 크게 들이쉬기" },
    { t: Math.round(d * 0.36), kind: "chorus", label: "🔥 후렴 — 다 같이!", hint: highHint },
    { t: Math.round(d * 0.5), kind: "verse", label: "2절", hint: "한 번 쉬어가는 구간" },
    { t: Math.round(d * 0.63), kind: "chorus", label: "🔥 두 번째 후렴", hint: "관객 호응 유도!" },
    { t: Math.round(d * 0.75), kind: "bridge", label: "브릿지 — 잠깐 숨 고르기", hint: "마지막 고음 준비" },
    { t: Math.round(d * 0.84), kind: "high", label: "⭐ 하이라이트 고음 구간", hint: highHint },
    { t: Math.round(d * 0.94), kind: "outro", label: "마무리 — 끝까지 또박또박", hint: "곧 점수가 나옵니다" },
  ];
}

/**
 * 2026년 9월 기준 중·고등학생 노래방 애창곡 10곡
 * 순서를 바꾸거나 곡을 교체하려면 이 배열만 수정하면 된다.
 */
export const KARAOKE_SONGS: KaraokeSong[] = [
  {
    id: "gomin-jungdok",
    title: "고민중독",
    singer: "QWER",
    genre: "밴드 / 펑크록",
    tag: "떼창 1순위 🔥",
    year: 2024,
    pickReason: "발매 2년이 지난 2026년에도 노래방 차트 상위권을 지키는 10대 대표 떼창곡. 음역이 좁아 남녀 모두 부르기 쉽다.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 고민중독 QWER",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 138, style: "rock", progression: "I-V-vi-IV", tonic: 329.63 },
    approxDurationSec: 200,
    guideCues: standardCues(200, "후렴은 목이 아니라 배로 지르기!"),
  },
  {
    id: "one-page",
    title: "한 페이지가 될 수 있게",
    singer: "DAY6",
    genre: "밴드 / 록",
    tag: "졸업식 떼창 ✨",
    year: 2019,
    pickReason: "학교 행사·수학여행 단골 합창곡. 노래방 연간 차트 붙박이로 남아 있는 장수 인기곡.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 한 페이지가 될 수 있게 DAY6",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 136, style: "rock", progression: "I-V-vi-IV", tonic: 293.66 },
    approxDurationSec: 226,
    guideCues: standardCues(226, "'한 페이지가 될 수 있게' 부분에서 최고조!"),
  },
  {
    id: "event-horizon",
    title: "사건의 지평선",
    singer: "윤하",
    genre: "발라드 / 록",
    tag: "고음 챌린지 🚀",
    year: 2022,
    pickReason: "수능·졸업 시즌마다 역주행하는 곡. 고음 도전곡으로 중고생 사이 인지도가 매우 높다.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 사건의 지평선 윤하",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 124, style: "ballad", progression: "vi-IV-I-V", tonic: 277.18 },
    approxDurationSec: 268,
    guideCues: standardCues(268, "마지막 후렴 전조(키 상승) 주의 — 한 옥타브 준비!"),
  },
  {
    id: "apt",
    title: "APT.",
    singer: "로제 & Bruno Mars",
    genre: "팝 / 록",
    tag: "챈트 떼창 👏",
    year: 2024,
    pickReason: "'아파트' 챈트 구간 덕분에 노래를 잘 못해도 다 같이 즐길 수 있어 부스 단체 이용에 가장 잘 맞는다.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 APT 로제 브루노마스",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 149, style: "rock", progression: "I-V-vi-IV", tonic: 246.94 },
    approxDurationSec: 170,
    guideCues: standardCues(170, "챈트 구간은 관객이 함께 외치도록 마이크 넘기기!"),
  },
  {
    id: "golden",
    title: "Golden",
    singer: "HUNTR/X (케이팝 데몬 헌터스 OST)",
    genre: "OST / 팝",
    tag: "초고음 도전 ⭐",
    year: 2025,
    pickReason: "애니메이션 인기와 함께 전 연령이 아는 곡이 됐고, 고음 구간이 명확해 '점수 도전곡'으로 선호도가 높다.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 Golden 헌트릭스 케이팝 데몬 헌터스",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 100, style: "dance", progression: "I-V-vi-IV", tonic: 311.13 },
    approxDurationSec: 195,
    guideCues: standardCues(195, "마지막 하이노트는 무리하지 말고 한 옥타브 내려도 OK"),
  },
  {
    id: "404-new-era",
    title: "404 (New Era)",
    singer: "KiiiKiii (키키)",
    genre: "댄스 / 팝",
    tag: "2026 상반기 1위 🏆",
    year: 2026,
    pickReason: "2026년 발매곡 중 가장 먼저 멜론 TOP100 1위에 올랐고 빌보드 상반기 K-POP 25선 1위. 현재 10대 인지도 최상위.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 404 New Era 키키 KiiiKiii",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 126, style: "dance", progression: "vi-IV-I-V", tonic: 293.66 },
    approxDurationSec: 185,
    guideCues: standardCues(185, "랩 구간은 박자만 맞춰도 점수가 올라갑니다"),
  },
  {
    id: "bang-bang",
    title: "BANG BANG",
    singer: "IVE (아이브)",
    genre: "댄스 / 팝",
    tag: "최장기 1위 👑",
    year: 2026,
    pickReason: "2026년 발매곡 중 멜론 일간 1위를 40일로 가장 오래 지킨 곡. 여학생 선곡 1순위.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 BANG BANG 아이브 IVE",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 130, style: "dance", progression: "i-VI-III-VII", tonic: 293.66 },
    approxDurationSec: 190,
    guideCues: standardCues(190, "후렴 훅은 짧게 끊어서 또박또박!"),
  },
  {
    id: "rude",
    title: "RUDE!",
    singer: "Hearts2Hearts (하츠투하츠)",
    genre: "하우스 / 댄스",
    tag: "장기 흥행 💫",
    year: 2026,
    pickReason: "2월 발매 후 6월까지 일간 TOP10을 유지한 롱런 히트. 빌보드 상반기 K-POP 25선 2위.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 RUDE 하츠투하츠 Hearts2Hearts",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 124, style: "dance", progression: "vi-IV-I-V", tonic: 349.23 },
    approxDurationSec: 180,
    guideCues: standardCues(180, "하우스 비트라 박자만 놓치지 않으면 됩니다"),
  },
  {
    id: "rumored-paradise",
    title: "소문의 낙원",
    singer: "AKMU (악뮤)",
    genre: "팝 / 어쿠스틱",
    tag: "음정 안정 🎯",
    year: 2026,
    pickReason: "빌보드 상반기 K-POP 25선 3위. 멜로디가 또렷하고 음역이 넓지 않아 노래방 점수가 잘 나오는 곡.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 소문의 낙원 악뮤 AKMU",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 112, style: "acoustic", progression: "I-vi-IV-V", tonic: 261.63 },
    approxDurationSec: 210,
    guideCues: standardCues(210, "화음 구간은 두 명이 나눠 부르면 훨씬 좋습니다"),
  },
  {
    id: "traffic-light",
    title: "신호등",
    singer: "이무진",
    genre: "어쿠스틱 / 스윙",
    tag: "남학생 애창곡 🎸",
    year: 2021,
    pickReason: "남학생 선곡 스테디셀러. 셔플 리듬이라 박자를 타기 쉽고 음역이 낮아 변성기에도 부담이 적다.",
    youtubeId: null,
    youtubeSearchQuery: "TJ노래방 신호등 이무진",
    localMediaExt: null,
    license: "youtube-embed",
    mr: { bpm: 95, style: "acoustic", progression: "I-vi-IV-V", tonic: 261.63 },
    approxDurationSec: 210,
    guideCues: standardCues(210, "셔플(스윙) 박자 — 뒤로 살짝 끌면서 부르기"),
  },
];

/** id로 곡 찾기 */
export function findSongById(id: string): KaraokeSong | undefined {
  return KARAOKE_SONGS.find((s) => s.id === id);
}

/** 로컬 미디어 파일 경로 (설정돼 있을 때만) */
export function localMediaPath(song: KaraokeSong): string | null {
  return song.localMediaExt ? `/media/karaoke/${song.id}.${song.localMediaExt}` : null;
}

/** 유튜브 검색 결과 페이지 URL — 영상 ID를 직접 찾아 등록할 때 쓴다 */
export function youtubeSearchUrl(song: KaraokeSong): string {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(song.youtubeSearchQuery)}`;
}
