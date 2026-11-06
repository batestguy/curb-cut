// The sensitivity page (site/sensitivity.html, src/sensitivity.js): an assumed rate against the
// DHS 2024 survey's state intervals.
//
// The real data have no suppressed or unreliable DISABILITY3 cell for both sexes, so two tests
// serve other data: the committed fixture tests/fixtures/sensitivity.json (built by
// packages/transform/scripts/sensitivity_data.py from the explorer's fixture Parquet files;
// test_sensitivity_data.py keeps it in step), with suppressed cells and a state with no data,
// and the real file with one cell turned unreliable in the test.
import { fileURLToPath } from 'node:url';
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { isVisitCount } from './visit-count.js';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const FIXTURES = fileURLToPath(new URL('./fixtures/', import.meta.url));
// The page waits this long after the rate stops moving before it announces the summary.
const SETTLE = 700;

const summary = (page) => page.locator('#summary');
const range = (page) => page.locator('#rate-range');
const number = (page) => page.locator('#rate-number');
const table = (page) => page.locator('#sensitivity-data');

async function ready(page, path = 'sensitivity.html') {
  await page.goto(path);
  await expect(summary(page)).toHaveText(/At an assumed /);
  await expect(table(page)).toBeVisible();
}

/** The table's body rows as text. */
async function bodyText(page) {
  return table(page).evaluate((t) =>
    [...t.tBodies[0].rows].map((tr) => [...tr.cells].map((c) => c.textContent.trim())),
  );
}

async function headerText(page) {
  return table(page).evaluate((t) =>
    [...t.tHead.rows[0].cells].map((c) => c.textContent.replace(/[▲▼↕]/g, '').trim()),
  );
}

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

const pct = (v) => (v > 0 && v < 0.05 ? '<0.1' : v.toFixed(1));

/** Counts of each comparison word in the table's rows. */
function tally(rows) {
  const count = (word) => rows.filter((r) => r.includes(word)).length;
  return {
    above: count('Above the interval'),
    inside: count('Inside the interval'),
    below: count('Below the interval'),
    left: rows.filter((r) => r.includes('Not compared')).map((r) => r[0]),
  };
}

