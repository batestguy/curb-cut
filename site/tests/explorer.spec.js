// The data explorer (site/explorer.html, src/explorer.js): a filterable, sortable table of the
// DHS 2024 cells, queried in the browser with DuckDB-WASM from the two public Parquet files.
//
// The real data have no suppressed cell, so one test serves the fixture warehouse's exports
// instead (tests/fixtures/*.parquet: `uv run python packages/transform/scripts/export_marts.py
// --db data/fixtures.duckdb --out-dir <dir>`, after the fixture dbt build in CLAUDE.md), which
// have suppressed cells of both kinds and a state with no data.
import { fileURLToPath } from 'node:url';
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
// The first DuckDB-WASM start can take a while on a busy machine.
const LOAD = { timeout: 45_000 };
const FIXTURES = fileURLToPath(new URL('./fixtures/', import.meta.url));

const status = (page) => page.locator('#explorer-status');
const table = (page) => page.locator('#results-data');

async function ready(page, path = 'explorer.html') {
  await page.goto(path);
  await expect(page.locator('#f-show')).toBeEnabled(LOAD);
}

// A percentage as the table shows it: 1 decimal, "<0.1" above 0 but under 0.05.
const pct = (v) => (v > 0 && v < 0.05 ? '<0.1' : v.toFixed(1));

async function shown(page, path) {
  await page.goto(path);
  // A link with invalid choices puts its message first.
  await expect(status(page)).toHaveText(/(^|\. )Showing \d+ rows?: /, LOAD);
  await expect(table(page)).toBeVisible();
}

/** The table as text: one array per body row (the header row's labels first). */
async function tableText(page) {
  return table(page).evaluate((t) =>
    [...t.rows].map((tr) => [...tr.cells].map((c) => c.textContent.replace(/[▲▼↕]/g, '').trim())),
  );
}

/** The text of a download link's file (a blob: URL made in the page). */
async function download(page, format) {
  const href = await page.locator('#results-downloads a', { hasText: format }).getAttribute('href');
  return page.evaluate(async (url) => (await fetch(url)).text(), href);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {
      row.push(field);
      field = '';
    } else if (ch === '\r' && text[i + 1] === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      i += 1;
    } else field += ch;
  }
  return rows;
}

