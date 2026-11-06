// The data explorer's pure parts (no DOM, no DuckDB), so they can be unit-tested with node:test
// (site/unit/). The page (explorer.js) wires them to the form, the table and the downloads.
//
// `meta` is data/explorer.json, written at build time by
// packages/transform/scripts/explorer_charts.py: the labels of the files' codes, the words for
// cells with no figure, the downloads' provenance and the chart of each view.

export const DEFAULT_VIEW = Object.freeze({
  level: 'state',
  measure: 'disability3',
  age: '18+',
  sex: 'all',
  place: '',
  sort: Object.freeze({ column: 'place', dir: 'asc' }),
});

// The query-string names of the view's fields.
const PARAMS = ['level', 'measure', 'age', 'sex', 'place', 'sort'];

/**
 * The table's columns, in order. `key` names the field of a table row (see tableRows);
 * `dictionary` the column of the Parquet file it comes from (for the data dictionary's anchor).
 * The CSV header follows downloads.py's Column.header: the label, with the unit added only
 * when the label lacks it (all labels here already carry theirs).
 */
export function columns(level) {
  const place = level === 'state' ? 'State' : level === 'zone' ? 'Zone' : 'Place';
  return [
    { key: 'place', label: place, type: 'text' },
    { key: 'estimate', label: 'Estimate (%)', type: 'number', decimals: 1, unit: '%', dictionary: 'estimate' },
    { key: 'low', label: 'Low (%)', type: 'number', decimals: 1, unit: '%', dictionary: 'ci_low' },
    { key: 'high', label: 'High (%)', type: 'number', decimals: 1, unit: '%', dictionary: 'ci_high' },
    { key: 'flag', label: 'Precision', type: 'text', dictionary: 'precision_flag' },
    { key: 'reason', label: 'Reason for the flag', type: 'text', dictionary: 'precision_reason' },
    { key: 'n', label: 'Respondents (unweighted)', type: 'integer', decimals: 0, dictionary: 'n_unweighted' },
  ];
}

const SORT_KEYS = new Set(columns('state').map((c) => c.key));

function labelled(list, values) {
  // The meta's order and labels; a value the meta does not know keeps its code as its label
  // (the build refuses unlabelled measures, so this is only a safety net).
  const known = list.filter((o) => values.has(o.value));
  const extra = [...values].filter((v) => !list.some((o) => o.value === v)).sort();
  return [...known, ...extra.map((v) => ({ value: v, label: v }))];
}

/**
 * Read a query string ("?level=zone&…") into raw values (strings, or undefined when absent).
 */
export function parseQuery(search) {
  const params = new URLSearchParams(search);
  return Object.fromEntries(PARAMS.map((name) => [name, params.get(name) ?? undefined]));
}

/** The query string of a view; the default sort and an empty place are left out. */
export function toQuery(view) {
  const params = new URLSearchParams();
  params.set('level', view.level);
  params.set('measure', view.measure);
  params.set('age', view.age);
  params.set('sex', view.sex);
  if (view.place) params.set('place', view.place);
  const sort = view.sort ?? DEFAULT_VIEW.sort;
  if (sort.column !== DEFAULT_VIEW.sort.column || sort.dir !== DEFAULT_VIEW.sort.dir) {
    params.set('sort', `${sort.column}-${sort.dir}`);
  }
  return `?${params}`;
}

function parseSort(text) {
  const match = /^([a-z]+)-(asc|desc)$/.exec(text ?? '');
  if (!match || !SORT_KEYS.has(match[1])) return null;
  return { column: match[1], dir: match[2] };
}

/**
 * The choices for each field and a valid view, from what the data hold. Each field's choices
 * are the distinct values present given the fields before it (level, then measure, age group,
 * sex and place). A requested value that is not among its choices falls back to the default
 * (or the first choice), and is listed in `invalid` as {field, given, used}.
 *
 * @param {object} meta explorer.json
 * @param {{level: string, measure: string, age_group: string, sex: string}[]} combos
 * @param {{level: string, place: string}[]} places
 * @param {Record<string, string | undefined>} wanted raw values (parseQuery, or the form)
 */