for (const colorScheme of ['light', 'dark']) {
  for (const width of [null, 320]) {
    const view = width ? `${colorScheme}, ${width}px` : colorScheme;
    test(`sensitivity: axe finds no WCAG A/AA violations (${view})`, async ({ page }) => {
      if (width) await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ colorScheme });
      await ready(page);
      await expect(page.locator('#sensitivity-chart svg').first()).toBeVisible();
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}

test('sensitivity: the range, the buttons and the number input stay in step, by keyboard', async ({ page }) => {
  await ready(page);
  const slider = range(page);
  await expect(page.getByRole('slider', { name: 'Assumed rate' })).toBeVisible();
  await expect(slider).toHaveAttribute('aria-valuetext', '15 percent');
  await expect(page.locator('#rate-value')).toHaveText('15%');
  // Tab reaches the slider (after the skip link, the nav, the definitions' links).
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveValue('15.5');
  await expect(slider).toHaveAttribute('aria-valuetext', '15.5 percent');
  await expect(number(page)).toHaveValue('15.5');
  await expect(page.locator('#rate-value')).toHaveText('15.5%');
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(number(page)).toHaveValue('14.5');
  await page.keyboard.press('Home');
  await expect(slider).toHaveValue('2');
  await expect(number(page)).toHaveValue('2');
  await expect(page.locator('#rate-down')).toBeDisabled();
  await page.keyboard.press('End');
  await expect(slider).toHaveValue('20');
  await expect(number(page)).toHaveValue('20');
  await expect(page.locator('#rate-up')).toBeDisabled();
  // The buttons, by keyboard.
  await page.locator('#rate-down').focus();
  await page.keyboard.press('Enter');
  await expect(slider).toHaveValue('19.5');
  await expect(number(page)).toHaveValue('19.5');
  await page.keyboard.press('Space');
  await expect(slider).toHaveValue('19');
  await expect(page.locator('#rate-up')).toBeEnabled();
  // Typing a rate moves the slider; an off-step rate moves to the nearest, with a hint.
  await number(page).fill('12');
  await expect(slider).toHaveValue('12');
  await expect(slider).toHaveAttribute('aria-valuetext', '12 percent');
  await number(page).fill('12.3');
  await number(page).press('Enter');
  await expect(slider).toHaveValue('12.5');
  await expect(number(page)).toHaveValue('12.5');
  await expect(page.locator('#rate-hint')).toHaveText(/“12.3” is not one of the rates .* so 12.5% is used\./);
  await expect(summary(page)).toHaveText(/^“12.3” is not one of the rates.*At an assumed 12.5%, /);
  // The caption names the definition, the age group and the rate.
  await expect(table(page).locator('caption')).toContainText('(DISABILITY3), adults 18 and over: an assumed rate of 12.5%');
  // The age group, by keyboard.
  await page.getByRole('radio', { name: 'Children 5 to 17' }).check();
  await expect(table(page).locator('caption')).toContainText('children 5 to 17: an assumed rate of 12.5%');
  await expect(summary(page)).toHaveText(/children 5–17, DHS 2024/);
  await expect(page).toHaveURL(/\?rate=12\.5&age=5-17$/);
});

test('sensitivity: a held arrow key gives one announcement, after the rate settles', async ({ page }) => {
  await ready(page);
  await page.evaluate(() => {
    window.announcements = [];
    const el = document.getElementById('summary');
    new MutationObserver(() => window.announcements.push(el.textContent)).observe(el, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  });
  await range(page).focus();
  for (let i = 0; i < 10; i += 1) await page.keyboard.press('ArrowLeft', { delay: 30 });
  await expect(range(page)).toHaveValue('10');
  // The table follows at once; the summary only once the key is let go.
  await expect(table(page).locator('caption')).toContainText('an assumed rate of 10%');
  expect(await page.evaluate(() => window.announcements.length)).toBe(0);
  await page.waitForTimeout(SETTLE + 600);
  const said = await page.evaluate(() => window.announcements);
  expect(said).toHaveLength(1);
  expect(said[0]).toMatch(/^At an assumed 10%, /);
  // The one live region on the page.
  await expect(page.locator('[role="status"], [aria-live]')).toHaveCount(1);
});

test('sensitivity: the summary says what the table rows say, at every rate tried', async ({ page }) => {
  for (const [rate, age] of [['15', '18%2B'], ['3', '18%2B'], ['2', '5-17'], ['8.5', '5-17']]) {
    await ready(page, `sensitivity.html?rate=${rate}&age=${age}`);
    const rows = await bodyText(page);
    expect(rows).toHaveLength(37);
    const t = tally(rows);
    const n = t.above + t.inside + t.below;
    await expect(summary(page)).toHaveText(
      `At an assumed ${rate}%, the assumption is above the survey's interval in ${t.above} of ${n} states, ` +
        `inside it in ${t.inside} and below it in ${t.below} ` +
        `(DISABILITY3, ${age === '5-17' ? 'children 5–17' : 'adults 18+'}, DHS 2024).`,
    );
    // Each row's word follows from its own bounds (inclusive), as far as the rounded table shows.
    for (const row of rows) {
      const [low, high] = [Number(row[3].replace('<', '')), Number(row[4])];
      const r = Number(rate);
      if (row[6] === 'Above the interval') expect(r, row[0]).toBeGreaterThanOrEqual(high);
      if (row[6] === 'Below the interval') expect(r, row[0]).toBeLessThanOrEqual(low);
      if (row[6] === 'Inside the interval') {
        expect(r, row[0]).toBeGreaterThanOrEqual(low - 0.05);
        expect(r, row[0]).toBeLessThanOrEqual(high + 0.05);
      }
    }
  }
});

test('sensitivity: the table has the assumed rate, the survey interval, words and the implied count', async ({ page, request }) => {
  await ready(page);
  expect(await headerText(page)).toEqual([
    'State',
    'Assumed rate (%)',
    'Survey estimate (%)',
    'Low (%)',
    'High (%)',
    'Precision',
    'Assumed rate against the interval',
    'Implied count at the assumed rate (all ages, 2023 projection)',
  ]);
  const data = await (await request.get('data/sensitivity.json')).json();
  const kano = data.states['18+'].find((c) => c.state === 'Kano');
  const row = (await bodyText(page)).find((r) => r[0] === 'Kano');
  expect(row[1]).toBe('15.0');
  expect(row[2]).toBe(pct(100 * kano.estimate));
  expect(row[3]).toBe(pct(100 * kano.ci_low));
  expect(row[4]).toBe(pct(100 * kano.ci_high));
  expect(row[7]).toBe(Math.round(0.15 * kano.population_2023).toLocaleString('en-NG'));
  await expect(table(page).getByRole('link', { name: 'Kano' })).toHaveAttribute('href', /states\/kano\.html$/);
  // The definitions come from the data and the dictionary's words.
  const defs = page.locator('section[aria-labelledby="what-heading"]');
  await expect(defs).toContainText(data.assumption.definition);
  await expect(defs).toContainText(data.measure.definition);
  await expect(defs).toContainText(data.population.description);
  await expect(defs).toContainText('both bounds included');
});

test('sensitivity: sorting by keyboard follows the explorer, and the view keeps it', async ({ page }) => {
  await ready(page, 'sensitivity.html?rate=3&age=18%2B');
  const button = page.getByRole('button', { name: 'Survey estimate (%)' });
  await button.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('th[aria-sort="ascending"]')).toContainText('Survey estimate');
  await page.keyboard.press('Enter');
  await expect(page.locator('th[aria-sort="descending"]')).toContainText('Survey estimate');
  // The sort is said in the page's one live region, as on the explorer.
  await expect(summary(page)).toHaveText('Sorted by Survey estimate (%), highest first.');
  const values = (await bodyText(page)).map((r) => Number(r[2]));
  expect(values).toEqual([...values].sort((a, b) => b - a));
  await expect(page).toHaveURL(/sort=estimate-desc/);
  // The comparison sorts by position: below, inside, above.
  await page.getByRole('button', { name: 'Assumed rate against the interval' }).click();
  const words = (await bodyText(page)).map((r) => r[6]);
  const order = { 'Below the interval': 1, 'Inside the interval': 2, 'Above the interval': 3 };
  expect(words.map((w) => order[w])).toEqual([...words.map((w) => order[w])].sort((a, b) => a - b));
  await expect(summary(page)).toHaveText('Sorted by Assumed rate against the interval, below first.');
  // The sort survives a change of rate, and the assumed rate column is not a sort button.
  await range(page).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('th[aria-sort="ascending"]')).toContainText('Assumed rate against the interval');
  await expect(page.getByRole('button', { name: 'Assumed rate (%)' })).toHaveCount(0);
});

