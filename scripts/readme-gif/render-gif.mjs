import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
const dir = process.argv[2];
const frames = JSON.parse(readFileSync(`${dir}/frames.json`, 'utf8'));
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const css = `body{margin:0;width:1100px;height:660px;background:#0f1a14;font-family:'Segoe UI',Arial,sans-serif;display:flex;flex-direction:column}
.cap{background:#006b3f;color:#fff;padding:18px 28px;min-height:96px;box-sizing:border-box}
.step{font-size:18px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;opacity:.95}
.text{font-size:27px;line-height:1.3;margin-top:4px}
.term{flex:1;margin:18px 28px 24px;background:#1b1f1d;border:1px solid #3b4440;border-radius:10px;padding:18px 22px;overflow:hidden}
pre{margin:0;font-family:Consolas,'Cascadia Mono',monospace;font-size:20px;line-height:1.42;white-space:pre-wrap;word-break:break-word}
.code{color:#f2f2f2}.prompt{color:#7fd1a0}.out{color:#ffd88a;margin-top:14px}.label{color:#9fb3a9;font-size:15px;font-family:'Segoe UI',Arial;margin:12px 0 2px}
.card{flex:1;display:flex;flex-direction:column;justify-content:center;padding:60px;color:#fff;background:#006b3f}
.card h1{font-size:54px;margin:0 0 12px}.card p{font-size:28px;margin:6px 0;line-height:1.35}.card code{font-family:Consolas,monospace;background:#004d2d;padding:2px 10px;border-radius:6px}`;
const pages = [];
pages.push(`<div class="card"><h1>disability-access-charts</h1><p>Charts that check their own words.</p><p>A tour in ${frames.length} steps: install it, build a chart, and watch it reject a claim the data can't support.</p></div>`);
frames.forEach((f, i) => {
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
  pages.push(`<div class="cap"><div class="step">Step ${i + 1} of ${frames.length}</div><div class="text">${esc(f.caption)}</div></div>
<div class="term"><pre class="code">${lines}</pre>${out}</div>`);
});
pages.push(`<div class="card"><h1>Try it</h1><p><code>pip install disability-access-charts</code></p><p>Docs and source: github.com/batestguy/curb-cut</p><p>MIT licence. The same steps, as text, are in the README.</p></div>`);
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1100, height: 660 } });
mkdirSync(`${dir}/png`, { recursive: true });
for (const [i, body] of pages.entries()) {
  await p.setContent(`<!doctype html><html lang="en"><head><style>${css}</style></head><body>${body}</body></html>`);
  const over = await p.evaluate(() => { const t = document.querySelector('.term'); return t ? t.scrollHeight - t.clientHeight : 0; });
  if (over > 0) console.log('OVERFLOW frame', i, over);
  await p.screenshot({ path: `${dir}/png/f${String(i).padStart(2, '0')}.png` });
}
await b.close();
console.log('frames', pages.length);
