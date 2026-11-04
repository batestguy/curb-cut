// Render a choropleth document built by disability_access_charts.maps (see build_charts.py).
//
// The map is one image to assistive technology: its container has role="img" and is named by
// the data-derived alt-text, and the SVG inside is aria-hidden. The states are not separate
// Tab stops; the table after the map holds every figure, and the state picker below is the
// keyboard route to one state.
//
// Each class has its own pattern (disability_access_charts 0.2; ordered by ink weight with an
// ink per class since 0.3): the document's tiles are drawn as SVG <pattern> fills over the
// class colour, and the legend shows the same pattern in each swatch, so neighbouring classes
// differ by more than a shade (WCAG 2.2 SC 1.4.1).
//
// Boundaries (0.3): when the theme has a halo, every boundary is cased, drawn twice after all
// the fills: a wide halo stroke under a narrow edge stroke, so at each border one of the two
// is 3:1 against the fills either side (audited in the document). A 0.2 document has one
// edge colour and no halo layer.
//
// The legend (0.3, when the document has a legend block) is a list of toggle buttons
// (aria-pressed), lowest class first: pressing one shows only that class's states (the others
// are dimmed, their boundaries still faint), pressing it again or Esc (focus in the legend or
// on the map) shows all. One polite live region announces the document's sentence for the
// class, with the state names, or "Showing all 37 states."
//
// A tooltip shows a state's figure on hover (mouse), on tap or click, and on keyboard focus
// of the map (the state chosen in the explorer, or a hint). Esc closes it, the pointer can
// move onto it, and it stays until the pointer leaves the map (WCAG 2.2 SC 1.4.13). It is
// hidden from screen readers, which get the same figures from the name and the table.
import { formatValue, placeAfterTable, renderTable, stateHref } from './format.js';

const SVG_NS = 'http://www.w3.org/2000/svg';
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

const HINT =
  'Hover over or tap a state. By keyboard, use the table below the map or the state picker under "Explore by state".';

function pct(value, decimals) {
  return `${formatValue(value, 'number', decimals)}%`;
}

function svgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}

// The ink for class k in a scheme: one per class (0.3, null where the tile draws nothing),
// or one per theme (0.2).
function inkFor(doc, scheme, k) {
  const perClass = doc.patterns?.class_ink?.[scheme];
  if (perClass) return perClass[k];
  return doc.patterns?.ink?.[scheme] ?? null;
}

// Colours come from the document's themes, as CSS custom properties on the figure, so the
// map and its legend switch with the colour scheme and never disagree.
function applyTheme(figure, doc) {
  const scheme = darkQuery.matches && doc.themes.dark ? 'dark' : 'light';
  const theme = doc.themes[scheme];
  figure.style.setProperty('--map-edge', theme.edge);
  if (theme.halo) figure.style.setProperty('--map-halo', theme.halo);
  theme.classes.forEach((fill, k) => {
    figure.style.setProperty(`--map-c${k}`, fill);
    const ink = inkFor(doc, scheme, k);
    if (ink) figure.style.setProperty(`--map-ink${k}`, ink);
    else figure.style.removeProperty(`--map-ink${k}`);
  });
  figure.dataset.scheme = scheme;
}

// One <pattern> for class k: the class colour behind, the tile in the class's ink in front
// (no ink for the plain and solid tiles). Colours are CSS custom properties, so the pattern
// follows the colour scheme.
function makePattern(id, tile, k, scale) {
  const pattern = svgEl('pattern', {
    id,
    patternUnits: 'userSpaceOnUse',
    width: tile.size,
    height: tile.size,
    patternTransform: `scale(${scale})`,
  });
  pattern.dataset.pattern = tile.id;
  const back = svgEl('rect', { width: tile.size, height: tile.size });
  back.style.fill = `var(--map-c${k})`;
  pattern.append(back);
  if (tile.path) {
    const ink = svgEl('path', { d: tile.path });
    ink.classList.add('tile');
    ink.style.fill = `var(--map-ink${k})`;
    pattern.append(ink);
  }
  return pattern;
}

// The document's tile scale gives about 12px tiles on a 630px-wide map. On a narrow screen the
// map shrinks and so would the tiles (about 5.5px at 288px), too small to tell apart. So the
// tiles never go below MIN_TILE_PX on screen: the scale is raised to match the drawn width.
const MIN_TILE_PX = 8;

