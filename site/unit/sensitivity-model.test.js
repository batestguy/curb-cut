// Unit tests for the sensitivity page's pure helpers (src/sensitivity-model.js) and its
// build-time plugin (scripts/sensitivity-static.mjs), with Node's built-in test runner.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  DEFAULT_SORT,
  POSITIONS,
  asRate,
  caption,
  cellText,
  chartKey,
  classify,
  columns,
  csvText,
  definitionsHtml,
  downloadRows,
  esc,
  fileBase,
  invalidText,
  jsonText,
  parseQuery,
  parseRate,
  rateList,
  rateText,
  resolveView,
  snapRate,
  sortRows,
  staticHtml,
  summary,
  tableHtml,
  tableRows,
  toQuery,
  valueText,
} from '../src/sensitivity-model.js';
import { fillPage, staticFiles } from '../scripts/sensitivity-static.mjs';

const RATES = { min: 2, max: 20, step: 0.5, default: 15 };

// The committed fixture (built by sensitivity_data.py from tests/fixtures/*.parquet): Abia,
// Adamawa, Anambra and Bauchi suppressed for children 5-17, Zamfara with no data.
const FIXTURE = JSON.parse(readFileSync(new URL('../tests/fixtures/sensitivity.json', import.meta.url), 'utf8'));

function cellOf(state, estimate, low, high, extra = {}) {
  return {
    state,
    estimate,
    ci_low: low,
    ci_high: high,
    n_unweighted: estimate == null ? null : 500,
    precision_flag: 'reliable',
    precision_reason: null,
    suppressed: false,
    has_data: true,
    population_2023: 1_000_000,
    ...extra,
  };
}

// A small sensitivity.json.
const DATA = {
  ...FIXTURE,
  states: {
    '18+': [
      cellOf('Kano', 0.1, 0.08, 0.15),
      cellOf('Abia', 0.03, 0.02, 0.04),
      cellOf('Lagos', 0.2, 0.15, 0.25),
      cellOf('Oyo', 0.03, 0.001, 0.4, { precision_flag: 'unreliable' }),
      cellOf('Imo', null, null, null, { suppressed: true, precision_flag: 'suppressed', precision_reason: 'n<30 (disclosure)' }),
    ],
    '5-17': [cellOf('Kano', 0.0004, 0.0001, 0.001, { precision_flag: 'review' })],
  },
};

test('rates: 2 to 20 in steps of 0.5, typed text and snapping', () => {
  const list = rateList(RATES);
  assert.equal(list.length, 37);
  assert.equal(list[0], 2);
  assert.equal(list.at(-1), 20);
  assert.ok(list.includes(15));
  assert.equal(parseRate('12', RATES), 12);
  assert.equal(parseRate(' 12.5 ', RATES), 12.5);
  assert.equal(parseRate('2', RATES), 2);
  assert.equal(parseRate('20', RATES), 20);
  for (const bad of ['', '  ', 'abc', '12.3', '1.5', '20.5', '-5', 'Infinity', '0x10', '1e1', '+12', '12.', '.5', null, undefined]) {
    assert.equal(parseRate(bad, RATES), null, String(bad));
  }
  assert.equal(asRate(15, RATES), 15);
  assert.equal(asRate(Number.NaN, RATES), null);
  assert.equal(snapRate(12.3, RATES), 12.5);
  assert.equal(snapRate(12.2, RATES), 12);
  assert.equal(snapRate(99, RATES), 20);
  assert.equal(snapRate(-3, RATES), 2);
  assert.equal(snapRate(Number.NaN, RATES), null);
  assert.equal(rateText(15), '15');
  assert.equal(rateText(15.5), '15.5');
  assert.equal(valueText(15), '15 percent');
  assert.equal(valueText(2.5), '2.5 percent');
  assert.equal(chartKey('18+', 15), '18+|15.0');
  assert.equal(chartKey('5-17', 2.5), '5-17|2.5');
});

