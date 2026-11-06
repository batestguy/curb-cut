// The data explorer (explorer.html, P6 item 10): a filterable, sortable table of the DHS 2024
// cells, queried in the browser with DuckDB-WASM from the two Parquet files the site serves.
//
// * The form's choices are the distinct values in the files for the chosen level, labelled
//   from data/explorer.json (built by packages/transform/scripts/explorer_charts.py).
// * Nothing is queried while choosing: "Show figures" applies the choices, moves focus to the
//   results heading, and the one polite live region says "Showing N rows: …".
// * The view lives in the query string (shareable, bookmarkable, the back button works); a
//   value the data do not hold falls back to the default, with a visible message.
// * Suppressed cells, cells with no data and unreliable estimates show words, never numbers.
// * The chart of a view is a pre-built disability_access_charts document (the library has no
//   browser-side renderer); a CSV and a JSON of the table are made in the browser from the
//   rows the table shows, in downloads.py's format.
import { START_TIMEOUT_MS, withTimeout } from './engine.js';
import {
  DEFAULT_VIEW,
  caption,
  columns,
  countValue,
  csvText,
  fileBase,
  jsonText,
  parseQuery,
  pctText,
  resolveView,
  sizeText,
  sortRows,
  statusText,
  tableRows,
  toQuery,
} from './explorer-model.js';
import { downloadLine, formatValue, stateHref, watchTableWraps } from './format.js';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;
const EXTENSIONS_URL = `${import.meta.env.BASE_URL}duckdb-extensions`;
const FIELDS = ['level', 'measure', 'age', 'sex', 'place'];

const $ = (id) => document.getElementById(id);
const form = $('explorer-form');
const status = $('explorer-status');
const urlMessage = $('url-message');
const fallback = $('explorer-fallback');
const results = $('results');
const heading = $('results-heading');
const tableHolder = $('results-table');
const downloadsEl = $('results-downloads');
const columnsEl = $('results-columns');
const chartNote = $('chart-note');
const chartFigure = $('explorer-chart-figure');
const chartData = $('chart-data');
const chartDataSummary = $('chart-data-summary');
const chartDataTable = $('chart-data-table');
const selects = Object.fromEntries(FIELDS.map((f) => [f, $(`f-${f}`)]));
const showButton = $('f-show');

let meta;
let combos;
let places;
let runQuery;
let options;
let current; // the view on screen
let shownRows = [];
let latest = 0;
let blobUrls = [];

function setStatus(text, error = false) {
  status.classList.toggle('error', error);
  status.textContent = text;
}

async function getJson(path) {
  const response = await fetch(`${DATA_URL}${path}`);
  if (!response.ok) throw new Error(`could not fetch ${path} (HTTP ${response.status})`);
  return response.json();
}

const FIGURES =
  'measure, age_group, sex, estimate, ci_low, ci_high, n_unweighted, precision_flag, ' +
  'precision_reason, suppressed';

async function startEngine(files) {
  const { openDatabase } = await import('./duckdb-client.js');
  const state = files.state;
  const nz = files.zone;
  const conn = await openDatabase(
    [...new Set([state, nz])].map((name) => ({ url: `${DATA_URL}${name}`, name })),
    EXTENSIONS_URL,
  );
  const plain = async (sql) => (await conn.query(sql)).toArray().map((r) => r.toJSON());
  const byState = await conn.prepare(
    `select state as place, ${FIGURES}, has_data from read_parquet('${state}')
     where measure = ? and age_group = ? and sex = ? and (? = '' or state = ?)`,
  );
  const byGeography = await conn.prepare(
    `select geography as place, ${FIGURES}, true as has_data from read_parquet('${nz}')
     where geography_level = ? and measure = ? and age_group = ? and sex = ?
       and (? = '' or geography = ?)`,
  );
  const comboRows = await plain(
    `select distinct 'state' as level, measure, age_group, sex from read_parquet('${state}')
     union all
     select distinct geography_level, measure, age_group, sex from read_parquet('${nz}')`,
  );
  const placeRows = await plain(
    `select distinct 'state' as level, state as place from read_parquet('${state}')
     union all
     select distinct geography_level, geography from read_parquet('${nz}')`,
  );
  const query = async (view) => {
    const result =
      view.level === 'state'
        ? await byState.query(view.measure, view.age, view.sex, view.place, view.place)
        : await byGeography.query(view.level, view.measure, view.age, view.sex, view.place, view.place);
    return result.toArray().map((r) => r.toJSON());
  };
  return { query, combos: comboRows, places: placeRows };
}

// --- The form -------------------------------------------------------------------------------

