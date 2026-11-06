// The data dictionary (site/data-dictionary.html, built by
// packages/transform/scripts/build_data_dictionary.py from the dbt marts' YAML and the exported
// files): plain HTML with no script, one section and one table per public file.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
// A long page with no script or image; it must still be light on a phone.
const HTML_BUDGET = 200 * 1024;
const TOTAL_BUDGET = 260 * 1024;

const FILES = [
  'dhs2024_state_prevalence.parquet',
  'dhs2024_national_zone.parquet',
  'prevalence_comparison.parquet',
  'spatial_state.parquet',
  'spatial_moran.parquet',
  'jonapwd_state_by_type.parquet',
  'jonapwd_national_by_type.parquet',
  'states.json',
  'prevalence.json',
  'spatial.json',
  'poverty.json',
];
const anchor = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

async function open(page) {
  await page.goto('data-dictionary.html');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Data dictionary');
}

for (const colorScheme of ['light', 'dark']) {
  for (const width of [null, 320]) {
    const view = width ? `${colorScheme}, ${width}px` : colorScheme;
    test(`data dictionary: axe finds no WCAG A/AA violations (${view})`, async ({ page }) => {
      if (width) await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ colorScheme });
      await open(page);
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}

test('data dictionary: one section and one table per public file, with stable anchors', async ({ page, request }) => {
  await open(page);
  for (const file of FILES) {
    const heading = page.locator(`h2#${anchor(file)}`);
    await expect(heading, file).toContainText(file);
    const table = page.locator(`section[aria-labelledby="${anchor(file)}"] table`);
    await expect(table, file).toHaveCount(1);
    expect(await table.locator('tbody tr').count(), file).toBeGreaterThan(2);
    // The contents list links the section.
    await expect(page.locator(`nav[aria-labelledby="contents-heading"] a[href="#${anchor(file)}"]`)).toHaveCount(1);
  }
  // Column anchors other pages can link to.
  for (const id of [
    'dhs2024-state-prevalence-parquet--estimate',
    'dhs2024-state-prevalence-parquet--precision-flag',
    'states-json--item-dhs2024-estimate',
    'poverty-json--estimates-estimate-id-ci-low',
    'table-downloads--columns-item-unit',
    'api--prevalence',
  ]) {
    await expect(page.locator(`th#${id}`), id).toHaveCount(1);
  }
  // Every top-level key of the JSON files has a row (the build checks every field; this
  // checks the page shows the file that is served).
  for (const file of ['prevalence.json', 'spatial.json', 'poverty.json']) {
    const data = await (await request.get(`data/${file}`)).json();
    for (const key of Object.keys(data)) {
      await expect(page.locator(`th#${anchor(file)}--${anchor(key)}`), `${file} ${key}`).toHaveCount(1);
    }
  }
  // Every linked data file is served; JONAPWD's files are named but not linked.
  const links = await page.locator('main a[href^="./data/"]').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(links.length).toBe(FILES.length - 2);
  for (const href of links) expect((await request.get(href)).status(), href).toBe(200);
  await expect(page.locator('main a[href*="data/jonapwd"]')).toHaveCount(0);
  // Units and the conventions the brief asks for.
  const text = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  expect(text).toContain('proportion (0 to 1)');
  expect(text).toContain('percent (0 to 100)');
  expect(text).toContain('JONAPWD\'s figures are an assumption, not a count');
  expect(text).toContain('fewer than 30');
  await expect(page.locator('main a[href="https://curb-cut-api.onrender.com/docs"]')).toHaveCount(1);
});

test('data dictionary: no script and nothing hidden, so the browser\'s find reaches it all', async ({ page }) => {
  await open(page);
  expect(await page.evaluate(() => document.scripts.length)).toBe(0);
  await expect(page.locator('details, [hidden]')).toHaveCount(0);
  expect(await page.locator('[onclick], [onmouseover], [onmousedown]').count()).toBe(0);
  // Names wrap at <wbr> after "_" and "."; find still matches them whole.
  for (const name of ['share_of_national', 'precision_reason', 'summary.{analysis}.{item_id}.value_text']) {
    expect(await page.evaluate((n) => window.find(n), name), name).toBe(true);
  }
});

test('data dictionary: keyboard reaches every link and table caption in order, with no trap', async ({ page }) => {
  await open(page);
  const expected = await page.evaluate(() =>
    [...document.querySelectorAll('a[href], [tabindex="0"]')]
      .filter((el) => el.checkVisibility())
      .map((el) => el.outerHTML.slice(0, 90)),
  );
  expect(expected.filter((h) => h.startsWith('<caption tabindex="0"')).length).toBe(13);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  const reached = [];
  for (let i = 0; i < expected.length; i += 1) {
    reached.push(await page.evaluate(() => document.activeElement.outerHTML.slice(0, 90)));
    await page.keyboard.press('Tab');
  }
  expect(reached).toEqual(expected);
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
});

test('data dictionary: headings in order, captions and scoped headers, no sideways scroll at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await open(page);
  expect(await page.getAttribute('html', 'lang')).toMatch(/^en\b/);
  for (const role of ['banner', 'main', 'contentinfo']) await expect(page.getByRole(role)).toHaveCount(1);
  await expect(page.getByRole('navigation', { name: 'Site' })).toBeVisible();
  const levels = await page.evaluate(() =>
    [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].map((h) => Number(h.tagName[1])),
  );
  expect(levels[0]).toBe(1);
  expect(levels.filter((l) => l === 1)).toHaveLength(1);
  levels.forEach((level, i) => {
    if (i > 0) expect(level - levels[i - 1]).toBeLessThanOrEqual(1);
  });
  const tables = await page.evaluate(() =>
    [...document.querySelectorAll('table')].map((t) => ({
      caption: t.querySelector('caption')?.textContent.trim() ?? '',
      tabStop: t.querySelector('caption')?.getAttribute('tabindex') === '0',
      wrapped: t.parentElement.classList.contains('table-wrap') && !t.parentElement.hasAttribute('tabindex'),
      unscoped: [...t.querySelectorAll('th')].filter((th) => !['col', 'row'].includes(th.scope)).length,
    })),
  );
  expect(tables).toHaveLength(13);
  for (const t of tables) expect(t).toEqual({ ...t, tabStop: true, wrapped: true, unscoped: 0 });
  expect(tables.every((t) => t.caption !== '')).toBe(true);
  const overflow = () =>
    page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await overflow()).toBeLessThanOrEqual(0);
  // Fonts differ by platform (Linux CI's fallback is wider than Windows'): long names must
  // still wrap with wider letters, so a pass here does not depend on the machine's fonts.
  await page.addStyleTag({ content: 'main * { letter-spacing: 0.12em; }' });
  expect(await overflow()).toBeLessThanOrEqual(0);
});

