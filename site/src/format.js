// Number formatting and table rendering shared by the chart fallback and the state explorer.

const integer = new Intl.NumberFormat('en-NG', { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('en-NG', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const fixed = new Map();

export function formatValue(value, type, decimals = 1) {
  // DuckDB-WASM returns BIGINT columns as JavaScript BigInt.
  const n = typeof value === 'bigint' ? Number(value) : value;
  if (type === 'integer') return integer.format(n);
  if (type === 'percent') return percent.format(n);
  if (type === 'number') {
    // A fixed number of decimals, from the chart document's column (interval bounds, rates).
    if (!fixed.has(decimals)) {
      fixed.set(
        decimals,
        new Intl.NumberFormat('en-NG', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }),
      );
    }
    return fixed.get(decimals).format(n);
  }
  return String(value);
}

/**
 * The URL of a state's own page (site/states/<slug>.html). The slug is the name in lower case
 * with every run of other characters replaced by one hyphen, the same rule as
 * build_state_pages.py's state_slug ("Akwa Ibom" -> "akwa-ibom").
 */
export function stateHref(name) {
  const slug = String(name)
    .toLowerCase()
    .replace(/[^a-z]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `${import.meta.env.BASE_URL}states/${slug}.html`;
}

/**
 * The line under a table with its downloads, from an entry of downloads/main/index.json
 * (written by build_charts.py from the same table spec the page renders; the browser never
 * computes a file). Each link's accessible name starts with its visible text ("CSV, 2 KB")
 * and then names the table, so names are unique and make sense in a list of links.
 *
 * @param {{name: string, files: {href: string, text: string}[]}} entry
 * @param {string} dataUrl the data folder's URL, ending in "/"
 */
export function downloadLine(entry, dataUrl) {
  const p = document.createElement('p');
  p.className = 'table-download';
  p.append('Download this table: ');
  entry.files.forEach((file, i) => {
    if (i > 0) p.append(' · ');
    const a = document.createElement('a');
    a.href = `${dataUrl}${file.href}`;
    a.setAttribute('download', '');
    a.setAttribute('aria-label', `${file.text}: ${entry.name}`);
    a.textContent = file.text;
    p.append(a);
  });
  return p;
}

/** The line under a JONAPWD table: cited, all rights reserved, so no download. */
export function citedLine(name) {
  const p = document.createElement('p');
  p.className = 'table-source';
  const a = document.createElement('a');
  a.href = 'https://jonapwdng.org/10865-2/';
  a.textContent = "JONAPWD's publication";
  // A unique accessible name that starts with the visible text (WCAG 2.2 SC 2.5.3).
  a.setAttribute('aria-label', `JONAPWD's publication: ${name}`);
  p.append(
    'Figures cited from ',
    a,
    '. © JONAPWD, all rights reserved; the PDF is not redistributed, and no download is offered for this table.',
  );
  return p;
}

/** Put a line directly after a table, or after its scroll wrapper. */
export function placeAfterTable(table, line) {
  if (line) (table.closest('.table-wrap') ?? table).after(line);
}

/**
 * Render an accessible data table: <caption>, column headers with scope="col", the first
 * cell of each row as a row header with scope="row", and numbers right-aligned.
 *
 * With `rowHref`, each row header links to rowHref(first value) (e.g. the state's page).
 *
 * @param {{caption: string, columns: {label: string, type: string, decimals?: number}[], rows: unknown[][], rowHref?: (value: unknown) => string}} spec
 */
export function renderTable(spec) {
  const table = document.createElement('table');
  const caption = table.createCaption();
  caption.textContent = spec.caption;

  const headRow = table.createTHead().insertRow();
  for (const column of spec.columns) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = column.label;
    if (column.type !== 'text') th.className = 'num';
    headRow.append(th);
  }

  const body = table.createTBody();
  for (const row of spec.rows) {
    const tr = body.insertRow();
    row.forEach((value, i) => {
      const column = spec.columns[i];
      const cell = document.createElement(i === 0 ? 'th' : 'td');
      if (i === 0) cell.scope = 'row';
      if (column.type !== 'text') cell.className = 'num';
      const text = formatValue(value, column.type, column.decimals);
      if (i === 0 && spec.rowHref) {
        const a = document.createElement('a');
        a.href = spec.rowHref(value);
        a.textContent = text;
        cell.append(a);
      } else {
        cell.textContent = text;
      }
      tr.append(cell);
    });
  }
  return table;
}
