// The sensitivity page's pure parts (no DOM), so they can be unit-tested with node:test
// (site/unit/) and run at build time: vite.config.js uses them to write the page's
// <noscript> version and its static downloads (scripts/sensitivity-static.mjs), the same
// code the page runs (sensitivity.js).
//
// `data` is data/sensitivity.json, written at build time by
// packages/transform/scripts/sensitivity_data.py: the DISABILITY3 cells for both sexes per age
// group (proportions, as in the Parquet file), each state's 2023 projection (all ages), the
// assumed and global figures with their wording, the definitions and the chart of each view.
//
// The comparison: "inside" means the assumed rate lies within the survey's 95% confidence
// interval, BOUNDS INCLUDED (low <= rate <= high); "above" and "below" mean outside it. It is
// made with the unrounded bounds, as proportions (rate / 100), never with the table's rounded
// figures. A state whose cell shows words (suppressed, no data, unreliable: the explorer's
// missingText) is not compared.
import { clean, csvCell, csvQuote, missingText, pctText } from './explorer-model.js';
import { stateSlug } from './format.js';

export const DEFAULT_SORT = Object.freeze({ column: 'place', dir: 'asc' });
const PARAMS = ['rate', 'age', 'sort'];

// --- Rates ----------------------------------------------------------------------------------

const EPS = 1e-9;

/** Every rate the slider offers, from data.rates ({min, max, step, default}). */
export function rateList(rates) {
  const count = Math.round((rates.max - rates.min) / rates.step);
  return Array.from({ length: count + 1 }, (_, i) => rates.min + i * rates.step);
}

/** The offered rate a number stands for, or null if it is not one (out of range, off-step). */
export function asRate(x, rates) {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  if (x < rates.min - EPS || x > rates.max + EPS) return null;
  const steps = (x - rates.min) / rates.step;
  if (Math.abs(steps - Math.round(steps)) > EPS) return null;
  return rates.min + Math.round(steps) * rates.step;
}

/** A typed text as a rate, or null: "12", "12.5", " 7 " are rates; "", "abc", "12.3" are not. */
export function parseRate(text, rates) {
  const t = text == null ? '' : String(text).trim();
  // Plain decimals only: Number() would also take "0x10", "1e1" or "+12".
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  const x = Number(t);
  return asRate(x, rates);
}

/** The nearest offered rate to any number (clamped to the range); null for a non-number. */
export function snapRate(x, rates) {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  const clamped = Math.min(rates.max, Math.max(rates.min, x));
  return rates.min + Math.round((clamped - rates.min) / rates.step) * rates.step;
}

/** "15" or "15.5": the rate as the page writes it (before "%" or " percent"). */
export function rateText(rate) {
  return Number.isInteger(rate) ? String(rate) : rate.toFixed(1);
}

/** The range input's aria-valuetext: "15 percent". */
export function valueText(rate) {
  return `${rateText(rate)} percent`;
}

/** The manifest's chart key of a view: "18+|15.0". */
export function chartKey(age, rate) {
  return `${age}|${rate.toFixed(1)}`;
}

// --- The comparison -------------------------------------------------------------------------

export const POSITIONS = Object.freeze({
  below: { order: 1, text: 'Below the interval' },
  inside: { order: 2, text: 'Inside the interval' },
  above: { order: 3, text: 'Above the interval' },
});
export const NOT_COMPARED = 'Not compared';

/**
 * Where an assumed rate (percent) falls against an interval (proportions): "below", "inside"
 * (bounds included) or "above"; null without an interval.
 */
export function classify(rate, low, high) {
  if (low == null || high == null) return null;
  const r = rate / 100;
  if (r < low) return 'below';
  if (r > high) return 'above';
  return 'inside';
}

const flagCode = (cell) => (!cell.has_data ? 'no_data' : cell.suppressed ? 'suppressed' : cell.precision_flag);

/**
 * The table's rows for an age group at a rate. Survey figures are percentages, not rounded;
 * a state with no figure has `words` and no comparison. `count` is only the assumption: the
 * rate times the state's 2023 projection for all ages (not a survey figure).
 */
export function tableRows(data, age, rate) {
  return (data.states[age] ?? []).map((cell) => {
    const words = missingText(cell, data);
    const where = words ? null : classify(rate, cell.ci_low, cell.ci_high);
    return {
      place: cell.state,
      rate,
      words,
      estimate: words ? null : 100 * cell.estimate,
      low: words ? null : 100 * cell.ci_low,
      high: words ? null : 100 * cell.ci_high,
      flag: data.flags[flagCode(cell)] ?? flagCode(cell),
      where,
      position: where ? POSITIONS[where].order : null,
      positionText: where ? POSITIONS[where].text : NOT_COMPARED,
      count: cell.population_2023 == null ? null : (rate / 100) * cell.population_2023,
    };
  });
}