for (const colorScheme of ['light', 'dark']) {
  for (const width of [null, 320]) {
    const view = width ? `${colorScheme}, ${width}px` : colorScheme;
    test(`explorer: axe finds no WCAG A/AA violations before and after showing (${view})`, async ({ page }) => {
      if (width) await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ colorScheme });
      await ready(page);
      await expect(page.locator('#results')).toBeHidden();
      let results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
      await page.locator('#f-show').click();
      await expect(table(page)).toBeVisible();
      await expect(page.locator('#explorer-chart svg').first()).toBeVisible(LOAD);
      results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}

test('explorer: the choices come from the data, labelled in words', async ({ page }) => {
  await ready(page);
  const labels = (id) => page.locator(`#${id} option`).allTextContents();
  expect(await labels('f-level')).toEqual(['States', 'Geopolitical zones', 'Nigeria as a whole']);
  const measures = await labels('f-measure');
  expect(measures).toHaveLength(7);
  expect(measures[0]).toBe('Disability: a lot of difficulty or cannot do at all in at least one of six activities');
  expect(measures).toContain('Seeing: a lot of difficulty or cannot do at all');
  expect(await labels('f-age')).toEqual(['Adults 18 and over', 'Children 5 to 17']);
  expect(await labels('f-sex')).toEqual(['Both sexes', 'Female', 'Male']);
  const places = await labels('f-place');
  expect(places[0]).toBe('All 37 states');
  expect(places).toHaveLength(38);
  // Each level offers what its file holds: the national level adds the four levels of difficulty.
  await page.locator('#f-level').selectOption('national');
  expect(await labels('f-measure')).toHaveLength(31);
  expect(await labels('f-measure')).toContain('Seeing: cannot do at all');
  expect(await labels('f-place')).toEqual(['Nigeria']);
  await page.locator('#f-level').selectOption('zone');
  expect(await labels('f-place')).toEqual([
    'All 6 zones', 'North Central', 'North East', 'North West', 'South East', 'South South', 'South West',
  ]);
  // Nothing was queried while choosing: no results yet.
  await expect(page.locator('#results')).toBeHidden();
});

test('explorer: keyboard only, in Tab order: choose, Show figures, then sort', async ({ page }) => {
  await ready(page);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  // Every stop before the form, in order: site name, seven nav links, the intro's link.
  const before = await page.evaluate(() =>
    [...document.querySelectorAll('header a, main > p a')].map((a) => a.textContent.trim()),
  );
  expect(before).toHaveLength(9);
  for (const name of before) {
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement.textContent.trim())).toBe(name);
  }
  // The form, in order.
  for (const id of ['f-level', 'f-measure', 'f-age', 'f-sex', 'f-place']) {
    await page.keyboard.press('Tab');
    await expect(page.locator(`#${id}`)).toBeFocused();
  }
  await page.keyboard.press('Tab');
  await expect(page.locator('#f-show')).toBeFocused();

  // Choose by typing on the closed selects, as a keyboard user would.
  await page.locator('#f-age').focus();
  await page.keyboard.type('Children');
  await expect(page.locator('#f-age')).toHaveValue('5-17');
  await page.keyboard.press('Tab');
  await page.keyboard.type('Female');
  await expect(page.locator('#f-sex')).toHaveValue('female');
  await page.keyboard.press('Tab');
  await page.keyboard.type('Kano');
  await expect(page.locator('#f-place')).toHaveValue('Kano');
  await expect(page.locator('#results')).toBeHidden();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');

  // Focus moves to the results heading; the live region says what is shown.
  await expect(page.locator('#results-heading')).toBeFocused();
  await expect(status(page)).toHaveText(
    'Showing 1 row: Disability: a lot of difficulty or cannot do at all in at least one of six activities. Girls 5–17, Kano.',
  );
  expect(new URL(page.url()).search).toBe('?level=state&measure=disability3&age=5-17&sex=female&place=Kano');

  // Tab on to the sort buttons (the caption is a stop only when the table overflows).
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'State' })).toBeFocused();
  await page.keyboard.press('Tab');
  const estimate = page.getByRole('button', { name: 'Estimate (%)' });
  await expect(estimate).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(estimate).toBeFocused();
  await expect(page.locator('th', { has: estimate })).toHaveAttribute('aria-sort', 'ascending');
  await expect(page.locator('th[aria-sort]')).toHaveCount(1);
  await expect(status(page)).toHaveText('Sorted by Estimate (%), lowest first.');
  await page.keyboard.press('Space');
  await expect(page.locator('th', { has: estimate })).toHaveAttribute('aria-sort', 'descending');
  await expect(status(page)).toHaveText('Sorted by Estimate (%), highest first.');
  expect(new URL(page.url()).searchParams.get('sort')).toBe('estimate-desc');
  // After the seven sort buttons: Kano's page, the two downloads, the dictionary's links.
  for (let i = 0; i < 6; i += 1) await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Kano' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#results-downloads a').first()).toBeFocused();
});

test('explorer: sorting by keyboard reorders all 37 states', async ({ page }) => {
  await shown(page, 'explorer.html?level=state&measure=disability3&age=18%2B&sex=all');
  expect(await page.locator('#results-data tbody tr').count()).toBe(37);
  await page.getByRole('button', { name: 'Estimate (%)' }).focus();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  const values = await page.locator('#results-data tbody tr td:nth-child(2)').allTextContents();
  const numbers = values.map(Number);
  expect([...numbers].sort((a, b) => b - a)).toEqual(numbers);
  await page.getByRole('button', { name: 'State' }).press('Enter');
  await expect(page.locator('th', { has: page.getByRole('button', { name: 'State' }) })).toHaveAttribute('aria-sort', 'ascending');
  await page.getByRole('button', { name: 'State' }).press('Enter');
  const names = await page.locator('#results-data tbody th').allTextContents();
  expect(names[0]).toBe('Zamfara');
  expect(names.at(-1)).toBe('Abia');
});

