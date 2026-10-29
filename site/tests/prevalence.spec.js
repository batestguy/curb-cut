// The measured figures (P4a, P4b): headline, comparison, prevalence map with pattern
// fills, dot plot with its statistical findings, spatial findings, the state card's DHS
// figure, and the methodology page.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// No claim to be first (docs/verification.md D46): "the first", "first of", "first-ever",
// "world's first" and the like. "The first query" (the explorer's loading note) is not a claim.
const FIRST_CLAIM =
  /\b(?:the|world['’]s)\s+first\b(?!\s+query\b)|\bfirst[\s-]+ever\b|\bfirst\s+of\b|\bfirst\s+(?:measured|state|estimates?|figures?)\b/i;

// Expected figures hard-coded from data/public/aggregates/dhs2024_*.csv (DISABILITY3, 18+,
// both sexes), so a wrong export cannot pass by agreeing with itself.
// National: 0.030087 (0.028315 to 0.031938). Kano (NG-KN): 0.045929 (0.036115 to 0.057482).
const NATIONAL = { estimate: '3.0%', low: '2.8%', high: '3.2%' };
const KANO = { estimate: '4.6%', low: '3.6%', high: '5.7%' };

async function ready(page) {
  await page.goto('./');
  await expect(page.locator('#prevalence-map svg')).toBeVisible();
  await expect(page.locator('#prevalence-chart svg').first()).toBeVisible();
  await expect(page.locator('#comparison-list li')).toHaveCount(5);
  await expect(page.locator('#moran-sentence')).not.toBeEmpty();
  await expect(page.locator('#state-select')).toBeEnabled();
}

async function chooseState(page, state) {
  await page.locator('#state-select').selectOption(state);
  await page.getByRole('button', { name: 'Show figures' }).click();
  await expect(page.locator('#state-table table')).toBeVisible({ timeout: 30_000 });
}

test('the page leads with the measured national figure, with its interval', async ({ page }) => {
  await ready(page);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    "Disability in Nigeria's states, as measured by the DHS 2024 survey",
  );
  const headline = page.locator('#headline');
  await expect(headline).toContainText(
    `${NATIONAL.estimate} of adults aged 18 and over living in households in Nigeria`,
  );
  await expect(headline).toContainText(
    `95% confidence interval ${NATIONAL.low} to ${NATIONAL.high}`,
  );
  // JONAPWD's assumed figures come after the measured ones, framed as an assumption.
  const order = await page.evaluate(() => {
    const map = document.getElementById('map-heading');
    const jonapwd = document.getElementById('jonapwd-heading');
    return Boolean(map.compareDocumentPosition(jonapwd) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(order).toBe(true);
  await expect(page.locator('#jonapwd-heading')).toHaveText(
    "What was assumed: JONAPWD's 2025 estimates",
  );
  await expect(page.locator('body')).not.toContainText(FIRST_CLAIM);
});

test('the comparison uses verified figures only, each with a source', async ({ page }) => {
  await ready(page);
  const items = page.locator('#comparison-list li');
  await expect(items.nth(0)).toContainText('JONAPWD 2025: 15%');
  await expect(items.nth(0)).toContainText('Nobody was counted');
  await expect(items.nth(1)).toContainText('WHO global estimate: 16%');
  await expect(items.nth(1)).toContainText('does not define');
  // 100 - 84.5 (no difficulty) - 0.0 (don't know), computed in the warehouse.
  await expect(items.nth(2)).toContainText('any difficulty: 15.5%');
  await expect(items.nth(3)).toContainText('Washington Group cut-off: 2.8%');
  await expect(items.nth(4)).toContainText(/adults 18\+: 3\.0% \(95% confidence interval/);
  for (let i = 0; i < 5; i += 1) {
    await expect(items.nth(i).getByRole('link')).toHaveCount(1);
  }
  await expect(page.locator('#comparison-message')).toContainText(
    'mostly about the definition',
  );
  await expect(page.locator('#comparison-message')).toContainText('not a contradiction');
  // The spec's unsourced range is gone.
  await expect(page.locator('main')).not.toContainText(/10\s*[–-]\s*18%/);
});

test('the map is one image named by its data-derived alt-text, with no state Tab stops', async ({
  page,
  request,
}) => {
  const doc = await (await request.get('data/charts/prevalence_map.json')).json();
  expect(doc.audit.passed).toBe(true);
  await ready(page);
  const map = page.locator('#prevalence-map');
  await expect(map).toHaveAttribute('role', 'img');
  await expect(map).toHaveAccessibleName(doc.alt_text);
  await expect(map.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  await expect(map.locator('path[data-state]')).toHaveCount(37);
  await expect(map.locator('[tabindex]')).toHaveCount(0);
  // The legend gives every class in words, and the classes cover all 37 states.
  const legend = page.locator('#prevalence-map-legend li');
  await expect(legend).toHaveCount(doc.classes.length);
  for (const [i, c] of doc.classes.entries()) {
    await expect(legend.nth(i)).toHaveText(`${c.label}: ${c.count} states`);
    // Each swatch shows its class's pattern (hidden from assistive technology).
    const swatch = legend.nth(i).locator('svg.swatch');
    await expect(swatch).toHaveAttribute('data-pattern', c.pattern);
    await expect(swatch).toHaveAttribute('aria-hidden', 'true');
  }
  expect(doc.classes.reduce((sum, c) => sum + c.count, 0)).toBe(37);
  expect(doc.classes.every((c) => c.count > 0)).toBe(true);
  // No hotspot outlines, and the page says why.
  await expect(page.locator('#lisa-sentence')).toContainText('no hotspot outlines');
});

for (const colorScheme of ['light', 'dark']) {
  test(`each map class has its own pattern, in the audited ink (${colorScheme})`, async ({
    page,
    request,
  }) => {
    const doc = await (await request.get('data/charts/prevalence_map.json')).json();
    expect(doc.audit.passed).toBe(true);
    const ids = doc.classes.map((c) => c.pattern);
    expect(new Set(ids).size).toBe(doc.classes.length); // one pattern per class
    await page.emulateMedia({ colorScheme });
    await ready(page);
    const map = page.locator('#prevalence-map');
    await expect(map.locator('svg pattern')).toHaveCount(doc.classes.length);
    // Every state is filled with its class's pattern.
    const fills = await map.locator('path[data-state]').evaluateAll((paths) =>
      paths.map((p) => [p.dataset.state, p.style.fill]),
    );
    const classOf = new Map(doc.regions.map((r) => [r.code, r.class]));
    for (const [code, fill] of fills) {
      expect(fill).toContain(`prevalence_map-pattern-${classOf.get(code)}`);
    }
    // The ink drawn is the document's ink for this scheme.
    const ink = await map
      .locator('svg pattern path.tile')
      .first()
      .evaluate((el) => getComputedStyle(el).fill);
    const hex = doc.patterns.ink[colorScheme];
    const rgb = `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`;
    expect(ink).toBe(rgb);
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('the findings under the dot plot are plain text from the document, after the chart', async ({
  page,
  request,
}) => {
  const doc = await (await request.get('data/charts/prevalence_by_state.json')).json();
  const findings = doc.findings;
  expect(doc.audit.passed).toBe(true);
  expect(doc.audit.checks.filter((c) => c.id.startsWith('findings-') && !c.passed)).toEqual([]);
  await ready(page);
  const block = page.locator('#prevalence-chart-findings');
  await expect(block.getByRole('heading', { level: 4 })).toHaveText(
    'Which differences the survey can show',
  );
  // The count line, as the library wrote it: 'N comparisons checked, K supported.'
  await expect(block.locator('.findings-count')).toHaveText(findings.lines.count);
  await expect(block.locator('.findings-count')).toHaveText(
    /^\d+ comparisons? checked, \d+ supported\.$/,
  );
  const items = block.locator('.findings-list li');
  await expect(items).toHaveCount(findings.statements.length);
  for (const [i, s] of findings.statements.entries()) {
    await expect(items.nth(i)).toHaveText(s.text);
  }
  // The list is named by the heading; nothing in the block is a live region, so it is
  // read in order, not announced over the page.
  await expect(block.locator('.findings-list')).toHaveAccessibleName(
    'Which differences the survey can show',
  );
  await expect(block.locator('[aria-live], [role="status"], [role="alert"]')).toHaveCount(0);
  // The method, with the false discovery rate and the source, one click away.
  await block.locator('details summary').click();
  await expect(block.locator('.findings-method')).toContainText('false discovery rate 5%');
  await expect(block.locator('.findings-method')).toContainText(`Source: ${doc.meta.source}.`);
  await expect(block.locator('.findings-families li').first()).toContainText('checked');
  // After the chart, before its table.
  const order = await page.evaluate(() => {
    const chart = document.getElementById('prevalence-chart');
    const f = document.getElementById('prevalence-chart-findings');
    const table = document.getElementById('prevalence-chart-table');
    const after = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    return after(chart, f) && after(f, table);
  });
  expect(order).toBe(true);
  // Hedged wording only: no causes, no 'first', no unqualified 'significant'.
  await expect(block).not.toContainText(FIRST_CLAIM);
  await expect(block).not.toContainText(/\bsignificant|\bcaused by\b|\bbecause of\b/i);
  // The dot-plot table shows each state's precision flag.
  await expect(page.locator('#prevalence-chart-table thead th').last()).toHaveText('Precision');
});

test('the map tip shows on hover, tap and focus; it can be hovered and Esc closes it', async ({
  page,
}) => {
  await ready(page);
  const map = page.locator('#prevalence-map');
  const tip = page.locator('.choropleth-figure .map-tip');
  await expect(tip).toBeHidden();

  await map.locator('path[data-state="NG-KN"]').hover();
  await expect(tip).toBeVisible();
  await expect(tip).toContainText('Kano');
  await expect(tip).toContainText('95% confidence interval');
  await expect(tip).toContainText('Map class: 4% to under 6%');
  await tip.hover(); // the pointer can move onto the tip
  await expect(tip).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(tip).toBeHidden();

  // Tap or click shows it; leaving the map closes it.
  await page.mouse.move(0, 0);
  await map.locator('path[data-state="NG-TA"]').click();
  await expect(tip).toContainText('Taraba');
  await page.mouse.move(0, 0);
  await expect(tip).toBeHidden();

  // Keyboard focus with no state chosen: a hint pointing to the table and the picker.
  await page.locator('#dots-heading').scrollIntoViewIfNeeded();
  await map.focus();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Tab');
  await expect(map).toBeFocused();
  await expect(tip).toContainText('state picker');
  await page.keyboard.press('Escape');
  await expect(tip).toBeHidden();
});

test('a state chosen in the explorer is outlined on the map and shown on focus', async ({
  page,
}) => {
  await ready(page);
  await chooseState(page, 'Lagos');
  const map = page.locator('#prevalence-map');
  await expect(map.locator('path.selected')).toHaveCount(1);
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-LA');
  await map.focus();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Tab');
  await expect(page.locator('.choropleth-figure .map-tip')).toContainText('Lagos');
  await chooseState(page, 'Kano');
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-KN');
});

test('the map table and the dot plot table hold every state, with scoped headers', async ({
  page,
  request,
}) => {
  const dots = await (await request.get('data/charts/prevalence_by_state.json')).json();
  expect(dots.audit.passed).toBe(true);
  await ready(page);
  const mapTable = page.locator('#prevalence-map-table table');
  await expect(mapTable.locator('caption')).not.toBeEmpty();
  await expect(mapTable.locator('thead th[scope="col"]')).toHaveCount(6);
  await expect(mapTable.locator('tbody th[scope="row"]')).toHaveCount(37);
  await expect(mapTable.locator('tbody th').first()).toHaveText('Abia'); // by name
  await expect(mapTable.getByRole('row', { name: /^Taraba/ })).toContainText('6% and over');

  const chart = page.locator('#prevalence-chart');
  await expect(chart).toHaveAttribute('role', 'img');
  await expect(chart).toHaveAccessibleName(dots.alt_text);
  const dotTable = page.locator('#prevalence-chart-table table');
  await expect(dotTable.locator('tbody th[scope="row"]')).toHaveCount(37);
  await expect(dotTable.locator('tbody th').first()).toHaveText('Taraba'); // highest first
});

test('the spatial findings are sentences, with cluster members sorted by name', async ({
  page,
  request,
}) => {
  const spatial = await (await request.get('data/spatial.json')).json();
  await ready(page);
  await expect(page.locator('#moran-sentence')).toHaveText(spatial.moran[0].sentence);
  expect(spatial.moran[0].measure).toBe('disability3');
  expect(spatial.moran[0].age_group).toBe('18+');
  await page.locator('#spatial-heading ~ details.more summary').click();
  await expect(page.locator('#moran-table table tbody tr')).toHaveCount(8);
  await expect(page.locator('#moran-sentences li')).toHaveCount(7);
  await expect(page.locator('#lisa-detail')).toHaveText(spatial.lisa.sentence);
  const lists = page.locator('#cluster-groups ul');
  await expect(lists).toHaveCount(spatial.clusters.groups.length);
  for (let i = 0; i < spatial.clusters.groups.length; i += 1) {
    const names = await lists.nth(i).locator('li').allTextContents();
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)));
  }
  await expect(page.locator('#services-sentence')).toContainText('Ecological');
  // Spatial wording never touches JONAPWD.
  const jonapwd = page.locator('section', { has: page.locator('#jonapwd-heading') });
  await expect(jonapwd).not.toContainText(/Moran|hotspot|clustered/i);
});

test('the state card adds the DHS 2024 figure and the national one', async ({ page }) => {
  await ready(page);
  await chooseState(page, 'Kano');
  const facts = page.locator('#state-card .facts');
  await expect(facts).toContainText(
    `${KANO.estimate} (95% confidence interval ${KANO.low} to ${KANO.high}); precision: reliable`,
  );
  await expect(facts).toContainText('Nigeria, for comparison');
  await expect(facts).toContainText(NATIONAL.estimate);
  await expect(page.getByRole('heading', { level: 3, name: 'Kano' })).toBeFocused();
});

test('if the map fails, the failure is shown and announced, and the rest still works', async ({
  page,
}) => {
  await page.route('**/charts/prevalence_map.json', (route) => route.abort());
  await page.goto('./');
  const status = page.locator('#prevalence-map-status');
  await expect(status).toHaveAttribute('role', 'status');
  await expect(status).toContainText('The map could not be loaded');
  await expect(page.locator('#prevalence-map')).toHaveAccessibleName(/could not be loaded/);
  await expect(page.locator('#prevalence-map')).not.toHaveAttribute('tabindex');
  await expect(page.locator('#prevalence-chart svg').first()).toBeVisible();
  await expect(page.locator('#prevalence-chart-table table')).toBeVisible();
});

test('if the national figures fail, the failure is shown and announced', async ({ page }) => {
  await page.route('**/data/prevalence.json', (route) => route.abort());
  await page.goto('./');
  await expect(page.locator('#headline-status')).toHaveAttribute('role', 'status');
  await expect(page.locator('#headline-status')).toContainText('could not be loaded');
  await expect(page.locator('#comparison-status')).toContainText('could not be loaded');
  await expect(page.locator('#prevalence-map svg')).toBeVisible();
  // The explorer still works, without the national line on the card.
  await chooseState(page, 'Oyo');
  await expect(page.locator('#state-card .facts')).toContainText('DHS 2024');
  await expect(page.locator('#state-card .facts')).not.toContainText('Nigeria, for comparison');
});

test('if the spatial findings fail, the failure is shown and announced', async ({ page }) => {
  await page.route('**/data/spatial.json', (route) => route.abort());
  await page.goto('./');
  await expect(page.locator('#spatial-status')).toHaveAttribute('role', 'status');
  await expect(page.locator('#spatial-status')).toContainText('could not be loaded');
  await expect(page.locator('#prevalence-map svg')).toBeVisible();
});

test('at 320px the map fits and wide tables scroll inside a named region', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await ready(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const box = await page.locator('#prevalence-map svg').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  // A table wider than the screen is a focusable, named region (so it can be scrolled by key).
  const wraps = await page.locator('.table-wrap').evaluateAll((els) =>
    els.map((el) => ({
      scrolls: el.scrollWidth > el.clientWidth + 1,
      focusable: el.tabIndex === 0,
      named: Boolean(el.getAttribute('aria-label')),
    })),
  );
  for (const w of wraps.filter((x) => x.scrolls)) {
    expect(w.focusable && w.named).toBe(true);
  }
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations).toEqual([]);
});

for (const colorScheme of ['light', 'dark']) {
  test(`the methodology page has no WCAG A/AA violations (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto('./methodology.html');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      'Methodology: definitions, sources and limits',
    );
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('the methodology page is linked from the page and the footer, and covers the rules', async ({
  page,
}) => {
  await ready(page);
  await expect(page.locator('main a[href="./methodology.html"]').first()).toBeVisible();
  await expect(page.locator('footer a[href="./methodology.html"]')).toHaveCount(1);
  await page.locator('footer a[href="./methodology.html"]').click();
  await expect(page).toHaveURL(/methodology\.html$/);
  for (const id of ['definition-heading', 'disclosure-heading', 'precision-heading', 'small-area', 'spatial', 'sources-heading', 'new-heading']) {
    await expect(page.locator(`#${id}`)).toBeVisible();
  }
  const main = page.locator('main');
  await expect(main).toContainText('15.5%');
  await expect(main).toContainText('complementary suppression');
  await expect(main).toContainText('49 people');
  await expect(main).toContainText('No spatial analysis is made of JONAPWD');
  await expect(page.locator('body')).not.toContainText(FIRST_CLAIM);
});
