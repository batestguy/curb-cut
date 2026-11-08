import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

// The walkthrough video page (P6 gate): both cuts play from the site with English captions,
// the transcript is on the page, and the page passes axe in both themes and at 320 px.
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const CUTS = [
  { heading: 'Full walkthrough (5 minutes 40 seconds)', file: 'curbcut-walkthrough', seconds: 340.2 },
  { heading: 'One-minute version (1 minute 19 seconds)', file: 'curbcut-1min', seconds: 79.4 },
];

for (const colorScheme of ['light', 'dark']) {
  for (const width of [1280, 320]) {
    test(`walkthrough: no axe violations (${colorScheme}, ${width} px)`, async ({ page }) => {
      await page.emulateMedia({ colorScheme });
      await page.setViewportSize({ width, height: 900 });
      await page.goto('walkthrough.html');
      const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
      expect(results.violations).toEqual([]);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
}

test('walkthrough: each video is named, plays its file and has English captions', async ({ page, request }) => {
  await page.goto('walkthrough.html');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Walkthrough video');
  for (const { heading, file, seconds } of CUTS) {
    const video = page.locator(`video[src="./video/${file}.mp4"]`);
    await expect(video).toHaveAccessibleName(heading);
    await expect(video).toHaveAttribute('controls', '');
    // The browser reads the file's metadata (preload="metadata"): it is a playable video.
    await expect
      .poll(() => video.evaluate((v) => v.duration), { timeout: 30_000 })
      .toBeCloseTo(seconds, 0);
    const track = video.locator('track');
    await expect(track).toHaveAttribute('kind', 'captions');
    await expect(track).toHaveAttribute('srclang', 'en');
    const vtt = await request.get(`video/${file}.en.vtt`);
    expect(vtt.ok()).toBe(true);
    expect((await vtt.text()).startsWith('WEBVTT')).toBe(true);
    // The track loads and has cues.
    await expect
      .poll(() => video.evaluate((v) => {
        const t = v.textTracks[0];
        t.mode = 'hidden';
        return t.cues ? t.cues.length : 0;
      }), { timeout: 15_000 })
      .toBeGreaterThan(10);
  }
});

test('walkthrough: the transcript is on the page and Tab reaches both players', async ({ page }) => {
  await page.goto('walkthrough.html');
  const transcript = page.locator('section[aria-labelledby="transcript-heading"]');
  await expect(transcript.getByRole('heading', { level: 3 }).first()).toBeVisible();
  await expect(transcript).toContainText('How many disabled people live in Nigeria?');
  await expect(transcript).toContainText('On-screen caption:');
  await expect(transcript).toContainText('NVDA:');
  await expect(transcript).not.toContainText('clips/');
  const reached = new Set();
  for (let i = 0; i < 40 && reached.size < 2; i += 1) {
    await page.keyboard.press('Tab');
    const src = await page.evaluate(() => document.activeElement?.getAttribute('src'));
    if (src?.endsWith('.mp4')) reached.add(src);
  }
  expect([...reached].sort()).toEqual(['./video/curbcut-1min.mp4', './video/curbcut-walkthrough.mp4']);
});

test('walkthrough: linked from the nav of every page and the state pages’ footer', async ({ page }) => {
  for (const path of ['./', 'methodology.html', 'poverty.html', 'data-dictionary.html', 'explorer.html', 'sensitivity.html', 'walkthrough.html']) {
    await page.goto(path);
    const nav = page.getByRole('navigation', { name: 'Site' });
    await expect(nav.getByRole('link', { name: 'Walkthrough video' }), path).toHaveAttribute('href', './walkthrough.html');
  }
  for (const path of ['states/', 'states/kano.html']) {
    await page.goto(path);
    const link = page.locator('footer.site-footer').getByRole('link', { name: /Walkthrough video/ });
    await expect(link, path).toHaveAttribute('href', '../walkthrough.html');
  }
});