test('explorer: one polite live region, and the view round-trips through the address', async ({ page }) => {
  await ready(page);
  const live = await page.locator('[role="status"], [aria-live]').evaluateAll((els) => els.map((e) => e.id));
  expect(live).toEqual(['explorer-status']);
  await expect(status(page)).toHaveAttribute('aria-live', 'polite');

  await page.locator('#f-level').selectOption('zone');
  await page.locator('#f-measure').selectOption('walking_3plus');
  await page.locator('#f-sex').selectOption('male');
  await page.locator('#f-show').click();
  await expect(status(page)).toHaveText(/^Showing 6 rows: Walking or climbing steps: .*Men 18\+, each geopolitical zone\.$/);
  const first = page.url();
  expect(new URL(first).search).toBe('?level=zone&measure=walking_3plus&age=18%2B&sex=male');

  await page.locator('#f-level').selectOption('national');
  await page.locator('#f-show').click();
  await expect(status(page)).toHaveText(/^Showing 1 row: .*Nigeria\.$/);
  await expect(page.locator('#results-data tbody th')).toHaveText('Nigeria');
  await expect(page.locator('#chart-note')).toHaveText(/^No chart: Nigeria as a whole has one figure/);
  await expect(page.locator('#explorer-chart-figure')).toBeHidden();

  // Back: the zone view again, in the form and the table.
  await page.goBack();
  await expect(status(page)).toHaveText(/^Showing 6 rows: /);
  await expect(page.locator('#f-level')).toHaveValue('zone');
  await expect(page.locator('#f-measure')).toHaveValue('walking_3plus');
  await expect(page.locator('#f-sex')).toHaveValue('male');

  // A fresh visit to the same address shows the same view.
  const rows = await tableText(page);
  await page.goto(first);
  await expect(status(page)).toHaveText(/^Showing 6 rows: /, LOAD);
  expect(await tableText(page)).toEqual(rows);
  await expect(page.locator('#url-message')).toBeHidden();
});

test('explorer: an address with invalid values falls back to the defaults, visibly', async ({ page }) => {
  await shown(page, 'explorer.html?level=state&measure=happiness&age=99&sex=all&place=Atlantis&sort=colour-up');
  const message = page.locator('#url-message');
  await expect(message).toBeVisible();
  await expect(message).toContainText('measure “happiness” is not in the data');
  await expect(message).toContainText('place “Atlantis”');
  await expect(message).toContainText('The defaults are shown instead.');
  await expect(page.locator('#f-measure')).toHaveValue('disability3');
  await expect(page.locator('#f-age')).toHaveValue('18+');
  await expect(page.locator('#f-place')).toHaveValue('');
  // The live region says it too, before the result.
  await expect(status(page)).toHaveText(
    /^This link's choices were not all valid: .*The defaults are shown instead\. Showing 37 rows: Disability: .*Adults 18\+, each state\.$/,
  );
  expect(new URL(page.url()).search).toBe('?level=state&measure=disability3&age=18%2B&sex=all');
});

