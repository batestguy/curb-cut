// The P5 poverty page (site/poverty.html, built by
// packages/transform/scripts/build_poverty_page.py from data/poverty.json): plain HTML with no
// script. Every number on it is either a span naming its path in poverty.json (checked here
// against the exported file), a cell of a chart document's own table (checked against the
// chart JSON, which is checked against poverty.json), or one of a short list of fixed
// constants from the pre-registration.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// The pre-registration's wording rules (section 7): never these phrases.
const FORBIDDEN = [/effect of disability/i, /impact of/i, /\bcauses\b/i, /caused by/i, /event stud(y|ies)/i];

// Numbers that are not data: years and survey rounds, ages, the 95% level, the 2-point
// smallest difference, k = 26%, the 0.01/0.99 clip, the 30-unit disclosure rule, "1 in 100",
// "95 in 100", "out of 100", 7 days, 5 folds.
const CONSTANTS = new Set([
  '2018', '19', '2021', '2022', '2023', '24', '2026',
  '1', '2', '5', '7', '15', '26', '30', '95', '100', '0.01', '0.99',
  // Citations: MPI 2021 version 1.0, GHS-Panel Waves 4 and 5.
  '1.0', '4',
  // The propensity quantile rows (1%, 5%, 25%, ... 99% of households below).
  '25', '50', '75', '99',
]);

function fixed(value, decimals) {
  let text = value.toFixed(decimals);
  if (Number(text) === 0) text = text.replace(/^-/, '');
  return text;
}

function format(value, { factor, decimals, format: kind }) {
  if (kind === 'text') return String(value);
  if (kind === 'int') return Math.round(value).toLocaleString('en-US');
  if (kind === 'p') return value < 0.0001 ? '<0.0001' : fixed(value, 4);
  return fixed(Number(factor) * value, Number(decimals));
}

function lookup(data, key) {
  return key.split('.').reduce((node, part) => node[part], data);
}

async function open(page) {
  await page.goto('poverty.html');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Disability and poverty in Nigeria');
}

const VIEWS = [
  ['light', null],
  ['dark', null],
  ['light', 320],
  ['dark', 320],
];