test('classify: inside includes both bounds; the comparison uses the unrounded proportions', () => {
  assert.equal(classify(5, 0.03, 0.05), 'inside'); // on the upper bound
  assert.equal(classify(3, 0.03, 0.05), 'inside'); // on the lower bound
  assert.equal(classify(4, 0.03, 0.05), 'inside');
  assert.equal(classify(5.5, 0.03, 0.05), 'above');
  assert.equal(classify(2.5, 0.03, 0.05), 'below');
  // Just past a bound counts, even where the table's rounded figure would read the same.
  assert.equal(classify(5, 0.03, 0.04996), 'above'); // High shows "5.0"
  assert.equal(classify(3, 0.03004, 0.05), 'below'); // Low shows "3.0"
  assert.equal(classify(15, null, null), null);
  // Rates on every step stay exact against bounds written as the same decimal.
  for (const rate of rateList(RATES)) {
    assert.equal(classify(rate, rate / 100, rate / 100), 'inside', String(rate));
  }
});

test('table rows: words for cells without a figure, the comparison and the implied count', () => {
  const rows = tableRows(DATA, '18+', 15);
  const by = Object.fromEntries(rows.map((r) => [r.place, r]));
  assert.equal(by.Kano.where, 'inside'); // 15 is Kano's High: bounds included
  assert.equal(by.Kano.positionText, POSITIONS.inside.text);
  assert.equal(by.Abia.where, 'above');
  assert.equal(by.Lagos.where, 'inside');
  assert.equal(by.Oyo.words, 'Not shown: too imprecise (unreliable)');
  assert.equal(by.Oyo.where, null);
  assert.equal(by.Oyo.estimate, null);
  assert.equal(by.Oyo.positionText, 'Not compared');
  assert.equal(by.Oyo.flag, 'Unreliable');
  assert.equal(by.Imo.words, 'Suppressed (fewer than 30 respondents)');
  assert.equal(by.Imo.flag, 'Suppressed');
  assert.ok(Math.abs(by.Kano.estimate - 10) < 1e-12);
  // The count is the assumption only: rate x the all-ages projection, for every state.
  assert.equal(by.Kano.count, 150_000);
  assert.equal(by.Imo.count, 150_000);
  assert.equal(tableRows(DATA, '18+', 2).find((r) => r.place === 'Abia').where, 'inside');
  assert.equal(tableRows(DATA, '18+', 2).find((r) => r.place === 'Lagos').where, 'below');
});

test('summary: generated from the rows, with the states not compared named', () => {
  const rows = tableRows(DATA, '18+', 15);
  assert.equal(
    summary(rows, 15, DATA, '18+'),
    "At an assumed 15%, the assumption is above the survey's interval in 1 of 3 states, inside it in 2 " +
      'and below it in 0 (DISABILITY3, adults 18+, DHS 2024). Not compared, as the survey figure is ' +
      'not shown: Imo and Oyo.',
  );
  const kids = tableRows(DATA, '5-17', 2.5);
  assert.equal(
    summary(kids, 2.5, DATA, '5-17'),
    "At an assumed 2.5%, the assumption is above the survey's interval in 1 of 1 state, inside it in 0 " +
      'and below it in 0 (DISABILITY3, children 5–17, DHS 2024).',
  );
  const none = tableRows({ ...DATA, states: { '18+': [DATA.states['18+'][4]] } }, '18+', 15);
  assert.equal(
    summary(none, 15, DATA, '18+'),
    'At an assumed 15%, no state has a survey figure to compare (DISABILITY3, adults 18+, DHS 2024). ' +
      'Not compared, as the survey figure is not shown: Imo.',
  );
  // On the fixture: four suppressed children's cells and Zamfara's missing ones.
  const fixture = summary(tableRows(FIXTURE, '5-17', 15), 15, FIXTURE, '5-17');
  assert.match(fixture, /in 32 of 32 states/);
  assert.match(fixture, /not shown: Abia, Adamawa, Anambra, Bauchi and Zamfara\.$/);
});

