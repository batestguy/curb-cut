import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// Lagos, from data/public/jonapwd/state_disability_type.csv (hand-checked on PDF page 38).
const LAGOS_PHYSICAL = '471,385';

async function loaded(page) {
  await page.goto('./');
  await expect(page.locator('#prevalence-map svg')).toBeVisible();
  await expect(page.locator('#prevalence-chart svg').first()).toBeVisible();
  await expect(page.locator('#comparison-list li')).toHaveCount(5);
  await expect(page.locator('#moran-sentence')).not.toBeEmpty();
  await expect(page.locator('#national-table table')).toBeVisible();
  await expect(page.locator('#national-chart svg').first()).toBeVisible();
  await expect(page.locator('#state-chart svg').first()).toBeVisible();
  await expect(page.locator('#state-select')).toBeEnabled();
}

// The by-state chart's bar colours and outline widths, read from Plotly's live data.
async function stateChartMarker(page) {
  return page.locator('#state-chart .chart-plot').evaluate((el) => {
    const { y, marker } = el.data[0];
    return { y, color: marker.color, width: marker.line?.width ?? null };
  });
}

async function chooseState(page, state) {
  await page.locator('#state-select').selectOption(state);
  await page.getByRole('button', { name: 'Show figures' }).click();
  await expect(page.locator('#state-table table')).toBeVisible({ timeout: 30_000 });
}

