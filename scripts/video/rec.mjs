// Walkthrough act 5: four NVDA scenes on the live site, recorded.
// Writes video/*.webm (Playwright), nvda.wav (loopback, by loopback.py), speech.json.
import { chromium } from 'playwright';
import { nvda } from '@guidepup/guidepup';
import { execFileSync, spawn } from 'node:child_process';
import { writeFileSync, existsSync, rmSync, readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const DIR = fileURLToPath(new URL('.', import.meta.url));
// Outputs go to the git-ignored data/sources/video/rec/.
const OUT = DIR + '../../data/sources/video/rec/';
const SITE = 'https://batestguy.github.io/curb-cut/';
const HOST = 'batestguy.github.io';
const BAD = /running window|tool ?bar|address and search bar|google chrome for testing|chromium/i;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = [];
let browser, page, t0 = 0, scene = '';
const now = () => Date.now() - t0;
const abort = (m) => { throw new Error('ABORT: ' + m); };

async function guard() {
  if (new URL(page.url()).host !== HOST) abort('left the site: ' + page.url());
}
// Press, then wait until NVDA has had time to say it (about 2.6 words a second).
async function step(label, fn, { min = 900, max = 40000, want = null } = {}) {
  await guard();
  await nvda.clearSpokenPhraseLog();
  const start = now();
  await fn();
  await sleep(700);
  let spoken = await nvda.spokenPhraseLog();
  if (want && !want(spoken.join(' '))) {
    await nvda.perform(nvda.keyboardCommands.stopSpeech).catch(() => {});
    log.push({ scene, step: label, start, end: now(), spoken, skipped: true });
    console.log(`[${scene}/${label}] skipped: ${spoken.join(' | ').slice(0, 120)}`);
    return spoken.join(' ');
  }
  const words = spoken.join(' ').split(/\s+/).filter(Boolean).length;
  await sleep(Math.min(max, Math.max(min, (words / 2.6) * 1000 + 600)) - 700);
  spoken = await nvda.spokenPhraseLog();
  const end = now();
  log.push({ scene, step: label, start, end, spoken });
  console.log(`[${scene}/${label}] ${start}-${end} ${spoken.join(' | ')}`);
  if (spoken.some((s) => BAD.test(s))) abort('focus left the page at ' + label);
  return spoken.join(' ');
}
const show = (sel, block = 'center') => page.evaluate(([s, b]) => document.querySelector(s)?.scrollIntoView({ block: b }), [sel, block]);
const activeId = () => page.evaluate(() => document.activeElement?.id);
const mark = (name) => { scene = name; log.push({ scene, mark: 'start', t: now() }); console.log('== ' + name); };

async function pick(letter, want) {
  await step('focus mode', () => nvda.perform(nvda.keyboardCommands.toggleBetweenBrowseAndFocusMode));
  if ((await activeId()) !== 'state-select') abort('select not focused');
  for (let i = 0; i < 8; i++) {
    if ((await page.$eval('#state-select', (s) => s.options[s.selectedIndex]?.text)) === want) break;
    if ((await activeId()) !== 'state-select') abort('focus moved off select');
    await step(`press ${letter}`, () => nvda.press(letter));
  }
  if ((await page.$eval('#state-select', (s) => s.options[s.selectedIndex].text)) !== want) abort('no ' + want);
  let t = await step('Tab', () => nvda.press('Tab'), { min: 2500 });
  if ((await activeId()) !== 'state-show') abort('Tab did not reach Show figures (focus on ' + (await activeId()) + ')');
  if (!/show figures/i.test(t)) console.log('note: NVDA did not name the button within the wait');
  await nvda.clearSpokenPhraseLog();
  const start = now();
  await nvda.press('Enter');
  await page.waitForFunction((w) => {
    const c = document.getElementById('state-card'), h = document.getElementById('state-card-heading');
    return c && !c.hidden && h && h.textContent.includes(w) && document.activeElement === h;
  }, want, { timeout: 60000 });
  await sleep(4000); // NVDA announces the heading when focus moves to it
  log.push({ scene, step: `Enter (Show figures, ${want})`, start, end: now(), spoken: await nvda.spokenPhraseLog() });
  console.log(`[${scene}/Enter] ` + (await nvda.spokenPhraseLog()).join(' | ').slice(0, 300));
}

mkdirSync(OUT, { recursive: true });
const stopFile = OUT + 'STOP', startFile = OUT + 'audio-start.txt';
for (const f of [stopFile, startFile]) if (existsSync(f)) rmSync(f);
const rec = spawn('uv', ['run', '--no-project', '--python', '3.12', '--with', 'soundcard', '--with', 'numpy',
  'python', '-I', DIR + 'loopback.py', OUT + 'nvda.wav', stopFile, startFile], { cwd: DIR, stdio: 'inherit' });

try {
  for (let i = 0; i < 120 && !existsSync(startFile); i++) await sleep(500);
  if (!existsSync(startFile)) abort('audio recorder did not start');
  browser = await chromium.launch({ headless: false, args: ['--window-size=1296,900', '--window-position=0,0'] });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: OUT + 'video', size: { width: 1280, height: 720 } },
  });
  await ctx.route(/goatcounter\.com/, (r) => r.abort());
  // Slow connection (about 18 KB/s on 2026-11-07): the DuckDB engine files come from the local
  // build, like a warm browser cache. Each must match the live file's size; every figure still
  // comes from the live site.
  const DIST = DIR + '../../site/dist/';
  const CACHED = {
    'assets/duckdb-eh-9ubY-jlA.wasm': 'application/wasm',
    'assets/duckdb-browser-eh.worker-hQa-dcAV.js': 'application/javascript; charset=utf-8',
    'assets/duckdb-client-u12hMWq9.js': 'application/javascript; charset=utf-8',
    'duckdb-extensions/v1.4.3/wasm_eh/parquet.duckdb_extension.wasm': 'application/wasm',
  };
  const { statSync } = await import('node:fs');
  for (const [rel, type] of Object.entries(CACHED)) {
    const head = await fetch(SITE + rel, { method: 'HEAD', headers: { 'Accept-Encoding': 'identity' } });
    const live = Number(head.headers.get('content-length'));
    const local = statSync(DIST + rel).size;
    if (!head.ok || live !== local) abort(`${rel}: live ${live} bytes, local ${local}`);
    await ctx.route(SITE + rel, (r) => r.fulfill({ path: DIST + rel, contentType: type }));
  }
  console.log('DuckDB files served from the local build (sizes match the live site)');
  ctx.setDefaultNavigationTimeout(180000);
  ctx.setDefaultTimeout(120000);
  t0 = Date.now();
  page = await ctx.newPage();
  await page.goto(SITE, { waitUntil: 'networkidle' });
  await page.waitForSelector('#state-select:not([disabled])', { timeout: 60000 });
  await page.waitForFunction(() => /Taraba/.test(document.getElementById('prevalence-chart-desc')?.textContent || ''), null, { timeout: 60000 });
  await page.evaluate(() => {
    const s = document.createElement('div'); s.id = 'nvda-start'; s.tabIndex = -1;
    document.body.prepend(s); s.focus();
  });
  const title = await page.title();
  execFileSync('powershell', ['-NoProfile', '-Command', 'Add-Type -AssemblyName System.Windows.Forms; $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(($b.Width - 2), ($b.Height - 2))']);
  // Guidepup's NVDA runs at rate 100 with rate boost (fine for tests, unintelligible on video):
  // NVDA's default rate for this session only.
  await nvda.start({ settings: { speech: { oneCore: { rate: '50', rateBoost: 'False' } } } });
  await sleep(3000);
  // Activate the window the way the 2026-11-07 check did (no click: a title-bar click leaves focus off the page).
  execFileSync('powershell', ['-NoProfile', '-Command', `(New-Object -ComObject WScript.Shell).AppActivate('${title.replace(/'/g, "''")}') | Out-Null`]);
  await sleep(2000);
  await page.evaluate(() => { document.getElementById('nvda-start').focus(); window.scrollTo(0, 0); });
  await sleep(2500);

  // Scene 1: main heading and the national figure.
  mark('s1-main');
  // Several ways to the main heading; the first that NVDA confirms is kept.
  const tries = [
    ['1 (next heading level 1)', () => nvda.perform(nvda.keyboardCommands.moveToNextHeadingLevel1)],
    ['1 again', () => nvda.perform(nvda.keyboardCommands.moveToNextHeadingLevel1)],
    ['H (next heading)', () => nvda.perform(nvda.keyboardCommands.moveToNextHeading)],
    ['Ctrl+Home (top of page)', () => nvda.press('Control+Home')],
    ['1 after Ctrl+Home', () => nvda.perform(nvda.keyboardCommands.moveToNextHeadingLevel1)],
  ];
  let found = false;
  for (const [label, fn] of tries) {
    const h = await step(label, fn, { min: 2000 });
    if (/Disability in Nigeria/i.test(h)) { found = true; break; }
  }
  if (!found) abort('could not reach the main heading (see the lines above for what NVDA said)');
  for (let i = 0; i < 6; i++) {
    const s = await step(`Down ${i + 1}`, () => nvda.next());
    if (/\d\.\d%/.test(s)) break;
  }

  // Scene 2: the state chart's description, reached with G (next graphic).
  mark('s2-chart');
  await page.evaluate(() => { const f = document.getElementById('prevalence-chart').closest('figure'); window.scrollTo(0, f.getBoundingClientRect().top + window.scrollY - 16); });
  let ok = false;
  for (let i = 0; i < 6 && !ok; i++) {
    const s = await step(`G ${i + 1}`, () => nvda.perform(nvda.keyboardCommands.moveToNextGraphic), { max: 45000, want: (t) => /Dot plot/i.test(t) });
    ok = /Dot plot/i.test(s) && /Highest estimate: Taraba/i.test(s);
  }
  if (!ok) abort('G did not reach the state chart');

  // Scene 3: Lagos card.
  mark('s3-lagos');
  await show('#state-select');
  const c = await step('C (next combo box)', () => nvda.perform(nvda.keyboardCommands.moveToNextComboBox), { min: 1500 });
  if (!/state/i.test(c) || !/combo/i.test(c)) abort('C did not land on the State combo box');
  await pick('l', 'Lagos');
  for (let i = 0; i < 12; i++) {
    const s = await step(`card Down ${i + 1}`, () => nvda.next());
    if (/percent/i.test(s) && i > 3) break;
  }

  // Scene 4: the poverty page's main result.
  mark('s4-poverty');
  await nvda.perform(nvda.keyboardCommands.toggleBetweenBrowseAndFocusMode).catch(() => {});
  await page.goto(SITE + 'poverty.html', { waitUntil: 'networkidle' });
  await guard();
  await sleep(2500);
  ok = false;
  for (let i = 0; i < 4 && !ok; i++) {
    const s = await step(`H ${i + 1}`, () => nvda.perform(nvda.keyboardCommands.moveToNextHeading));
    ok = /main result/i.test(s);
  }
  if (!ok) abort('H did not reach The main result');
  let r = '';
  for (let i = 0; i < 5 && !/points\)\./.test(r); i++) r += ' ' + (await step(`Down ${i + 1} (main result)`, () => nvda.next()));
  if (!/11\.7/.test(r) || !/points\)\./.test(r)) abort('main result not read in full');
  mark('end');
  await sleep(1000);
  console.log('DONE');
} catch (e) {
  log.push({ error: String(e) });
  console.error(String(e));
  process.exitCode = 1;
} finally {
  try { await nvda.stop(); } catch {}
  const video = page ? await page.video()?.path() : null;
  try { await browser?.close(); } catch {}
  writeFileSync(stopFile, '');
  await new Promise((r) => rec.on('exit', r));
  const audioStart = existsSync(startFile) ? Number(readFileSync(startFile, 'utf8')) : null;
  writeFileSync(OUT + 'speech.json', JSON.stringify({ videoStartEpoch: t0, audioStartEpoch: audioStart, video, log }, null, 1));
}
