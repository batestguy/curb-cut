// The sensitivity page (sensitivity.html, P6 item 11): an assumed rate against the DHS 2024
// survey, state by state.
//
// * The rate is chosen with a native range input (arrows, Page Up/Down, Home, End), two
//   buttons that move it by one step, or a number input; all three stay in step.
// * The table and the chart's document change at once; the summary sentence, the page's one
//   polite live region, changes once the rate has stopped moving (SETTLE_MS), so a held arrow
//   key gives one announcement, not one per step. The table is never announced.
// * The view (rate, age group, sort) lives in the query string; an invalid value falls back
//   to the default, with a visible message that is announced with the summary.
// * The chart of a view is a pre-built disability_access_charts document (the library has no
//   browser-side renderer and draws no reference line): the survey estimates with their
//   intervals, and the assumed rate as a second series. The CSV and JSON are made in the
//   browser from the rows the table shows, in downloads.py's format.
// The pure parts are in sensitivity-model.js (also used at build time for the <noscript>
// version).
import {
  caption,
  cellText,
  chartKey,
  columns,
  csvText,
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
  summary,
  tableRows,
  toQuery,
  valueText,
} from './sensitivity-model.js';
import { sizeText } from './explorer-model.js';
import { downloadLine, stateHref, watchTableWraps } from './format.js';
import { SORT_WORDS, cell, headerRow, updateHeader } from './sort-table.js';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;
// How long the rate must rest before the summary is announced (and the chart redrawn).
const SETTLE_MS = 700;

const $ = (id) => document.getElementById(id);
const form = $('rate-form');
const range = $('rate-range');
const number = $('rate-number');
const hint = $('rate-hint');
const down = $('rate-down');
const up = $('rate-up');
const rateValue = $('rate-value');
const ageOptions = $('age-options');
const summaryEl = $('summary');
const urlMessage = $('url-message');
const fallback = $('sensitivity-fallback');
const results = $('results');
const tableHolder = $('results-table');
const downloadsEl = $('results-downloads');
const columnsEl = $('results-columns');
const chartNote = $('chart-note');
const chartFigure = $('sensitivity-chart-figure');

let data;
let rates;
let view;
let rows = [];
let blobUrls = [];
let settleTimer;
let pendingPrefix = '';
let latest = 0;
let chartModule;
let chartHandle;

async function getJson(path) {
  const response = await fetch(`${DATA_URL}${path}`);
  if (!response.ok) throw new Error(`could not fetch ${path} (HTTP ${response.status})`);
  return response.json();
}

// --- The table ------------------------------------------------------------------------------

function bodyRows(tbody) {
  const cols = columns();
  tbody.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement('tr');
      const th = cell('th', null);
      th.scope = 'row';
      const a = document.createElement('a');
      a.href = stateHref(row.place);
      a.textContent = row.place;
      th.append(a);
      tr.append(th);
      for (const col of cols.slice(1)) {
        if (row.words && ['estimate', 'low', 'high'].includes(col.key)) {
          // One cell across Estimate, Low and High, as in the explorer: words, never a number.
          if (col.key === 'estimate') {
            const td = cell('td', row.words, 'words');
            td.colSpan = 3;
            tr.append(td);
          }
          continue;
        }
        tr.append(cell('td', cellText(row, col), col.type === 'text' ? undefined : 'num'));
      }
      return tr;
    }),
  );
}

function renderTable() {
  let table = $('sensitivity-data');
  if (!table) {
    table = document.createElement('table');
    table.id = 'sensitivity-data';
    table.createCaption();
    table.createTHead().append(headerRow(columns(), view.sort));
    table.createTBody();
    tableHolder.replaceChildren(table);
  }
  table.caption.textContent = caption(view.rate, data, view.age);
  updateHeader(table.tHead.rows[0], view.sort);
  bodyRows(table.tBodies[0]);
}

function viewUrl() {
  return `${window.location.origin}${window.location.pathname}${toQuery(view)}`;
}

function renderDownloads() {
  for (const url of blobUrls) URL.revokeObjectURL(url);
  blobUrls = [];
  const base = fileBase(view.rate, view.age);
  const files = [
    ['CSV', 'text/csv', csvText(rows), `${base}.csv`],
    // The view's own address (the address bar follows only once the rate settles).
    ['JSON', 'application/json', jsonText(rows, view.rate, view.age, data, viewUrl()), `${base}.json`],
  ].map(([format, type, text, filename]) => {
    const blob = new Blob([text], { type: `${type};charset=utf-8` });
    const href = URL.createObjectURL(blob);
    blobUrls.push(href);
    return { format, href, filename, text: `${format}, ${sizeText(blob.size)}` };
  });
  const line = downloadLine({ name: 'the table of states at this rate', files }, '');
  line.querySelectorAll('a').forEach((a, i) => a.setAttribute('download', files[i].filename));
  downloadsEl.replaceChildren(line);
}

