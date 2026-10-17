// "Explore by state": a native <select> plus a "Show figures" button. Nothing is queried until
// the button is pressed, so arrowing or typing in the select never starts a load. DuckDB-WASM
// (about 8 MB) starts downloading when the user first focuses the picker, not on page load,
// so visitors who never use the explorer don't pay for it.
//
// After "Show figures", a state card (facts from states.json, a locator map) appears above
// the state's table, and focus moves to the card's heading; the table follows it.
import { formatValue, renderTable } from './format.js';

const PARQUET = 'jonapwd_state_by_type.parquet';
const SQL = `select disability_type_label, persons, share_of_state * 100 as share
  from read_parquet('${PARQUET}')
  where state = ?
  order by persons desc, sort_order`;

// If the wasm fails to download inside the worker, DuckDB's start-up never settles, so give
// up after a generous limit (the wasm is about 8 MB compressed) and say so.
const START_TIMEOUT_MS = 90_000;
// The locator map is optional: past this, the card is shown without it.
const MAP_TIMEOUT_MS = 10_000;

function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function link(href, text) {
  const a = document.createElement('a');
  a.href = href;
  a.textContent = text;
  return a;
}

const SVG_NS = 'http://www.w3.org/2000/svg';

// The map is an orientation graphic: the container is one image named in words, and the SVG
// inside is hidden from assistive technology.
function renderMap(figure, map, profile) {
  const holder = figure.querySelector('.locator-map');
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', map.viewBox);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  let selected;
  for (const [code, d] of Object.entries(map.paths)) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', d);
    path.dataset.state = code;
    if (code === profile.state_code) {
      path.classList.add('selected');
      selected = path;
    } else {
      svg.append(path);
    }
  }
  // Drawn last so its thick outline sits on top of the neighbouring borders.
  if (selected) svg.append(selected);
  // Small states also get a ring, so they can be found at card size.
  const ring = map.rings?.[profile.state_code];
  if (ring) {
    const circle = document.createElementNS(SVG_NS, 'circle');
    circle.setAttribute('cx', ring[0]);
    circle.setAttribute('cy', ring[1]);
    circle.setAttribute('r', ring[2]);
    circle.classList.add('locator-ring');
    svg.append(circle);
  }
  holder.replaceChildren(svg);
  holder.setAttribute(
    'aria-label',
    `Map of Nigeria with ${profile.state} highlighted, in the ${profile.zone} zone`,
  );
  figure.hidden = false;
}

function renderCard(card, profile, map, total) {
  card.querySelector('h3').textContent = profile.state;
  const facts = card.querySelector('.facts');
  const rows = [
    ['Capital', profile.capital],
    ['Geopolitical zone', profile.zone],
    ['Population, 2023 projection', formatValue(profile.population_2023, 'integer')],
  ];
  if (profile.slogan) rows.push(['Slogan', `“${profile.slogan}”`]);
  rows.push([
    "JONAPWD's estimate of persons with disabilities",
    `${formatValue(profile.jonapwd_total, 'integer')}: ${formatValue(
      profile.share_of_national * 100,
      'percent',
    )}% of the ${total} for all 37 states, ranked ${profile.rank_of_37} of 37. ` +
      "JONAPWD's figures are about 15% of each state's population, so this ranking mostly follows population.",
  ]);
  facts.replaceChildren(
    ...rows.flatMap(([term, value]) => {
      const dt = document.createElement('dt');
      dt.textContent = term;
      const dd = document.createElement('dd');
      dd.textContent = value;
      if (term === 'Slogan') dd.className = 'slogan';
      return [dt, dd];
    }),
  );

  const sources = card.querySelector('.card-sources');
  const parts = [
    'Sources: population, ',
    link(
      'https://microdata.nigerianstat.gov.ng/index.php/catalog/182',
      'NBS Demographic Bulletin 2023, Annex 3',
    ),
    '; capital, ',
    link(profile.capital_source_url, 'Wikipedia'),
    '; zone, ',
    link('https://en.wikipedia.org/wiki/Geopolitical_zones_of_Nigeria', 'Wikipedia'),
  ];
  if (profile.slogan) parts.push('; slogan, ', link(profile.slogan_source_url, 'Zikoko'));
  parts.push('; persons with disabilities, JONAPWD 2025 (see Source at the foot of the page).');
  sources.replaceChildren(...parts);

  const figure = card.querySelector('.locator');
  if (map) renderMap(figure, map, profile);
  else figure.hidden = true;
  card.hidden = false;
}

export function setUpExplorer({
  select,
  button,
  status,
  card,
  tableEl,
  dataUrl,
  extensionsUrl,
  states,
  onStateShown = () => {},
}) {
  select.replaceChildren(new Option('Choose a state', ''));
  for (const { state } of states) select.append(new Option(state, state));
  select.disabled = false;
  button.disabled = false;

  const profiles = new Map(states.map((s) => [s.state, s]));
  const total = formatValue(
    states.reduce((sum, s) => sum + s.jonapwd_total, 0),
    'integer',
  );

  let queryPromise;
  let mapPromise;
  let latest = 0;

  // The locator map is optional: if it fails or stalls, the card is shown without it, and
  // the next "Show figures" tries again.
  function loadMap() {
    mapPromise ??= withTimeout(
      fetch(`${dataUrl}nigeria-states.json`).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
      MAP_TIMEOUT_MS,
      'map timed out',
    ).catch(() => {
      mapPromise = undefined;
      return null;
    });
    return mapPromise;
  }

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
      card.hidden = true;
      status.textContent = 'Choose a state first, then press Show figures.';
      select.focus();
      return;
    }
    status.textContent = `Loading figures for ${state}. This can take a few seconds the first time.`;
    try {
      const query = await startEngine();
      const [result, map] = await Promise.all([query(state), loadMap()]);
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
      renderCard(card, profiles.get(state), map, total);
      tableEl.replaceChildren(table);
      status.textContent = `Showing ${rows.length} disability types for ${state}.`;
      onStateShown(state);
      // Move focus to the card's heading: screen readers then read the state's name at once,
      // and the card and table follow in reading order. This is more reliable than the live
      // region alone, and it only happens after a button press.
      card.querySelector('h3').focus();
    } catch (error) {
      if (request !== latest) return;
      queryPromise = undefined; // allow a retry on the next press
      tableEl.replaceChildren();
      card.hidden = true;
      status.classList.add('error');
      status.textContent = `Sorry, the state figures could not be loaded: ${error.message}. The national chart and table above still work.`;
    }
  }

  button.addEventListener('click', showFigures);
}
