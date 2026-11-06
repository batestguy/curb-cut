// Sortable table headers shared by the data explorer (explorer.js) and the sensitivity page
// (sensitivity.js): a button in each sortable `th`, `aria-sort` on the sorted column only, and
// an arrow icon hidden from screen readers (the attribute says the same thing).

export const SORT_WORDS = {
  text: { asc: 'A to Z', desc: 'Z to A' },
  number: { asc: 'lowest first', desc: 'highest first' },
  integer: { asc: 'smallest first', desc: 'largest first' },
};

export function cell(tag, text, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = text;
  return el;
}

/** The header row: a sort button per column, or plain text where `sortable` is false. */
export function headerRow(cols, sort) {
  const tr = document.createElement('tr');
  for (const col of cols) {
    const th = cell('th', null, col.type === 'number' || col.type === 'integer' ? 'num' : undefined);
    th.scope = 'col';
    if (col.sortable === false) {
      th.textContent = col.label;
      tr.append(th);
      continue;
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'sort-button';
    button.dataset.key = col.key;
    button.append(col.label);
    const icon = cell('span', '', 'sort-icon');
    icon.setAttribute('aria-hidden', 'true');
    button.append(icon);
    th.append(button);
    tr.append(th);
  }
  updateHeader(tr, sort);
  return tr;
}

export function updateHeader(tr, sort) {
  for (const th of tr.children) {
    const button = th.querySelector('button');
    if (!button) continue;
    const on = button.dataset.key === sort.column;
    if (on) th.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending');
    else th.removeAttribute('aria-sort');
    button.querySelector('.sort-icon').textContent = on ? (sort.dir === 'asc' ? '▲' : '▼') : '↕';
  }
}
