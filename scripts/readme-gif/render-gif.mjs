// Render frames.json (from frames.py) into one PNG per GIF frame, with Playwright.
//   node render-gif.mjs <folder with frames.json, chart-*.html and pypi.png>
// pypi.png is a screenshot of https://pypi.org/project/disability-access-charts/ (see README.md).
import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const dir = process.argv[2];
const frames = JSON.parse(readFileSync(`${dir}/frames.json`, 'utf8'));
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const dataUri = (file) => `data:image/png;base64,${readFileSync(file).toString('base64')}`;
const css = `body{margin:0;width:1100px;height:660px;background:#0f1a14;font-family:'Segoe UI',Arial,sans-serif;display:flex;flex-direction:column}
.cap{background:#006b3f;color:#fff;padding:18px 28px;min-height:96px;box-sizing:border-box}
.step{font-size:18px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;opacity:.95}
.text{font-size:27px;line-height:1.3;margin-top:4px}
.term{flex:1;margin:18px 28px 24px;background:#1b1f1d;border:1px solid #3b4440;border-radius:10px;padding:18px 22px;overflow:hidden}
pre{margin:0;font-family:Consolas,'Cascadia Mono',monospace;font-size:20px;line-height:1.42;white-space:pre-wrap;word-break:break-word}
.code{color:#f2f2f2}.prompt{color:#7fd1a0}.out{color:#ffd88a;margin-top:14px}.label{color:#9fb3a9;font-size:15px;font-family:'Segoe UI',Arial;margin:12px 0 2px}
.shots{display:flex;gap:14px;margin-top:14px}.shots img{width:50%;border-radius:6px;border:1px solid #3b4440}
.web{flex:1;display:flex;justify-content:center;align-items:flex-start;padding:16px 28px 0;overflow:hidden}.web img{width:100%;border-radius:8px 8px 0 0;border:1px solid #3b4440}
.card{flex:1;display:flex;flex-direction:column;justify-content:center;padding:60px;color:#fff;background:#006b3f}
.card h1{font-size:54px;margin:0 0 12px}.card p{font-size:28px;margin:6px 0;line-height:1.35}.card code{font-family:Consolas,monospace;background:#004d2d;padding:2px 10px;border-radius:6px}`;

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1100, height: 660 } });

// Screenshots of the chart pages figure() wrote (the real rendered Plotly charts).
const shots = {};
const chartPage = await b.newPage({ viewport: { width: 760, height: 470 } });
for (const f of frames) {
  for (const html of f.images ?? []) {
    await chartPage.goto(pathToFileURL(`${dir}/${html}`).href);
    await chartPage.waitForSelector('.main-svg');
    await chartPage.waitForTimeout(500);
    const png = `${dir}/${html.replace('.html', '.png')}`;
    await chartPage.screenshot({ path: png });
    shots[html] = png;
  }
}

const pages = [];
// The GIF opens on the PyPI page (author, 2026-11-08), so there is no title card.
frames.forEach((f, i) => {
  const head = `<div class="cap"><div class="step">Step ${i + 1} of ${frames.length}</div><div class="text">${esc(f.caption)}</div></div>`;
  if (f.kind === 'pypi') {
    pages.push(`${head}<div class="web"><img alt="" src="${dataUri(`${dir}/pypi.png`)}"></div>`);
    return;
  }
  const lines = f.kind === 'shell'
    ? `<span class="prompt">$ </span>${esc(f.code)}`
    : (() => {
        // '>>> ' starts a top-level statement; '... ' continues one (open brackets, a block body).
        let depth = 0;
        return f.code.split('\n').filter((l) => l.trim()).map((l) => {
          const cont = depth > 0 || /^\s/.test(l);
          for (const ch of l.replace(/"[^"]*"/g, '').replace(/#.*$/, '')) depth += '([{'.includes(ch) ? 1 : ')]}'.includes(ch) ? -1 : 0;
          return `<span class="prompt">${cont ? '... ' : '&gt;&gt;&gt; '}</span>${esc(l)}`;
        }).join('\n');
      })();
  const out = f.output ? `<div class="label">Output</div><pre class="out">${esc(f.output)}</pre>` : '';
  const imgs = (f.images ?? []).length
    ? `<div class="label">The chart (left: light theme; right: dark theme)</div><div class="shots">${[...f.images].sort().reverse().map((h) => `<img alt="" src="${dataUri(shots[h])}">`).join('')}</div>`
    : '';
  pages.push(`${head}<div class="term"><pre class="code">${lines}</pre>${out}${imgs}</div>`);
});
pages.push(`<div class="card"><h1>Try it</h1><p><code>pip install disability-access-charts</code></p><p>pypi.org/project/disability-access-charts</p><p>Docs and source: github.com/batestguy/curb-cut · MIT licence. The same steps, as text, are in the README.</p></div>`);

mkdirSync(`${dir}/png`, { recursive: true });
for (const [i, body] of pages.entries()) {
  await p.setContent(`<!doctype html><html lang="en"><head><style>${css}</style></head><body>${body}</body></html>`);
  const over = await p.evaluate(() => { const t = document.querySelector('.term'); return t ? t.scrollHeight - t.clientHeight : 0; });
  if (over > 0) console.log('OVERFLOW frame', i, over);
  await p.screenshot({ path: `${dir}/png/f${String(i).padStart(2, '0')}.png` });
}
await b.close();
console.log('frames', pages.length);
