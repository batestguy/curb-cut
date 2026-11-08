// Walkthrough video stills: site screenshots, terminal and code cards, caption and correction
// overlays, title and end cards. Every card's text contrast is checked with axe (as cards.mjs).
// Usage (run by make_video.py): node shots.mjs <build dir>
//   reads <build>/overlays.json (captions, corrections, terminal output) and writes
//   <build>/shots/*.png (2560x1440: screenshots at device scale 2, so the slow zoom stays sharp)
//   and <build>/overlays/*.png (1280x720, transparent).
// Site pages come from the local build (site/dist) under the live URL, after checking that the
// pages and data files used match the live site byte for byte (except the state chart, whose
// p-values differ in the 16th digit between Linux CI and this machine). GoatCounter is blocked,
// so no visit is counted. PyPI, OSF and GitHub are loaded live; if one does not load in time,
// a card states what that page shows instead.
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync, rmSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { extname } from 'node:path';

const DIR = fileURLToPath(new URL('.', import.meta.url));
const ROOT = DIR + '../../';
const BUILD = process.argv[2];
if (!BUILD) throw new Error('usage: node shots.mjs <build dir>');
const SHOTS = BUILD + '/shots/';
const OVER = BUILD + '/overlays/';
mkdirSync(SHOTS, { recursive: true });
mkdirSync(OVER, { recursive: true });
const SPEC = JSON.parse(readFileSync(BUILD + '/overlays.json', 'utf8'));
const AXE = readFileSync(ROOT + 'site/node_modules/axe-core/axe.min.js', 'utf8');
const DIST = ROOT + 'site/dist/';
const SITE = 'https://batestguy.github.io/curb-cut/';
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.parquet': 'application/octet-stream',
  '.wasm': 'application/wasm', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8',
};
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const md5 = (buf) => createHash('md5').update(buf).digest('hex');
const report = { site: 'local build', checked: {}, external: {}, contrast: {} };

// 1. The local build must match the live site for the files the shots show.
const SAME = ['index.html', 'methodology.html', 'poverty.html', 'data/prevalence.json',
  'data/poverty.json', 'data/spatial.json', 'data/charts/national_by_type.json'];
for (const rel of SAME) {
  let live = null;
  try {
    const r = await fetch(SITE + rel, { signal: AbortSignal.timeout(120000) });
    live = md5(Buffer.from(await r.arrayBuffer()));
  } catch (e) { live = 'unreachable: ' + e.message; }
  const local = md5(readFileSync(DIST + rel));
  report.checked[rel] = live === local ? 'identical' : `DIFFERS (live ${live}, local ${local})`;
  if (live !== local) console.log('WARNING', rel, report.checked[rel]);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2, colorScheme: 'light' });
await ctx.route(/goatcounter\.com/, (r) => r.abort());
await ctx.route(SITE + '**', (r) => {
  let rel = decodeURIComponent(new URL(r.request().url()).pathname.replace('/curb-cut/', ''));
  if (rel === '' || rel.endsWith('/')) rel += 'index.html';
  const file = DIST + rel;
  if (existsSync(file) && statSync(file).isFile()) {
    return r.fulfill({ path: file, contentType: TYPES[extname(file)] ?? 'application/octet-stream' });
  }
  console.log('not in the local build, fetched live:', rel);
  return r.continue();
});
const page = await ctx.newPage();
page.setDefaultTimeout(120000);

async function shotAt(id, locator, offset = 28) {
  if (locator) {
    // Twice: charts above may re-lay out after the first scroll.
    for (let i = 0; i < 2; i++) {
      await locator.first().evaluate((el, off) => {
        window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - off);
      }, offset);
      await page.waitForTimeout(600);
    }
  } else {
    await page.evaluate(() => window.scrollTo(0, 0));
  }
  await page.waitForTimeout(400);
  await page.screenshot({ path: SHOTS + id + '.png' });
  console.log('shot', id);
}