test('explorer: a choice reset by an earlier one is announced, and focus stays put', async ({ page }) => {
  await shown(page, 'explorer.html?level=national&measure=seeing_level_1&age=18%2B&sex=all');
  const level = page.locator('#f-level');
  await level.focus();
  await level.selectOption('state');
  await expect(level).toBeFocused();
  await expect(page.locator('#f-measure')).toHaveValue('disability3');
  await expect(status(page)).toHaveText(
    'Measure reset to Disability: a lot of difficulty or cannot do at all in at least one of six activities: the previous choice is not available for States with the choices above it.',
  );
  await page.locator('#f-place').selectOption('Kano');
  await level.selectOption('zone');
  await expect(status(page)).toHaveText(/^State or zone reset to All 6 zones: .* for Geopolitical zones /);
  // A change that keeps every later choice says nothing new.
  await page.locator('#f-sex').selectOption('male');
  await expect(status(page)).toHaveText(/^State or zone reset/);
});

test('explorer: values above 0 but under 0.05% read "<0.1", as on the state pages', async ({ page }) => {
  await shown(page, 'explorer.html?level=state&measure=cognition_3plus&age=18%2B&sex=all&place=Akwa+Ibom');
  const row = (await tableText(page))[1];
  const csv = parseCsv(await download(page, 'CSV'))[1];
  // Akwa Ibom's lower bound is 0.0257%: the table says "<0.1", the file keeps the value.
  expect(Number(csv[2])).toBeGreaterThan(0);
  expect(Number(csv[2])).toBeLessThan(0.05);
  expect(row[2]).toBe('<0.1');
  expect(row[1]).toBe(pct(Number(csv[1])));
  await shown(page, 'explorer.html?level=state&measure=cognition_3plus&age=18%2B&sex=all');
  const zeros = (await tableText(page)).slice(1).filter((r) => r[1] === '0.0');
  for (const r of zeros) expect(r[0]).toBeTruthy(); // exactly 0 stays "0.0"
});

test('explorer: a one-place view gives the chart\'s own table of every place', async ({ page, request }) => {
  await shown(page, 'explorer.html?level=state&measure=disability3&age=18%2B&sex=all&place=Imo');
  expect((await tableText(page)).length).toBe(2);
  const details = page.locator('#chart-data');
  await expect(details).toBeVisible(LOAD);
  const doc = await (await request.get('data/charts/explorer/state-disability3-18plus-all.json')).json();
  const summary = details.locator('summary');
  await expect(summary).toHaveText(`Chart data: all ${doc.data.categories.length} states in the chart`);
  await expect(page.locator('#chart-note')).toContainText('under "Chart data" after the chart');
  // By keyboard: the summary opens it; the table has every place the chart draws.
  await summary.focus();
  await page.keyboard.press('Enter');
  const table = details.locator('table');
  await expect(table).toBeVisible();
  await expect(table.locator('caption')).toHaveText(doc.table.caption);
  await expect(table.locator('tbody tr')).toHaveCount(doc.data.categories.length);
  await expect(table.locator('tbody th').first()).toHaveText(doc.data.categories[0]);
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations).toEqual([]);
  // At 320 px its caption is the Tab stop for the scrolling table, and the page does not scroll.
  await page.setViewportSize({ width: 320, height: 800 });
  await expect(table.locator('caption')).toHaveAttribute('tabindex', '0');
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
  ).toBeLessThanOrEqual(0);
  // A view of every state: the page's table is the chart's, so no second one.
  await page.goto('explorer.html?level=state&measure=disability3&age=18%2B&sex=all');
  await expect(page.locator('#explorer-chart svg').first()).toBeVisible(LOAD);
  await expect(details).toBeHidden();
  await expect(details.locator('table')).toHaveCount(0);
});

test('explorer: a quick second Show leaves only the newer view and its chart', async ({ page, request }) => {
  await ready(page);
  await page.locator('#f-level').selectOption('zone');
  await page.locator('#f-show').click();
  await page.locator('#f-level').selectOption('state');
  await page.locator('#f-place').selectOption('Kano');
  await page.locator('#f-show').click();
  await expect(status(page)).toHaveText(/^Showing 1 row: .*Kano\.$/, LOAD);
  const doc = await (await request.get('data/charts/explorer/state-disability3-18plus-all.json')).json();
  await expect(page.locator('#explorer-chart-title')).toHaveText(doc.title, LOAD);
  await page.waitForTimeout(1500);
  await expect(page.locator('#explorer-chart-title')).toHaveText(doc.title);
  await expect(page.locator('#explorer-chart')).toHaveAccessibleName(doc.alt_text);
  await expect(page.locator('#results-data tbody tr')).toHaveCount(1);
});

