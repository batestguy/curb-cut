// Chart descriptions in Hausa, Yorùbá, Igbo and Naijá (P6 item 8): a <details> under each
// in-scope chart (the main page's map and dot plot, each state page's chart), drafted by AI
// and labelled as not reviewed; and the decorative adire band on every page.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const LANGS = ['ha', 'yo', 'ig', 'pcm'];
const NAMES = ['Hausa', 'Yorùbá', 'Igbo', 'Naijá (Nigerian Pidgin)'];
const LABEL = 'drafted by AI, not reviewed by a native speaker';
const SUMMARY = 'This description in Hausa, Yorùbá, Igbo and Naijá';
const FONT = /\/fonts\/noto-sans-nigeria\.woff2$/;

async function mainReady(page) {
  await page.goto('./');
  await expect(page.locator('#prevalence-map-translations details')).toHaveCount(1);
  await expect(page.locator('#prevalence-chart-translations details')).toHaveCount(1);
}

// Tags, classes and lang attributes, without the text: the markup's shape.
function shape(page, selector) {
  return page.locator(selector).first().evaluate((root) => {
    const walk = (node) =>
      `<${node.tagName.toLowerCase()} class="${node.className}" lang="${node.lang}">` +
      [...node.children].map(walk).join('') +
      '</>';
    return walk(root);
  });
}

async function checkDisclosure(details, doc) {
  await expect(details.locator('summary')).toHaveText(SUMMARY);
  await expect(details.locator('.translations-note')).toContainText('drafted by AI (Claude)');
  await expect(details.locator('.translations-note')).toContainText('eSpeak NG');
  const blocks = details.locator('.translation');
  await expect(blocks).toHaveCount(4);
  for (const [i, code] of LANGS.entries()) {
    const block = blocks.nth(i);
    await expect(block.locator('.translation-label')).toHaveText(`${NAMES[i]}: ${LABEL}`);
    await expect(block.locator('.translation-label')).not.toHaveAttribute('lang', /./);
    await expect(block.locator(`.translation-note[lang="${code}"]`)).toHaveCount(1);
    const text = block.locator(`.translation-text[lang="${code}"]`);
    await expect(text).toHaveCount(1);
    if (doc) await expect(text).toHaveText(doc.alt_text_translations[code].text);
  }
}

test('main page: the map and the dot plot each have the disclosure, from their documents', async ({
  page,
  request,
}) => {
  await mainReady(page);
  for (const [holder, name] of [
    ['#prevalence-map-translations', 'prevalence_map'],
    ['#prevalence-chart-translations', 'prevalence_by_state'],
  ]) {
    const doc = await (await request.get(`data/charts/${name}.json`)).json();
    for (const code of LANGS) {
      expect(doc.alt_text_translations[code].origin).toBe('template');
      expect(doc.alt_text_translations[code].reviewed).toBe(false);
    }
    const details = page.locator(`${holder} details.translations`);
    await expect(details).not.toHaveAttribute('open', /.*/);
    await checkDisclosure(details, doc);
    // Directly under its chart's figure.
    const after = await page.locator(holder).evaluate((el) => el.previousElementSibling?.tagName);
    expect(after).toBe('FIGURE');
  }
  // The JONAPWD charts are out of scope.
  await expect(page.locator('details.translations')).toHaveCount(2);
});

for (const slug of ['kano', 'lagos', 'federal-capital-territory']) {
  test(`${slug}: the chart's disclosure, from its document`, async ({ page, request }) => {
    await page.goto(`states/${slug}.html`);
    const doc = await (await request.get(`data/charts/states/${slug}.json`)).json();
    const details = page.locator('details.translations');
    await expect(details).toHaveCount(1);
    await checkDisclosure(details, doc);
    const before = await details.evaluate((el) => el.previousElementSibling?.tagName);
    expect(before).toBe('FIGURE');
  });
}

test.describe('without JavaScript', () => {
  test.use({ javaScriptEnabled: false });
  test('a state page disclosure opens and shows all four languages', async ({ page }) => {
    await page.goto('states/kano.html');
    const details = page.locator('details.translations');
    await checkDisclosure(details, null);
    await details.locator('summary').click();
    await expect(details).toHaveAttribute('open', '');
    for (const code of LANGS) {
      await expect(details.locator(`.translation-text[lang="${code}"]`)).toBeVisible();
    }
  });
});

test('the main page and the state pages use the same markup', async ({ page }) => {
  await mainReady(page);
  const main = await shape(page, '#prevalence-chart-translations details');
  await page.goto('states/kano.html');
  const state = await shape(page, 'details.translations');
  expect(main).toBe(state);
});

for (const path of ['poverty.html', 'explorer.html', 'sensitivity.html', 'methodology.html']) {
  test(`${path}: no translated descriptions (out of scope)`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('details.translations, [lang="ha"], [lang="yo"], [lang="ig"], [lang="pcm"]')).toHaveCount(0);
  });
}

