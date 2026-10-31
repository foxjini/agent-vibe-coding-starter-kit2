// render_frames.mjs — player.html 을 시각마다 그려 ffmpeg 로 흘려 넣는다.
//   node render_frames.mjs <작업폴더> --fps 15 --out video.mp4 --duration 540
//   node render_frames.mjs <작업폴더> --check 12.5 40     (그 시각의 PNG 만)
// 환경 변수: PW_CORE(playwright-core/index.mjs 경로), PW_CHROME(크롬 실행 파일)
import { spawn } from 'node:child_process';
import path from 'node:path';

const { chromium } = await import(process.env.PW_CORE);
const args = process.argv.slice(2);
const work = path.resolve(args[0]);
const opt = (k, d) => { const i = args.indexOf(k); return i < 0 ? d : args[i + 1]; };

const browser = await chromium.launch({ executablePath: process.env.PW_CHROME, args: ['--no-sandbox', '--font-render-hinting=none'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => { console.error('PAGEERROR', e.message); process.exitCode = 1; });
await page.goto('file://' + path.join(work, 'player.html'));
await page.evaluate(() => document.fonts.ready);

if (args.includes('--check')) {
  const times = args.slice(args.indexOf('--check') + 1).map(Number);
  for (const t of times) {
    await page.evaluate((x) => window.renderAt(x), t);
    await page.evaluate(() => document.fonts.ready);
    const file = path.join(work, `check-${String(t).replace('.', '_')}.png`);
    await page.screenshot({ path: file });
    console.log(file);
  }
  await browser.close();
  process.exit(process.exitCode || 0);
}

const fps = Number(opt('--fps', 15));
const dur = Number(opt('--duration', 10));
const out = opt('--out', path.join(work, 'video.mp4'));
const total = Math.ceil(dur * fps);
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', 'pipe:0',
  '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-tune', 'animation',
  '-g', '60', out], { stdio: ['pipe', 'inherit', 'inherit'] });
const write = (buf) => new Promise((res) => (ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res)));

let prevSig = null, prevBuf = null, shots = 0;
const t0 = Date.now();
for (let k = 0; k < total; k++) {
  const t = k / fps;
  const sig = await page.evaluate((x) => window.renderAt(x), t);
  if (sig !== prevSig) {
    prevBuf = await page.screenshot({ type: 'jpeg', quality: 94 });
    prevSig = sig;
    shots++;
  }
  await write(prevBuf);
  if (k % (fps * 30) === 0) {
    const el = (Date.now() - t0) / 1000;
    console.log(`  ${(t / 60).toFixed(1)}분 / ${(dur / 60).toFixed(1)}분  (새로 그린 화면 ${shots}장, ${el.toFixed(0)}초)`);
  }
}
ff.stdin.end();
await new Promise((res) => ff.on('close', res));
await browser.close();
console.log(`완료: ${total}프레임, 새로 그린 화면 ${shots}장`);