for (const [colorScheme, width] of VIEWS) {
  const view = width ? `${colorScheme}, ${width}px` : colorScheme;
  test(`poverty page: axe finds no WCAG A/AA violations (${view})`, async ({ page }) => {
    if (width) await page.setViewportSize({ width, height: 800 });
    await page.emulateMedia({ colorScheme });
    await open(page);
    for (const summary of await page.locator('details summary').all()) await summary.click();
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('poverty page: every number span equals the exported data', async ({ page, request }) => {
  const data = await (await request.get('data/poverty.json')).json();
  await open(page);
  const spans = await page.locator('span.n').evaluateAll((els) =>
    els.map((el) => ({ text: el.textContent, ...el.dataset })),
  );
  expect(spans.length).toBeGreaterThan(150);
  for (const span of spans) {
    const value = lookup(data, span.key);
    expect(value, span.key).not.toBeUndefined();
    expect(value, span.key).not.toBeNull();
    expect(span.text, span.key).toBe(format(value, span));
  }
  // The headline numbers, by name, so a page that drops them cannot pass.
  const keys = new Set(spans.map((s) => s.key));
  for (const key of [
    'estimates.primary.estimate',
    'estimates.primary.ci_low',
    'estimates.primary.ci_high',
    'estimates.primary.mu0',
    'derived.primary_implied',
    'estimates.overlap_population.estimate',
    'estimates.overlap_population.ci_low',
    'estimates.overlap_population.ci_high',
    'summary.mpi.outside_weighted_share.value',
    'estimates.s5_unasked_severe.estimate',
    'summary.mpi.osf_url.value_text',
    'summary.mpi.registered_utc.value_text',
    'estimates.ghs_dwork.estimate',
    'estimates.ghs_dlog_consumption.estimate',
  ]) {
    expect(keys.has(key), key).toBe(true);
  }
  await expect(page.locator('#headline .n').first()).toHaveAttribute('data-key', 'estimates.primary.estimate');
});

test('poverty page: no other number appears outside the data and the chart tables', async ({ page }) => {
  await open(page);
  const text = await page.locator('main').evaluate((main) => {
    const copy = main.cloneNode(true);
    // .table-download: the file sizes in the download links ("CSV, 2 KB"), checked against
    // the files in downloads.spec.js.
    copy
      .querySelectorAll('span.n, svg, .chart-table, .chart-desc, .chart-title, code, .table-download')
      .forEach((el) => el.remove());
    return copy.textContent;
  });
  const tokens = text.match(/(?<![A-Za-z0-9._-])-?\d+(?:,\d{3})*(?:\.\d+)?/g) ?? [];
  const stray = [...new Set(tokens.filter((t) => !CONSTANTS.has(t)))];
  expect(stray).toEqual([]);
});

test('poverty page: the charts are library documents whose tables match poverty.json', async ({ page, request }) => {
  const data = await (await request.get('data/poverty.json')).json();
  const ids = {
    poverty_headline: ['primary', 'overlap_population', 'survey_lpm', 's2_broad', 's3_head'],
    poverty_dimensions: ['s4_health', 's4_education', 's4_living_standards', 's4_work_and_shocks'],
  };
  await open(page);
  for (const [chart, estimateIds] of Object.entries(ids)) {
    const doc = await (await request.get(`data/charts/${chart}.json`)).json();
    expect(doc.audit.passed).toBe(true);
    expect(doc.meta.generator).toBe('disability_access_charts.plots.dot');
    expect(doc.findings).toBeUndefined();
    const series = doc.data.series[0];
    estimateIds.forEach((id, i) => {
      const e = data.estimates[id];
      expect(series.values[i]).toBeCloseTo(100 * e.estimate, 9);
      expect(series.lower[i]).toBeCloseTo(100 * e.ci_low, 9);
      expect(series.upper[i]).toBeCloseTo(100 * e.ci_high, 9);
    });
    const table = page.locator(`.chart-table[data-chart="${chart}"] table`);
    const rows = await table.locator('tbody tr').evaluateAll((trs) =>
      trs.map((tr) => [...tr.children].map((c) => c.textContent)),
    );
    expect(rows).toEqual(
      doc.table.rows.map((row) => row.map((v, j) => (j === 0 ? v : fixed(v, doc.table.columns[j].decimals)))),
    );
    // The figure is one image named by the library's alt-text.
    const holder = page.locator(`.chart-table[data-chart="${chart}"]`).locator('xpath=preceding-sibling::figure[1]').locator('.dot-holder');
    await expect(holder).toHaveAttribute('role', 'img');
    await expect(holder).toHaveAccessibleName(doc.alt_text);
  }
});

test('poverty page: wording follows the pre-registration', async ({ page }) => {
  await open(page);
  const text = await page.locator('body').innerText();
  for (const phrase of FORBIDDEN) expect(text).not.toMatch(phrase);
  for (const match of text.matchAll(/causal effects?/gi)) {
    expect(text.slice(Math.max(0, match.index - 6), match.index).toLowerCase()).toBe('not a ');
  }
  const flat = text.replace(/\s+/g, ' ');
  expect(flat).toContain('An adjusted association, not a causal effect');
  expect(flat).toContain('Poverty can come first');
  expect(flat).toContain('Some shared factors were not measured');
  expect(flat).toContain("MPI's own disability questions (not the Washington Group's DISABILITY3 measure)");
  expect(flat).toContain('Exploratory, not confirmatory');
  expect(flat).toContain('it has not yet been tested by a regular screen-reader user');
  await expect(page.locator('#headline')).toContainText('percentage points');
  await expect(page.getByRole('link', { name: 'report a problem on GitHub' })).toBeVisible();
  await expect(page.locator('script')).toHaveCount(0);
});

test('poverty page: keyboard reaches the skip link, every table region and every details', async ({ page }) => {
  await open(page);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  // Tab from <main> to the end of <main>, recording which stops were reached. First with every
  // <details> closed (their tables are hidden), then with every one opened by the keyboard.
  async function tabThrough() {
    await page.locator('main').focus();
    const reached = new Set();
    for (let i = 0; i < 300; i += 1) {
      await page.keyboard.press('Tab');
      const info = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || !el.closest('main')) return { inMain: false };
        const all = [...document.querySelectorAll('main .table-wrap, main details > summary')];
        return { inMain: true, index: all.indexOf(el) };
      });
      if (!info.inMain) break;
      if (info.index >= 0) reached.add(info.index);
    }
    return reached;
  }
  const closed = await page
    .locator('main .table-wrap, main details > summary')
    .evaluateAll((els) => els.filter((el) => el.tagName === 'SUMMARY' || !el.closest('details')).length);
  expect((await tabThrough()).size).toBe(closed);
  const summaries = page.locator('main details > summary');
  for (let i = 0; i < (await summaries.count()); i += 1) {
    await summaries.nth(i).focus();
    await page.keyboard.press('Enter');
  }
  const all = await page.locator('main .table-wrap, main details > summary').count();
  expect((await tabThrough()).size).toBe(all);
  for (const summary of await summaries.all()) {
    await summary.focus();
    await page.keyboard.press('Enter');
  }
  // A details opens from the keyboard, and its table is then reachable.
  const summary = page.locator('main details > summary').first();
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('main details').first()).toHaveAttribute('open', '');
  await page.keyboard.press('Tab');
  await expect(page.locator('main details').first().locator('.table-wrap')).toBeFocused();
});