test('cells: "<0.1" for small percentages, whole people for counts, the rate to 1 decimal', () => {
  const cols = columns();
  const col = (key) => cols.find((c) => c.key === key);
  const [row] = tableRows(DATA, '5-17', 2.5);
  assert.equal(cellText(row, col('estimate')), '<0.1');
  assert.equal(cellText(row, col('low')), '<0.1');
  assert.equal(cellText(row, col('high')), '0.1');
  assert.equal(cellText(row, col('rate')), '2.5');
  assert.equal(cellText(row, col('flag')), 'Review: few events, read with care');
  assert.equal(cellText(row, col('position')), 'Above the interval');
  assert.equal(cellText(row, col('count')), '25,000');
  assert.equal(col('rate').sortable, false);
});

test('sort: by state by default, the comparison by position, rows without a value last', () => {
  const rows = tableRows(DATA, '18+', 15);
  assert.deepEqual(sortRows(rows, DEFAULT_SORT).map((r) => r.place), ['Abia', 'Imo', 'Kano', 'Lagos', 'Oyo']);
  assert.deepEqual(
    sortRows(rows, { column: 'position', dir: 'asc' }).map((r) => r.place),
    ['Kano', 'Lagos', 'Abia', 'Imo', 'Oyo'],
  );
  assert.deepEqual(
    sortRows(rows, { column: 'position', dir: 'desc' }).map((r) => r.place),
    ['Abia', 'Kano', 'Lagos', 'Imo', 'Oyo'],
  );
  assert.deepEqual(
    sortRows(rows, { column: 'estimate', dir: 'desc' }).map((r) => r.place),
    ['Lagos', 'Kano', 'Abia', 'Imo', 'Oyo'],
  );
});