export function resolveView(meta, combos, places, wanted) {
  const invalid = [];
  const options = {};
  const view = {};

  function choose(field, list, fallback) {
    options[field] = list;
    const given = wanted[field];
    const has = (v) => list.some((o) => o.value === v);
    if (given !== undefined && has(given)) {
      view[field] = given;
      return;
    }
    const used = has(fallback) ? fallback : (list[0]?.value ?? '');
    if (given !== undefined) invalid.push({ field, given, used });
    view[field] = used;
  }

  const levelValues = new Set(combos.map((c) => c.level));
  choose('level', labelled(meta.levels, levelValues), DEFAULT_VIEW.level);
  const atLevel = combos.filter((c) => c.level === view.level);
  choose('measure', labelled(meta.measures, new Set(atLevel.map((c) => c.measure))), DEFAULT_VIEW.measure);
  const atMeasure = atLevel.filter((c) => c.measure === view.measure);
  choose('age', labelled(meta.age_groups, new Set(atMeasure.map((c) => c.age_group))), DEFAULT_VIEW.age);
  const atAge = atMeasure.filter((c) => c.age_group === view.age);
  choose('sex', labelled(meta.sexes, new Set(atAge.map((c) => c.sex))), DEFAULT_VIEW.sex);

  const names = [...new Set(places.filter((p) => p.level === view.level).map((p) => p.place))].sort(
    (a, b) => a.localeCompare(b, 'en'),
  );
  let placeList;
  if (view.level === 'national') {
    placeList = [{ value: '', label: meta.places.national.label }];
  } else {
    const plural = view.level === 'state' ? 'states' : 'zones';
    placeList = [
      { value: '', label: `All ${names.length} ${plural}` },
      ...names.map((n) => ({ value: n, label: n })),
    ];
  }
  choose('place', placeList, '');

  const sort = parseSort(wanted.sort);
  if (wanted.sort !== undefined && !sort) {
    invalid.push({ field: 'sort', given: wanted.sort, used: 'place-asc' });
  }
  view.sort = sort ?? { ...DEFAULT_VIEW.sort };
  return { view, options, invalid };
}

/** The label of a value among a field's choices (its code if missing). */
export function optionLabel(options, field, value) {
  return options[field]?.find((o) => o.value === value)?.label ?? value;
}

/** The words a cell shows instead of a figure (explorer_charts.missing_text), or null. */
export function missingText(cell, meta) {
  if (!cell.has_data) return meta.missing.no_data;
  if (cell.suppressed) {
    return String(cell.precision_reason ?? '').includes('complementary')
      ? meta.missing.withheld
      : meta.missing.too_few;
  }
  if (cell.precision_flag === 'unreliable' || cell.estimate == null) return meta.missing.unreliable;
  return null;
}

