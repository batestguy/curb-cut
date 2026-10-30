import { renderChart } from './chart.js';
import { setUpExplorer } from './explore.js';
import { renderChoropleth } from './map.js';
import { renderComparison, renderFindings, renderHeadline, renderSpatial } from './prevalence.js';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;

async function getJson(path) {
  const response = await fetch(`${DATA_URL}${path}`);
  if (!response.ok) throw new Error(`could not fetch ${path} (HTTP ${response.status})`);
  return response.json();
}

function fail(statusId, message) {
  const status = document.getElementById(statusId);
  status.classList.add('error');
  status.textContent = message;
}

// The state chosen in the explorer, highlighted in the by-state chart and on the map once
// they have loaded.
let chosenState = null;
let stateChart = null;
let prevalenceMap = null;

// The findings under a chart. Rendered on their own, so a problem here never takes the chart
// down; a chart without a findings block hides the block instead of leaving its placeholder.
function showFindings(doc, id) {
  const findingsEl = document.getElementById(`${id}-findings`);
  if (!findingsEl) return;
  if (!doc.findings) {
    findingsEl.querySelector('.findings-count')?.replaceChildren();
    findingsEl.hidden = true;
    return;
  }
  try {
    renderFindings(doc.findings, doc.meta.source, {
      count: findingsEl.querySelector('.findings-count'),
      list: findingsEl.querySelector('.findings-list'),
      notes: findingsEl.querySelector('.findings-notes'),
      families: findingsEl.querySelector('.findings-families'),
      method: findingsEl.querySelector('.findings-method'),
    });
  } catch (error) {
    findingsEl.querySelector('.findings-list').hidden = true;
    findingsEl.querySelector('.findings-count').textContent =
      `The findings could not be shown: ${error.message}.`;
  }
}

async function showChart(name, id) {
  const titleEl = document.getElementById(`${id}-title`);
  try {
    const doc = await getJson(`charts/${name}.json`);
    showFindings(doc, id);
    return await renderChart(doc, {
      container: document.getElementById(id),
      titleEl,
      descEl: document.getElementById(`${id}-desc`),
      tableEl: document.getElementById(id === 'national-chart' ? 'national-table' : `${id}-table`),
      highlight: id === 'state-chart' ? chosenState : null,
    });
  } catch (error) {
    const message = `The chart could not be loaded: ${error.message}.`;
    const count = document.querySelector(`#${id}-findings .findings-count`);
    if (count) count.textContent = 'The findings are unavailable because the chart could not be loaded.';
    titleEl.textContent = 'Chart unavailable';
    const chart = document.getElementById(id);
    chart.removeAttribute('aria-labelledby'); // it would override aria-label
    chart.setAttribute('aria-label', message);
    fail(`${id}-status`, message);
    return null;
  }
}

async function showMap() {
  const holder = document.getElementById('prevalence-map');
  try {
    const doc = await getJson('charts/prevalence_map.json');
    prevalenceMap = renderChoropleth(doc, {
      figure: holder.closest('figure'),
      holder,
      legendEl: document.getElementById('prevalence-map-legend'),
      titleEl: document.getElementById('prevalence-map-title'),
      tableEl: document.getElementById('prevalence-map-table'),
    });
    if (chosenState) prevalenceMap.highlight(chosenState);
  } catch (error) {
    const message = `The map could not be loaded: ${error.message}. The same figures are in the chart and table below.`;
    document.getElementById('prevalence-map-title').textContent = 'Map unavailable';
    holder.setAttribute('aria-label', message);
    holder.removeAttribute('tabindex');
    fail('prevalence-map-status', message);
  }
}

// prevalence.json feeds the headline, the comparison and the state card's national figure.
const prevalencePromise = getJson('prevalence.json');

async function showPrevalence() {
  try {
    const prevalence = await prevalencePromise;
    renderHeadline(document.getElementById('headline'), prevalence);
    renderComparison(
      document.getElementById('comparison-message'),
      document.getElementById('comparison-list'),
      prevalence,
    );
  } catch (error) {
    const message = `The national figures could not be loaded: ${error.message}.`;
    document.getElementById('headline').textContent = 'National figure unavailable.';
    document.getElementById('comparison-message').textContent = 'Comparison unavailable.';
    fail('headline-status', message);
    fail('comparison-status', message);
  }
}

async function showSpatial() {
  try {
    const spatial = await getJson('spatial.json');
    renderSpatial(spatial, {
      moranSentence: document.getElementById('moran-sentence'),
      moranTable: document.getElementById('moran-table'),
      moranSentences: document.getElementById('moran-sentences'),
      lisaDetail: document.getElementById('lisa-detail'),
      lisaUnderMap: document.getElementById('lisa-sentence'),
      clusterSentence: document.getElementById('cluster-sentence'),
      clusterGroups: document.getElementById('cluster-groups'),
      servicesSentence: document.getElementById('services-sentence'),
      servicesCaveats: document.getElementById('services-caveats'),
    });
  } catch (error) {
    fail('spatial-status', `The spatial findings could not be loaded: ${error.message}.`);
  }
}

async function showExplorer() {
  const status = document.getElementById('state-status');
  try {
    const states = await getJson('states.json');
    setUpExplorer({
      select: document.getElementById('state-select'),
      button: document.getElementById('state-show'),
      status,
      card: document.getElementById('state-card'),
      tableEl: document.getElementById('state-table'),
      dataUrl: DATA_URL,
      extensionsUrl: `${import.meta.env.BASE_URL}duckdb-extensions`,
      states,
      // The card shows the national figure for comparison when it loads; never required.
      national: prevalencePromise.then((p) => p.national).catch(() => null),
      onStateShown(state) {
        chosenState = state;
        stateChart?.highlight(state);
        prevalenceMap?.highlight(state);
      },
    });
  } catch (error) {
    status.classList.add('error');
    status.textContent = `The list of states could not be loaded: ${error.message}.`;
  }
}

// A wide table that scrolls sideways (at 320px, say) becomes a named, focusable region, so a
// keyboard user can scroll it; when it fits, it is plain again (no extra Tab stop).
function watchTableWraps() {
  const update = (wrap) => {
    if (wrap.scrollWidth > wrap.clientWidth + 1) {
      const caption = wrap.querySelector('caption')?.textContent ?? 'Table';
      wrap.tabIndex = 0;
      wrap.setAttribute('role', 'region');
      wrap.setAttribute('aria-label', `${caption} (scrolls sideways)`);
    } else {
      wrap.removeAttribute('tabindex');
      wrap.removeAttribute('role');
      wrap.removeAttribute('aria-label');
    }
  };
  const resized = new ResizeObserver((entries) => entries.forEach((e) => update(e.target)));
  for (const wrap of document.querySelectorAll('.table-wrap')) {
    resized.observe(wrap);
    new MutationObserver(() => update(wrap)).observe(wrap, { childList: true, subtree: true });
  }
}

watchTableWraps();
// Independent: a failure in one never blocks the others.
showPrevalence();
showMap();
showChart('prevalence_by_state', 'prevalence-chart');
showSpatial();
showChart('national_by_type', 'national-chart');
showChart('national_by_state', 'state-chart').then((handle) => {
  stateChart = handle;
  // A state chosen while the chart was still drawing.
  if (chosenState) stateChart?.highlight(chosenState);
});
showExplorer();