test('explorer: suppressed and no-data cells show words, never a number (fixture data)', async ({ page }) => {
  for (const file of ['dhs2024_state_prevalence.parquet', 'dhs2024_national_zone.parquet']) {
    await page.route(`**/data/${file}`, (route) => route.fulfill({ path: `${FIXTURES}${file}` }));
  }
  // The real chart would not match the fixture rows.
  await page.route('**/data/charts/explorer/**', (route) => route.abort());
  await shown(page, 'explorer.html?level=state&measure=disability3&age=5-17&sex=all');
  const rows = await tableText(page);
  const byPlace = new Map(rows.slice(1).map((r) => [r[0], r]));
  expect(byPlace.get('Abia')).toEqual([
    'Abia', 'Suppressed (fewer than 30 respondents)', 'Suppressed', 'Fewer than 30 respondents (disclosure rule)', '',
  ]);
  expect(byPlace.get('Adamawa').slice(0, 3)).toEqual([
    'Adamawa', 'Suppressed (withheld to protect a neighbouring small cell)', 'Suppressed',
  ]);
  expect(byPlace.get('Zamfara')).toEqual(['Zamfara', 'No data', 'No data', '', '']);
  const hidden = rows.slice(1).filter((r) => r[1].startsWith('Suppressed') || r[1] === 'No data');
  expect(hidden.length).toBeGreaterThan(2);
  // No figure anywhere in those rows (the words' own "30" aside).
  const figures = (row) => row.join(' ').replaceAll('fewer than 30 respondents', '').replaceAll('Fewer than 30 respondents', '');
  for (const row of hidden) expect(figures(row), row[0]).not.toMatch(/\d/);
  // The downloads keep the words and leave the figures empty.
  const csv = parseCsv(await download(page, 'CSV'));
  for (const row of csv.slice(1).filter((r) => r[1].startsWith('Suppressed') || r[1] === 'No data')) {
    expect(figures(row), row[0]).not.toMatch(/\d/);
  }
  await expect(page.locator('#chart-note')).toHaveText(/^The chart could not be loaded/);

  // The zone file's suppressed cell too.
  await page.goto('explorer.html?level=zone&measure=disability3&age=5-17&sex=all&place=South+East');
  await expect(status(page)).toHaveText(/^Showing 1 row: /, LOAD);
  expect((await tableText(page))[1]).toEqual([
    'South East', 'Suppressed (fewer than 30 respondents)', 'Suppressed', 'Fewer than 30 respondents (disclosure rule)', '',
  ]);
});

