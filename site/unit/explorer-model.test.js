// Unit tests for the data explorer's pure helpers (src/explorer-model.js), with Node's built-in
// test runner (no framework to install): `npm run test:unit`, also run by `npm test`.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  DEFAULT_VIEW,
  caption,
  csvText,
  downloadRows,
  fileBase,
  jsonText,
  missingText,
  parseQuery,
  pyFloat,
  resolveView,
  sizeText,
  sortRows,
  statusText,
  tableRows,
  toQuery,
} from '../src/explorer-model.js';

// A small explorer.json, shaped as packages/transform/scripts/explorer_charts.py writes it.
const META = {
  levels: [
    { value: 'state', label: 'States' },
    { value: 'zone', label: 'Geopolitical zones' },
    { value: 'national', label: 'Nigeria as a whole' },
  ],
  measures: [
    { value: 'disability3', label: 'Disability: a lot of difficulty or cannot do at all in at least one of six activities' },
    { value: 'seeing_3plus', label: 'Seeing: a lot of difficulty or cannot do at all' },
    { value: 'seeing_level_1', label: 'Seeing: no difficulty' },
  ],
  age_groups: [
    { value: '18+', label: 'Adults 18 and over' },
    { value: '5-17', label: 'Children 5 to 17' },
  ],
  sexes: [
    { value: 'all', label: 'Both sexes' },
    { value: 'female', label: 'Female' },
    { value: 'male', label: 'Male' },
  ],
  groups: { '18+|all': 'Adults 18+', '5-17|female': 'Girls 5–17', '18+|female': 'Women 18+' },
  places: { national: { value: 'NG', label: 'Nigeria' } },
  files: { state: 'dhs2024_state_prevalence.parquet', zone: 'dhs2024_national_zone.parquet', national: 'dhs2024_national_zone.parquet' },
  flags: { reliable: 'Reliable', review: 'Review: few events, read with care', unreliable: 'Unreliable', suppressed: 'Suppressed', no_data: 'No data' },
  reasons: {
    'low_events<10': 'fewer than 10 people with the difficulty in the sample',
    'zero_events': 'no one in the sample has the difficulty',
    'df<8': 'fewer than 8 degrees of freedom',
    'n<30 (disclosure)': 'fewer than 30 respondents (disclosure rule)',
    'complementary suppression (disclosure)': 'withheld so that a neighbouring small cell cannot be worked out by subtraction',
  },
  missing: {
    too_few: 'Suppressed (fewer than 30 respondents)',
    withheld: 'Suppressed (withheld to protect a neighbouring small cell)',
    unreliable: 'Not shown: too imprecise (unreliable)',
    no_data: 'No data',
  },
  download: { survey: 'DHS', year: '2024', sources: ['DHS citation'], terms: 'Terms.', values: 'Values rule.' },
  charts: {},
};

const COMBOS = [
  ...['18+', '5-17'].flatMap((age) =>
    ['all', 'female', 'male'].map((sex) => ({ level: 'state', measure: 'disability3', age_group: age, sex })),
  ),
  { level: 'state', measure: 'seeing_3plus', age_group: '18+', sex: 'all' },
  { level: 'zone', measure: 'disability3', age_group: '18+', sex: 'all' },
  { level: 'national', measure: 'disability3', age_group: '18+', sex: 'all' },
  { level: 'national', measure: 'seeing_level_1', age_group: '18+', sex: 'all' },
];
const PLACES = [
  { level: 'state', place: 'Lagos' },
  { level: 'state', place: 'Kano' },
  { level: 'state', place: 'Akwa Ibom' },
  { level: 'zone', place: 'North West' },
  { level: 'national', place: 'NG' },
];

const cell = (place, extra = {}) => ({
  place,
  estimate: 0.05,
  ci_low: 0.04,
  ci_high: 0.06,
  n_unweighted: 1234,
  precision_flag: 'reliable',
  precision_reason: null,
  suppressed: false,
  has_data: true,
  ...extra,
});

test('the query string round-trips, leaving out the defaults', () => {
  const view = { level: 'state', measure: 'disability3', age: '5-17', sex: 'female', place: 'Akwa Ibom', sort: { column: 'estimate', dir: 'desc' } };
  const query = toQuery(view);
  assert.equal(query, '?level=state&measure=disability3&age=5-17&sex=female&place=Akwa+Ibom&sort=estimate-desc');
  const back = resolveView(META, COMBOS, PLACES, parseQuery(query));
  assert.deepEqual(back.invalid, []);
  assert.deepEqual(back.view, view);
  assert.equal(toQuery({ ...DEFAULT_VIEW }), '?level=state&measure=disability3&age=18%2B&sex=all');
  assert.equal(parseQuery('?age=18%2B').age, '18+');
});

