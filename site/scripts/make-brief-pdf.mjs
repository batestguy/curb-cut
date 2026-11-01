// The P5 policy brief as a PDF: prints the committed pandoc HTML
// (docs/brief/p5-poverty-brief.html, written by packages/transform/scripts/build_brief.py
// --html) to A4 with Playwright's Chromium, which the build already uses for the share
// images. Runs before `vite build` (npm "prebuild"), so Vite copies the PDF from
// public/downloads/ into the site, where site/poverty.html links it. A tagged PDF (headings,
// lists and links carry structure for screen readers) with an outline.
//
// The PDF is a build artefact (git-ignored): CI's guard refuses committed PDFs.
import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from '@playwright/test';

const site = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(site, '..', 'docs', 'brief', 'p5-poverty-brief.html');
const outDir = resolve(site, 'public', 'downloads');
const out = resolve(outDir, 'p5-poverty-brief.pdf');

async function main() {
  if (!existsSync(source)) {
    console.log('No brief HTML (docs/brief/p5-poverty-brief.html): no PDF made.');
    return;
  }
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(source).href);
    await page.emulateMedia({ media: 'print', colorScheme: 'light' });
    await page.pdf({
      path: out,
      format: 'A4',
      preferCSSPageSize: true,
      printBackground: true,
      tagged: true,
      outline: true,
    });
  } finally {
    await browser.close();
  }
  console.log(`Wrote ${out}`);
}

await main();
