// Lower-third scene cards for act 5: transparent 1280x720 PNGs, site colours, axe-checked.
// Usage: node cards.mjs  -> ../cards/*.png
import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const DIR = fileURLToPath(new URL('.', import.meta.url));
const OUT = DIR + '../../data/sources/video/cards/';
const AXE = readFileSync(DIR + '../../site/node_modules/axe-core/axe.min.js', 'utf8');
export const CARDS = {
  's1-main': ['The main page, read by NVDA', 'Main heading and the national figure'],
  's2-chart': ['Every chart describes itself', "The state chart's description"],
  's3-lagos': ['Pick a state by keyboard', "One state's card"],
  's4-poverty': ['The poverty result, in one sentence', "The poverty page's main result"],
};
const html = (title, sub) => `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title>
<style>
  :root { --green: #006b3f; --ink: #ffffff; }
  html, body { margin: 0; width: 1280px; height: 720px; background: transparent; }
  .band { position: absolute; left: 0; right: 0; bottom: 56px; padding: 18px 56px 20px;
    background: var(--green); color: var(--ink); font-family: "Segoe UI", system-ui, sans-serif;
    border-top: 6px solid #ffffff; }
  h1 { margin: 0; font-size: 40px; font-weight: 700; line-height: 1.15; }
  p { margin: 6px 0 0; font-size: 26px; line-height: 1.3; }
</style></head><body><main><div class="band"><h1>${title}</h1><p>${sub}</p></div></main></body></html>`;

mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
let bad = 0;
for (const [id, [title, sub]] of Object.entries(CARDS)) {
  await p.setContent(html(title, sub));
  await p.addScriptTag({ content: AXE });
  const r = await p.evaluate(() => window.axe.run(document, { runOnly: ['color-contrast'] }));
  if (r.violations.length) { bad++; console.log(id, 'CONTRAST FAIL', JSON.stringify(r.violations[0].nodes[0].any[0].data)); }
  await p.screenshot({ path: `${OUT}${id}.png`, omitBackground: true });
  console.log(id, 'ok:', r.passes.length ? 'contrast passes' : 'no text checked');
}
await b.close();
process.exitCode = bad ? 1 : 0;