function renderColumnLinks() {
  const links = data.dictionary;
  const items = [
    ['Survey estimate', links.estimate],
    ['Low', links.ci_low],
    ['High', links.ci_high],
    ['Precision', links.precision_flag],
    ['the population projection', links.population_2023],
  ];
  const parts = ['What these columns mean, in the data dictionary: '];
  items.forEach(([text, href], i) => {
    const a = document.createElement('a');
    a.href = `./${href}`;
    a.textContent = text;
    parts.push(a, i < items.length - 1 ? ', ' : '.');
  });
  parts.push(' The file the survey figures come from: ');
  const file = document.createElement('a');
  file.href = `./${links.file}`;
  file.textContent = data.files.state;
  parts.push(file, '.');
  columnsEl.replaceChildren(...parts);
}

// --- The chart ------------------------------------------------------------------------------

async function renderViewChart(request) {
  const entry = data.charts[chartKey(view.age, view.rate)];
  if (!entry?.href) {
    chartHandle?.dispose();
    chartHandle = null;
    chartFigure.hidden = true;
    chartNote.textContent = 'No chart: fewer than two states have a survey figure in this view.';
    return;
  }
  try {
    chartModule ??= await import('./chart.js');
    const doc = await getJson(entry.href);
    if (request !== latest) return;
    const notes = [
      `The chart shows the ${doc.data.categories.length} states with a survey figure, highest ` +
        'estimate first, each with its 95% confidence interval; the assumed rate is the second ' +
        `marker in every row, at ${rateText(view.rate)}%. The table above has the same figures.`,
    ];
    if (entry.left_out.length > 0) {
      notes.push(`Not drawn, as they have no figure in the table: ${entry.left_out.map((l) => l.place).join(', ')}.`);
    }
    chartNote.textContent = notes.join(' ');
    chartFigure.hidden = false;
    chartHandle?.dispose();
    chartHandle = null;
    // The page's table holds exactly the chart's figures, so the document's own table is not
    // drawn (tableEl null).
    const handle = await chartModule.renderChart(doc, {
      container: $('sensitivity-chart'),
      titleEl: $('sensitivity-chart-title'),
      descEl: $('sensitivity-chart-desc'),
      tableEl: null,
    });
    if (request !== latest) {
      handle.dispose();
      return;
    }
    chartHandle = handle;
  } catch (error) {
    if (request !== latest) return;
    chartFigure.hidden = true;
    chartNote.textContent = `The chart could not be loaded: ${error.message}. The table above has the same figures.`;
  }
}

// --- Showing a view -------------------------------------------------------------------------

// The number input is left alone while it is being typed in ("12." on the way to "12.5").
function syncControls({ typing = false } = {}) {
  range.value = String(view.rate);
  range.setAttribute('aria-valuetext', valueText(view.rate));
  if (!typing) number.value = rateText(view.rate);
  rateValue.textContent = `${rateText(view.rate)}%`;
  // A button disabled at an end of the range would keep focus and do nothing; focus moves to
  // the range input, which says the rate.
  for (const [button, off] of [
    [down, view.rate <= rates.min],
    [up, view.rate >= rates.max],
  ]) {
    if (off && document.activeElement === button) range.focus();
    button.disabled = off;
  }
  for (const radio of ageOptions.querySelectorAll('input')) radio.checked = radio.value === view.age;
}

// The summary, the address and the chart follow once the rate has settled.
function settle() {
  const request = ++latest;
  const text = summary(rows, view.rate, data, view.age);
  summaryEl.textContent = pendingPrefix ? `${pendingPrefix} ${text}` : text;
  pendingPrefix = '';
  history.replaceState(null, '', toQuery(view));
  return renderViewChart(request);
}

function update(next, { now = false, prefix = '', typing = false } = {}) {
  view = next;
  syncControls({ typing });
  rows = sortRows(tableRows(data, view.age, view.rate), view.sort);
  renderTable();
  renderDownloads();
  if (prefix) pendingPrefix = pendingPrefix ? `${pendingPrefix} ${prefix}` : prefix;
  clearTimeout(settleTimer);
  if (now) return settle();
  settleTimer = setTimeout(settle, SETTLE_MS);
  return Promise.resolve();
}

