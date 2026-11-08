import { expect, test } from '@playwright/test';
import { COUNT_ORIGIN, isVisitCount } from './visit-count.js';

// P6 item 6: each page counts one visit with a GoatCounter image (no script, no cookies),
// says so in its footer, and makes no other request to another origin. The test browser
// cannot resolve GoatCounter's host (playwright.config.js), so these runs add no counts.
const PAGES = [
  { path: './', counted: '/' },
  { path: 'methodology.html', counted: '/methodology.html' },
  { path: 'poverty.html', counted: '/poverty.html' },
  { path: 'states/', counted: '/states/' },
  { path: 'states/kano.html', counted: '/states/kano.html' },
  { path: 'explorer.html', counted: '/explorer.html' },
  { path: 'sensitivity.html', counted: '/sensitivity.html' },
  { path: 'data-dictionary.html', counted: '/data-dictionary.html' },
  { path: 'walkthrough.html', counted: '/walkthrough.html' },
];

for (const { path, counted } of PAGES) {
  test(`${path}: one visit count for ${counted}, no other origin, and a footer note`, async ({
    page,
    baseURL,
  }) => {
    const origin = new URL(baseURL).origin;
    const elsewhere = [];
    page.on('request', (r) => {
      const url = r.url();
      if (!url.startsWith(origin) && !url.startsWith('data:')) elsewhere.push(url);
    });
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    expect(elsewhere.filter((u) => !isVisitCount(u))).toEqual([]);
    expect(elsewhere).toHaveLength(1);
    const url = new URL(elsewhere[0]);
    expect(url.origin).toBe(COUNT_ORIGIN);
    expect(url.searchParams.get('p')).toBe(counted);
    expect(url.searchParams.get('t')).toBeTruthy();
    // No cookies or storage are set by the page.
    expect(await page.context().cookies()).toEqual([]);
    // The image is decorative: empty alt, no referrer, takes no space.
    const img = page.locator('img.visit-count');
    await expect(img).toHaveCount(1);
    await expect(img).toHaveAttribute('alt', '');
    await expect(img).toHaveAttribute('referrerpolicy', 'no-referrer');
    const box = await img.boundingBox();
    expect((box?.width ?? 0) <= 1 && (box?.height ?? 0) <= 1).toBe(true);
    // The footer says visits are counted and links to what is recorded.
    const footer = page.locator('footer.site-footer');
    await expect(footer).toContainText('Visits are counted with GoatCounter: no cookies, and no IP addresses stored.');
    const link = footer.getByRole('link', { name: 'What is recorded' });
    await expect(link).toHaveAttribute('href', /methodology\.html#visits-heading$/);
  });
}

test('the methodology page says what the visit count records', async ({ page }) => {
  await page.goto('methodology.html');
  const section = page.locator('section[aria-labelledby="visits-heading"]');
  await expect(section.getByRole('heading', { name: 'Visit counts' })).toBeVisible();
  await expect(section).toContainText('stores no IP addresses');
  await expect(section).toContainText('sets no cookies');
  await expect(section.getByRole('link', { name: 'privacy policy' })).toHaveAttribute(
    'href',
    'https://www.goatcounter.com/help/privacy',
  );
});