function reasonText(code, meta) {
  if (!code) return null;
  const parts = String(code)
    .split(';')
    .map((c) => meta.reasons[c.trim()] ?? c.trim());
  const text = parts.join('; ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const toNumber = (v) => (v == null ? null : typeof v === 'bigint' ? Number(v) : Number(v));

/**
 * The table's rows from the query's cells. Figures are percentages, not rounded (the table
 * rounds them for display, the downloads keep them); a cell with no figure has `words`
 * instead, and no estimate, interval or (when suppressed or without data) count.
 */
export function tableRows(cells, meta) {
  return cells.map((cell) => {
    const words = missingText(cell, meta);
    const place = cell.place === meta.places.national.value ? meta.places.national.label : cell.place;
    const flagCode = !cell.has_data ? 'no_data' : cell.suppressed ? 'suppressed' : cell.precision_flag;
    const hidden = !cell.has_data || cell.suppressed;
    return {
      place,
      words,
      estimate: words ? null : 100 * toNumber(cell.estimate),
      low: words ? null : 100 * toNumber(cell.ci_low),
      high: words ? null : 100 * toNumber(cell.ci_high),
      flag: meta.flags[flagCode] ?? flagCode,
      reason: reasonText(cell.precision_reason, meta),
      n: hidden ? null : toNumber(cell.n_unweighted),
    };
  });
}

/**
 * Sort rows by a column. Rows without a value in that column (words, or no count) always come
 * last, whatever the direction; ties keep place order.
 */
export function sortRows(rows, sort) {
  const { column, dir } = sort ?? DEFAULT_VIEW.sort;
  const sign = dir === 'desc' ? -1 : 1;
  const byPlace = (a, b) => a.place.localeCompare(b.place, 'en');
  return [...rows].sort((a, b) => {
    const x = a[column];
    const y = b[column];
    if (x == null && y == null) return byPlace(a, b);
    if (x == null) return 1;
    if (y == null) return -1;
    const order = typeof x === 'number' ? x - y : String(x).localeCompare(String(y), 'en');
    return order !== 0 ? sign * order : byPlace(a, b);
  });
}

// The project's rule for counts (CLAUDE.md): a count under 30 is never shown, only "<30". The
// disclosure gate means a published cell never has one; this is a second line of defence.
const MIN_COUNT = 30;

/** A count as the table and the files show it: "<30" under 30, otherwise the number. */
export function countValue(n) {
  if (n == null) return null;
  return n < MIN_COUNT ? `<${MIN_COUNT}` : n;
}

const oneDecimal = new Intl.NumberFormat('en-NG', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/**
 * A percentage as the table shows it, to 1 decimal like format.js; above 0 but under 0.05 is
 * "<0.1", not a misleading "0.0" (as build_state_pages.py's num1). Exactly 0 stays "0.0". The
 * downloads keep the value itself (downloads.VALUES_RULE).
 */
export function pctText(value) {
  if (value == null) return '';
  return value > 0 && value < 0.05 ? '<0.1' : oneDecimal.format(value);
}

/** "Disability: …. Women 18+, each state" — the view in words, for the caption and status. */
export function describeView(view, options, meta) {
  const measure = optionLabel(options, 'measure', view.measure);
  const group = meta.groups[`${view.age}|${view.sex}`] ??
    `${optionLabel(options, 'age', view.age)}, ${optionLabel(options, 'sex', view.sex)}`;
  let where;
  if (view.level === 'national') where = meta.places.national.label;
  else if (view.place) where = view.place;
  else where = view.level === 'state' ? 'each state' : 'each geopolitical zone';
  return { measure, group, where };
}

export function caption(view, options, meta) {
  const { measure, group, where } = describeView(view, options, meta);
  return `${measure}. ${group}, ${where} (DHS 2024). Low and High: the 95% confidence interval.`;
}

export function statusText(count, view, options, meta) {
  const { measure, group, where } = describeView(view, options, meta);
  return `Showing ${count} ${count === 1 ? 'row' : 'rows'}: ${measure}. ${group}, ${where}.`;
}

/** The name of the view's download files, without extension: lower case, hyphens only. */
export function fileBase(view) {
  const part = (s) =>
    String(s)
      .toLowerCase()
      .replace(/\+/g, 'plus')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  const age = view.age.replace('+', 'plus').replace('-', 'to');
  const bits = ['dhs2024', view.level, view.measure, age, view.sex];
  if (view.place) bits.push(view.place);
  return bits.map(part).join('-');
}

// --- Downloads: the same format as packages/transform/scripts/downloads.py ------------------

/** A value as downloads.py's clean() writes it: 12 significant digits, whole counts as integers. */
export function clean(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    // Integer columns stay integers; JavaScript numbers do not tell 3 from 3.0 apart, so the
    // CSV writer (csvCell) decides how each is written.
    return Number(value.toPrecision(12));
  }
  return String(value);
}

/** Python's repr() of a float (the CSV writes floats that way): "3.5", "0.0", "1e-05". */
export function pyFloat(x) {
  if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
  const abs = Math.abs(x);
  if (abs < 1e-4 || abs >= 1e16) {
    const [mantissa, exponent] = x.toExponential().split('e');
    const sign = exponent.startsWith('-') ? '-' : '+';
    const digits = exponent.replace(/^[+-]/, '').padStart(2, '0');
    return `${mantissa}e${sign}${digits}`;
  }
  const text = String(x);
  return text.includes('.') ? text : `${text}.0`;
}

/** A value as a CSV cell (downloads.py's _csv_cell): integers plain, floats as Python's repr. */
export function csvCell(value, column) {
  if (value == null) return '';
  if (typeof value === 'number') {
    return column.type === 'integer' && Number.isInteger(value) ? String(value) : pyFloat(value);
  }
  return String(value);
}

/** Quote a CSV cell as Python's csv module does (only when needed). */
export function csvQuote(text) {
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** The values of each row as the files hold them: words in the first value column. */
export function downloadRows(rows, level) {
  const cols = columns(level);
  return rows.map((row) =>
    cols.map((c) => {
      if (c.key === 'estimate' && row.words) return row.words;
      if (c.key === 'n') return countValue(row.n);
      return clean(row[c.key]);
    }),
  );
}

export function csvText(rows, level) {
  const cols = columns(level);
  const lines = [cols.map((c) => csvQuote(c.label))];
  for (const values of downloadRows(rows, level)) {
    lines.push(values.map((v, i) => csvQuote(csvCell(v, cols[i]))));
  }
  return lines.map((cells) => `${cells.join(',')}\r\n`).join('');
}

export function jsonText(rows, view, options, meta, pageUrl) {
  const cols = columns(view.level);
  const document = {
    table: `explorer-${fileBase(view)}`,
    name: 'the data explorer’s current view',
    caption: caption(view, options, meta),
    page: pageUrl,
    survey: meta.download.survey,
    year: meta.download.year,
    sources: meta.download.sources,
    terms: meta.download.terms,
    values: meta.download.values,
    columns: cols.map((c) => {
      const out = { label: c.label, type: c.type };
      if (c.decimals != null) out.decimals = c.decimals;
      if (c.unit) out.unit = c.unit;
      return out;
    }),
    rows: downloadRows(rows, view.level),
  };
  return `${JSON.stringify(document, null, 2)}\n`;
}

/** Whole kilobytes, at least 1 KB (downloads.size_text). */
export function sizeText(bytes) {
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