function setRate(rate, options) {
  if (rate == null || rate === view.rate) {
    syncControls();
    if (options?.prefix) update(view, options);
    return;
  }
  update({ ...view, rate }, options);
}

// Moving the rate any other way drops an earlier hint about a typed rate, shown or pending,
// so it is never announced with the summary of a different rate.
function moveRate(rate) {
  hint.textContent = '';
  pendingPrefix = '';
  setRate(rate);
}

range.addEventListener('input', () => moveRate(parseRate(range.value, rates)));
down.addEventListener('click', () => moveRate(snapRate(view.rate - rates.step, rates)));
up.addEventListener('click', () => moveRate(snapRate(view.rate + rates.step, rates)));

// While typing, a complete rate is applied at once ("1" on the way to "12" is not); on
// leaving the field or pressing Enter, anything else is moved to the nearest rate, with a hint.
number.addEventListener('input', () => {
  const rate = parseRate(number.value, rates);
  if (rate != null && rate !== view.rate) {
    hint.textContent = '';
    update({ ...view, rate }, { typing: true });
  }
});
number.addEventListener('change', () => {
  const rate = parseRate(number.value, rates);
  if (rate != null) {
    hint.textContent = '';
    setRate(rate);
    return;
  }
  const given = number.value.trim();
  const snapped = given === '' ? view.rate : snapRate(Number(given), rates) ?? view.rate;
  const offered = `${rateText(rates.min)} to ${rateText(rates.max)} in steps of ${rateText(rates.step)}`;
  const message =
    given === ''
      ? `The rate field is empty, so ${rateText(snapped)}% is kept (rates are ${offered}).`
      : `“${given}” is not one of the rates (${offered}), so ${rateText(snapped)}% is used.`;
  hint.textContent = message;
  if (snapped === view.rate) {
    syncControls();
    update(view, { prefix: message });
  } else {
    update({ ...view, rate: snapped }, { prefix: message });
  }
});
form.addEventListener('submit', (event) => event.preventDefault());

ageOptions.addEventListener('change', (event) => {
  if (event.target.name === 'age') {
    pendingPrefix = '';
    update({ ...view, age: event.target.value });
  }
});

tableHolder.addEventListener('click', (event) => {
  const button = event.target.closest('button.sort-button');
  if (!button) return;
  const key = button.dataset.key;
  const before = view.sort;
  const dir = before.column === key && before.dir === 'asc' ? 'desc' : 'asc';
  view = { ...view, sort: { column: key, dir } };
  rows = sortRows(rows, view.sort);
  const table = $('sensitivity-data');
  updateHeader(table.tHead.rows[0], view.sort);
  bodyRows(table.tBodies[0]);
  renderDownloads();
  history.replaceState(null, '', toQuery(view));
  // Announced in the page's one live region, as on the explorer; a pending summary is not
  // overwritten (it follows within SETTLE_MS and says the rate).
  const col = columns().find((c) => c.key === key);
  const words = (col.sortWords ?? SORT_WORDS[col.type])[dir];
  summaryEl.textContent = `Sorted by ${col.label}, ${words}.`;
});

function ageRadios() {
  ageOptions.replaceChildren(
    ...data.age_groups.map((g, i) => {
      const wrap = document.createElement('div');
      wrap.className = 'radio-line';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'age';
      input.id = `age-${i}`;
      input.value = g.value;
      const label = document.createElement('label');
      label.htmlFor = input.id;
      label.textContent = g.label;
      wrap.append(input, label);
      return wrap;
    }),
  );
}

function showInvalid(invalid) {
  const text = invalidText(invalid, data);
  urlMessage.textContent = text ? `${text} The defaults are shown instead.` : '';
  urlMessage.hidden = !text;
  return urlMessage.textContent;
}

async function start() {
  watchTableWraps();
  try {
    data = await getJson('sensitivity.json');
  } catch (error) {
    summaryEl.classList.add('error');
    summaryEl.textContent = `Sorry, the figures could not be loaded: ${error.message}. The same figures are in the places listed below.`;
    fallback.hidden = false;
    return;
  }
  rates = data.rates;
  const list = rateList(rates);
  for (const input of [range, number]) {
    input.min = String(rates.min);
    input.max = String(list.at(-1));
    input.step = String(rates.step);
  }
  ageRadios();
  const resolved = resolveView(data, parseQuery(window.location.search));
  const message = showInvalid(resolved.invalid);
  form.hidden = false;
  results.hidden = false;
  renderColumnLinks();
  await update(resolved.view, { now: true, prefix: message });
}

start();