test('sensitivity: a hint about a typed rate is dropped when the rate moves another way', async ({ page }) => {
  await ready(page);
  await number(page).fill('12.3');
  await page.keyboard.press('Tab');
  await expect(page.locator('#rate-hint')).toContainText('so 12.5% is used');
  // Within the settle time, the slider moves on: only the new rate's summary is announced.
  await range(page).focus();
  await page.keyboard.press('ArrowRight');
  await expect(summary(page)).toContainText('At an assumed 13%');
  await expect(summary(page)).not.toContainText('12.5% is used');
  await expect(page.locator('#rate-hint')).toHaveText('');
});

test('sensitivity: at an end of the range the disabled button hands focus to the slider', async ({ page }) => {
  await ready(page, 'sensitivity.html?rate=19.5');
  await page.locator('#rate-up').focus();
  await page.keyboard.press('Enter');
  await expect(range(page)).toBeFocused();
  await expect(range(page)).toHaveAttribute('aria-valuetext', '20 percent');
});

test('sensitivity: suppressed and no-data cells show words and are not compared (fixture data)', async ({ page }) => {
  await page.route('**/data/sensitivity.json', (route) => route.fulfill({ path: `${FIXTURES}sensitivity.json` }));
  // The real charts would not match the fixture rows.
  await page.route('**/data/charts/sensitivity/**', (route) => route.abort());
  await ready(page, 'sensitivity.html?rate=15&age=5-17');
  const rows = await bodyText(page);
  const by = Object.fromEntries(rows.map((r) => [r[0], r]));
  expect(by.Abia.slice(1, 6)).toEqual(['15.0', 'Suppressed (fewer than 30 respondents)', 'Suppressed', 'Not compared', by.Abia[5]]);
  expect(by.Adamawa[2]).toBe('Suppressed (withheld to protect a neighbouring small cell)');
  expect(by.Zamfara[2]).toBe('No data');
  expect(by.Zamfara[4]).toBe('Not compared');
  // A row with words has no number in its survey cells (one cell across three columns).
  for (const r of [by.Abia, by.Adamawa, by.Zamfara]) expect(r).toHaveLength(6);
  await expect(summary(page)).toHaveText(
    "At an assumed 15%, the assumption is above the survey's interval in 32 of 32 states, inside it in 0 " +
      'and below it in 0 (DISABILITY3, children 5–17, DHS 2024). Not compared, as the survey figure is ' +
      'not shown: Abia, Adamawa, Anambra, Bauchi and Zamfara.',
  );
});

