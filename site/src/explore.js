// "Explore by state": a native <select> plus a "Show figures" button. Nothing is queried until
// the button is pressed, so arrowing or typing in the select never starts a load. DuckDB-WASM
// (about 8 MB) starts downloading when the user first focuses the picker, not on page load,
// so visitors who never use the explorer don't pay for it.
import { renderTable } from './format.js';

const PARQUET = 'jonapwd_state_by_type.parquet';
const SQL = `select disability_type_label, persons, share_of_state * 100 as share
  from read_parquet('${PARQUET}')
  where state = ?
  order by persons desc, sort_order`;

// If the wasm fails to download inside the worker, DuckDB's start-up never settles, so give
// up after a generous limit (the wasm is about 8 MB compressed) and say so.
const START_TIMEOUT_MS = 90_000;

function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export function setUpExplorer({ select, button, status, tableEl, dataUrl, extensionsUrl, states }) {
  select.replaceChildren(new Option('Choose a state', ''));
  for (const { state } of states) select.append(new Option(state, state));
  select.disabled = false;
  button.disabled = false;

  let queryPromise;
  let latest = 0;

  function startEngine() {
    queryPromise ??= withTimeout(
      import('./duckdb-client.js').then(({ openParquet }) =>
        openParquet(`${dataUrl}${PARQUET}`, PARQUET, SQL, extensionsUrl),
      ),
      START_TIMEOUT_MS,
      'the in-browser database took too long to start',
    );
    // A failed warm-up is reported when the user asks for figures, not before.
    queryPromise.catch(() => {});
    return queryPromise;
  }

  // Warm up on first sign of intent.
  select.addEventListener('focus', () => startEngine(), { once: true });
  button.addEventListener('focus', () => startEngine(), { once: true });

  async function showFigures() {
    const state = select.value;
    const request = ++latest;
    status.classList.remove('error');
    if (!state) {
      tableEl.replaceChildren();
      status.textContent = 'Choose a state first, then press Show figures.';
      select.focus();
      return;
    }
    status.textContent = `Loading figures for ${state}. This can take a few seconds the first time.`;
    try {
      const query = await startEngine();
      const result = await query(state);
      if (request !== latest) return; // a newer request has superseded this one
      const rows = result.map((r) => [r.disability_type_label, r.persons, r.share]);
      const table = renderTable({
        caption: `${state}: persons with disabilities by type (JONAPWD estimates)`,
        columns: [
          { label: 'Disability type', type: 'text' },
          { label: 'Persons', type: 'integer' },
          { label: 'Share of state total (%)', type: 'percent' },
        ],
        rows,
      });
      tableEl.replaceChildren(table);
      status.textContent = `Showing ${rows.length} disability types for ${state}.`;
      // Move focus to the new table: screen readers then read its caption at once. This is
      // more reliable than the live region alone, and it only happens after a button press.
      table.tabIndex = -1;
      table.focus();
    } catch (error) {
      if (request !== latest) return;
      queryPromise = undefined; // allow a retry on the next press
      tableEl.replaceChildren();
      status.classList.add('error');
      status.textContent = `Sorry, the state figures could not be loaded: ${error.message}. The national chart and table above still work.`;
    }
  }

  button.addEventListener('click', showFigures);
}
