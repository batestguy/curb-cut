import { expect, test } from '@playwright/test';

// P6 item 5 (verification.md D29): Nigerian-language text uses the self-hosted Noto Sans
// subset; English pages never download it.
const FONT = /\/fonts\/noto-sans-nigeria\.woff2$/;
const SAMPLE = 'Ẹ̀kọ́ ṣé ọmọ · ɓ ɗ ƙ ƴ ʼ · ị ụ ṅ n̄ · ₦';

for (const path of ['./', 'poverty.html', 'states/kano.html']) {
  test(`${path}: English pages do not download the Nigerian-language font`, async ({ page }) => {
    const fonts = [];
    page.on('request', (r) => {
      if (r.resourceType() === 'font') fonts.push(r.url());
    });
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    expect(fonts.filter((u) => FONT.test(u))).toEqual([]);
  });
}

for (const lang of ['yo', 'ha', 'ig', 'pcm']) {
  test(`lang="${lang}" text loads the subset from this origin and renders with it`, async ({
    page,
    baseURL,
  }) => {
    const fontResponse = page.waitForResponse((r) => FONT.test(r.url()));
    await page.goto('states/kano.html');
    await page.evaluate(
      ({ lang, sample }) => {
        const p = document.createElement('p');
        p.lang = lang;
        p.id = 'font-probe';
        p.textContent = sample;
        document.querySelector('main').prepend(p);
      },
      { lang, sample: SAMPLE },
    );
    const response = await fontResponse;
    expect(response.status()).toBe(200);
    expect(new URL(response.url()).origin).toBe(new URL(baseURL).origin);
    const result = await page.evaluate(async (sample) => {
      await document.fonts.ready;
      const el = document.getElementById('font-probe');
      const face = [...document.fonts].find((f) => f.family.replaceAll('"', '') === 'Noto Sans Nigeria');
      return {
        family: getComputedStyle(el).fontFamily,
        status: face?.status,
        covers: document.fonts.check('16px "Noto Sans Nigeria"', sample),
      };
    }, SAMPLE);
    expect(result.family.startsWith('"Noto Sans Nigeria"')).toBe(true);
    expect(result.status).toBe('loaded');
    expect(result.covers).toBe(true);
  });
}