function fitPatterns(svg, doc, prefix) {
  const width = svg.getBoundingClientRect().width;
  const units = Number(doc.map.viewBox.trim().split(/\s+/)[2]);
  if (!width || !units) return;
  const pxPerUnit = width / units;
  doc.classes.forEach((c, k) => {
    const pattern = svg.querySelector(`#${CSS.escape(`${prefix}-${k}`)}`);
    const size = doc.patterns.tiles[c.pattern].size;
    const scale = Math.max(doc.patterns.scale, MIN_TILE_PX / (size * pxPerUnit));
    pattern?.setAttribute('patternTransform', `scale(${scale.toFixed(4)})`);
  });
}

function patternDefs(doc, prefix, scale) {
  const defs = svgEl('defs');
  doc.classes.forEach((c, k) => {
    defs.append(makePattern(`${prefix}-${k}`, doc.patterns.tiles[c.pattern], k, scale));
  });
  return defs;
}

// A legend swatch: 40 x 28 px, large enough to show the tile (drawn at its own 12px size, so
// more than three repeats show), outlined in the theme's edge colour. Hidden from assistive
// technology: the button's text names the class.
const SWATCH_W = 40;
const SWATCH_H = 28;

function swatchFor(doc, k) {
  const svg = svgEl('svg', {
    viewBox: `0 0 ${SWATCH_W} ${SWATCH_H}`,
    'aria-hidden': 'true',
    focusable: 'false',
  });
  svg.classList.add('swatch');
  const rect = svgEl('rect', { width: SWATCH_W, height: SWATCH_H });
  if (doc.patterns) {
    svg.dataset.pattern = doc.classes[k].pattern;
    const id = `${doc.id}-legend-pattern-${k}`;
    const defs = svgEl('defs');
    defs.append(makePattern(id, doc.patterns.tiles[doc.classes[k].pattern], k, 1));
    rect.style.fill = `url(#${id})`;
    svg.append(defs);
  } else {
    rect.style.fill = `var(--map-c${k})`;
  }
  svg.append(rect);
  return svg;
}

function legendText(doc, c) {
  const label = doc.data.category_label.toLowerCase();
  return `${c.label}: ${c.count} ${c.count === 1 ? label : `${label}s`}`;
}

