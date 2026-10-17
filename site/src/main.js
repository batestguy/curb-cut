import { renderChart } from './chart.js';
import { setUpExplorer } from './explore.js';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;

async function getJson(path) {
  const response = await fetch(`${DATA_URL}${path}`);
  if (!response.ok) throw new Error(`could not fetch ${path} (HTTP ${response.status})`);
  return response.json();
}

async function showNationalChart() {
  const titleEl = document.getElementById('national-chart-title');
  try {
    const doc = await getJson('charts/national_by_type.json');
    await renderChart(doc, {
      container: document.getElementById('national-chart'),
      titleEl,
      descEl: document.getElementById('national-chart-desc'),
      tableEl: document.getElementById('national-table'),
    });
  } catch (error) {
    titleEl.textContent = `The chart could not be loaded: ${error.message}.`;
  }
}

async function showExplorer() {
  const status = document.getElementById('state-status');
  try {
    const states = await getJson('states.json');
    setUpExplorer({
      select: document.getElementById('state-select'),
      status,
      tableEl: document.getElementById('state-table'),
      dataUrl: DATA_URL,
      extensionsUrl: `${import.meta.env.BASE_URL}duckdb-extensions`,
      states,
    });
  } catch (error) {
    status.classList.add('error');
    status.textContent = `The list of states could not be loaded: ${error.message}.`;
  }
}

// Independent: a failure in one never blocks the other.
showNationalChart();
showExplorer();
