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

// A hex colour as the browser reports a computed fill or stroke.
function rgb(hex) {
  return `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`;
}

for (const colorScheme of ['light', 'dark']) {
  test(`the map draws the audited fills, patterns, inks and cased boundaries (${colorScheme})`, async ({
    page,
    request,
  }) => {
    const doc = await (await request.get('data/charts/prevalence_map.json')).json();
    expect(doc.audit.passed).toBe(true);
    expect(doc.meta.scheme).toBe('ylgnbu');
    // Patterns by ink weight, lowest class lightest; one pattern per class.
    const ids = doc.classes.map((c) => c.pattern);
    expect(ids).toEqual(['plain', 'dots', 'lines', 'crosshatch', 'solid']);
    const theme = doc.themes[colorScheme];
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
    // Each pattern draws the class's fill from the document, and the class's own ink in front
    // (no ink for plain and solid).
    const drawn = await map.locator('svg pattern').evaluateAll((patterns) =>
      patterns.map((p) => {
        const tile = p.querySelector('path.tile');
        return {
          id: p.id,
          pattern: p.dataset.pattern,
          fill: getComputedStyle(p.querySelector('rect')).fill,
          ink: tile ? getComputedStyle(tile).fill : null,
        };
      }),
    );
    expect(drawn).toHaveLength(doc.classes.length);
    for (const [k, d] of drawn.entries()) {
      expect(d.id).toBe(`prevalence_map-pattern-${k}`);
      expect(d.pattern).toBe(ids[k]);
      expect(d.fill).toBe(rgb(theme.classes[k]));
      const ink = doc.patterns.class_ink[colorScheme][k];
      expect(d.ink).toBe(ink ? rgb(ink) : null);
    }
    // The legend swatches draw the same fills and inks.
    const swatches = await page.locator('#prevalence-map-legend svg.swatch').evaluateAll((svgs) =>
      svgs.map((svg) => {
        const tile = svg.querySelector('path.tile');
        return {
          fill: getComputedStyle(svg.querySelector('pattern rect')).fill,
          ink: tile ? getComputedStyle(tile).fill : null,
        };
      }),
    );
    for (const [k, s] of swatches.entries()) {
      expect(s.fill).toBe(rgb(theme.classes[k]));
      const ink = doc.patterns.class_ink[colorScheme][k];
      expect(s.ink).toBe(ink ? rgb(ink) : null);
    }
    // Cased boundaries: every fill first, then 37 halos, then 37 narrower edges on top, in the
    // theme's colours.
    const layers = await map
      .locator('svg > g')
      .evaluateAll((groups) => groups.map((g) => g.getAttribute('class')));
    expect(layers.slice(0, 3)).toEqual(['map-fills', 'map-halos', 'map-edges']);
    await expect(map.locator('g.map-halos path')).toHaveCount(37);
    await expect(map.locator('g.map-edges path')).toHaveCount(37);
    const strokes = await map.evaluate((holder) => {
      const halo = getComputedStyle(holder.querySelector('.map-halos path'));
      const edge = getComputedStyle(holder.querySelector('.map-edges path'));
      return {
        halo: halo.stroke,
        haloWidth: parseFloat(halo.strokeWidth),
        edge: edge.stroke,
        edgeWidth: parseFloat(edge.strokeWidth),
      };
    });
    expect(strokes.halo).toBe(rgb(theme.halo));
    expect(strokes.edge).toBe(rgb(theme.edge));
    // The widths are the document's (map.casing), the halo wider than the edge.
    expect(strokes.haloWidth).toBe(doc.map.casing.halo);
    expect(strokes.edgeWidth).toBe(doc.map.casing.edge);
    expect(strokes.haloWidth).toBeGreaterThan(strokes.edgeWidth);
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

// Which states are drawn at full strength: [code, fill opacity, edge opacity].
async function strengths(page) {
  return page.locator('#prevalence-map').evaluate((holder) =>
    [...holder.querySelectorAll('path[data-state]')].map((p) => [
      p.dataset.state,
      getComputedStyle(p).opacity,
      getComputedStyle(
        holder.querySelector(`.map-edges path[data-outline="${p.dataset.state}"]`),
      ).opacity,
    ]),
  );
}

test('the legend buttons show one class at a time, by keyboard, and Esc shows all', async ({
  page,
  request,
}) => {
  const doc = await (await request.get('data/charts/prevalence_map.json')).json();
  expect(doc.keyboard.legend_filter).toBe(true);
  await ready(page);
  const legend = page.locator('#prevalence-map-legend');
  const buttons = legend.getByRole('button');
  const status = page.locator('#prevalence-map-filter-status');
  // A visible label names the list; one button per class, lowest first.
  await expect(page.locator('#prevalence-map-key-label')).toBeVisible();
  await expect(legend).toHaveAccessibleName('Map key: press a range to show only its states');
  await expect(buttons).toHaveCount(doc.classes.length);
  for (const [i, c] of doc.classes.entries()) {
    await expect(buttons.nth(i)).toHaveAccessibleName(`${c.label}: ${c.count} states`);
    await expect(buttons.nth(i)).toHaveAttribute('aria-pressed', 'false');
    await expect(buttons.nth(i)).toHaveAttribute('type', 'button');
  }
  // One live region for the whole legend, polite, and none on the buttons.
  await expect(status).toHaveAttribute('role', 'status');
  await expect(status).toBeEmpty();
  await expect(legend.locator('[aria-live], [role="status"], [role="alert"]')).toHaveCount(0);

  // Tab reaches every button in order, after the comparison's links (the last one goes to the
  // sensitivity page) and before the map.
  await page.locator('section[aria-labelledby="comparison-heading"] a[href="./sensitivity.html"]').focus();
  for (let i = 0; i < doc.classes.length; i += 1) {
    await page.keyboard.press('Tab');
    await expect(buttons.nth(i)).toBeFocused();
  }
  await page.keyboard.press('Tab');
  await expect(page.locator('#prevalence-map')).toBeFocused();

  // Enter on "4% to under 6%": only that class at full strength, and the names announced.
  const k = 3;
  const names = doc.regions
    .filter((r) => r.class === k)
    .map((r) => r.name)
    .sort();
  expect(doc.classes[k].regions).toEqual(names);
  await buttons.nth(k).focus();
  await page.keyboard.press('Enter');
  await expect(buttons.nth(k)).toHaveAttribute('aria-pressed', 'true');
  await expect(status).toHaveText(doc.classes[k].announce);
  await expect(status).toHaveText(
    `Showing ${names.length} states in ${doc.classes[k].label}: ${names.join(', ')}.`,
  );
  const codesIn = new Set(doc.regions.filter((r) => r.class === k).map((r) => r.code));
  for (const [code, fill, edge] of await strengths(page)) {
    if (codesIn.has(code)) {
      expect([fill, edge]).toEqual(['1', '1']);
    } else {
      expect(Number(fill)).toBeLessThan(0.5); // dimmed
      expect(Number(edge)).toBeGreaterThan(0); // its boundary still shows, faintly
      expect(Number(edge)).toBeLessThan(1);
    }
  }
  for (let i = 0; i < doc.classes.length; i += 1) {
    if (i !== k) await expect(buttons.nth(i)).toHaveAttribute('aria-pressed', 'false');
  }

  // Space on another class moves the filter: only one class at a time.
  await buttons.nth(0).focus();
  await page.keyboard.press('Space');
  await expect(buttons.nth(0)).toHaveAttribute('aria-pressed', 'true');
  await expect(buttons.nth(k)).toHaveAttribute('aria-pressed', 'false');
  await expect(status).toHaveText(doc.classes[0].announce);
  // Pressing it again shows all.
  await page.keyboard.press('Space');
  await expect(buttons.nth(0)).toHaveAttribute('aria-pressed', 'false');
  await expect(status).toHaveText('Showing all 37 states.');
  await expect(status).toHaveText(doc.legend.announce_all);
  for (const [, fill, edge] of await strengths(page)) expect([fill, edge]).toEqual(['1', '1']);

  // Esc in the legend shows all; focus stays on the button.
  await buttons.nth(1).click();
  await expect(buttons.nth(1)).toHaveAttribute('aria-pressed', 'true');
  await expect(status).toHaveText(doc.classes[1].announce);
  await buttons.nth(1).focus();
  await page.keyboard.press('Escape');
  await expect(buttons.nth(1)).toHaveAttribute('aria-pressed', 'false');
  await expect(buttons.nth(1)).toBeFocused();
  await expect(status).toHaveText('Showing all 37 states.');

  // Esc on the map shows all too (and closes the tip).
  await buttons.nth(2).click();
  await buttons.nth(2).focus();
  await page.keyboard.press('Tab'); // past the other buttons to the map
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await expect(page.locator('#prevalence-map')).toBeFocused();
  await expect(page.locator('.choropleth-figure .map-tip')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.choropleth-figure .map-tip')).toBeHidden();
  await expect(buttons.nth(2)).toHaveAttribute('aria-pressed', 'false');
  await expect(status).toHaveText('Showing all 37 states.');

  // Esc elsewhere on the page leaves the filter alone.
  await buttons.nth(4).click();
  await page.locator('#state-select').focus();
  await page.keyboard.press('Escape');
  await expect(buttons.nth(4)).toHaveAttribute('aria-pressed', 'true');
});

for (const colorScheme of ['light', 'dark']) {
  test(`with a class shown, the page has no WCAG A/AA violations (${colorScheme})`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme });
    await ready(page);
    await page.locator('#prevalence-map-legend').getByRole('button').nth(3).click();
    await expect(page.locator('#prevalence-map-filter-status')).not.toBeEmpty();
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('the legend filter and the state highlight work together', async ({ page, request }) => {
  const doc = await (await request.get('data/charts/prevalence_map.json')).json();
  await ready(page);
  const lagos = doc.regions.find((r) => r.name === 'Lagos');
  const other = doc.classes.findIndex((_, i) => i !== lagos.class);
  const buttons = page.locator('#prevalence-map-legend').getByRole('button');
  const map = page.locator('#prevalence-map');
  // Show a class Lagos is not in, then choose Lagos: it is dimmed but still outlined on top.
  await buttons.nth(other).click();
  await chooseState(page, 'Lagos');
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-LA');
  await expect(map.locator('.map-outline-selected .outline-edge')).toHaveAttribute(
    'd',
    doc.map.paths['NG-LA'],
  );
  await expect(buttons.nth(other)).toHaveAttribute('aria-pressed', 'true');
  // Clearing the filter keeps the highlight; choosing another state moves it.
  await buttons.nth(other).click();
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-LA');
  await chooseState(page, 'Kano');
  await expect(map.locator('path.selected')).toHaveAttribute('data-state', 'NG-KN');
  await expect(map.locator('.map-outline-selected .outline-edge')).toHaveAttribute(
    'd',
    doc.map.paths['NG-KN'],
  );
});

for (const colorScheme of ['light', 'dark']) {
  test(`a small chosen state gets a cased outline and ring, at the document's widths (${colorScheme})`, async ({
    page,
    request,
  }) => {
    const doc = await (await request.get('data/charts/prevalence_map.json')).json();
    const theme = doc.themes[colorScheme];
    expect(theme.halo).toBeTruthy();
    const casing = doc.map.casing;
    // Imo is small (it has a ring) and in the highest class, the darkest fill in light mode.
    const imo = doc.regions.find((r) => r.name === 'Imo');
    expect(doc.map.rings[imo.code]).toBeTruthy();
    expect(imo.class).toBe(doc.classes.length - 1);
    await page.emulateMedia({ colorScheme });
    await ready(page);
    await chooseState(page, 'Imo');
    const map = page.locator('#prevalence-map');
    const drawn = await map.evaluate((holder) => {
      const style = (sel) => {
        const el = holder.querySelector(sel);
        const cs = getComputedStyle(el);
        return { stroke: cs.stroke, width: parseFloat(cs.strokeWidth), r: el.getAttribute('r') };
      };
      return {
        ringHalo: style('circle.map-ring-halo'),
        ring: style('circle.map-ring'),
        outlineHalo: style('.map-outline-selected .outline-halo'),
        outlineEdge: style('.map-outline-selected .outline-edge'),
        // The halo circle is drawn under the edge circle.
        haloFirst: Boolean(
          holder
            .querySelector('circle.map-ring-halo')
            .compareDocumentPosition(holder.querySelector('circle.map-ring')) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        ),
      };
    });
    const r = String(doc.map.rings[imo.code][2]);
    expect(drawn.ringHalo).toEqual({ stroke: rgb(theme.halo), width: casing.outline_halo, r });
    expect(drawn.ring).toEqual({ stroke: rgb(theme.edge), width: casing.outline_edge, r });
    expect(drawn.haloFirst).toBe(true);
    expect(drawn.outlineHalo.stroke).toBe(rgb(theme.halo));
    expect(drawn.outlineHalo.width).toBe(casing.outline_halo);
    expect(drawn.outlineEdge.width).toBe(casing.outline_edge);
    // A shown class's boundaries are drawn at the document's active widths.
    await page.locator('#prevalence-map-legend').getByRole('button').nth(imo.class).click();
    const active = await map.evaluate((holder) => ({
      halo: parseFloat(getComputedStyle(holder.querySelector('.map-halos path.active')).strokeWidth),
      edge: parseFloat(getComputedStyle(holder.querySelector('.map-edges path.active')).strokeWidth),
    }));
    expect(active).toEqual({ halo: casing.active_halo, edge: casing.active_edge });
  });
}

test('at 320px the legend fits, with no sideways scroll, before and after a press', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await ready(page);
  const buttons = page.locator('#prevalence-map-legend').getByRole('button');
  for (const press of [false, true]) {
    if (press) await buttons.nth(0).click();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    for (const box of await buttons.evaluateAll((els) =>
      els.map((el) => el.getBoundingClientRect().toJSON()),
    )) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(320);
      expect(box.height).toBeGreaterThanOrEqual(24); // WCAG 2.2 SC 2.5.8
    }
    // The swatch is large enough to show its tile.
    const swatch = await page.locator('#prevalence-map-legend svg.swatch').first().boundingBox();
    expect(swatch.width).toBeGreaterThanOrEqual(36);
    expect(swatch.height).toBeGreaterThanOrEqual(24);
  }
});

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

test('at 320px the map pattern tiles are drawn at least 8px wide', async ({ page, request }) => {
  const doc = await (await request.get('data/charts/prevalence_map.json')).json();
  await page.setViewportSize({ width: 320, height: 800 });
  await ready(page);
  // On-screen tile size: tile width x patternTransform scale x screen pixels per map unit.
  const sizes = await page.locator('#prevalence-map svg').evaluate((svg) => {
    const units = Number(svg.getAttribute('viewBox').trim().split(/\s+/)[2]);
    const px = svg.getBoundingClientRect().width / units;
    return [...svg.querySelectorAll('pattern')].map((pattern) => {
      const scale = Number(/scale\(([\d.]+)\)/.exec(pattern.getAttribute('patternTransform'))[1]);
      return Number(pattern.getAttribute('width')) * scale * px;
    });
  });
  expect(sizes).toHaveLength(doc.classes.length);
  for (const size of sizes) expect(size).toBeGreaterThanOrEqual(7.99);
});

test('a findings problem does not take the chart down; no findings block, no placeholder', async ({
  page,
}) => {
  // A malformed findings block: the chart still draws, and the block says what went wrong.
  await page.route('**/data/charts/prevalence_by_state.json', async (route) => {
    const doc = await (await route.fetch()).json();
    doc.findings.statements = null;
    await route.fulfill({ json: doc });
  });
  await ready(page);
  await expect(page.locator('#prevalence-chart-findings .findings-count')).toContainText(
    'The findings could not be shown',
  );
  await expect(page.locator('#prevalence-chart-title')).not.toHaveText('Chart unavailable');
  // No findings block at all: the "Loading the findings…" placeholder is not left behind.
  await page.unroute('**/data/charts/prevalence_by_state.json');
  await page.route('**/data/charts/prevalence_by_state.json', async (route) => {
    const doc = await (await route.fetch()).json();
    delete doc.findings;
    await route.fulfill({ json: doc });
  });
  await ready(page);
  await expect(page.locator('#prevalence-chart-findings')).toBeHidden();
  await expect(page.getByText('Loading the findings')).toHaveCount(0);
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
  // A table wider than the screen has a focusable caption (so it can be scrolled by key);
  // the wrapper is never the Tab stop (NVDA would read every row).
  const wraps = await page.locator('.table-wrap').evaluateAll((els) =>
    els.map((el) => {
      const caption = el.querySelector('caption');
      return {
        scrolls: el.scrollWidth > el.clientWidth + 1,
        focusable: caption?.tabIndex === 0 && !el.hasAttribute('tabindex'),
        named: Boolean(caption?.textContent.trim()),
      };
    }),
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