test('sensitivity: an unreliable estimate is left out with words, never a number', async ({ page, request }) => {
  const data = await (await request.get('data/sensitivity.json')).json();
  const kano = data.states['18+'].find((c) => c.state === 'Kano');
  kano.precision_flag = 'unreliable';
  await page.route('**/data/sensitivity.json', (route) => route.fulfill({ json: data }));
  await page.route('**/data/charts/sensitivity/**', (route) => route.abort());
  await ready(page);
  const row = (await bodyText(page)).find((r) => r[0] === 'Kano');
  expect(row[2]).toBe('Not shown: too imprecise (unreliable)');
  expect(row[3]).toBe('Unreliable');
  expect(row[4]).toBe('Not compared');
  expect(row.join(' ')).not.toContain(pct(100 * kano.estimate));
  await expect(summary(page)).toHaveText(/ in 36 of 36 states, .* Not compared, as the survey figure is not shown: Kano\.$/);
});

test('sensitivity: the view is in the address, and an invalid one falls back with a message', async ({ page }) => {
  await ready(page, 'sensitivity.html?rate=7.5&age=5-17&sort=high-desc');
  await expect(range(page)).toHaveValue('7.5');
  await expect(page.getByRole('radio', { name: 'Children 5 to 17' })).toBeChecked();
  await expect(page.locator('th[aria-sort="descending"]')).toContainText('High');
  await expect(page.locator('#url-message')).toBeHidden();
  // Moving the rate rewrites the address once it settles, keeping the rest.
  await range(page).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page).toHaveURL(/\?rate=8&age=5-17&sort=high-desc$/);
  await page.reload();
  await expect(range(page)).toHaveValue('8');

  await ready(page, 'sensitivity.html?rate=abc&age=old');
  await expect(range(page)).toHaveValue('15');
  await expect(page.getByRole('radio', { name: 'Adults 18 and over' })).toBeChecked();
  const message = page.locator('#url-message');
  await expect(message).toBeVisible();
  await expect(message).toHaveText(/the rate “abc” is not one of the rates offered .* so 15% is used; the age group “old” is not in the data/);
  // Announced with the summary, in the one live region.
  await expect(summary(page)).toHaveText(/^This link's choices were not all valid: .* At an assumed 15%, /);
  await expect(page).toHaveURL(/\?rate=15&age=18%2B$/);
  await ready(page, 'sensitivity.html?rate=25');
  await expect(range(page)).toHaveValue('15');
});

