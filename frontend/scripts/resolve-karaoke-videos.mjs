#!/usr/bin/env node
/**
 * 노래방 영상 ID 일괄 조회 스크립트 (선택 도구)
 *
 * 곡마다 앱에서 링크를 붙여넣는 대신, YouTube Data API v3로 한 번에 찾아
 * data/karaokeSongs.ts의 youtubeId 값을 채워 준다.
 *
 * ✅ 이 스크립트는 영상을 **내려받지 않는다.** 유튜브가 공식으로 제공하는
 *    검색 API로 "임베드가 허용된 영상"의 ID만 조회한다.
 *    (videoEmbeddable=true 조건 → 앱에서 재생이 막히는 영상을 애초에 거른다)
 *
 * ── 사용법 ─────────────────────────────────────────────────────────
 *   1. Google Cloud Console에서 YouTube Data API v3를 켜고 API 키를 만든다
 *      https://console.cloud.google.com/apis/library/youtube.googleapis.com
 *   2. 키를 환경변수로 넘긴다 (코드나 채팅에 직접 붙여넣지 않는다!)
 *
 *      YOUTUBE_API_KEY=... node scripts/resolve-karaoke-videos.mjs
 *
 *   3. 미리보기만 하려면 --dry-run, 실제로 파일을 고치려면 --write
 *
 *      YOUTUBE_API_KEY=... node scripts/resolve-karaoke-videos.mjs --write
 *
 * ⚠️ API 키는 .env에 넣고 절대 커밋하지 않는다 (.agents/rules/security-rules.md)
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MANIFEST = join(__dirname, "..", "data", "karaokeSongs.ts");

const apiKey = process.env.YOUTUBE_API_KEY;
const write = process.argv.includes("--write");

if (!apiKey) {
  console.error("❌ YOUTUBE_API_KEY 환경변수가 없습니다.");
  console.error("   예) YOUTUBE_API_KEY=... node scripts/resolve-karaoke-videos.mjs --write");
  process.exit(1);
}

const source = readFileSync(MANIFEST, "utf8");

// manifest에서 id와 검색어만 뽑아 온다 (TS를 실행하지 않고 정규식으로 읽는다)
const songs = [];
const blockRe = /id:\s*"([^"]+)"[\s\S]*?youtubeSearchQuery:\s*"([^"]+)"/g;
let m;
while ((m = blockRe.exec(source)) !== null) {
  songs.push({ id: m[1], query: m[2] });
}

if (songs.length === 0) {
  console.error("❌ karaokeSongs.ts에서 곡을 읽지 못했습니다.");
  process.exit(1);
}

console.log(`🔎 ${songs.length}곡의 노래방 영상을 검색합니다...\n`);

/** 임베드 가능한 영상만 골라 첫 번째 결과를 돌려준다 */
async function search(query) {
  const url = new URL("https://www.googleapis.com/youtube/v3/search");
  url.searchParams.set("part", "snippet");
  url.searchParams.set("q", query);
  url.searchParams.set("type", "video");
  url.searchParams.set("videoEmbeddable", "true"); // 앱에서 재생 가능한 영상만
  url.searchParams.set("videoSyndicated", "true");
  url.searchParams.set("maxResults", "3");
  url.searchParams.set("regionCode", "KR");
  url.searchParams.set("relevanceLanguage", "ko");
  url.searchParams.set("key", apiKey);

  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status} — ${body.slice(0, 200)}`);
  }
  const data = await res.json();
  const first = data.items?.[0];
  return first ? { id: first.id.videoId, title: first.snippet.title } : null;
}

const results = [];
for (const song of songs) {
  try {
    const hit = await search(song.query);
    if (hit) {
      results.push({ ...song, videoId: hit.id });
      console.log(`  ✅ ${song.id.padEnd(20)} ${hit.id}  ${hit.title.slice(0, 45)}`);
    } else {
      console.log(`  ⚠️  ${song.id.padEnd(20)} 검색 결과 없음 — 앱에서 직접 등록하세요`);
    }
  } catch (err) {
    console.log(`  ❌ ${song.id.padEnd(20)} ${err.message}`);
  }
}

if (!write) {
  console.log("\n미리보기만 실행했습니다. 실제로 반영하려면 --write 를 붙이세요.");
  process.exit(0);
}

// youtubeId: null → youtubeId: "..." 로 교체
let updated = source;
let changed = 0;
for (const r of results) {
  const re = new RegExp(`(id:\\s*"${r.id}"[\\s\\S]*?youtubeId:\\s*)(null|"[^"]*")`);
  if (re.test(updated)) {
    updated = updated.replace(re, `$1"${r.videoId}"`);
    changed++;
  }
}
writeFileSync(MANIFEST, updated, "utf8");

console.log(`\n💾 ${changed}곡의 영상 ID를 data/karaokeSongs.ts에 기록했습니다.`);
console.log("   ⚠️ 반드시 앱을 실행해 곡마다 실제로 재생되는지 직접 확인하세요!");