// 2. Site screenshots.
await page.goto(SITE, { waitUntil: 'networkidle' });
await page.waitForFunction(() => {
  const t = (id) => document.getElementById(id)?.textContent || '';
  return /Taraba/.test(t('prevalence-chart-desc')) && t('national-chart-desc').length > 20
    && !/Loading/.test(t('headline')) && t('moran-sentence').length > 20
    && !/Loading/.test(document.querySelector('.findings-count')?.textContent || 'Loading')
    && !/Loading/.test(document.getElementById('prevalence-map')?.getAttribute('aria-label') || 'Loading');
});
await page.waitForTimeout(1500);
await shotAt('home-top', null);
await shotAt('comparison', page.locator('#comparison-heading'));
await shotAt('jonapwd', page.locator('#jonapwd-heading'));
await shotAt('jonapwd-chart', page.locator('#national-heading'));
await shotAt('map', page.locator('#map-heading'));
await shotAt('dots', page.locator('#dots-heading'));
await shotAt('dots-findings', page.locator('#findings-heading'));
await shotAt('spatial', page.locator('#spatial-heading'));

await page.goto(SITE + 'methodology.html', { waitUntil: 'networkidle' });
await shotAt('meth-new', page.locator('#new-heading'));
await shotAt('meth-fh', page.locator('#small-area'));

await page.goto(SITE + 'poverty.html', { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
await shotAt('pov-top', null);
await shotAt('pov-headline-chart', page.locator('figure[aria-labelledby="headline-chart-title"]'), 130);
await shotAt('pov-refute', page.locator('#refutations-heading'));
await shotAt('pov-sens', page.locator('#sensitivity-heading'));
await shotAt('pov-bench', page.locator('#bench-heading'));
await shotAt('pov-dims', page.locator('#dimensions-heading'));
await shotAt('pov-ghs', page.locator('#ghs-heading'));
await shotAt('pov-ghs-cons', page.locator('th', { hasText: 'Log household consumption' }), 260);

// 3. External pages, live, with a time limit; a card if they do not load.
for (const id of ['pypi', 'osf', 'gha']) rmSync(SHOTS + id + '.png', { force: true });
const EXTERNAL = {
  pypi: { url: 'https://pypi.org/project/disability-access-charts/', ready: 'h1.package-header__name' },
  osf: { url: 'https://osf.io/kes3p/', ready: 'text=/Curb Cut/i' },
  gha: { url: SPEC.gha?.url, ready: 'text=/Success/' },
};
for (const [id, { url, ready }] of Object.entries(EXTERNAL)) {
  if (!url) { report.external[id] = 'no URL'; continue; }
  const p = await ctx.newPage();
  try {
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await p.locator(ready).first().waitFor({ timeout: 90000 });
    await p.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});
    await p.screenshot({ path: SHOTS + id + '.png' });
    report.external[id] = 'live screenshot';
    console.log('shot', id, '(live)');
  } catch (e) {
    report.external[id] = 'did not load: ' + e.message.split('\n')[0];
    console.log(id, report.external[id]);
  }
  await p.close();
}