test('no query gives the defaults, with nothing reported as invalid', () => {
  const { view, invalid } = resolveView(META, COMBOS, PLACES, parseQuery(''));
  assert.deepEqual(invalid, []);
  assert.deepEqual(view, { ...DEFAULT_VIEW, sort: { ...DEFAULT_VIEW.sort } });
});

test('invalid values fall back to the defaults and are each reported', () => {
  const { view, invalid } = resolveView(
    META,
    COMBOS,
    PLACES,
    parseQuery('?level=planet&measure=happiness&age=99&sex=x&place=Atlantis&sort=colour-up'),
  );
  assert.deepEqual(view, { ...DEFAULT_VIEW, sort: { ...DEFAULT_VIEW.sort } });
  assert.deepEqual(
    invalid.map((i) => i.field),
    ['level', 'measure', 'age', 'sex', 'place', 'sort'],
  );
  assert.equal(invalid[0].given, 'planet');
  assert.equal(invalid[0].used, 'state');
});

test("each field's choices are what the data hold given the fields before it", () => {
  const state = resolveView(META, COMBOS, PLACES, { level: 'state' });
  assert.deepEqual(state.options.measure.map((o) => o.value), ['disability3', 'seeing_3plus']);
  assert.deepEqual(state.options.place.map((o) => o.label), ['All 3 states', 'Akwa Ibom', 'Kano', 'Lagos']);
  const seeing = resolveView(META, COMBOS, PLACES, { level: 'state', measure: 'seeing_3plus' });
  assert.deepEqual(seeing.options.age.map((o) => o.value), ['18+']);
  assert.deepEqual(seeing.options.sex.map((o) => o.value), ['all']);
  const national = resolveView(META, COMBOS, PLACES, { level: 'national', place: '' });
  assert.deepEqual(national.options.measure.map((o) => o.value), ['disability3', 'seeing_level_1']);
  assert.deepEqual(national.options.place, [{ value: '', label: 'Nigeria' }]);
  // A state's name is not a zone: back to all zones.
  const zone = resolveView(META, COMBOS, PLACES, { level: 'zone', place: 'Kano' });
  assert.equal(zone.view.place, '');
  assert.deepEqual(zone.invalid, [{ field: 'place', given: 'Kano', used: '' }]);
});

test('suppressed, no-data and unreliable cells show words and no figure', () => {
  const rows = tableRows(
    [
      cell('Abia', { suppressed: true, estimate: null, ci_low: null, ci_high: null, n_unweighted: null, precision_flag: 'suppressed', precision_reason: 'n<30 (disclosure)' }),
      cell('Adamawa', { suppressed: true, estimate: null, ci_low: null, ci_high: null, n_unweighted: null, precision_flag: 'suppressed', precision_reason: 'complementary suppression (disclosure)' }),
      cell('Zamfara', { has_data: false, estimate: null, ci_low: null, ci_high: null, n_unweighted: null, precision_flag: 'no_data' }),
      cell('Taraba', { precision_flag: 'unreliable', precision_reason: 'relative_ci_width>130%' }),
      cell('Kano', { precision_flag: 'review', precision_reason: 'zero_events;df<8' }),
    ],
    META,
  );
  assert.equal(rows[0].words, 'Suppressed (fewer than 30 respondents)');
  assert.equal(rows[1].words, 'Suppressed (withheld to protect a neighbouring small cell)');
  assert.equal(rows[2].words, 'No data');
  assert.equal(rows[3].words, 'Not shown: too imprecise (unreliable)');
  for (const row of rows.slice(0, 4)) {
    assert.equal(row.estimate, null);
    assert.equal(row.low, null);
    assert.equal(row.high, null);
  }
  assert.equal(rows[0].n, null);
  assert.equal(rows[2].n, null);
  assert.equal(rows[3].n, 1234); // published: the count is not what makes it unreliable
  assert.equal(rows[0].flag, 'Suppressed');
  assert.equal(rows[2].flag, 'No data');
  assert.equal(rows[0].reason, 'Fewer than 30 respondents (disclosure rule)');
  // An unknown reason code is shown as it is, never made up.
  assert.equal(rows[3].reason, 'Relative_ci_width>130%');
  assert.equal(rows[4].reason, 'No one in the sample has the difficulty; fewer than 8 degrees of freedom');
  assert.equal(rows[4].estimate, 5);
  assert.equal(missingText(cell('x'), META), null);
  // Not a number anywhere in a suppressed row's files.
  const [suppressed] = downloadRows(rows.slice(0, 1), 'state');
  assert.deepEqual(suppressed, ['Abia', 'Suppressed (fewer than 30 respondents)', null, null, 'Suppressed', 'Fewer than 30 respondents (disclosure rule)', null]);
});

