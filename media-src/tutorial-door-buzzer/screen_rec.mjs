// screen_rec.mjs — 실습 영상에 넣을 /admin 실제 화면을 프레임으로 기록한다.
//
//   node screen_rec.mjs <이름> <초> '<동작 JSON>'
//
// 동작 JSON 예: [{"t":2,"do":"door","value":1},{"t":6,"do":"reload"},{"t":8,"do":"click","text":"경고 부저 울리기"}]
//   door   — 파이 대신 문 센서 값을 보고한다 (POST /api/v1/devices/door_sensor_1/state)
//   reload — 새로고침(F5)
//   click  — 그 글자가 있는 버튼을 누른다
//
// 결과: captured/screens/<이름>/f0000.jpg … 와 frames.json(각 프레임의 실제 시각)
// 환경 변수: PW_CHROME(크롬 경로), PW_CORE(playwright-core 경로), FE(기본 http://localhost:3000),
//           BE(기본 http://localhost:8000), DEVICE_KEY, ADMIN_PIN
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(process.env.PW_CORE);
const [name, secs, planJson] = process.argv.slice(2);
const plan = JSON.parse(planJson || '[]');
const FE = process.env.FE || 'http://localhost:3000';
const BE = process.env.BE || 'http://localhost:8000';
const KEY = process.env.DEVICE_KEY || '';
const PIN = process.env.ADMIN_PIN || '9179';
const FPS = Number(process.env.FPS || 6);

const out = path.join(here, 'captured', 'screens', name);
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.PW_CHROME, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });

async function toPanel() {
  const el = page.getByText('가상 노래방 부스 실시간 물리 상태');
  await el.waitFor({ timeout: 15000 });
  await el.evaluate((n) => {
    const box = n.closest('.grid') || n;
    window.scrollTo(0, box.getBoundingClientRect().top + window.scrollY - 92);
  });
  await page.waitForTimeout(400);
}

await page.goto(`${FE}/admin`, { waitUntil: 'networkidle' });
await page.fill('input[type="password"]', PIN);
await page.click('button:has-text("인증")');
await toPanel();

const frames = [];
const t0 = Date.now();
let next = 0;
const pending = [...plan].sort((a, b) => a.t - b.t);
while ((Date.now() - t0) / 1000 < Number(secs)) {
  const now = (Date.now() - t0) / 1000;
  while (pending.length && pending[0].t <= now) {
    const a = pending.shift();
    if (a.do === 'door') {
      await fetch(`${BE}/api/v1/devices/door_sensor_1/state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-Api-Key': KEY },
        body: JSON.stringify({ value: a.value, unit: 'door_open' }),
      });
    } else if (a.do === 'reload') {
      await page.reload({ waitUntil: 'networkidle' });
      await toPanel();
    } else if (a.do === 'click') {
      await page.click(`button:has-text("${a.text}")`);
    }
    frames.push({ t: now, event: a });
  }
  if (now >= next) {
    const file = `f${String(frames.filter((f) => f.file).length).padStart(4, '0')}.jpg`;
    await page.screenshot({ path: path.join(out, file), type: 'jpeg', quality: 90 });
    frames.push({ t: (Date.now() - t0) / 1000, epoch: Date.now() / 1000, file });
    next += 1 / FPS;
  } else {
    await page.waitForTimeout(10);
  }
}
fs.writeFileSync(path.join(out, 'frames.json'), JSON.stringify({ name, started_at: t0 / 1000, fps: FPS, frames }, null, 1));
await browser.close();
console.log(`[screen_rec] ${name}: ${frames.filter((f) => f.file).length}장`);