// The legend, lowest class first. With a legend block, each item is a toggle button.
function renderLegend(legendEl, doc, onToggle) {
  const filter = Boolean(doc.legend?.filter);
  legendEl.classList.toggle('map-legend-filter', filter);
  const buttons = [];
  legendEl.replaceChildren(
    ...doc.classes.map((c, k) => {
      const li = document.createElement('li');
      const text = document.createElement('span');
      text.className = 'legend-label';
      text.textContent = legendText(doc, c);
      if (!filter) {
        li.append(swatchFor(doc, k), text);
        return li;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'legend-button';
      button.dataset.class = String(k);
      button.setAttribute('aria-pressed', 'false');
      button.append(swatchFor(doc, k), text);
      button.addEventListener('click', () => onToggle(k));
      buttons.push(button);
      li.append(button);
      return li;
    }),
  );
  return buttons;
}

/**
 * Render the map, its legend and its table. Returns a handle whose highlight(stateName)
 * outlines that state (null clears it); the map's name does not change. `tableNote`, if
 * given, goes directly after the table (its download line).
 */
export function renderChoropleth(
  doc,
  { figure, holder, legendEl, titleEl, tableEl, statusEl, tableNote = null },
) {
  titleEl.textContent = doc.title;
  holder.setAttribute('aria-label', doc.alt_text);
  // Each state's name links to its own page.
  const table = renderTable({ ...doc.table, rowHref: stateHref });
  tableEl.replaceChildren(table);
  placeAfterTable(table, tableNote);
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
  const cased = Boolean(doc.themes.light.halo);
  // The casing's stroke widths come from the document (map.casing, audited: each halo wider
  // than its edge), as CSS custom properties the stylesheet reads.
  for (const [key, width] of Object.entries(doc.map.casing ?? {})) {
    figure.style.setProperty(`--map-${key.replace('_', '-')}-w`, `${width}px`);
  }

  const svg = svgEl('svg', { viewBox: doc.map.viewBox, 'aria-hidden': 'true', focusable: 'false' });
  const prefix = `${doc.id}-pattern`;
  if (doc.patterns) svg.append(patternDefs(doc, prefix, doc.patterns.scale));

  // Layers: every fill first, then every halo, then every edge, so each shared border gets
  // the whole casing whichever state is drawn last. Then the outlines of the chosen and the
  // hovered state, then the ring for small states.
  const fills = svgEl('g', { class: 'map-fills' });
  const halos = svgEl('g', { class: 'map-halos' });
  const edges = svgEl('g', { class: 'map-edges' });
  const layers = new Map(); // code -> the state's fill, halo and edge paths
  for (const region of doc.regions) {
    const d = doc.map.paths[region.code];
    const fill = svgEl('path', { d });
    fill.dataset.state = region.code;
    fill.classList.add(`c${region.class}`);
    if (doc.patterns) fill.style.fill = `url(#${prefix}-${region.class})`;
    fills.append(fill);
    const parts = [fill];
    if (cased) {
      const halo = svgEl('path', { d });
      halo.dataset.outline = region.code;
      halos.append(halo);
      parts.push(halo);
    }
    const edge = svgEl('path', { d });
    edge.dataset.outline = region.code;
    edges.append(edge);
    parts.push(edge);
    layers.set(region.code, { fill, parts, cls: region.class });
  }
  svg.append(fills);
  if (cased) svg.append(halos);
  svg.append(edges);

  // A thick outline over everything: a halo under an edge, so it shows on any fill.
  function outline(kind) {
    const group = svgEl('g', { class: `map-outline map-outline-${kind}` });
    const halo = svgEl('path', { class: 'outline-halo' });
    const edge = svgEl('path', { class: 'outline-edge' });
    if (cased) group.append(halo);
    group.append(edge);
    svg.append(group);
    return (code) => {
      const d = code ? doc.map.paths[code] : '';
      for (const p of [halo, edge]) {
        if (d) p.setAttribute('d', d);
        else p.removeAttribute('d');
      }
    };
  }
  const setSelectedOutline = outline('selected');
  const setHoverOutline = outline('hover');
  // The ring is cased like the boundaries: a halo circle under the edge circle.
  const ringHalo = cased ? svgEl('circle', { r: '0', class: 'map-ring-halo' }) : null;
  if (ringHalo) svg.append(ringHalo);
  const ring = svgEl('circle', { r: '0' });
  ring.classList.add('map-ring');
  svg.append(ring);
  holder.replaceChildren(svg);
  if (doc.patterns) {
    fitPatterns(svg, doc, prefix);
    if ('ResizeObserver' in window) {
      new ResizeObserver(() => fitPatterns(svg, doc, prefix)).observe(holder);
    }
  }

  // The legend filter: one class at a time, or all.
  let active = null;
  const buttons = renderLegend(legendEl, doc, (k) => (active === k ? clearFilter() : setFilter(k)));

  function announce(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function showClass(k) {
    active = k;
    svg.classList.toggle('filtered', k != null);
    for (const { parts, cls } of layers.values()) {
      const dim = k != null && cls !== k;
      for (const p of parts) {
        p.classList.toggle('dim', dim);
        p.classList.toggle('active', k != null && !dim);
      }
    }
    for (const b of buttons) b.setAttribute('aria-pressed', String(Number(b.dataset.class) === k));
  }

  function setFilter(k) {
    showClass(k);
    announce(doc.classes[k].announce);
  }

  function clearFilter() {
    if (active == null) return;
    showClass(null);
    announce(doc.legend.announce_all);
  }

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
    place(layers.get(code).fill);
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
    if (!event.target.matches('path[data-state]')) return;
    if (event.pointerType === 'mouse') setHoverOutline(event.target.dataset.state);
    if (event.pointerType === 'mouse' && !hoverOff) show(event.target.dataset.state);
  });
  holder.addEventListener('pointerleave', () => setHoverOutline(null));
  holder.addEventListener('click', (event) => {
    if (event.target.matches('path[data-state]')) show(event.target.dataset.state);
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
    if (event.key !== 'Escape') return;
    if (!tip.hidden) {
      hoverOff = true;
      hide();
    }
    const focus = document.activeElement;
    if (active != null && (legendEl.contains(focus) || focus === holder)) clearFilter();
  });
  document.addEventListener('pointerdown', (event) => {
    if (!figure.contains(event.target)) hide();
  });

  return {
    highlight(stateName) {
      const code = stateName == null ? null : codeByName.get(stateName);
      for (const [c, { fill }] of layers) fill.classList.toggle('selected', c === code);
      selected = code ?? null;
      // The thick outline is drawn over every layer, so it shows whether or not the state's
      // class is the one the legend shows; small states also get a ring so they can be found.
      setSelectedOutline(code ?? null);
      const r = code ? doc.map.rings?.[code] : null;
      for (const circle of ringHalo ? [ringHalo, ring] : [ring]) {
        circle.setAttribute('cx', r ? r[0] : 0);
        circle.setAttribute('cy', r ? r[1] : 0);
        circle.setAttribute('r', r ? r[2] : 0);
      }
    },
  };
}
