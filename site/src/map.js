// Render a choropleth document built by disability_access_charts.maps (see build_charts.py).
//
// The map is one image to assistive technology: its container has role="img" and is named by
// the data-derived alt-text, and the SVG inside is aria-hidden. The states are not separate
// Tab stops; the table after the map holds every figure, and the state picker below is the
// keyboard route to one state. The legend gives each class's range in words.
//
// A tooltip shows a state's figure on hover (mouse), on tap or click, and on keyboard focus
// of the map (the state chosen in the explorer, or a hint). Esc closes it, the pointer can
// move onto it, and it stays until the pointer leaves the map (WCAG 2.2 SC 1.4.13). It is
// hidden from screen readers, which get the same figures from the name and the table.
import { formatValue, renderTable } from './format.js';

const SVG_NS = 'http://www.w3.org/2000/svg';
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

const HINT =
  'Hover over or tap a state. By keyboard, use the table below the map or the state picker under "Explore by state".';

function pct(value, decimals) {
  return `${formatValue(value, 'number', decimals)}%`;
}

// Colours come from the document's themes, as CSS custom properties on the figure, so the
// map and its legend switch with the colour scheme and never disagree.
function applyTheme(figure, doc) {
  const theme = darkQuery.matches ? (doc.themes.dark ?? doc.themes.light) : doc.themes.light;
  figure.style.setProperty('--map-edge', theme.edge);
  theme.classes.forEach((fill, k) => figure.style.setProperty(`--map-c${k}`, fill));
}

function renderLegend(legendEl, doc) {
  const label = doc.data.category_label.toLowerCase();
  legendEl.replaceChildren(
    ...doc.classes.map((c, k) => {
      const li = document.createElement('li');
      const swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.background = `var(--map-c${k})`;
      swatch.setAttribute('aria-hidden', 'true');
      const text = document.createElement('span');
      text.textContent = `${c.label}: ${c.count} ${c.count === 1 ? label : `${label}s`}`;
      li.append(swatch, text);
      return li;
    }),
  );
}

/**
 * Render the map, its legend and its table. Returns a handle whose highlight(stateName)
 * outlines that state (null clears it); the map's name does not change.
 */
export function renderChoropleth(doc, { figure, holder, legendEl, titleEl, tableEl }) {
  titleEl.textContent = doc.title;
  holder.setAttribute('aria-label', doc.alt_text);
  tableEl.replaceChildren(renderTable(doc.table));
  renderLegend(legendEl, doc);
  applyTheme(figure, doc);
  darkQuery.addEventListener('change', () => applyTheme(figure, doc));

  const series = doc.data.series[0];
  const decimals = doc.data.decimals;
  const extra = doc.table.columns.findIndex((c) => c.key === 'extra:0');
  const rowsByName = new Map(doc.table.rows.map((r) => [r[0], r]));
  const info = new Map(
    doc.regions.map((region, i) => [
      region.code,
      {
        name: region.name,
        value: series.values[i],
        lower: series.lower?.[i],
        upper: series.upper?.[i],
        label: doc.classes[region.class].label,
        note: extra >= 0 ? rowsByName.get(region.name)?.[extra] : null,
      },
    ]),
  );
  const codeByName = new Map(doc.regions.map((r) => [r.name, r.code]));

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', doc.map.viewBox);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const paths = new Map();
  for (const region of doc.regions) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', doc.map.paths[region.code]);
    path.dataset.state = region.code;
    path.classList.add(`c${region.class}`);
    svg.append(path);
    paths.set(region.code, path);
  }
  const ring = document.createElementNS(SVG_NS, 'circle');
  ring.classList.add('map-ring');
  ring.setAttribute('r', '0');
  svg.append(ring);
  holder.replaceChildren(svg);

  const tip = figure.querySelector('.map-tip');
  const tipName = tip.querySelector('.map-tip-state');
  const tipFigure = tip.querySelector('.map-tip-figure');
  let selected = null;

  function place(target) {
    const box = figure.getBoundingClientRect();
    const area = target.getBoundingClientRect();
    const left = area.left + area.width / 2 - box.left - tip.offsetWidth / 2;
    tip.style.left = `${Math.max(0, Math.min(left, box.width - tip.offsetWidth))}px`;
    tip.style.top = `${area.bottom - box.top + 4}px`;
  }

  function show(code) {
    const s = info.get(code);
    if (!s) return;
    tipName.textContent = s.name;
    const interval =
      s.lower != null ? ` (95% confidence interval ${pct(s.lower, decimals)} to ${pct(s.upper, decimals)})` : '';
    const note = s.note ? `. ${s.note}` : '';
    tipFigure.textContent = `${pct(s.value, decimals)} of adults${interval}. Map class: ${s.label}${note}.`;
    tip.hidden = false;
    place(paths.get(code));
  }

  function showHint() {
    tipName.textContent = 'Figures by state';
    tipFigure.textContent = HINT;
    tip.hidden = false;
    place(holder);
    tip.style.top = `${holder.getBoundingClientRect().bottom - figure.getBoundingClientRect().top - tip.offsetHeight - 8}px`;
  }

  function hide() {
    tip.hidden = true;
  }

  // After Esc, hovering stays off until the pointer leaves the map: browsers re-send "over"
  // to the state under the pointer once the tip disappears, which would reopen it at once.
  let hoverOff = false;
  holder.addEventListener('pointerover', (event) => {
    if (event.pointerType === 'mouse' && !hoverOff && event.target.matches('path')) {
      show(event.target.dataset.state);
    }
  });
  holder.addEventListener('click', (event) => {
    if (event.target.matches('path')) show(event.target.dataset.state);
  });
  // Touch pointers "leave" when the finger lifts, so only a mouse leaving closes the tip;
  // the tip is inside the figure, so moving onto it keeps it open.
  figure.addEventListener('pointerleave', (event) => {
    if (event.pointerType !== 'mouse') return;
    hoverOff = false;
    if (!holder.matches(':focus-visible')) hide();
  });
  holder.addEventListener('focus', () => {
    if (!holder.matches(':focus-visible')) return;
    if (selected) show(selected);
    else showHint();
  });
  holder.addEventListener('blur', hide);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !tip.hidden) {
      hoverOff = true;
      hide();
    }
  });
  document.addEventListener('pointerdown', (event) => {
    if (!figure.contains(event.target)) hide();
  });

  return {
    highlight(stateName) {
      const code = stateName == null ? null : codeByName.get(stateName);
      for (const [c, path] of paths) path.classList.toggle('selected', c === code);
      selected = code ?? null;
      if (code) {
        // Drawn last so its thick outline sits on top of the neighbouring borders; small
        // states also get a ring so they can be found.
        svg.insertBefore(paths.get(code), ring);
        const r = doc.map.rings?.[code];
        ring.setAttribute('cx', r ? r[0] : 0);
        ring.setAttribute('cy', r ? r[1] : 0);
        ring.setAttribute('r', r ? r[2] : 0);
      } else {
        ring.setAttribute('r', '0');
      }
    },
  };
}