test('sensitivity: the downloads hold the rows the table shows', async ({ page }) => {
  await ready(page, 'sensitivity.html?rate=4&age=18%2B');
  const check = async () => {
    const rows = await bodyText(page);
    const csv = parseCsv(await download(page, 'CSV'));
    const doc = JSON.parse(await download(page, 'JSON'));
    expect(csv[0]).toEqual(await headerText(page));
    expect(csv.length - 1).toBe(rows.length);
    expect(doc.rows).toHaveLength(rows.length);
    rows.forEach((cells, i) => {
      const file = csv[i + 1];
      expect(file[0]).toBe(cells[0]);
      expect(doc.rows[i][0]).toBe(cells[0]);
      expect(Number(file[1]).toFixed(1)).toBe(cells[1]);
      for (let j = 2; j <= 4; j += 1) expect(pct(Number(file[j])), `${cells[0]} ${j}`).toBe(cells[j]);
      expect(file[5]).toBe(cells[5]);
      expect(file[6]).toBe(cells[6]);
      expect(Math.round(Number(file[7])).toLocaleString('en-NG')).toBe(cells[7]);
      expect(doc.rows[i][7]).toBe(Number(file[7]));
    });
    expect(doc.page).toBe(page.url());
    expect(doc.caption).toBe(await table(page).locator('caption').textContent());
    expect(doc.terms).toContain('Reuse is subject to the source terms');
  };
  await check();
  await page.getByRole('button', { name: 'High (%)' }).click();
  await check();
  const names = await page.locator('#results-downloads a').evaluateAll((as) => as.map((a) => [a.download, a.getAttribute('aria-label')]));
  expect(names[0][0]).toBe('curb-cut-assumed-rate-4-0-dhs2024-disability3-18plus.csv');
  expect(names[1][0]).toBe('curb-cut-assumed-rate-4-0-dhs2024-disability3-18plus.json');
  expect(names[0][1]).toMatch(/^CSV, \d+ KB: the table of states at this rate$/);
});

test('sensitivity: the chart is the library document of the view', async ({ page, request }) => {
  await ready(page, 'sensitivity.html?rate=4&age=18%2B');
  await expect(page.locator('#sensitivity-chart svg').first()).toBeVisible();
  const doc = await (await request.get('data/charts/sensitivity/18plus-rate-4-0.json')).json();
  expect(doc.audit.passed).toBe(true);
  expect(doc.meta.chart_type).toBe('dot');
  expect(doc.data.series.map((s) => s.name)).toEqual(['DHS 2024 survey estimate', 'Assumed rate']);
  expect(doc.data.series[1].values.every((v) => v === 4)).toBe(true);
  await expect(page.locator('#sensitivity-chart')).toHaveAccessibleName(doc.alt_text);
  await expect(page.locator('#sensitivity-chart-title')).toHaveText(doc.title);
  // Its figures are the table's.
  const rows = await bodyText(page);
  doc.data.categories.forEach((state, i) => {
    const row = rows.find((r) => r[0] === state);
    expect(doc.data.series[0].values[i].toFixed(1)).toBe(row[2]);
  });
  // A new rate brings that rate's document, once it settles.
  await range(page).focus();
  await page.keyboard.press('End');
  await expect(page.locator('#sensitivity-chart-title')).toContainText('an assumed rate of 20.0%');
  const manifest = await (await request.get('data/sensitivity.json')).json();
  expect(Object.values(manifest.charts).filter((c) => c.href)).toHaveLength(74);
});

test('sensitivity: the columns link to the data dictionary\'s anchors', async ({ page, request }) => {
  await ready(page);
  const hrefs = await page.locator('#results-columns a').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(hrefs).toContain('./data-dictionary.html#dhs2024-state-prevalence-parquet--population-2023');
  const dictionary = await (await request.get('data-dictionary.html')).text();
  for (const href of hrefs) {
    const id = href.split('#')[1];
    expect(dictionary, id).toContain(`id="${id}"`);
  }
});

test('sensitivity: no sideways page scroll at 320px, even with wider letters', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await ready(page);
  await expect(page.locator('#sensitivity-chart svg').first()).toBeVisible();
  const overflow = () =>
    page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await overflow()).toBeLessThanOrEqual(0);
  // The wide table scrolls inside its wrapper, whose caption is then a Tab stop.
  await expect(table(page).locator('caption')).toHaveAttribute('tabindex', '0');
  await page.addStyleTag({ content: 'main * { letter-spacing: 0.12em; }' });
  expect(await overflow()).toBeLessThanOrEqual(0);
});

