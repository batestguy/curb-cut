// A Vite plugin for the sensitivity page (sensitivity.html, P6 item 11): at build time it fills
// the page's definitions and its <noscript> version (a static table at the default rate for
// each age group) from public/data/sensitivity.json, with the same code the page runs
// (src/sensitivity-model.js), and writes that static table's CSV and JSON to
// data/downloads/sensitivity/. Without the data file (no data built yet) the page says so.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  DEFAULT_SORT,
  csvText,
  definitionsHtml,
  fileBase,
  jsonText,
  sortRows,
  staticHtml,
  tableRows,
  toQuery,
} from '../src/sensitivity-model.js';
import { sizeText } from '../src/explorer-model.js';

const DEFINITIONS = '<!-- sensitivity:definitions -->';
const NOSCRIPT = '<!-- sensitivity:static -->';
const FOLDER = 'data/downloads/sensitivity';

/** The static downloads: {age: {csv: {path, text, body}, json: {...}}}. */
export function staticFiles(data, siteUrl) {
  const rate = data.rates.default;
  const out = {};
  for (const g of data.age_groups) {
    const rows = sortRows(tableRows(data, g.value, rate), DEFAULT_SORT);
    const page = `${siteUrl}sensitivity.html${toQuery({ rate, age: g.value, sort: DEFAULT_SORT })}`;
    const base = fileBase(rate, g.value);
    out[g.value] = Object.fromEntries(
      [
        ['csv', 'CSV', csvText(rows)],
        ['json', 'JSON', jsonText(rows, rate, g.value, data, page)],
      ].map(([ext, format, body]) => [
        ext,
        {
          path: `${FOLDER}/${base}.${ext}`,
          href: `./${FOLDER}/${base}.${ext}`,
          text: `${format}, ${sizeText(Buffer.byteLength(body))}`,
          body,
        },
      ]),
    );
  }
  return out;
}

export function fillPage(html, data, files) {
  if (!data) {
    return html
      .replace(DEFINITIONS, '<p>The definitions are built with the data; this build has none.</p>')
      .replace(NOSCRIPT, '<p>This build has no data.</p>');
  }
  return html
    // Function replacements, so a "$" in the data's wording is never read as a pattern.
    .replace(DEFINITIONS, () => definitionsHtml(data))
    .replace(NOSCRIPT, () => staticHtml(data, (age) => files[age]));
}

export default function sensitivityStatic({ root, siteUrl }) {
  const dataPath = resolve(root, 'public/data/sensitivity.json');
  let files = null;
  return {
    name: 'curb-cut-sensitivity-static',
    transformIndexHtml: {
      order: 'pre',
      handler(html, ctx) {
        if (!ctx.filename.endsWith('sensitivity.html')) return html;
        const data = existsSync(dataPath) ? JSON.parse(readFileSync(dataPath, 'utf8')) : null;
        files = data ? staticFiles(data, siteUrl) : null;
        return fillPage(html, data, files);
      },
    },
    generateBundle() {
      if (!files) return;
      for (const byFormat of Object.values(files)) {
        for (const f of Object.values(byFormat)) {
          this.emitFile({ type: 'asset', fileName: f.path, source: f.body });
        }
      }
    },
  };
}