for (const path of ['./', 'states/kano.html']) {
  test(`${path}: the disclosure opens and closes by keyboard, with a visible focus ring`, async ({
    page,
  }) => {
    if (path === './') await mainReady(page);
    else await page.goto(path);
    const summary = page.locator('details.translations summary').first();
    const details = page.locator('details.translations').first();
    // Tab reaches it: focus the element before it, then Tab until the summary has focus.
    await summary.evaluate((el) => {
      el.setAttribute('data-target', '');
    });
    await page.locator('main').focus();
    let reached = false;
    for (let i = 0; i < 200 && !reached; i += 1) {
      await page.keyboard.press('Tab');
      reached = await page.evaluate(() => document.activeElement?.hasAttribute('data-target'));
    }
    expect(reached).toBe(true);
    const outline = await summary.evaluate((el) => {
      const s = getComputedStyle(el);
      return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
    });
    expect(outline.style).not.toBe('none');
    expect(outline.width).toBeGreaterThanOrEqual(2);
    await page.keyboard.press('Enter');
    await expect(details).toHaveAttribute('open', '');
    await page.keyboard.press('Space');
    await expect(details).not.toHaveAttribute('open', /.*/);
    await page.keyboard.press('Enter');
    await expect(details).toHaveAttribute('open', '');
  });
}

test('translated text uses the Noto Sans subset, fetched only once a disclosure opens', async ({
  page,
}) => {
  const fonts = [];
  page.on('request', (r) => {
    if (FONT.test(r.url())) fonts.push(r.url());
  });
  await page.goto('states/kano.html');
  await page.waitForLoadState('networkidle');
  expect(fonts).toEqual([]);
  const font = page.waitForResponse((r) => FONT.test(r.url()));
  await page.locator('details.translations summary').click();
  expect((await font).status()).toBe(200);
  for (const code of LANGS) {
    const family = await page
      .locator(`.translation-text[lang="${code}"]`)
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(family.startsWith('"Noto Sans Nigeria"')).toBe(true);
  }
  // The English label is in the system font.
  const label = await page
    .locator('.translation-label')
    .first()
    .evaluate((el) => getComputedStyle(el).fontFamily);
  expect(label.startsWith('"Noto Sans Nigeria"')).toBe(false);
});

const VIEWS = [
  ['light', null],
  ['dark', null],
  ['light', 320],
  ['dark', 320],
];

for (const [colorScheme, width] of VIEWS) {
  const view = width ? `${colorScheme}, ${width}px` : colorScheme;
  for (const path of ['./', 'states/kano.html']) {
    test(`${path}: axe is clean with the disclosures open (${view})`, async ({ page }) => {
      if (width) await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ colorScheme });
      if (path === './') await mainReady(page);
      else await page.goto(path);
      for (const summary of await page.locator('details.translations summary').all()) {
        await summary.click();
      }
      const results = await new AxeBuilder({ page })
        .withTags(WCAG_TAGS)
        .include('details.translations')
        .analyze();
      expect(results.violations).toEqual([]);
      // No sideways scroll from the translated text at 320 px.
      if (width) {
        const wide = await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        );
        expect(wide).toBe(false);
      }
    });
  }
}

// --- The adire band -----------------------------------------------------------------------

const PAGES = [
  './',
  'methodology.html',
  'explorer.html',
  'sensitivity.html',
  'poverty.html',
  'data-dictionary.html',
  'states/',
  'states/kano.html',
];

for (const path of PAGES) {
  test(`${path}: the adire band follows the flag band, hidden from assistive technology`, async ({
    page,
  }) => {
    await page.goto(path);
    const band = page.locator('.adire-band');
    await expect(band).toHaveCount(1);
    await expect(band).toHaveAttribute('aria-hidden', 'true');
    const next = await page
      .locator('.flag-band')
      .evaluate((el) => el.nextElementSibling?.className);
    expect(next).toBe('adire-band');
    const box = await band.boundingBox();
    expect(box.height).toBeGreaterThan(10);
    // The mask draws the library's tiles in the theme's ink.
    const mask = await band.evaluate((el) => {
      const s = getComputedStyle(el, '::before');
      return s.maskImage || s.webkitMaskImage;
    });
    expect(mask).toContain('data:image/svg+xml');
  });
}

for (const colorScheme of ['light', 'dark']) {
  test(`the band's colours are the audited tokens (${colorScheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto('states/kano.html');
    const colours = await page.locator('.adire-band').evaluate((el) => ({
      bg: getComputedStyle(el).backgroundColor,
      ink: getComputedStyle(el, '::before').backgroundColor,
    }));
    const want =
      colorScheme === 'light'
        ? { bg: 'rgb(29, 43, 100)', ink: 'rgb(255, 255, 255)' }
        : { bg: 'rgb(74, 99, 200)', ink: 'rgb(240, 240, 240)' };
    expect(colours).toEqual(want);
  });
}

test('the band is hidden in forced colours (Windows High Contrast)', async ({ page }) => {
  await page.emulateMedia({ forcedColors: 'active' });
  await page.goto('./');
  await expect(page.locator('.adire-band')).toBeHidden();
  await expect(page.locator('.flag-band')).toBeVisible();
});
