// Share images for the state pages: one 1200x630 PNG per state (Open Graph / Twitter card),
// made by screenshotting an HTML template in headless Chromium with Playwright, which is
// already a dev dependency. Runs before `vite build` (npm "prebuild"), so Vite copies the
// images from public/share/ into the site.
//
// The text is the page's own headline sentence, which is also the image's alt text
// (og:image:alt), from site/states/share-images.json (written by
// packages/transform/scripts/build_state_pages.py). Each image is checked before it is saved:
// axe's colour-contrast rule must pass and the text must fit inside the image.
//
// No state pages built yet (no share-images.json): nothing to do, and the build goes on.
import { existsSync } from 'node:fs';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import AxeBuilder from '@axe-core/playwright';
import { chromium } from '@playwright/test';

const site = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const list = resolve(site, 'states', 'share-images.json');
const outDir = resolve(site, 'public', 'share');
const WIDTH = 1200;
const HEIGHT = 630;

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

// Light theme only: text #1a1a1a (17.4:1) and #4d4d4d (8.4:1), the name in --green #006b3f
// (6.6:1), all on white; the flag band is decorative.
function template({ state, sentence }) {
  return `<!doctype html>
<html lang="en-NG"><head><meta charset="utf-8"><title>${escapeHtml(state)}</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; overflow: hidden; }
  body { background: #ffffff; color: #1a1a1a; font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", Arial, sans-serif; display: flex; flex-direction: column; }
  .band { height: 18px; flex: none; background: linear-gradient(to right, #008751 0 33.333%, #ffffff 33.333% 66.667%, #008751 66.667% 100%); border-bottom: 1px solid #767676; }
  main { flex: 1; padding: 40px 64px 36px; display: flex; flex-direction: column; }
  .brand { margin: 0; font-size: 30px; font-weight: 700; color: #006b3f; }
  h1 { margin: 10px 0 18px; font-size: 58px; line-height: 1.1; }
  .sentence { margin: 0; font-size: 31px; line-height: 1.35; }
  .foot { margin: auto 0 0; padding-top: 16px; font-size: 22px; color: #4d4d4d; }
</style></head>
<body><div class="band"></div><main>
  <p class="brand">Curb Cut</p>
  <h1>${escapeHtml(state)}</h1>
  <p class="sentence">${escapeHtml(sentence)}</p>
  <p class="foot">Nigeria DHS 2024 survey, Washington Group cut-off · batestguy.github.io/curb-cut</p>
</main></body></html>`;
}

async function main() {
  if (!existsSync(list)) {
    console.log('No state pages built (site/states/share-images.json is missing): no share images made.');
    return;
  }
  const pages = JSON.parse(await readFile(list, 'utf8'));
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT }, colorScheme: 'light' });
    const page = await context.newPage();
    for (const entry of pages) {
      await page.setContent(template(entry));
      const fits = await page.evaluate(() => {
        const main = document.querySelector('main');
        return main.scrollHeight <= main.clientHeight && document.body.scrollWidth <= window.innerWidth;
      });
      if (!fits) throw new Error(`the share image text for ${entry.state} does not fit in ${WIDTH}x${HEIGHT}`);
      const contrast = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
      if (contrast.violations.length > 0) {
        throw new Error(`the share image for ${entry.state} fails colour contrast: ${JSON.stringify(contrast.violations)}`);
      }
      await page.screenshot({ path: resolve(outDir, `${entry.slug}.png`), type: 'png' });
    }
  } finally {
    await browser.close();
  }
  console.log(`made ${pages.length} share images in public/share/`);
}

main().catch((error) => {
  console.error(`Share images failed: ${error.message}`);
  process.exit(1);
});