test('data dictionary: within the byte budget, everything from this origin', async ({ page, baseURL }) => {
  const origin = new URL(baseURL).origin;
  const responses = [];
  page.on('response', (r) => responses.push(r));
  await open(page);
  await page.waitForLoadState('networkidle');
  let total = 0;
  let html = 0;
  for (const r of responses) {
    const url = r.url();
    expect(url.startsWith(origin) || url.startsWith('data:'), url).toBe(true);
    if (!url.startsWith(origin)) continue;
    const bytes = (await r.body()).length;
    total += bytes;
    if (r.request().resourceType() === 'document') html = bytes;
  }
  console.log(`data dictionary: HTML ${html} bytes, total ${total} bytes`);
  expect(html).toBeGreaterThan(0);
  expect(html).toBeLessThanOrEqual(HTML_BUDGET);
  expect(total).toBeLessThanOrEqual(TOTAL_BUDGET);
});

test('every other page links the data dictionary', async ({ page }) => {
  for (const path of ['./', 'methodology.html', 'poverty.html']) {
    await page.goto(path);
    const nav = page.getByRole('navigation', { name: 'Site' });
    await expect(nav.getByRole('link', { name: 'Data dictionary' }), path).toHaveAttribute('href', './data-dictionary.html');
  }
  for (const path of ['states/', 'states/kano.html']) {
    await page.goto(path);
    const link = page.locator('footer.site-footer').getByRole('link', { name: /Data dictionary/ });
    await expect(link, path).toHaveAttribute('href', '../data-dictionary.html');
  }
  await page.getByRole('link', { name: /Data dictionary/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Data dictionary');
});
