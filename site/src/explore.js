// "Explore by state": a native <select>; each choice is queried with DuckDB-WASM, which is
// only downloaded and started the first time it is needed.
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

export function setUpExplorer({ select, status, tableEl, dataUrl, extensionsUrl, states }) {
  select.replaceChildren(new Option('Choose a state', ''));
  for (const { state } of states) select.append(new Option(state, state));
  select.disabled = false;

  let queryPromise;
  let latest = 0;

  select.addEventListener('change', async () => {
    const state = select.value;
    const request = ++latest;
    status.classList.remove('error');
    if (!state) {
      tableEl.replaceChildren();
      status.textContent = '';
      return;
    }
    status.textContent = `Loading figures for ${state}…`;
    try {
      queryPromise ??= withTimeout(
        import('./duckdb-client.js').then(({ openParquet }) =>
          openParquet(`${dataUrl}${PARQUET}`, PARQUET, SQL, extensionsUrl),
        ),
        START_TIMEOUT_MS,
        'the in-browser database took too long to start',
      );
      const query = await queryPromise;
      const result = await query(state);
      if (request !== latest) return; // a newer choice has superseded this one
      const rows = result.map((r) => [r.disability_type_label, r.persons, r.share]);
      tableEl.replaceChildren(
        renderTable({
          caption: `${state}: persons with disabilities by type (JONAPWD estimates)`,
          columns: [
            { label: 'Disability type', type: 'text' },
            { label: 'Persons', type: 'integer' },
            { label: 'Share of state total (%)', type: 'percent' },
          ],
          rows,
        }),
      );
      status.textContent = `Showing ${rows.length} disability types for ${state}.`;
    } catch (error) {
      if (request !== latest) return;
      queryPromise = undefined; // allow a retry on the next change
      tableEl.replaceChildren();
      status.classList.add('error');
      status.textContent = `Sorry, the state figures could not be loaded: ${error.message}. The national chart and table above still work.`;
    }
  });
}