/**
 * Sort rows by a column. Rows without a value in that column (words, or not compared) always
 * come last, whatever the direction; ties keep state order. The comparison column sorts by
 * position (below, inside, above), not by its words.
 */
export function sortRows(rows, sort) {
  const { column, dir } = sort ?? DEFAULT_SORT;
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

function listText(names) {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;
}

export function groupOf(data, age) {
  return data.age_groups.find((g) => g.value === age);
}

/**
 * The summary sentence, from the rows (never hard-coded): "At an assumed 15%, the assumption is
 * above the survey's interval in 37 of 37 states, inside it in 0 and below it in 0
 * (DISABILITY3, adults 18+, DHS 2024)." States not compared are named after it.
 */
export function summary(rows, rate, data, age) {
  const group = groupOf(data, age);
  const what = `${data.measure.short}, ${group.short}, DHS 2024`;
  const compared = rows.filter((r) => r.where);
  const count = (w) => compared.filter((r) => r.where === w).length;
  const n = compared.length;
  let text;
  if (n === 0) {
    text = `At an assumed ${rateText(rate)}%, no state has a survey figure to compare (${what}).`;
  } else {
    text =
      `At an assumed ${rateText(rate)}%, the assumption is above the survey's interval in ` +
      `${count('above')} of ${n} ${n === 1 ? 'state' : 'states'}, inside it in ${count('inside')} ` +
      `and below it in ${count('below')} (${what}).`;
  }
  const left = rows
    .filter((r) => !r.where)
    .map((r) => r.place)
    .sort((a, b) => a.localeCompare(b, 'en'));
  if (left.length > 0) {
    text += ` Not compared, as the survey figure is not shown: ${listText(left)}.`;
  }
  return text;
}

// --- The table's columns and cells ----------------------------------------------------------

/**
 * The table's columns, in order. `key` names the row field the column sorts by; `field` (if
 * set) the one it shows and downloads. Types follow downloads.py's Column ("text", "number",
 * "integer"); the CSV header is the label (each carries its unit).
 */
export function columns() {
  return [
    { key: 'place', label: 'State', type: 'text' },
    { key: 'rate', label: 'Assumed rate (%)', type: 'number', decimals: 1, unit: '%', sortable: false },
    { key: 'estimate', label: 'Survey estimate (%)', type: 'number', decimals: 1, unit: '%' },
    { key: 'low', label: 'Low (%)', type: 'number', decimals: 1, unit: '%' },
    { key: 'high', label: 'High (%)', type: 'number', decimals: 1, unit: '%' },
    { key: 'flag', label: 'Precision', type: 'text' },
    { key: 'position', field: 'positionText', label: 'Assumed rate against the interval', type: 'text',
      sortWords: { asc: 'below first', desc: 'above first' } },
    {
      key: 'count',
      label: 'Implied count at the assumed rate (all ages, 2023 projection)',
      type: 'number',
      decimals: 0,
    },
  ];
}

export const SORT_KEYS = new Set(columns().filter((c) => c.sortable !== false).map((c) => c.key));

const wholeNumber = new Intl.NumberFormat('en-NG', { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat('en-NG', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** What one cell of the table shows. */
export function cellText(row, col) {
  const value = row[col.field ?? col.key];
  if (value == null) return '';
  if (col.key === 'rate') return oneDecimal.format(value);
  if (col.unit === '%') return pctText(value);
  if (col.key === 'count') return wholeNumber.format(value);
  return String(value);
}

export function caption(rate, data, age) {
  const group = groupOf(data, age);
  return (
    `${data.measure.label} (${data.measure.short}), ${group.label.toLowerCase()}: an assumed ` +
    `rate of ${rateText(rate)}% against each state's DHS 2024 survey estimate and its 95% ` +
    'confidence interval (Low to High). Implied count: the assumed rate times the state’s ' +
    '2023 population projection for all ages.'
  );
}

// --- The view in the address ----------------------------------------------------------------

export function parseQuery(search) {
  const params = new URLSearchParams(search);
  return Object.fromEntries(PARAMS.map((name) => [name, params.get(name) ?? undefined]));
}

function parseSort(text) {
  const match = /^([a-z]+)-(asc|desc)$/.exec(text ?? '');
  if (!match || !SORT_KEYS.has(match[1])) return null;
  return { column: match[1], dir: match[2] };
}

/**
 * A valid view from raw values (parseQuery): the rate must be one the slider offers, the age
 * group one the data hold, the sort a sortable column. Anything else falls back to the
 * default and is listed in `invalid` as {field, given, used}.
 */
export function resolveView(data, wanted) {
  const invalid = [];
  const fallbackRate = data.rates.default;
  let rate = fallbackRate;
  if (wanted.rate !== undefined) {
    const parsed = parseRate(wanted.rate, data.rates);
    if (parsed == null) invalid.push({ field: 'rate', given: wanted.rate, used: rateText(fallbackRate) });
    else rate = parsed;
  }
  const ages = data.age_groups.map((g) => g.value);
  let age = ages[0];
  if (wanted.age !== undefined) {
    if (ages.includes(wanted.age)) age = wanted.age;
    else invalid.push({ field: 'age', given: wanted.age, used: age });
  }
  let sort = { ...DEFAULT_SORT };
  if (wanted.sort !== undefined) {
    const parsed = parseSort(wanted.sort);
    if (parsed) sort = parsed;
    else invalid.push({ field: 'sort', given: wanted.sort, used: `${DEFAULT_SORT.column}-${DEFAULT_SORT.dir}` });
  }
  return { view: { rate, age, sort }, invalid };
}

/** The query string of a view; the default sort is left out. */
export function toQuery(view) {
  const params = new URLSearchParams();
  params.set('rate', rateText(view.rate));
  params.set('age', view.age);
  const sort = view.sort ?? DEFAULT_SORT;
  if (sort.column !== DEFAULT_SORT.column || sort.dir !== DEFAULT_SORT.dir) {
    params.set('sort', `${sort.column}-${sort.dir}`);
  }
  return `?${params}`;
}

/** The words for a link's invalid values, for the page's message and the live region. */
export function invalidText(invalid, data) {
  if (invalid.length === 0) return '';
  const parts = invalid.map(({ field, given }) => {
    if (field === 'rate') {
      return `the rate “${given}” is not one of the rates offered (${rateText(data.rates.min)} to ${rateText(data.rates.max)} in steps of ${rateText(data.rates.step)}), so ${rateText(data.rates.default)}% is used`;
    }
    if (field === 'age') return `the age group “${given}” is not in the data, so ${data.age_groups[0].label.toLowerCase()} is used`;
    return `the sort order “${given}” is not available, so the table is sorted by state`;
  });
  return `This link's choices were not all valid: ${parts.join('; ')}.`;
}

// --- Downloads: the same format as packages/transform/scripts/downloads.py ------------------

/** The name of a view's download files, without extension. */
export function fileBase(rate, age) {
  const a = age.replace('+', 'plus').replace('-', 'to');
  return `curb-cut-assumed-rate-${rate.toFixed(1).replace('.', '-')}-dhs2024-disability3-${a}`;
}

/** The values of each row as the files hold them: words in the survey estimate's column. */
export function downloadRows(rows) {
  const cols = columns();
  return rows.map((row) =>
    cols.map((c) => {
      if (c.key === 'estimate' && row.words) return row.words;
      return clean(row[c.field ?? c.key]);
    }),
  );
}

export function csvText(rows) {
  const cols = columns();
  const lines = [cols.map((c) => csvQuote(c.label))];
  for (const values of downloadRows(rows)) {
    lines.push(values.map((v, i) => csvQuote(csvCell(v, cols[i]))));
  }
  return lines.map((cells) => `${cells.join(',')}\r\n`).join('');
}

export function jsonText(rows, rate, age, data, pageUrl) {
  const doc = {
    table: fileBase(rate, age).replace(/^curb-cut-/, ''),
    name: 'the table of states at this rate',
    caption: caption(rate, data, age),
    page: pageUrl,
    survey: data.download.survey,
    year: data.download.year,
    sources: data.download.sources,
    terms: data.download.terms,
    values: data.download.values,
    columns: columns().map((c) => {
      const out = { label: c.label, type: c.type };
      if (c.decimals != null) out.decimals = c.decimals;
      if (c.unit) out.unit = c.unit;
      return out;
    }),
    rows: downloadRows(rows),
  };
  return `${JSON.stringify(doc, null, 2)}\n`;
}

// --- Static HTML (built at build time: the <noscript> version and the definitions) ----------

export function esc(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#x27;');
}

const link = (href, text) => `<a href="${esc(href)}">${esc(text)}</a>`;

/** The definitions section's body: every sentence from the data, none hard-coded with a number. */
export function definitionsHtml(data) {
  const a = data.assumption;
  const g = data.global;
  const m = data.measure;
  const ages = listText(data.age_groups.map((x) => x.label.toLowerCase()));
  const items = [
    `<strong>The assumed rate.</strong> ${esc(a.label)}: ${esc(rateText(a.value_percent))}% ` +
      `(${esc(a.population)}). ${esc(a.definition)} Source: ${link(a.source_url, a.source)}. ` +
      `The ${esc(g.label)} is ${esc(rateText(g.value_percent))}%: ${esc(g.definition)} Source: ` +
      `${link(g.source_url, g.source)}.`,
    `<strong>The survey measure.</strong> ${esc(m.short)}: ${esc(m.definition)} Curb Cut's ` +
      'estimates from the DHS 2024 microdata, each with its 95% confidence interval, as on the ' +
      'state pages and in the data explorer.',
    '<strong>Different definitions.</strong> An assumed share of everyone, a global figure for ' +
      '“significant disability” and a measured share at the Washington Group cut-off count ' +
      'different things. An assumed rate inside a survey interval does not show that the ' +
      'assumption is right, and one outside it does not show that it is wrong. The state file ' +
      `holds no broader survey measure for all activities together, so the page compares with ${esc(m.short)} only. ` +
      'The NDHS 2024 report gives a broader measure (“some difficulty” or worse) for each state, ' +
      'but for ages 15 and over, for women and men separately, and without intervals. ' +
      'The <a href="./#comparison-heading">main page’s comparison of published figures</a> shows how much the definition matters.',
    `<strong>Different ages.</strong> The survey figures are for one age group at a time (${esc(ages)}); ` +
      'the assumption is applied to people of all ages. So the page compares rates with rates, ' +
      'and never turns a survey rate into a count.',
    '<strong>The implied count.</strong> Only the assumption becomes a count: the assumed rate ' +
      `times the state's population projection. ${esc(data.population.description)} Source: ` +
      `${link(data.population.url, data.population.source)}. JONAPWD applied its rate to 2025 ` +
      'projections, so these counts are not its published figures.',
    '<strong>Inside the interval.</strong> “Inside” means the assumed rate lies within the ' +
      'survey’s 95% confidence interval, both bounds included; “above” and “below” mean outside ' +
      'it. The comparison uses the unrounded bounds; the table rounds them to 1 decimal. States ' +
      'whose survey figure is suppressed, missing or too imprecise are not compared, and the ' +
      'table says why. Estimates flagged “Review” are compared, but read them with care.',
  ];
  return `<ul class="sentences">${items.map((i) => `<li>${i}</li>`).join('')}</ul>`;
}

/** One age group's table at a rate, as plain HTML (no sort buttons): the <noscript> version. */
export function tableHtml(rows, rate, data, age) {
  const cols = columns();
  const head = cols
    .map((c) => `<th scope="col"${c.type === 'text' ? '' : ' class="num"'}>${esc(c.label)}</th>`)
    .join('');
  const body = rows
    .map((row) => {
      const cells = [`<th scope="row">${link(`./states/${stateSlug(row.place)}.html`, row.place)}</th>`];
      for (const c of cols.slice(1)) {
        if (row.words && (c.key === 'estimate' || c.key === 'low' || c.key === 'high')) {
          if (c.key === 'estimate') cells.push(`<td colspan="3" class="words">${esc(row.words)}</td>`);
          continue;
        }
        cells.push(`<td${c.type === 'text' ? '' : ' class="num"'}>${esc(cellText(row, c))}</td>`);
      }
      return `<tr>${cells.join('')}</tr>`;
    })
    .join('');
  return (
    `<table><caption tabindex="0">${esc(caption(rate, data, age))}</caption>` +
    `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`
  );
}

/**
 * The static version at the default rate, one section per age group, with links to the
 * view's files (`files(age)` -> {csv: {href, text}, json: {href, text}}).
 */
export function staticHtml(data, files) {
  const rate = data.rates.default;
  return data.age_groups
    .map((g) => {
      const rows = sortRows(tableRows(data, g.value, rate), DEFAULT_SORT);
      const f = files(g.value);
      const name = `${g.label.toLowerCase()} at ${rateText(rate)}%`;
      const dl = ['csv', 'json']
        .map((k) => `<a href="${esc(f[k].href)}" download aria-label="${esc(`${f[k].text}: ${name}`)}">${esc(f[k].text)}</a>`)
        .join(' · ');
      return (
        `<h3>${esc(g.label)}, at an assumed ${esc(rateText(rate))}%</h3>` +
        `<p>${esc(summary(rows, rate, data, g.value))}</p>` +
        `<div class="table-wrap">${tableHtml(rows, rate, data, g.value)}</div>` +
        `<p class="table-download">Download this table: ${dl}</p>`
      );
    })
    .join('');
}
