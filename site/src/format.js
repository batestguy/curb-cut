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
 * Render an accessible data table: <caption>, column headers with scope="col", the first
 * cell of each row as a row header with scope="row", and numbers right-aligned.
 *
 * @param {{caption: string, columns: {label: string, type: string, decimals?: number}[], rows: unknown[][]}} spec
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
      cell.textContent = formatValue(value, column.type, column.decimals);
      tr.append(cell);
    });
  }
  return table;
}
