// Table downloads (P6 item 2): under every data table, a CSV and a JSON file written at build
// time from the same table the page shows (packages/transform/scripts/downloads.py). JONAPWD's
// tables (all rights reserved) have a citation line instead and no download.
import { expect, test } from '@playwright/test';

// RFC 4180: quoted fields may hold commas, quotes ("") and line breaks.
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') {
      row.push(field);
      field = '';
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += c;
  }
  if (field !== '' || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

// Every table in <main>, with what directly follows it (or its scroll wrapper).
function describeTables(page) {
  return page.locator('main table').evaluateAll((tables) =>
    tables.map((table) => {
      const after = (table.closest('.table-wrap') ?? table).nextElementSibling;
      return {
        caption: table.querySelector('caption').textContent,
        rowHeads: [...table.querySelectorAll('tbody tr')].map((tr) => tr.children[0].textContent),
        afterClass: after?.className ?? null,
        afterText: after?.textContent ?? '',
        links: [...(after?.querySelectorAll('a') ?? [])].map((a) => ({
          href: a.href,
          text: a.textContent,
          label: a.getAttribute('aria-label'),
          download: a.hasAttribute('download'),
        })),
      };
    }),
  );
}

async function checkDownloads(page, request, { expectTables, expectJonapwd }) {
  const tables = await describeTables(page);
  expect(tables.length).toBe(expectTables);
  const names = [];
  let jonapwd = 0;
  for (const t of tables) {
    if (t.caption.includes('JONAPWD')) {
      jonapwd += 1;
      expect(t.afterClass, t.caption).toBe('table-source');
      expect(t.afterText).toContain('© JONAPWD, all rights reserved');
      expect(t.links.map((l) => l.href)).toEqual(['https://jonapwdng.org/10865-2/']);
      // Unique accessible name that starts with the visible text (SC 2.5.3).
      expect(t.links[0].label.startsWith(`${t.links[0].text}: `), t.links[0].label).toBe(true);
      names.push(t.links[0].label);
      continue;
    }
    expect(t.afterClass, t.caption).toBe('table-download');
    expect(t.afterText).toMatch(/^Download this table: CSV, \d+ KB · JSON, \d+ KB$/);
    expect(t.links.map((l) => l.text.split(',')[0])).toEqual(['CSV', 'JSON']);
    const bodies = {};
    for (const link of t.links) {
      // The accessible name starts with the visible text, then names the table.
      expect(link.download).toBe(true);
      expect(link.label.startsWith(`${link.text}: `), link.label).toBe(true);
      names.push(link.label);
      const response = await request.get(link.href);
      expect(response.status(), link.href).toBe(200);
      const type = response.headers()['content-type'];
      const body = await response.body();
      const kb = Math.max(1, Math.round(body.length / 1024));
      expect(link.text).toBe(`${link.text.split(',')[0]}, ${kb} KB`);
      if (link.text.startsWith('CSV')) {
        expect(type).toMatch(/text\/csv/);
        bodies.csv = parseCsv(body.toString('utf-8'));
      } else {
        expect(type).toMatch(/application\/json/);
        bodies.json = JSON.parse(body.toString('utf-8'));
      }
    }
    const [header, ...rows] = bodies.csv;
    expect(rows.length, t.caption).toBe(t.rowHeads.length);
    expect(rows.map((r) => r[0])).toEqual(t.rowHeads);
    expect(header).toEqual(bodies.json.columns.map((c) => c.label));
    expect(bodies.json.caption).toBe(t.caption);
    expect(bodies.json.terms).toMatch(/^Reuse is subject to the source terms; cite the sources\./);
    // The JSON's rows are the CSV's rows: numbers equal as numbers, empty cells null.
    expect(bodies.json.rows.length).toBe(rows.length);
    bodies.json.rows.forEach((jsonRow, i) => {
      expect(jsonRow.length).toBe(rows[i].length);
      jsonRow.forEach((value, j) => {
        const cell = rows[i][j];
        if (value === null) expect(cell).toBe('');
        else if (typeof value === 'number') expect(Number(cell)).toBe(value);
        else expect(cell).toBe(String(value));
      });
    });
  }
  expect(jonapwd).toBe(expectJonapwd);
  expect(new Set(names).size).toBe(names.length);
  // The links are in the accessibility tree under those names (with every <details> open:
  // some tables are inside one).
  for (const summary of await page.locator('main details > summary').all()) {
    if (!(await summary.evaluate((s) => s.parentElement.open))) await summary.click();
  }
  for (const name of names) {
    await expect(page.getByRole('link', { name, exact: true })).toHaveCount(1);
  }
  return names;
}

test('main page: every table has its downloads; JONAPWD tables are cited, not downloadable', async ({
  page,
  request,
}) => {
  await page.goto('./');
  await expect(page.locator('#prevalence-map-table table')).toBeVisible();
  await expect(page.locator('#prevalence-chart-table table')).toBeVisible();
  await expect(page.locator('#national-table table')).toBeVisible();
  await expect(page.locator('#state-chart-table table')).toBeVisible();
  await expect(page.locator('#moran-table table')).toHaveCount(1);
  await page.locator('#state-select').selectOption('Kano');
  await page.getByRole('button', { name: 'Show figures' }).click();
  await expect(page.locator('#state-table table')).toBeVisible({ timeout: 30_000 });
  // Map table, dot-plot table and Moran table; two JONAPWD charts and the explorer's table.
  const names = await checkDownloads(page, request, { expectTables: 6, expectJonapwd: 3 });
  // Six download links and three JONAPWD citation links, all with distinct names.
  expect(names).toHaveLength(9);
  expect(names).toContain("JONAPWD's publication: persons with disabilities by type, Kano");
  await expect(page.locator('#state-table .table-source')).toBeVisible();
  await expect(page.locator('#state-table .table-download')).toHaveCount(0);
});

test('poverty page: every table has its downloads', async ({ page, request }) => {
  await page.goto('poverty.html');
  const names = await checkDownloads(page, request, { expectTables: 13, expectJonapwd: 0 });
  expect(names).toHaveLength(26);
});

test('a state page: every table has its downloads', async ({ page, request }) => {
  await page.goto('states/kano.html');
  const names = await checkDownloads(page, request, { expectTables: 7, expectJonapwd: 0 });
  expect(names).toContain('CSV, 1 KB: disability in Kano by sex and age');
});

test('download links are reached by Tab, with the visible focus style of other links', async ({
  page,
}) => {
  await page.goto('states/kano.html');
  const link = page.locator('.table-download a').first();
  await page.locator('#groups-heading').evaluate((h) => {
    h.tabIndex = -1;
    h.focus();
  });
  for (let i = 0; i < 5 && !(await link.evaluate((a) => a === document.activeElement)); i += 1) {
    await page.keyboard.press('Tab');
  }
  await expect(link).toBeFocused();
  const outline = await link.evaluate((a) => getComputedStyle(a).outlineStyle);
  expect(outline).toBe('solid');
});