// 4. Cards: rendered as HTML, contrast-checked with axe, screenshotted.
const cardPage = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
const overPage = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
let bad = 0;
async function render(p, id, title, body, css, path, transparent = false) {
  await p.setContent(`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>html,body{margin:0;width:1280px;height:720px;font-family:"Segoe UI",system-ui,sans-serif}
${transparent ? 'html,body{background:transparent}' : ''}${css}</style></head><body><main>${body}</main></body></html>`);
  await p.addScriptTag({ content: AXE });
  const r = await p.evaluate(() => window.axe.run(document, { runOnly: ['color-contrast'] }));
  const fails = r.violations.length + r.incomplete.length;
  report.contrast[id] = fails ? 'FAIL ' + JSON.stringify((r.violations[0] || r.incomplete[0]).nodes[0].any[0].data) : 'passes';
  if (fails) { bad++; console.log(id, 'CONTRAST', report.contrast[id]); }
  await p.screenshot({ path, omitBackground: transparent });
}
const GREEN = '#006b3f';
const TEXTCARD = `body{background:#ffffff;color:#1a1a1a}
.card{position:absolute;inset:0;padding:64px 72px;border-top:14px solid ${GREEN}}
.kicker{margin:0;font-size:24px;font-weight:600;color:${GREEN};letter-spacing:.02em}
h1{margin:12px 0 0;font-size:46px;line-height:1.15;color:#1a1a1a}
p.body{margin:26px 0 0;font-size:28px;line-height:1.4;max-width:1100px}
p.src{position:absolute;left:72px;right:72px;bottom:190px;margin:0;font-size:21px;line-height:1.4;color:#4a4a4a}`;
const textCard = (id, kicker, title, body, src) => render(cardPage, id, title,
  `<div class="card"><p class="kicker">${esc(kicker)}</p><h1>${esc(title)}</h1><p class="body">${esc(body)}</p><p class="src">${esc(src)}</p></div>`,
  TEXTCARD, SHOTS + id + '.png');
const TERM = `body{background:#1e1e1e;color:#e8e8e8}
.bar{height:40px;background:#323232;color:#d4d4d4;font-size:17px;line-height:40px;padding:0 20px}
pre{margin:0;padding:26px 32px;font-family:Consolas,"Cascadia Mono",monospace;font-size:21px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.cmd{color:#9cdcfe}.ok{color:#89d185}.bad{color:#f48771}.dim{color:#b0b0b0}`;
const term = (id, title, html) => render(cardPage, id, title,
  `<div class="bar">${esc(title)}</div><pre>${html}</pre>`, TERM, SHOTS + id + '.png');
const colour = (line) => esc(line)
  .replace(/^(\s*OK)$/, '<span class="ok">$1</span>')
  .replace(/^(\s*REJECTED:.*)$/, '<span class="bad">$1</span>')
  .replace(/(: passed)$/, '<span class="ok">$1</span>');

const T = SPEC.terminal;
const demoLines = T.demo.split('\n');
const claimAt = demoLines.findIndex((l) => l.startsWith('>>>'));
const head = demoLines.slice(0, claimAt);
const claims = demoLines.slice(claimAt);
const prompt = (cmd) => `<span class="cmd">&gt; ${esc(cmd)}</span>\n`;
await term('term-demo-0', 'Terminal: the claim checker on the real state chart',
  prompt(T.demo_cmd) + head.map(colour).join('\n'));
await term('term-demo-1', 'Terminal: the claim checker on the real state chart',
  prompt(T.demo_cmd) + [...head, ...claims.slice(0, 2)].map(colour).join('\n'));
await term('term-demo-2', 'Terminal: the claim checker on the real state chart',
  prompt(T.demo_cmd) + [...head, ...claims].map(colour).join('\n'));
await term('term-check', 'Terminal: the check that runs before every build',
  prompt(T.check_cmd) + T.check.split('\n').map(colour).join('\n') + `\n<span class="dim">exit code ${T.check_exit}</span>`);
if (!existsSync(SHOTS + 'gha.png') && T.gha) {
  await term('gha', 'Terminal: the latest CI run on main (gh run view)',
    prompt(T.gha_cmd) + T.gha.split('\n').map((l) => esc(l).replace(/^(✓.*)$/, '<span class="ok">$1</span>')).join('\n'));
}