test('explorer: the CSV and JSON downloads hold exactly the rows the table shows, in its order', async ({ page }) => {
  await shown(page, 'explorer.html?level=state&measure=seeing_3plus&age=5-17&sex=female&sort=estimate-desc');
  const check = async () => {
    const shownRows = (await tableText(page)).slice(1);
    const csv = parseCsv(await download(page, 'CSV'));
    const doc = JSON.parse(await download(page, 'JSON'));
    expect(csv[0]).toEqual(doc.columns.map((c) => c.label));
    expect(csv[0]).toEqual([
      'State', 'Estimate (%)', 'Low (%)', 'High (%)', 'Precision', 'Reason for the flag', 'Respondents (unweighted)',
    ]);
    expect(csv.length - 1).toBe(shownRows.length);
    expect(doc.rows).toHaveLength(shownRows.length);
    shownRows.forEach((cells, i) => {
      const file = csv[i + 1];
      const json = doc.rows[i];
      expect(file[0]).toBe(cells[0]);
      expect(json[0]).toBe(cells[0]);
      if (cells.length === 5) {
        // Words across Estimate, Low and High.
        expect(file.slice(1, 4)).toEqual([cells[1], '', '']);
        expect(json.slice(1, 4)).toEqual([cells[1], null, null]);
        expect(file[4]).toBe(cells[2]);
        return;
      }
      for (let j = 1; j <= 3; j += 1) {
        expect(pct(Number(file[j])), `${cells[0]} column ${j}`).toBe(cells[j]);
        expect(json[j]).toBe(Number(file[j]));
      }
      expect(file[4]).toBe(cells[4]);
      expect(file[5]).toBe(cells[5]);
      expect(Number(file[6]).toLocaleString('en-NG')).toBe(cells[6]);
      expect(json[6]).toBe(Number(file[6]));
    });
    expect(doc.page).toBe(page.url());
    expect(doc.terms).toContain('Reuse is subject to the source terms');
    expect(doc.sources[0]).toContain('Nigeria Demographic and Health Survey 2024');
  };
  await check();
  await page.getByRole('button', { name: 'State' }).click();
  await check();
  const names = await page.locator('#results-downloads a').evaluateAll((as) => as.map((a) => [a.download, a.getAttribute('aria-label')]));
  expect(names[0][0]).toBe('curb-cut-dhs2024-state-seeing-3plus-5to17-female.csv');
  expect(names[1][0]).toBe('curb-cut-dhs2024-state-seeing-3plus-5to17-female.json');
  expect(names[0][1]).toMatch(/^CSV, \d+ KB: the table shown above$/);
});

test('explorer: the chart is the library document of the view, with the table\'s figures', async ({ page, request }) => {
  await shown(page, 'explorer.html?level=state&measure=disability3&age=18%2B&sex=female&place=Kano');
  await expect(page.locator('#explorer-chart svg').first()).toBeVisible(LOAD);
  const doc = await (await request.get('data/charts/explorer/state-disability3-18plus-female.json')).json();
  expect(doc.audit.passed).toBe(true);
  expect(doc.meta.chart_type).toBe('dot');
  // The chart's accessible name is the document's data-derived alt-text.
  await expect(page.locator('#explorer-chart')).toHaveAccessibleName(doc.alt_text);
  await expect(page.locator('#explorer-chart-title')).toHaveText(doc.title);
  await expect(page.locator('#chart-note')).toContainText('with Kano highlighted');
  // Its figures are the table's: all states' view, one row per drawn state.
  await page.goto('explorer.html?level=state&measure=disability3&age=18%2B&sex=female');
  await expect(status(page)).toHaveText(/^Showing 37 rows/, LOAD);
  const rows = (await tableText(page)).slice(1).filter((r) => r.length === 7);
  const values = doc.data.series[0].values;
  expect(doc.data.categories).toHaveLength(rows.length);
  doc.data.categories.forEach((state, i) => {
    const row = rows.find((r) => r[0] === state);
    expect(row, state).toBeTruthy();
    expect(values[i].toFixed(1)).toBe(row[1]);
  });
  // Every chart the manifest names passed its audit.
  const manifest = await (await request.get('data/explorer.json')).json();
  const hrefs = Object.values(manifest.charts).map((c) => c.href).filter(Boolean);
  expect(hrefs).toHaveLength(84);
});

test('explorer: the columns link to the data dictionary\'s anchors', async ({ page, request }) => {
  await shown(page, 'explorer.html?level=zone&measure=disability3&age=18%2B&sex=all');
  const hrefs = await page.locator('#results-columns a').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(hrefs).toContain('./data-dictionary.html#dhs2024-national-zone-parquet--precision-flag');
  const dictionary = await (await request.get('data-dictionary.html')).text();
  for (const href of hrefs) {
    const id = href.split('#')[1];
    expect(dictionary, id).toContain(`id="${id}"`);
  }
  await shown(page, 'explorer.html?level=state&measure=disability3&age=18%2B&sex=all');
  await expect(page.locator('#results-columns a', { hasText: 'Estimate' })).toHaveAttribute(
    'href',
    './data-dictionary.html#dhs2024-state-prevalence-parquet--estimate',
  );
});