for (const colorScheme of ['light', 'dark']) {
  test(`axe finds no WCAG A/AA violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await loaded(page);
    await chooseState(page, 'Kano');
    // The Moran table and the findings' method too.
    for (const summary of await page.locator('details.more summary').all()) {
      await summary.click();
    }
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('keyboard: skip link first, Tab reaches the state select, and a state can be chosen', async ({
  page,
}) => {
  await loaded(page);

  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();

  // The skip link moves focus to <main>.
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();

  // Tab from <main> until the select is reached (bounded, so a trap or a run of new stops
  // fails the test). At desktop width it is the 11th stop: the methodology link, five
  // comparison source links, the map, the two spatial links ("Why", "Methods and limits"),
  // the <summary> of the details, then the select. The bound allows a small margin.
  const select = page.locator('#state-select');
  let reached = false;
  for (let i = 0; i < 15 && !reached; i += 1) {
    await page.keyboard.press('Tab');
    reached = await select.evaluate((el) => el === document.activeElement);
  }
  expect(reached).toBe(true);

  // Choose Lagos by typing its name, as a keyboard user would on a closed select. Nothing loads
  // yet; Tab to "Show figures" and press Enter.
  await page.keyboard.type('Lagos');
  await expect(select).toHaveValue('Lagos');
  await expect(page.locator('#state-table table')).toHaveCount(0);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Show figures' })).toBeFocused();
  await page.keyboard.press('Enter');
  const table = page.locator('#state-table table');
  await expect(table).toBeVisible({ timeout: 30_000 });
  await expect(table.locator('caption')).toContainText('Lagos');
  await expect(table.getByRole('row', { name: /Physical disability/ })).toContainText(
    LAGOS_PHYSICAL,
  );
  await expect(page.locator('#state-status')).toHaveText('Showing 10 disability types for Lagos.');
  // Focus moves to the state card's heading so screen readers hear the state at once; the
  // card and then the table follow in reading order.
  await expect(page.getByRole('heading', { level: 3, name: 'Lagos' })).toBeFocused();
});

test('the state card shows the facts, and the map carries the share and rank', async ({
  page,
  request,
}) => {
  const states = await (await request.get('data/states.json')).json();
  const lagos = states.find((s) => s.state === 'Lagos');
  const total = states.reduce((sum, s) => sum + s.jonapwd_total, 0);
  const fmt = (n) => n.toLocaleString('en-NG');
  await loaded(page);
  await expect(page.locator('#state-card')).toBeHidden();
  await chooseState(page, 'Lagos');
  const card = page.locator('#state-card');
  await expect(card).toBeVisible();
  await expect(card.getByRole('heading', { level: 3 })).toHaveText('Lagos');
  await expect(card).toContainText('Ikeja');
  await expect(card).toContainText('South West');
  await expect(card).toContainText('13,710,862'); // NBS Demographic Bulletin 2023, Annex 3
  await expect(card).toContainText('“Centre of Excellence”');
  // Share and rank recomputed here from the per-state totals, not read from the mart.
  const share = ((100 * lagos.jonapwd_total) / total).toFixed(1);
  const rank = 1 + states.filter((s) => s.jonapwd_total > lagos.jonapwd_total).length;
  expect(rank).toBe(lagos.rank_of_37);
  const figure = `${fmt(lagos.jonapwd_total)} people: ${share}% of the ${fmt(total)} for all 37 states, ranked ${rank} of 37`;
  // Not in the facts list: the map's name has it, and hover, tap or focus show it.
  await expect(card.locator('.facts')).not.toContainText('JONAPWD');
  await expect(card.locator('.locator-map')).toHaveAccessibleName(new RegExp(`${figure}\\.$`));
  await expect(card.getByRole('link', { name: 'Zikoko' })).toHaveAttribute(
    'href',
    lagos.slogan_source_url,
  );
  // The card comes before the table in reading order.
  const cardFirst = await page.evaluate(() => {
    const cardEl = document.getElementById('state-card');
    const tableEl = document.querySelector('#state-table table');
    return Boolean(cardEl.compareDocumentPosition(tableEl) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(cardFirst).toBe(true);
});

test('the map tip shows a state on hover, tap and focus, and Esc closes it', async ({
  page,
  request,
}) => {
  const states = await (await request.get('data/states.json')).json();
  const kano = states.find((s) => s.state === 'Kano');
  await loaded(page);
  await chooseState(page, 'Lagos');
  const map = page.locator('#state-card .locator-map');
  const tip = page.locator('#state-card .map-tip');
  await expect(tip).toBeHidden();

  // Hovering any state shows that state, and the pointer can move onto the tip.
  await map.locator('path[data-state="NG-KN"]').hover();
  await expect(tip).toBeVisible();
  await expect(tip).toContainText('Kano');
  await expect(tip).toContainText(`ranked ${kano.rank_of_37} of 37`);
  await tip.hover();
  await expect(tip).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(tip).toBeHidden();

  // A click (or tap) shows it too; moving off the map closes it.
  await map.locator('path[data-state="NG-KN"]').click();
  await expect(tip).toContainText('Kano');
  await page.mouse.move(0, 0);
  await expect(tip).toBeHidden();

  // Keyboard: Tab from the card's heading to the map shows the chosen state; Esc closes it.
  await page.locator('#state-card h3').focus();
  await page.keyboard.press('Tab');
  await expect(map).toBeFocused();
  await expect(tip).toContainText('Lagos');
  await expect(tip).toContainText('ranked 2 of 37');
  await page.keyboard.press('Escape');
  await expect(tip).toBeHidden();
});

test('a state without a sourced slogan leaves the slogan line out', async ({ page }) => {
  await loaded(page);
  await chooseState(page, 'Ekiti');
  const card = page.locator('#state-card');
  await expect(card.getByRole('heading', { level: 3 })).toHaveText('Ekiti');
  await expect(card.locator('dt', { hasText: 'Slogan' })).toHaveCount(0);
  await expect(card.getByRole('link', { name: 'Zikoko' })).toHaveCount(0);
});

test('the locator map is one image named with the state, zone and figure', async ({ page }) => {
  await loaded(page);
  await chooseState(page, 'Lagos');
  const map = page.locator('#state-card .locator-map');
  await expect(map).toHaveAttribute('role', 'img');
  await expect(map).toHaveAccessibleName(
    /^Map of Nigeria with Lagos highlighted, in the South West zone\. JONAPWD's estimate: [\d,]+ people: [\d.]+% of the [\d,]+ for all 37 states, ranked 2 of 37\.$/,
  );
  await expect(map.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  await expect(map.locator('path')).toHaveCount(37);
  await expect(map.locator('path.selected')).toHaveCount(1);
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-LA');
  await expect(map.locator('circle.locator-ring')).toHaveCount(1); // Lagos is small
  await expect(page.locator('#state-card .locator figcaption')).toHaveText(
    'Boundaries: geoBoundaries (CC BY 4.0)',
  );
});

test('if the map fails to load, the card and table still appear without it', async ({ page }) => {
  await page.route('**/nigeria-states.json', (route) => route.abort());
  await loaded(page);
  await chooseState(page, 'Lagos');
  const card = page.locator('#state-card');
  await expect(card).toBeVisible();
  await expect(card).toContainText('Ikeja');
  await expect(card.locator('.locator')).toBeHidden();
  await expect(page.locator('#state-status')).toHaveText('Showing 10 disability types for Lagos.');
  await expect(page.getByRole('heading', { level: 3, name: 'Lagos' })).toBeFocused();
});

test('the chosen state is highlighted in the by-state chart, and moves with the choice', async ({
  page,
  request,
}) => {
  const doc = await (await request.get('data/charts/national_by_state.json')).json();
  const { mark, highlight } = doc.themes.light;
  await loaded(page);
  expect((await stateChartMarker(page)).color).toBe(mark); // nothing highlighted yet

  await chooseState(page, 'Lagos');
  await expect.poll(async () => typeof (await stateChartMarker(page)).color).toBe('object');
  let marker = await stateChartMarker(page);
  const lagos = marker.y.indexOf('Lagos');
  const kano = marker.y.indexOf('Kano');
  expect(marker.color[lagos]).toBe(highlight);
  expect(marker.width[lagos]).toBeGreaterThan(0); // an outline, not colour alone
  expect(marker.color.filter((c) => c === highlight)).toHaveLength(1);

  await chooseState(page, 'Kano');
  await expect.poll(async () => (await stateChartMarker(page)).color[kano]).toBe(highlight);
  marker = await stateChartMarker(page);
  expect(marker.color[lagos]).toBe(mark);
  expect(marker.width[lagos]).toBe(0);
  expect(marker.color.filter((c) => c === highlight)).toHaveLength(1);
  // The chart's accessible name does not change with the highlight.
  await expect(page.locator('#state-chart')).toHaveAccessibleName(doc.alt_text);
});

test('arrowing through the state picker does not run a query per state', async ({ page }) => {
  const parquetRequests = [];
  page.on('request', (r) => {
    if (r.url().endsWith('.parquet')) parquetRequests.push(r.url());
  });
  await loaded(page);
  await page.locator('#state-select').focus();
  for (let i = 0; i < 5; i += 1) await page.keyboard.press('ArrowDown');
  await page.keyboard.type('Gombe');
  await page.waitForTimeout(1500);
  // Focusing the picker warms DuckDB up in the background, which may fetch the Parquet file
  // once. What must not happen is a query per state: at most that one warm-up fetch.
  expect(parquetRequests.length).toBeLessThanOrEqual(1);
  await expect(page.locator('#state-table table')).toHaveCount(0);
  await expect(page.locator('#state-status')).toHaveText('');
});

test('pressing Show figures with no state chosen explains what to do', async ({ page }) => {
  await loaded(page);
  await page.getByRole('button', { name: 'Show figures' }).click();
  await expect(page.locator('#state-status')).toHaveText(
    'Choose a state first, then press Show figures.',
  );
  await expect(page.locator('#state-select')).toBeFocused();
});

for (const [name, id] of [
  ['national_by_type', '#national-chart'],
  ['national_by_state', '#state-chart'],
]) {
  test(`the ${name} chart is one image named by the data-derived alt-text`, async ({
    page,
    request,
  }) => {
    const doc = await (await request.get(`data/charts/${name}.json`)).json();
    await loaded(page);
    const chart = page.locator(id);
    await expect(chart).toHaveAttribute('role', 'img');
    await expect(chart).toHaveAccessibleName(doc.alt_text);
    await expect(page.getByRole('img', { name: doc.alt_text })).toHaveCount(1);
    // Plotly's SVG is hidden from assistive technology.
    await expect(chart.locator('.chart-plot')).toHaveAttribute('aria-hidden', 'true');
    expect(doc.audit.passed).toBe(true);
  });
}

test('tables have captions and scoped headers', async ({ page }) => {
  await loaded(page);
  await chooseState(page, 'Abia');
  for (const id of ['#national-table', '#state-table']) {
    const table = page.locator(`${id} table`);
    await expect(table.locator('caption')).not.toBeEmpty();
    await expect(table.locator('thead th[scope="col"]')).toHaveCount(3);
    await expect(table.locator('tbody th[scope="row"]')).toHaveCount(10);
    await expect(table.locator('tbody td')).toHaveCount(20);
  }
  // Same numbers as the chart document.
  const national = page.locator('#national-table table');
  await expect(national.getByRole('row', { name: /Physical disability/ })).toContainText(
    '8,186,521',
  );
});

test('no horizontal scrolling at 320px wide, and the card stacks inside the page', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await loaded(page);
  await chooseState(page, 'Federal Capital Territory');
  const card = page.locator('#state-card');
  await expect(card.locator('.locator-map svg')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const box = await card.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  // Stacked: the map sits below the facts, not beside them.
  const facts = await card.locator('.facts').boundingBox();
  const map = await card.locator('.locator').boundingBox();
  expect(map.y).toBeGreaterThanOrEqual(facts.y + facts.height - 1);
});

test('DuckDB-WASM loads only when needed, and nothing comes from another origin', async ({
  page,
}) => {
  const siteOrigin = new URL(test.info().project.use.baseURL).origin;
  const wasm = [];
  const elsewhere = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (url.pathname.endsWith('.wasm')) wasm.push(url.pathname);
    if (url.origin !== siteOrigin) elsewhere.push(r.url());
  });
  await loaded(page);
  expect(wasm).toEqual([]);
  await chooseState(page, 'Oyo');
  // The engine and its Parquet extension, both self-hosted (no CDN at runtime).
  expect(wasm.some((p) => /\/assets\/duckdb-(eh|mvp)-.*\.wasm$/.test(p))).toBe(true);
  expect(wasm.some((p) => p.endsWith('/parquet.duckdb_extension.wasm'))).toBe(true);
  expect(elsewhere).toEqual([]);
});

test('a data failure is announced and the chart and table still work', async ({ page }) => {
  await page.route('**/jonapwd_state_by_type.parquet', (route) => route.abort());
  await loaded(page);
  await page.locator('#state-select').selectOption('Oyo');
  await page.getByRole('button', { name: 'Show figures' }).click();
  await expect(page.locator('#state-status')).toContainText('could not be loaded', {
    timeout: 30_000,
  });
  await expect(page.locator('#state-table table')).toHaveCount(0);
  await expect(page.locator('#state-card')).toBeHidden();
  await expect(page.locator('#national-table table')).toBeVisible();
  await expect(page.locator('#national-chart svg').first()).toBeVisible();
});

test('a chart failure is announced and the chart keeps an accessible name', async ({ page }) => {
  await page.route('**/charts/national_by_type.json', (route) => route.abort());
  await page.goto('./');
  // The by-state chart is independent and still renders.
  await expect(page.locator('#state-chart svg').first()).toBeVisible();
  const status = page.locator('#national-chart-status');
  await expect(status).toHaveAttribute('role', 'status');
  await expect(status).toContainText('The chart could not be loaded');
  await expect(page.locator('#national-chart')).toHaveAccessibleName(
    /The chart could not be loaded/,
  );
  // The state explorer is independent of the chart and still works.
  await expect(page.locator('#state-select')).toBeEnabled();
});