function fillSelect(select, list, value) {
  const same =
    select.options.length === list.length &&
    list.every((o, i) => select.options[i].value === o.value && select.options[i].text === o.label);
  if (!same) select.replaceChildren(...list.map((o) => new Option(o.label, o.value)));
  select.value = value;
}

function fillForm(resolved) {
  options = resolved.options;
  for (const field of FIELDS) fillSelect(selects[field], options[field], resolved.view[field]);
}

function formWanted() {
  return Object.fromEntries(FIELDS.map((f) => [f, selects[f].value]));
}

function setFormEnabled(enabled) {
  for (const select of Object.values(selects)) select.disabled = !enabled;
  showButton.disabled = !enabled;
}

const FIELD_NAMES = {
  level: 'level',
  measure: 'measure',
  age: 'age group',
  sex: 'sex',
  place: 'place',
  sort: 'sort order',
};

// Shows (and returns, for the live region) the message about a link's invalid choices.
function showInvalid(invalid, view) {
  if (invalid.length === 0) {
    urlMessage.hidden = true;
    urlMessage.textContent = '';
    return '';
  }
  const parts = invalid.map(({ field, given }) => {
    const used =
      field === 'sort'
        ? 'by place name'
        : (options[field].find((o) => o.value === view[field])?.label ?? view[field]);
    return `the ${FIELD_NAMES[field]} “${given}” is not in the data, so ${used} is used`;
  });
  urlMessage.textContent = `This link's choices were not all valid: ${parts.join('; ')}. The defaults are shown instead.`;
  urlMessage.hidden = false;
  return urlMessage.textContent;
}

// --- The table ------------------------------------------------------------------------------

const SORT_WORDS = {
  text: { asc: 'A to Z', desc: 'Z to A' },
  number: { asc: 'lowest first', desc: 'highest first' },
  integer: { asc: 'smallest first', desc: 'largest first' },
};

function cell(tag, text, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = text;
  return el;
}