test('explorer: when the data cannot load, a message points to the state pages and the files', async ({ page }) => {
  await page.route('**/data/dhs2024_state_prevalence.parquet', (route) => route.abort());
  await page.goto('explorer.html');
  await expect(status(page)).toHaveText(/^Sorry, the explorer could not start: /, LOAD);
  await expect(status(page)).toHaveClass(/error/);
  await expect(page.locator('#explorer-form')).toBeHidden();
  const fallback = page.locator('#explorer-fallback');
  await expect(fallback).toBeVisible();
  await expect(fallback.getByRole('link', { name: 'The 37 state pages' })).toHaveAttribute('href', './states/');
  await expect(fallback.getByRole('link', { name: 'data dictionary' })).toBeVisible();
});

test.describe('explorer without JavaScript', () => {
  test.use({ javaScriptEnabled: false });

  test('explorer: without JavaScript, the page points to the same places', async ({ page, request }) => {
    // Chromium with scripts switched off by Playwright still parses <noscript> as if scripts
    // ran, so its text is checked in the served HTML; the rest in the page.
    const html = await (await request.get('explorer.html')).text();
    expect(html).toMatch(/<noscript>\s*<p class="status error">The data explorer needs JavaScript\./);
    await page.goto('explorer.html');
    await expect(page.locator('#explorer-fallback')).toBeVisible();
    await expect(page.locator('#explorer-form')).toBeHidden();
    await expect(page.locator('#explorer-fallback a[href="./states/"]')).toBeVisible();
  });
});

test('explorer: no sideways page scroll at 320px, even with wider letters', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await shown(page, 'explorer.html?level=state&measure=communication_3plus&age=5-17&sex=female');
  await expect(page.locator('#explorer-chart svg').first()).toBeVisible(LOAD);
  const overflow = () =>
    page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await overflow()).toBeLessThanOrEqual(0);
  // The wide table scrolls inside its wrapper, whose caption is then a Tab stop.
  await expect(page.locator('#results-data caption')).toHaveAttribute('tabindex', '0');
  await page.addStyleTag({ content: 'main * { letter-spacing: 0.12em; }' });
  expect(await overflow()).toBeLessThanOrEqual(0);
});

test('explorer: everything comes from this origin', async ({ page, baseURL }) => {
  const origin = new URL(baseURL).origin;
  const elsewhere = [];
  page.on('request', (r) => {
    const url = r.url();
    if (!url.startsWith(origin) && !url.startsWith('data:') && !url.startsWith('blob:')) elsewhere.push(url);
  });
  await shown(page, 'explorer.html?level=state&measure=disability3&age=18%2B&sex=all');
  await expect(page.locator('#explorer-chart svg').first()).toBeVisible(LOAD);
  await download(page, 'CSV');
  expect(elsewhere).toEqual([]);
});

test('every page links the data explorer', async ({ page }) => {
  for (const path of ['./', 'methodology.html', 'poverty.html', 'data-dictionary.html', 'explorer.html']) {
    await page.goto(path);
    const nav = page.getByRole('navigation', { name: 'Site' });
    await expect(nav.getByRole('link', { name: 'Data explorer' }), path).toHaveAttribute('href', './explorer.html');
  }
  for (const path of ['states/', 'states/kano.html']) {
    await page.goto(path);
    const link = page.locator('footer.site-footer').getByRole('link', { name: /Data explorer/ });
    await expect(link, path).toHaveAttribute('href', '../explorer.html');
  }
});