const CODE = `body{background:#1e1e1e;color:#d4d4d4}
.bar{height:40px;background:#323232;color:#d4d4d4;font-size:17px;line-height:40px;padding:0 20px}
pre{margin:0;padding:20px 0;font-family:Consolas,"Cascadia Mono",monospace;font-size:20px;line-height:1.5}
.l{display:block;padding:0 28px}.l.hi{background:#264f78;color:#ffffff}.l.hi *{color:#ffffff}
.n{display:inline-block;width:3.2em;color:#a0a0a0;text-align:right;margin-right:1.2em}
.k{color:#c9a0dc}.c{color:#8fc27a}.s{color:#e0b090}`;
const hl = (src) => esc(src)
  .replace(/(&quot;&quot;&quot;.*|#.*)$/, '<span class="c">$1</span>')
  .replace(/('[^']*')/g, '<span class="s">$1</span>')
  .replace(/\b(def|return|if|or|is|None|const|module|exports)\b/g, '<span class="k">$1</span>');
for (const c of SPEC.code) {
  const lines = c.lines.map(([n, text]) =>
    `<span class="l${c.highlight.includes(n) ? ' hi' : ''}"><span class="n">${n}</span>${hl(text)}</span>`).join('');
  await render(cardPage, c.id, c.title, `<div class="bar">${esc(c.title)}</div><pre>${lines}</pre>`, CODE, SHOTS + c.id + '.png');
}
for (const c of SPEC.textcards) {
  if (c.fallback_for && existsSync(SHOTS + c.fallback_for + '.png')) continue;
  await textCard(c.fallback_for ?? c.id, c.kicker, c.title, c.body, c.src);
}

// Title and end cards (full frame, 1280x720 for the overlay page; scaled 2x for the zoom input).
const FULL = `body{background:${GREEN};color:#ffffff}
.c{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 96px}
h1{margin:0;font-size:96px;line-height:1.05}p{margin:18px 0 0;font-size:40px;line-height:1.3}
p.small{font-size:34px;margin-top:10px}`;
await render(cardPage, 'title', 'Curb Cut', `<div class="c"><h1>Curb Cut</h1><p>${esc(SPEC.title_sub)}</p></div>`, FULL, SHOTS + 'title.png');
await render(cardPage, 'end', 'Curb Cut', `<div class="c"><h1>Curb Cut</h1><p>${esc(SPEC.end[0])}</p><p class="small">${esc(SPEC.end[1])}</p></div>`, FULL, SHOTS + 'end.png');

// Lower-third captions (green band, as cards.mjs) and correction footnotes (dark, top of frame).
const CAP = `.band{position:absolute;left:0;right:0;bottom:56px;padding:16px 56px 18px;background:${GREEN};color:#ffffff;border-top:6px solid #ffffff}
.band p{margin:0;font-size:var(--fs);line-height:1.3;font-weight:600}`;
// Keep "6.1–17.2" and "(−33.2 to −19.7)" on one line.
const nowrapRanges = (h) => h.replace(/([−-]?\d[\d.,]*(?:–| to )[−-]?\d[\d.,]*\)?)/g, '<span style="white-space:nowrap">$1</span>');
for (const c of SPEC.captions) {
  const fs = c.text.length > 150 ? 25 : c.text.length > 95 ? 27 : 30;
  await render(overPage, c.id, 'Caption', `<div class="band" style="--fs:${fs}px"><p>${nowrapRanges(esc(c.text))}</p></div>`, CAP, OVER + c.id + '.png', true);
}
const COR = `.fn{position:absolute;left:40px;right:40px;top:22px;padding:9px 18px 10px;background:#1a1a1a;color:#ffffff;border-left:6px solid #ffd54f}
.fn p{margin:0;font-size:23px;line-height:1.35}`;
for (const c of SPEC.corrections) {
  const [lead, ...rest] = c.text.split(':');
  await render(overPage, c.id, 'Correction', `<div class="fn"><p><strong>${esc(lead)}:</strong>${esc(rest.join(':'))}</p></div>`, COR, OVER + c.id + '.png', true);
}

await browser.close();
writeFileSync(BUILD + '/shots-report.json', JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
process.exitCode = bad ? 1 : 0;