function headerRow(cols, sort) {
  const tr = document.createElement('tr');
  for (const col of cols) {
    const th = cell('th', null, col.type === 'text' ? undefined : 'num');
    th.scope = 'col';
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

function updateHeader(tr, sort) {
  for (const th of tr.children) {
    const button = th.querySelector('button');
    const on = button.dataset.key === sort.column;
    if (on) th.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending');
    else th.removeAttribute('aria-sort');
    button.querySelector('.sort-icon').textContent = on ? (sort.dir === 'asc' ? '▲' : '▼') : '↕';
  }
}

function bodyRows(tbody, rows, level) {
  const trs = rows.map((row) => {
    const tr = document.createElement('tr');
    const th = cell('th', null);
    th.scope = 'row';
    if (level === 'state') {
      const a = document.createElement('a');
      a.href = stateHref(row.place);
      a.textContent = row.place;
      th.append(a);
    } else {
      th.textContent = row.place;
    }
    tr.append(th);
    if (row.words) {
      // One cell across Estimate, Low and High, as on the state pages: words, never a number.
      const td = cell('td', row.words, 'words');
      td.colSpan = 3;
      tr.append(td);
    } else {
      for (const key of ['estimate', 'low', 'high']) {
        tr.append(cell('td', pctText(row[key]), 'num'));
      }
    }
    tr.append(cell('td', row.flag));
    tr.append(cell('td', row.reason ?? ''));
    const n = countValue(row.n);
    tr.append(cell('td', typeof n === 'number' ? formatValue(n, 'integer') : (n ?? ''), 'num'));
    return tr;
  });
  tbody.replaceChildren(...trs);
}

function renderTable(rows, view) {
  const cols = columns(view.level);
  const table = document.createElement('table');
  table.id = 'results-data';
  table.createCaption().textContent = caption(view, options, meta);
  table.createTHead().append(headerRow(cols, view.sort));
  bodyRows(table.createTBody(), rows, view.level);
  tableHolder.replaceChildren(table);
}

function sortBy(key) {
  const before = current.sort;
  const dir = before.column === key && before.dir === 'asc' ? 'desc' : 'asc';
  current = { ...current, sort: { column: key, dir } };
  shownRows = sortRows(shownRows, current.sort);
  const table = $('results-data');
  updateHeader(table.tHead.rows[0], current.sort);
  bodyRows(table.tBodies[0], shownRows, current.level);
  history.replaceState(null, '', toQuery(current));
  renderDownloads(shownRows, current);
  const col = columns(current.level).find((c) => c.key === key);
  setStatus(`Sorted by ${col.label}, ${SORT_WORDS[col.type][dir]}.`);
}

tableHolder.addEventListener('click', (event) => {
  const button = event.target.closest('button.sort-button');
  if (button) sortBy(button.dataset.key);
});

// --- Downloads and the columns' meanings ----------------------------------------------------

function renderDownloads(rows, view) {
  for (const url of blobUrls) URL.revokeObjectURL(url);
  blobUrls = [];
  const base = `curb-cut-${fileBase(view)}`;
  const files = [
    ['CSV', 'text/csv', csvText(rows, view.level), `${base}.csv`],
    ['JSON', 'application/json', jsonText(rows, view, options, meta, window.location.href), `${base}.json`],
  ].map(([format, type, text, filename]) => {
    const blob = new Blob([text], { type: `${type};charset=utf-8` });
    const href = URL.createObjectURL(blob);
    blobUrls.push(href);
    return { format, href, filename, text: `${format}, ${sizeText(blob.size)}` };
  });
  const line = downloadLine({ name: 'the table shown above', files }, '');
  line.querySelectorAll('a').forEach((a, i) => a.setAttribute('download', files[i].filename));
  downloadsEl.replaceChildren(line);
}

function renderColumnLinks(level) {
  const links = meta.dictionary[level];
  const items = [
    ['Estimate', links.estimate],
    ['Low', links.ci_low],
    ['High', links.ci_high],
    ['Precision', links.precision_flag],
    ['Reason for the flag', links.precision_reason],
    ['Respondents', links.n_unweighted],
    ['suppressed cells', links.suppressed],
  ];
  const parts = ['What these columns mean, in the data dictionary: '];
  items.forEach(([text, href], i) => {
    const a = document.createElement('a');
    a.href = `./${href}`;
    a.textContent = text;
    parts.push(a, i < items.length - 1 ? ', ' : '.');
  });
  parts.push(' The file this table comes from: ');
  const file = document.createElement('a');
  file.href = `./${links.file}`;
  file.textContent = meta.files[level];
  parts.push(file, '.');
  columnsEl.replaceChildren(...parts);
}

// --- The chart ------------------------------------------------------------------------------

let chartModule;
let chartHandle;

function clearChart(text = '') {
  chartHandle?.dispose();
  chartHandle = null;
  chartFigure.hidden = true;
  chartData.hidden = true;
  chartDataTable.replaceChildren();
  chartNote.textContent = text;
}

const chartUnavailable = clearChart;

async function renderViewChart(view, request) {
  const key = `${view.level}|${view.measure}|${view.age}|${view.sex}`;
  if (view.level === 'national') {
    chartUnavailable(
      'No chart: Nigeria as a whole has one figure in this view, and the table above shows it.',
    );
    return;
  }
  const entry = meta.charts[key];
  const plural = view.level === 'state' ? 'states' : 'zones';
  if (!entry?.href) {
    chartUnavailable(`No chart: fewer than two ${plural} have a figure in this view.`);
    return;
  }
  try {
    chartModule ??= await import('./chart.js');
    const doc = await getJson(entry.href);
    if (request !== latest) return;
    const drawn = doc.data.categories.length;
    const notes = [];
    if (view.place) {
      const inChart = doc.data.categories.includes(view.place);
      notes.push(
        inChart
          ? `The chart shows all ${drawn} ${plural} with a figure in this view, highest first, with ${view.place} highlighted (thick outline, bold label). The table above shows ${view.place} alone; the chart's figures for all ${drawn} are under "Chart data" after the chart.`
          : `The chart shows all ${drawn} ${plural} with a figure in this view, highest first; their figures are under "Chart data" after the chart. ${view.place} has no figure here, so nothing is highlighted.`,
      );
    } else {
      notes.push(`The chart shows the ${drawn} ${plural} with a figure in this view, highest first.`);
    }
    if (entry.left_out.length > 0) {
      // The table says why for each (suppressed, no data, or too imprecise).
      notes.push(`Not drawn, as they have no figure in the table: ${entry.left_out.map((l) => l.place).join(', ')}.`);
    }
    chartNote.textContent = notes.join(' ');
    chartFigure.hidden = false;
    chartHandle?.dispose();
    chartHandle = null;
    // A view of every place: the table above holds exactly the chart's figures. A one-place
    // view: the chart shows the whole level, so its own table (from the same document) goes
    // under "Chart data".
    if (!view.place) chartDataTable.replaceChildren();
    chartDataSummary.textContent = `Chart data: all ${drawn} ${plural} in the chart`;
    chartData.hidden = !view.place;
    const handle = await chartModule.renderChart(doc, {
      container: $('explorer-chart'),
      titleEl: $('explorer-chart-title'),
      descEl: $('explorer-chart-desc'),
      tableEl: view.place ? chartDataTable : null,
      highlight: view.place || null,
    });
    if (request !== latest) {
      // A newer view was asked for while this one drew; that one draws its own chart.
      handle.dispose();
      return;
    }
    chartHandle = handle;
  } catch (error) {
    if (request !== latest) return;
    chartUnavailable(
      `The chart could not be loaded: ${error.message}. The table above has this view's figures.`,
    );
  }
}

// --- Showing a view -------------------------------------------------------------------------

async function show(view, { focus, prefix = '' }) {
  const request = ++latest;
  results.setAttribute('aria-busy', 'true');
  // The previous view's chart never stays up under a new table.
  clearChart();
  try {
    const cells = await runQuery(view);
    if (request !== latest) return;
    current = view;
    shownRows = sortRows(tableRows(cells, meta), view.sort);
    renderTable(shownRows, view);
    renderDownloads(shownRows, view);
    renderColumnLinks(view.level);
    results.hidden = false;
    fallback.hidden = true;
    const shownText = statusText(shownRows.length, view, options, meta);
    setStatus(prefix ? `${prefix} ${shownText}` : shownText);
    if (focus) heading.focus();
    await renderViewChart(view, request);
  } catch (error) {
    if (request !== latest) return;
    fail(`the figures could not be loaded: ${error.message}`);
  } finally {
    if (request === latest) results.removeAttribute('aria-busy');
  }
}

function fail(what) {
  results.hidden = true;
  fallback.hidden = false;
  setStatus(
    `Sorry, ${what}. The same figures are on the state pages and in the data files listed below.`,
    true,
  );
}

// The view in the address: shown at once (a shared or bookmarked link, or the back button).
// With no query string, the form shows the defaults and nothing is shown until the button is
// pressed.
function applyUrl({ focus }) {
  const wanted = parseQuery(window.location.search);
  const resolved = resolveView(meta, combos, places, wanted);
  fillForm(resolved);
  const invalidText = showInvalid(resolved.invalid, resolved.view);
  if (Object.values(wanted).every((v) => v === undefined)) {
    ++latest;
    current = undefined;
    results.hidden = true;
    setStatus('Ready. Choose what to show, then press Show figures.');
    return Promise.resolve();
  }
  if (resolved.invalid.length > 0) history.replaceState(null, '', toQuery(resolved.view));
  // The fallback is announced with the result, and stays visible above it.
  return show(resolved.view, { focus, prefix: invalidText });
}

const FIELD_LABELS = {
  level: 'Level',
  measure: 'Measure',
  age: 'Age group',
  sex: 'Sex',
  place: 'State or zone',
};

form.addEventListener('change', (event) => {
  // Keep every choice valid for the ones before it (no query: nothing is shown until the
  // button is pressed). A later choice that had to change is announced; focus stays put.
  const before = formWanted();
  const resolved = resolveView(meta, combos, places, before);
  fillForm(resolved);
  const changed = FIELDS.filter(
    (f) => f !== event.target.name && before[f] !== '' && before[f] !== resolved.view[f],
  );
  if (changed.length === 0) return;
  const level = options.level.find((o) => o.value === resolved.view.level)?.label;
  const parts = changed.map((f) => {
    const label = options[f].find((o) => o.value === resolved.view[f])?.label ?? resolved.view[f];
    return `${FIELD_LABELS[f]} reset to ${label}`;
  });
  setStatus(
    `${parts.join('; ')}: the previous choice is not available for ${level} with the choices above it.`,
  );
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const resolved = resolveView(meta, combos, places, formWanted());
  const view = { ...resolved.view, sort: current?.sort ?? { ...DEFAULT_VIEW.sort } };
  showInvalid([], view);
  const query = toQuery(view);
  if (query !== window.location.search) history.pushState(null, '', query);
  setStatus('Loading the figures…');
  show(view, { focus: true });
});

window.addEventListener('popstate', () => {
  if (meta && runQuery) applyUrl({ focus: false });
});

async function start() {
  form.hidden = false;
  fallback.hidden = true;
  setFormEnabled(false);
  for (const select of Object.values(selects)) select.replaceChildren(new Option('Loading…', ''));
  setStatus(
    'Loading the data in your browser. The first time can take about 10 seconds; nothing is sent to a server.',
  );
  watchTableWraps();
  try {
    meta = await getJson('explorer.json');
    const engine = await withTimeout(
      startEngine(meta.files),
      START_TIMEOUT_MS,
      'the in-browser database took too long to start',
    );
    ({ combos, places } = engine);
    runQuery = engine.query;
  } catch (error) {
    form.hidden = true;
    fail(`the explorer could not start: ${error.message}`);
    return;
  }
  setFormEnabled(true);
  await applyUrl({ focus: false });
}

start();
