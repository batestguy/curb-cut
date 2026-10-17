import { renderChart } from './chart.js';
import { setUpExplorer } from './explore.js';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;

async function getJson(path) {
  const response = await fetch(`${DATA_URL}${path}`);
  if (!response.ok) throw new Error(`could not fetch ${path} (HTTP ${response.status})`);
  return response.json();
}

// The state chosen in the explorer, highlighted in the by-state chart once that has loaded.
let chosenState = null;
let stateChart = null;

async function showChart(name, id) {
  const titleEl = document.getElementById(`${id}-title`);
  try {
    const doc = await getJson(`charts/${name}.json`);
    return await renderChart(doc, {
      container: document.getElementById(id),
      titleEl,
      descEl: document.getElementById(`${id}-desc`),
      tableEl: document.getElementById(id === 'national-chart' ? 'national-table' : `${id}-table`),
      highlight: id === 'state-chart' ? chosenState : null,
    });
  } catch (error) {
    const message = `The chart could not be loaded: ${error.message}.`;
    titleEl.textContent = 'Chart unavailable';
    const chart = document.getElementById(id);
    chart.removeAttribute('aria-labelledby'); // it would override aria-label
    chart.setAttribute('aria-label', message);
    const status = document.getElementById(`${id}-status`);
    status.classList.add('error');
    status.textContent = message;
    return null;
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
      onStateShown(state) {
        chosenState = state;
        stateChart?.highlight(state);
      },
    });
  } catch (error) {
    status.classList.add('error');
    status.textContent = `The list of states could not be loaded: ${error.message}.`;
  }
}

// Independent: a failure in one never blocks the others.
showChart('national_by_type', 'national-chart');
showChart('national_by_state', 'state-chart').then((handle) => {
  stateChart = handle;
  // A state chosen while the chart was still drawing.
  if (chosenState) stateChart?.highlight(chosenState);
});
showExplorer();