test('poverty page: no sideways scrolling at 320px, with every details open', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await open(page);
  for (const summary of await page.locator('details summary').all()) await summary.click();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test('poverty page: headings in order, tables with captions and scoped headers', async ({ page }) => {
  await open(page);
  const levels = await page.locator('main h1, main h2, main h3, main h4').evaluateAll((hs) => hs.map((h) => Number(h.tagName[1])));
  expect(levels[0]).toBe(1);
  for (let i = 1; i < levels.length; i += 1) expect(levels[i] - levels[i - 1]).toBeLessThanOrEqual(1);
  const tables = page.locator('main table');
  const n = await tables.count();
  expect(n).toBeGreaterThan(8);
  for (let i = 0; i < n; i += 1) {
    await expect(tables.nth(i).locator('caption')).toHaveCount(1);
    const unscoped = await tables.nth(i).locator('th:not([scope])').count();
    expect(unscoped).toBe(0);
  }
});

test('the policy brief PDF is served, at most two pages, and linked', async ({ page, request }) => {
  await open(page);
  const link = page.getByRole('link', { name: /policy brief \(PDF\)/ });
  await expect(link).toHaveAttribute('href', './downloads/p5-poverty-brief.pdf');
  const response = await request.get('downloads/p5-poverty-brief.pdf');
  expect(response.status()).toBe(200);
  const body = await response.body();
  expect(body.subarray(0, 5).toString()).toBe('%PDF-');
  const pages = body.toString('latin1').match(/\/Type\s*\/Page(?!s)/g) ?? [];
  expect(pages.length).toBeGreaterThan(0);
  expect(pages.length).toBeLessThanOrEqual(2);
});

test('the main page and the methodology page link the poverty page', async ({ page }) => {
  for (const path of ['./', 'methodology.html']) {
    await page.goto(path);
    const nav = page.getByRole('navigation', { name: 'Site' });
    await expect(nav.getByRole('link', { name: 'Disability and poverty' })).toHaveAttribute('href', './poverty.html');
  }
  await page.goto('methodology.html');
  await page.locator('#poverty-heading + p').getByRole('link', { name: 'disability and poverty page' }).click();
  await expect(page).toHaveURL(/poverty\.html$/);
});

test('poverty page: nothing comes from another origin', async ({ page, baseURL }) => {
  const origin = new URL(baseURL).origin;
  const requests = [];
  page.on('request', (r) => requests.push(r.url()));
  await open(page);
  expect(requests.filter((u) => !u.startsWith(origin) && !u.startsWith('data:'))).toEqual([]);
});
