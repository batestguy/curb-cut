import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// Lagos, from data/public/jonapwd/state_disability_type.csv (hand-checked on PDF page 38).
const LAGOS_PHYSICAL = '471,385';

async function loaded(page) {
  await page.goto('./');
  await expect(page.locator('#national-table table')).toBeVisible();
  await expect(page.locator('#national-chart svg').first()).toBeVisible();
  await expect(page.locator('#state-select')).toBeEnabled();
}

async function chooseState(page, state) {
  await page.locator('#state-select').selectOption(state);
  await expect(page.locator('#state-table table')).toBeVisible({ timeout: 30_000 });
}

for (const colorScheme of ['light', 'dark']) {
  test(`axe finds no WCAG A/AA violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await loaded(page);
    await chooseState(page, 'Kano');
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

  // Tab from <main> until the select is reached (bounded, so a trap fails the test).
  const select = page.locator('#state-select');
  let reached = false;
  for (let i = 0; i < 20 && !reached; i += 1) {
    await page.keyboard.press('Tab');
    reached = await select.evaluate((el) => el === document.activeElement);
  }
  expect(reached).toBe(true);

  // Choose Lagos by typing its name, as a keyboard user would on a closed select.
  await page.keyboard.type('Lagos');
  await expect(select).toHaveValue('Lagos');
  const table = page.locator('#state-table table');
  await expect(table).toBeVisible({ timeout: 30_000 });
  await expect(table.locator('caption')).toContainText('Lagos');
  await expect(table.getByRole('row', { name: /Physical disability/ })).toContainText(
    LAGOS_PHYSICAL,
  );
  await expect(page.getByRole('status')).toHaveText('Showing 10 disability types for Lagos.');
});

test('the chart is one image named by the data-derived alt-text', async ({ page, request }) => {
  const doc = await (await request.get('data/charts/national_by_type.json')).json();
  await loaded(page);
  const chart = page.locator('#national-chart');
  await expect(chart).toHaveAttribute('role', 'img');
  await expect(chart).toHaveAccessibleName(doc.alt_text);
  await expect(page.getByRole('img', { name: doc.alt_text })).toHaveCount(1);
  // Plotly's SVG is hidden from assistive technology.
  await expect(chart.locator('.chart-plot')).toHaveAttribute('aria-hidden', 'true');
  expect(doc.audit.passed).toBe(true);
});

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

test('no horizontal scrolling at 320px wide', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await loaded(page);
  await chooseState(page, 'Federal Capital Territory');
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
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
  await expect(page.getByRole('status')).toContainText('could not be loaded', {
    timeout: 30_000,
  });
  await expect(page.locator('#state-table table')).toHaveCount(0);
  await expect(page.locator('#national-table table')).toBeVisible();
  await expect(page.locator('#national-chart svg').first()).toBeVisible();
});