test('sensitivity: everything comes from this origin', async ({ page, baseURL }) => {
  const origin = new URL(baseURL).origin;
  const elsewhere = [];
  page.on('request', (r) => {
    const url = r.url();
    if (!url.startsWith(origin) && !url.startsWith('data:') && !url.startsWith('blob:')) elsewhere.push(url);
  });
  await ready(page);
  await expect(page.locator('#sensitivity-chart svg').first()).toBeVisible();
  await download(page, 'CSV');
  expect(elsewhere.filter((u) => !isVisitCount(u))).toEqual([]);
  expect(elsewhere.filter(isVisitCount)).toHaveLength(1);
});

test('sensitivity: when the data cannot load, the page says so and points elsewhere', async ({ page }) => {
  await page.route('**/data/sensitivity.json', (route) => route.abort());
  await page.goto('sensitivity.html');
  await expect(summary(page)).toHaveText(/^Sorry, the figures could not be loaded: /);
  await expect(page.locator('#rate-form')).toBeHidden();
  await expect(page.locator('#sensitivity-fallback')).toBeVisible();
  await expect(page.locator('#sensitivity-fallback').getByRole('link', { name: 'data dictionary' })).toBeVisible();
});

test.describe('sensitivity without JavaScript', () => {
  test.use({ javaScriptEnabled: false });

  test('sensitivity: the static version at JONAPWD\'s rate is in the served HTML', async ({ page, request }) => {
    const html = await (await request.get('sensitivity.html')).text();
    const noscript = html.match(/<noscript>([\s\S]*?)<\/noscript>/)?.[1] ?? '';
    expect(noscript).toContain('Changing the rate needs JavaScript.');
    expect(noscript).toContain('<h3>Adults 18 and over, at an assumed 15%</h3>');
    expect(noscript).toContain('<h3>Children 5 to 17, at an assumed 15%</h3>');
    expect(noscript).toMatch(/At an assumed 15%, the assumption is above the survey&#x27;s interval in \d+ of \d+ states/);
    expect((noscript.match(/<table>/g) ?? []).length).toBe(2);
    expect((noscript.match(/<tr>/g) ?? []).length).toBe(2 * 38);
    for (const href of ['./explorer.html', './data-dictionary.html', './data/dhs2024_state_prevalence.parquet']) {
      expect(noscript).toContain(`href="${href}"`);
    }
    // Its download links work, and hold its rows.
    const csvHref = noscript.match(/href="\.\/(data\/downloads\/sensitivity\/[^"]+18plus\.csv)"/)[1];
    const csv = parseCsv(await (await request.get(csvHref)).text());
    expect(csv).toHaveLength(38);
    expect(csv[0][0]).toBe('State');
    // The definitions are in the HTML too, with or without JavaScript.
    expect(html).toContain('An assumption, not a count');
    expect(html).not.toContain('sensitivity:static');
    await page.goto('sensitivity.html');
    await expect(page.locator('#rate-form')).toBeHidden();
  });
});

test('every page links the sensitivity page', async ({ page }) => {
  for (const path of ['./', 'methodology.html', 'poverty.html', 'data-dictionary.html', 'explorer.html', 'sensitivity.html']) {
    await page.goto(path);
    const nav = page.getByRole('navigation', { name: 'Site' });
    await expect(nav.getByRole('link', { name: 'Assumed rate vs survey' }), path).toHaveAttribute('href', './sensitivity.html');
  }
  for (const path of ['states/', 'states/kano.html']) {
    await page.goto(path);
    const link = page.locator('footer.site-footer').getByRole('link', { name: /Assumed rate vs survey/ });
    await expect(link, path).toHaveAttribute('href', '../sensitivity.html');
  }
  // The main page's and the methodology's comparison sections link it too.
  await page.goto('./');
  await expect(page.locator('section[aria-labelledby="comparison-heading"] a[href="./sensitivity.html"]')).toHaveCount(1);
  await page.goto('methodology.html');
  await expect(page.locator('main a[href="./sensitivity.html"]')).toHaveCount(1);
});
