// The 37 state pages (P4b step 13): plain HTML built by
// packages/transform/scripts/build_state_pages.py, with no script, no Plotly and no DuckDB.
import { readdirSync } from 'node:fs';
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// The same "first" check as prevalence.spec.js (docs/verification.md D46).
const FIRST_CLAIM =
  /\b(?:the|world['’]s)\s+first\b(?!\s+query\b)|\bfirst[\s-]+ever\b|\bfirst\s+of\b|\bfirst\s+(?:measured|state|estimates?|figures?)\b/i;

// Three states: Kano (figures hard-coded below), Edo (one state x wealth cell suppressed for
// too few respondents, two more withheld so it can't be worked out) and Lagos (one of each, a
// wealth group with no respondents, and estimates under 0.05%).
const STATES = ['kano', 'edo', 'lagos'];

// Every built state page (site/states/*.html, from build_state_pages.py), for the budget.
const ALL_SLUGS = readdirSync(new URL('../states/', import.meta.url))
  .filter((f) => f.endsWith('.html') && f !== 'index.html')
  .map((f) => f.slice(0, -5));

// Kano, hard-coded from the public aggregates so a wrong build cannot pass by agreeing with
// itself: data/public/aggregates/dhs2024_state.csv (NG-KN; DISABILITY3 unless named),
// mpi2021_state_national.csv, packages/transform/seeds/state_facts.csv and
// state_population_by_sex_2023.csv, and JONAPWD's per-type figures summed.
const KANO = {
  headline:
    'In Kano, the DHS 2024 survey estimates that 4.6% of adults aged 18 and over living in ' +
    'households (95% confidence interval 3.6% to 5.7%) have a lot of difficulty with, or ' +
    'cannot do at all, at least one of six everyday activities; for Nigeria as a whole the ' +
    'figure is 3.0%.',
  rows: {
    'Adults 18+': ['4.6', '3.6', '5.7', 'Reliable'], // 0.045929 (0.036115 to 0.057482)
    'Women 18+': ['4.2', '3.1', '5.6', 'Reliable'], // 0.042227 (0.031114 to 0.055871)
    'Men 18+': ['5.0', '3.8', '6.4', 'Reliable'], // 0.049962 (0.037982 to 0.064358)
    'Children 5–17': ['2.8', '1.9', '3.8', 'Reliable'], // 0.027779 (0.019436 to 0.038406)
    Urban: ['4.4', '2.8', '6.6', 'Reliable'], // 0.043961 (0.027784 to 0.065746)
    Rural: ['4.7', '3.5', '6.2', 'Reliable'], // 0.047375 (0.035110 to 0.062359)
  },
  walking: ['2.3', '1.7', '3.0'], // walking_3plus 0.02271 (0.016996 to 0.029689)
  mpiSeeing: ['0.9', '0.6', '1.3', 'Reliable'], // mpi_screener_seeing_any 0.009013
  population: ['15,671,491', '7,423,495', '8,247,996'],
  jonapwd: '2,514,444',
};

async function open(page, slug) {
  await page.goto(`states/${slug}.html`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

const VIEWS = [
  ['light', null],
  ['dark', null],
  ['light', 320],
];

for (const [colorScheme, width] of VIEWS) {
  const view = width ? `${colorScheme}, ${width}px` : colorScheme;
  for (const slug of STATES) {
    test(`${slug}: axe finds no WCAG A/AA violations (${view})`, async ({ page }) => {
      if (width) await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ colorScheme });
      await open(page, slug);
      for (const summary of await page.locator('details summary').all()) await summary.click();
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}

for (const colorScheme of ['light', 'dark']) {
  test(`the state index: axe finds no WCAG A/AA violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto('states/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('State pages');
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('Kano: the figures match the public aggregates', async ({ page }) => {
  await open(page, 'kano');
  await expect(page).toHaveTitle('Disability in Kano: Curb Cut');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en-NG');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Disability in Kano');
  await expect(page.locator('#headline')).toHaveText(KANO.headline);
  for (const [label, cells] of Object.entries(KANO.rows)) {
    const row = page.getByRole('row', { name: new RegExp(`^${label}\\b`) });
    await expect(row.locator('td')).toHaveText(cells);
  }
  const chartTable = page.locator('table').filter({
    has: page.locator('caption', { hasText: 'Adults 18+ in Kano with a lot of difficulty' }),
  });
  const walking = chartTable.getByRole('row', { name: /^Walking or climbing steps/ });
  await expect(walking.locator('td').nth(0)).toHaveText(KANO.walking[0]);
  await expect(walking.locator('td').nth(1)).toHaveText(KANO.walking[1]);
  await expect(walking.locator('td').nth(2)).toHaveText(KANO.walking[2]);
  const mpi = page.getByRole('row', { name: /^Seeing: any difficulty/ });
  await expect(mpi.locator('td')).toHaveText(KANO.mpiSeeing);
  const facts = page.locator('#about-heading + .state-card-body .facts');
  for (const n of KANO.population) await expect(facts).toContainText(n);
  await expect(page.locator('main')).toContainText(`${KANO.jonapwd} people with disabilities`);
  // The share image's alt text and the page's headline are the same sentence.
  await expect(page.locator('meta[property="og:image:alt"]')).toHaveAttribute(
    'content',
    KANO.headline,
  );
});

test('Kano: the activity chart is the library document drawn as SVG, named by its alt-text', async ({
  page,
  request,
}) => {
  const doc = await (await request.get('data/charts/states/kano.json')).json();
  expect(doc.audit.passed).toBe(true);
  expect(doc.meta.generator).toBe('disability_access_charts.plots.dot');
  await open(page, 'kano');
  const chart = page.locator('.dot-holder');
  await expect(chart).toHaveAttribute('role', 'img');
  await expect(chart).toHaveAccessibleName(doc.alt_text);
  await expect(chart.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  // One series (the state alone), one dot and one interval per activity, every value labelled
  // directly; above 0 but under 0.05 reads "<0.1".
  expect(doc.data.series.map((s) => s.name)).toEqual(['Kano']);
  const values = doc.data.series[0].values;
  const label = (v) => (v > 0 && v < 0.05 ? '<0.1%' : `${v.toFixed(1)}%`);
  await expect(chart.locator('circle.dot-s0.dot-mark')).toHaveCount(values.length);
  await expect(chart.locator('.dot-whisker')).toHaveCount(values.length);
  await expect(chart.locator('.dot-value')).toHaveText(values.map(label));
  // The findings compare only Kano's own activities, never Nigeria with itself.
  const named = doc.findings.comparisons.flatMap((c) => [c.a.series, c.b.series]);
  expect(new Set(named)).toEqual(new Set(['Kano']));
  expect(doc.alt_text).not.toContain('Nigeria as a whole');
  await expect(page.locator('.findings-count')).toHaveText(doc.findings.lines.count);
  await expect(page.locator('caption').filter({ hasText: doc.table.caption })).toHaveCount(1);
});

test('the chart colours follow the colour scheme', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await open(page, 'kano');
  const fill = () =>
    page.locator('.dot-holder circle.dot-s0').first().evaluate((el) => getComputedStyle(el).fill);
  expect(await fill()).toBe('rgb(0, 114, 178)'); // #0072b2, the light theme's first series
  await page.emulateMedia({ colorScheme: 'dark' });
  expect(await fill()).toBe('rgb(230, 159, 0)'); // #e69f00, the dark theme's first series
});

test('Edo: suppressed cells are named, never shown as numbers', async ({ page }) => {
  await open(page, 'edo');
  await page.getByText("Edo's own figures by wealth").click();
  const table = page.locator('details table');
  await expect(table.locator('caption')).toHaveText(
    'Disability among adults in Edo by household wealth, DHS 2024. Low and High: the 95% confidence interval.',
  );
  // From precision_reason: under 30 respondents, or complementary suppression (D49).
  const reasons = {
    'Poorest fifth': 'not shown: too few respondents',
    'Second fifth': "not shown: withheld so a neighbouring small cell can't be worked out",
    'Middle fifth': "not shown: withheld so a neighbouring small cell can't be worked out",
  };
  for (const [label, text] of Object.entries(reasons)) {
    await expect(table.getByRole('row', { name: new RegExp(`^${label}`) }).locator('td')).toHaveText([
      text,
    ]);
  }
  // The zone's figures are shown first, and say why.
  await expect(page.locator('#wealth-heading ~ p').first()).toContainText('South South zone');
});

test('every state page builds, links from the index, and makes no "first" claim', async ({
  page,
  request,
}) => {
  await page.goto('states/');
  const links = page.locator('.state-links a');
  await expect(links).toHaveCount(37);
  const hrefs = await links.evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(new Set(hrefs).size).toBe(37);
  for (const href of hrefs) {
    const response = await request.get(`states/${href.replace('./', '')}`);
    expect(response.status(), href).toBe(200);
    const text = (await response.text()).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
    expect(text, href).not.toMatch(FIRST_CLAIM);
    expect(text, href).toContain('has not yet been tested by a regular screen-reader user');
  }
  await expect(page.locator('body')).not.toContainText(FIRST_CLAIM);
});

test('meta tags: absolute share URLs, and the share image exists', async ({ page, request }) => {
  await open(page, 'akwa-ibom');
  const content = (selector) => page.locator(selector).getAttribute('content');
  const site = 'https://batestguy.github.io/curb-cut/';
  expect(await content('meta[property="og:url"]')).toBe(`${site}states/akwa-ibom.html`);
  expect(await content('meta[property="og:image"]')).toBe(`${site}share/akwa-ibom.png`);
  expect(await content('meta[name="twitter:card"]')).toBe('summary_large_image');
  expect(await content('meta[property="og:image:alt"]')).toBe(
    await page.locator('#headline').textContent(),
  );
  await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /Akwa Ibom/);
  const image = await request.get('share/akwa-ibom.png');
  expect(image.status()).toBe(200);
  expect(image.headers()['content-type']).toBe('image/png');
});

test('keyboard: skip link first, then every link and control in order, with no trap', async ({
  page,
}) => {
  await open(page, 'lagos');
  // The page has no script, so nothing can react to the mouse alone.
  expect(await page.evaluate(() => document.scripts.length)).toBe(0);
  expect(await page.locator('[onclick], [onmouseover], [onmousedown]').count()).toBe(0);
  // Every link, summary and table region that is rendered (the closed <details> hides its
  // table), in document order.
  const expected = await page.evaluate(() =>
    [...document.querySelectorAll('a[href], summary, [tabindex="0"]')]
      .filter((el) => el.checkVisibility())
      .map((el) => el.outerHTML.slice(0, 80)),
  );
  expect(expected.filter((h) => h.includes('role="region"')).length).toBeGreaterThanOrEqual(6);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  const reached = [];
  for (let i = 0; i < expected.length; i += 1) {
    reached.push(await page.evaluate(() => document.activeElement.outerHTML.slice(0, 80)));
    await page.keyboard.press('Tab');
  }
  expect(reached).toEqual(expected);
  // The skip link moves focus to <main>.
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  // The details opens from the keyboard.
  const summary = page.locator('summary', { hasText: "Lagos's own figures by wealth" });
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('details', { has: summary })).toHaveAttribute('open', '');
});

test('headings in order, tables with captions and scoped headers, no sideways scroll at 320px', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  for (const slug of STATES) {
    await open(page, slug);
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
        unscoped: [...t.querySelectorAll('th')].filter((th) => !['col', 'row'].includes(th.scope))
          .length,
      })),
    );
    expect(tables.length).toBeGreaterThanOrEqual(6);
    for (const t of tables) {
      expect(t.caption).not.toBe('');
      expect(t.unscoped).toBe(0);
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, slug).toBeLessThanOrEqual(0);
    // A table that scrolls sideways must be reachable by keyboard: a focusable, named region.
    const wraps = await page.evaluate(() =>
      [...document.querySelectorAll('.table-wrap')].map((w) => ({
        scrolls: w.scrollWidth > w.clientWidth,
        focusable: w.getAttribute('tabindex') === '0' && w.getAttribute('role') === 'region',
        named: Boolean(w.getAttribute('aria-label')),
      })),
    );
    for (const w of wraps) if (w.scrolls) expect(w, slug).toEqual({ ...w, focusable: true, named: true });
  }
});

// About a second on a phone: a small HTML document and a small total, all from this origin.
const HTML_BUDGET = 60 * 1024;
const TOTAL_BUDGET = 150 * 1024;

test('all 37 state pages were built', () => {
  expect(ALL_SLUGS).toHaveLength(37);
});

for (const slug of ALL_SLUGS) {
  test(`${slug}: within the byte budget, with no Plotly or DuckDB`, async ({ page, baseURL }) => {
    const origin = new URL(baseURL).origin;
    const responses = [];
    page.on('response', (r) => responses.push(r));
    await open(page, slug);
    await page.waitForLoadState('networkidle');
    let total = 0;
    let html = 0;
    for (const r of responses) {
      const url = r.url();
      expect(url.startsWith(origin) || url.startsWith('data:'), url).toBe(true);
      expect(url).not.toMatch(/plotly|duckdb/i);
      if (!url.startsWith(origin)) continue;
      const bytes = (await r.body()).length;
      total += bytes;
      if (r.request().resourceType() === 'document') html = bytes;
    }
    console.log(`${slug}: HTML ${html} bytes, total ${total} bytes`);
    expect(html).toBeGreaterThan(0);
    expect(html).toBeLessThanOrEqual(HTML_BUDGET);
    expect(total).toBeLessThanOrEqual(TOTAL_BUDGET);
  });
}

test('links in: the main page links to the state pages, from the text and the map table', async ({
  page,
  request,
}) => {
  await page.goto('./');
  await expect(page.getByRole('link', { name: 'all 37 state pages' })).toHaveAttribute(
    'href',
    './states/',
  );
  const rows = page.locator('#prevalence-map-table tbody th a');
  await expect(rows).toHaveCount(37);
  for (const href of await rows.evaluateAll((as) => as.map((a) => a.getAttribute('href')))) {
    expect((await request.get(href)).status(), href).toBe(200);
  }
  await page.locator('#prevalence-map-table').getByRole('link', { name: 'Federal Capital Territory' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Disability in the Federal Capital Territory',
  );
  // The breadcrumb leads back.
  await page.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('link', { name: 'Curb Cut' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    "Disability in Nigeria's states, as measured by the DHS 2024 survey",
  );
});

test('links in: the state card links to the state page', async ({ page }) => {
  await page.goto('./');
  await expect(page.locator('#state-select')).toBeEnabled();
  await page.locator('#state-select').selectOption('Akwa Ibom');
  await page.getByRole('button', { name: 'Show figures' }).click();
  const link = page.locator('#state-card').getByRole('link', { name: "Akwa Ibom's own page" });
  await expect(link).toBeVisible({ timeout: 30_000 });
  await link.click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Disability in Akwa Ibom');
});