test('Nigeria is named, not coded', () => {
  const [row] = tableRows([cell('NG')], META);
  assert.equal(row.place, 'Nigeria');
});

test('sorting puts rows without a value last in both directions, ties by place', () => {
  const rows = tableRows(
    [
      cell('Kano', { estimate: 0.02 }),
      cell('Abia', { suppressed: true, estimate: null, n_unweighted: null }),
      cell('Lagos', { estimate: 0.08 }),
      cell('Benue', { estimate: 0.02 }),
    ],
    META,
  );
  const order = (sort) => sortRows(rows, sort).map((r) => r.place);
  assert.deepEqual(order({ column: 'estimate', dir: 'asc' }), ['Benue', 'Kano', 'Lagos', 'Abia']);
  assert.deepEqual(order({ column: 'estimate', dir: 'desc' }), ['Lagos', 'Benue', 'Kano', 'Abia']);
  assert.deepEqual(order({ column: 'place', dir: 'desc' }), ['Lagos', 'Kano', 'Benue', 'Abia']);
  assert.deepEqual(order(undefined), ['Abia', 'Benue', 'Kano', 'Lagos']);
});

test("CSV follows downloads.py: header with units, CRLF, Python's float repr, empty for none", () => {
  const rows = tableRows(
    [
      cell('Akwa Ibom, south', { estimate: 0.034936, ci_low: 0, ci_high: 0.071118 }),
      cell('Abia', { suppressed: true, estimate: null, ci_low: null, ci_high: null, n_unweighted: null, precision_flag: 'suppressed', precision_reason: 'n<30 (disclosure)' }),
    ],
    META,
  );
  const text = csvText(rows, 'state');
  assert.equal(
    text,
    'State,Estimate (%),Low (%),High (%),Precision,Reason for the flag,Respondents (unweighted)\r\n' +
      '"Akwa Ibom, south",3.4936,0.0,7.1118,Reliable,,1234\r\n' +
      'Abia,Suppressed (fewer than 30 respondents),,,Suppressed,Fewer than 30 respondents (disclosure rule),\r\n',
  );
  assert.equal(pyFloat(0.00001), '1e-05');
  assert.equal(pyFloat(12), '12.0');
  assert.equal(pyFloat(-0), '-0.0');
  assert.equal(pyFloat(1.5e16), '1.5e+16');
});

test('JSON carries the same rows with the provenance fields of downloads.py', () => {
  const view = { level: 'state', measure: 'disability3', age: '5-17', sex: 'female', place: 'Kano', sort: { column: 'place', dir: 'asc' } };
  const { options } = resolveView(META, COMBOS, PLACES, view);
  const rows = tableRows([cell('Kano')], META);
  const doc = JSON.parse(jsonText(rows, view, options, META, 'https://example.org/explorer.html?x'));
  assert.deepEqual(Object.keys(doc), ['table', 'name', 'caption', 'page', 'survey', 'year', 'sources', 'terms', 'values', 'columns', 'rows']);
  assert.match(doc.table, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
  assert.equal(doc.table, 'explorer-dhs2024-state-disability3-5to17-female-kano');
  assert.ok(doc.name.length <= 64);
  assert.equal(doc.caption, caption(view, options, META));
  assert.deepEqual(doc.columns[1], { label: 'Estimate (%)', type: 'number', decimals: 1, unit: '%' });
  assert.deepEqual(doc.columns[6], { label: 'Respondents (unweighted)', type: 'integer', decimals: 0 });
  assert.deepEqual(doc.columns[0], { label: 'State', type: 'text' });
  assert.deepEqual(doc.rows, [['Kano', 5, 4, 6, 'Reliable', null, 1234]]);
  assert.equal(fileBase(view), 'dhs2024-state-disability3-5to17-female-kano');
});

test('the caption and status describe the view in words', () => {
  const view = { level: 'state', measure: 'disability3', age: '5-17', sex: 'female', place: 'Kano', sort: DEFAULT_VIEW.sort };
  const { options } = resolveView(META, COMBOS, PLACES, view);
  assert.equal(
    statusText(1, view, options, META),
    'Showing 1 row: Disability: a lot of difficulty or cannot do at all in at least one of six activities. Girls 5–17, Kano.',
  );
  const all = { ...view, place: '' };
  assert.match(statusText(37, all, options, META), /^Showing 37 rows: .*, each state\.$/);
  assert.match(caption(all, options, META), /Low and High: the 95% confidence interval\.$/);
  assert.equal(sizeText(10), '1 KB');
  assert.equal(sizeText(4000), '4 KB');
});