test('URL: round trip, and invalid values fall back to the defaults', () => {
  const view = { rate: 12.5, age: '5-17', sort: { column: 'estimate', dir: 'desc' } };
  const query = toQuery(view);
  assert.equal(query, '?rate=12.5&age=5-17&sort=estimate-desc');
  assert.deepEqual(resolveView(DATA, parseQuery(query)), { view, invalid: [] });
  assert.equal(toQuery({ rate: 15, age: '18+', sort: DEFAULT_SORT }), '?rate=15&age=18%2B');
  assert.deepEqual(resolveView(DATA, parseQuery('')), {
    view: { rate: 15, age: '18+', sort: { column: 'place', dir: 'asc' } },
    invalid: [],
  });
  const bad = resolveView(DATA, parseQuery('?rate=99&age=old&sort=rate-asc'));
  assert.deepEqual(bad.view, { rate: 15, age: '18+', sort: { column: 'place', dir: 'asc' } });
  assert.deepEqual(bad.invalid.map((i) => i.field), ['rate', 'age', 'sort']);
  assert.equal(resolveView(DATA, parseQuery('?rate=12.3')).view.rate, 15);
  assert.equal(resolveView(DATA, parseQuery('?rate=abc')).invalid[0].given, 'abc');
  const text = invalidText(bad.invalid, DATA);
  assert.match(text, /^This link's choices were not all valid: the rate “99” is not one of the rates offered \(2 to 20 in steps of 0\.5\), so 15% is used; /);
  assert.match(text, /the age group “old” is not in the data, so adults 18 and over is used/);
  assert.equal(invalidText([], DATA), '');
});

test('downloads: words in the estimate column, unrounded values, the explorer\'s CSV format', () => {
  const rows = sortRows(tableRows(DATA, '18+', 15), DEFAULT_SORT);
  const values = downloadRows(rows);
  const imo = values[1];
  assert.deepEqual(imo.slice(0, 5), ['Imo', 15, 'Suppressed (fewer than 30 respondents)', null, null]);
  assert.equal(imo[6], 'Not compared');
  assert.equal(imo[7], 150000);
  const csv = csvText(rows).split('\r\n');
  assert.equal(
    csv[0],
    'State,Assumed rate (%),Survey estimate (%),Low (%),High (%),Precision,Assumed rate against the interval,' +
      '"Implied count at the assumed rate (all ages, 2023 projection)"',
  );
  assert.equal(csv[1], 'Abia,15.0,3.0,2.0,4.0,Reliable,Above the interval,150000.0');
  assert.equal(csv[2], 'Imo,15.0,Suppressed (fewer than 30 respondents),,,Suppressed,Not compared,150000.0');
  const doc = JSON.parse(jsonText(rows, 15, '18+', DATA, 'https://example.org/sensitivity.html?rate=15'));
  assert.equal(doc.table, 'assumed-rate-15-0-dhs2024-disability3-18plus');
  assert.equal(doc.page, 'https://example.org/sensitivity.html?rate=15');
  assert.equal(doc.caption, caption(15, DATA, '18+'));
  assert.deepEqual(doc.rows, values);
  assert.equal(doc.columns.length, columns().length);
  assert.ok(doc.sources.some((s) => s.includes('Demographic Bulletin 2023')));
  assert.equal(fileBase(15, '18+'), 'curb-cut-assumed-rate-15-0-dhs2024-disability3-18plus');
  assert.equal(fileBase(2.5, '5-17'), 'curb-cut-assumed-rate-2-5-dhs2024-disability3-5to17');
});

test('caption names the definition, the age group and the rate', () => {
  const text = caption(12.5, DATA, '5-17');
  assert.match(text, /\(DISABILITY3\), children 5 to 17: an assumed rate of 12\.5% against/);
});

test('static HTML: escaped, words never numbers, every sentence from the data', () => {
  assert.equal(esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#x27;&lt;/a&gt;');
  const rows = sortRows(tableRows(DATA, '18+', 15), DEFAULT_SORT);
  const html = tableHtml(rows, 15, DATA, '18+');
  assert.match(html, /<td colspan="3" class="words">Suppressed \(fewer than 30 respondents\)<\/td>/);
  assert.match(html, /<th scope="row"><a href="\.\/states\/abia\.html">Abia<\/a><\/th>/);
  const defs = definitionsHtml(FIXTURE);
  assert.match(defs, /JONAPWD 2025: 15% \(All ages, all 37 states\)\. An assumption, not a count/);
  assert.match(defs, /WHO global estimate is 16%/);
  assert.match(defs, /The Washington Group Short Set DISABILITY3 measure/);
  assert.match(defs, /Not the denominator of the estimate\./);
  assert.match(defs, /both bounds included/);
});

test('build-time plugin: the static page and its files come from the same rows', () => {
  const files = staticFiles(FIXTURE, 'https://example.org/');
  const rows = sortRows(tableRows(FIXTURE, '5-17', 15), DEFAULT_SORT);
  assert.equal(files['5-17'].csv.body, csvText(rows));
  assert.equal(files['5-17'].csv.path, 'data/downloads/sensitivity/curb-cut-assumed-rate-15-0-dhs2024-disability3-5to17.csv');
  assert.equal(JSON.parse(files['18+'].json.body).page, 'https://example.org/sensitivity.html?rate=15&age=18%2B');
  const html = fillPage(
    '<main><!-- sensitivity:definitions --><noscript><!-- sensitivity:static --></noscript></main>',
    FIXTURE,
    files,
  );
  assert.doesNotMatch(html, /sensitivity:/);
  assert.equal((html.match(/<table>/g) ?? []).length, 2);
  assert.match(html, /in 32 of 32 states/);
  assert.match(html, /href="\.\/data\/downloads\/sensitivity\/curb-cut-assumed-rate-15-0-dhs2024-disability3-18plus\.csv"/);
  const page = staticHtml(FIXTURE, (age) => files[age]);
  assert.match(page, /<h3>Adults 18 and over, at an assumed 15%<\/h3>/);
  assert.match(fillPage('<!-- sensitivity:static -->', null, null), /no data/);
});
