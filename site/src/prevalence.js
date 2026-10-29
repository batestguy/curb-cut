// The measured figures: the national headline, the comparison of published figures, and the
// spatial findings. All numbers come from the build's JSON files (export_marts.py); the
// spatial sentences are used exactly as written by the analysis (data/public/spatial/).
import { formatValue, renderTable } from './format.js';

export function pct(value, decimals = 1) {
  return `${formatValue(value, 'number', decimals)}%`;
}

export function interval(low, high) {
  return `95% confidence interval ${pct(low)} to ${pct(high)}`;
}

/** The national headline sentence, from prevalence.json. */
export function renderHeadline(el, prevalence) {
  const n = prevalence.national;
  el.textContent =
    `The DHS 2024 survey estimates that ${pct(100 * n.estimate)} of adults aged 18 and over ` +
    `living in households in Nigeria (${interval(100 * n.ci_low, 100 * n.ci_high)}) have a lot of difficulty with, ` +
    'or cannot do at all, at least one of six everyday activities.';
}


/**
 * The comparison list and the key message. Every figure links to its source.
 */
export function renderComparison(messageEl, listEl, prevalence) {
  const rows = prevalence.comparison;
  const byId = new Map(rows.map((r) => [r.figure_id, r]));
  const any = byId.get('ndhs2024_15plus_any');
  const wg = byId.get('ndhs2024_15plus_wg');
  const ours = byId.get('dhs2024_18plus_wg');
  if (any && wg && ours) {
    messageEl.textContent =
      `In the NDHS 2024 report, ${pct(any.value_percent)} of people aged 15 and over have at ` +
      `least some difficulty in one of the six activities, but ${pct(wg.value_percent)} have ` +
      `"a lot of difficulty" or "cannot do at all", the Washington Group cut-off. Our estimate ` +
      `for adults 18 and over at the same cut-off is ${pct(ours.value_percent)}. So the gap ` +
      'between figures of about 15% and about 3% is mostly about the definition (any ' +
      'difficulty, against the disability cut-off), not a contradiction between sources. ' +
      "JONAPWD's 15% was assumed, not measured, and WHO's 16% uses its own wording, " +
      '"significant disability", which the fact sheet does not define.';
  } else {
    messageEl.textContent = 'The figures below come from different sources and definitions.';
  }

  // A list rather than a table: each figure carries a paragraph of definition, which a
  // three-column table could only show squeezed or scrolling sideways on a phone.
  const list = document.createElement('ul');
  list.className = 'comparison-list';
  list.setAttribute('aria-label', 'Published disability figures, with what each one counts');
  for (const r of rows) {
    const li = document.createElement('li');
    const head = document.createElement('p');
    head.className = 'comparison-figure';
    const label = document.createElement('span');
    label.className = 'comparison-label';
    label.textContent = `${r.label}: `;
    const value = document.createElement('strong');
    value.className = 'comparison-value';
    // Cited round figures keep their own precision (15%, 16%); measured ones show 1 decimal.
    value.textContent = pct(r.value_percent, r.kind === 'measured' ? 1 : 0);
    head.append(label, value);
    if (r.ci_low_percent != null) {
      head.append(` (${interval(r.ci_low_percent, r.ci_high_percent)})`);
    }
    const what = document.createElement('p');
    what.textContent = `${r.population}. ${r.definition} Source: `;
    const a = document.createElement('a');
    a.href = r.source_url;
    a.textContent = r.source;
    what.append(a, '.');
    li.append(head, what);
    list.append(li);
  }
  listEl.replaceChildren(list);
}

/** The spatial sentences, the Moran table, the cluster lists and the services caveats. */
export function renderSpatial(spatial, els) {
  const [primary, ...others] = spatial.moran;
  els.moranSentence.textContent = primary.sentence;
  els.moranTable.replaceChildren(
    renderTable({
      caption:
        "Global Moran's I by measure (one-sided permutation p; adjusted p: Benjamini-Hochberg across the 8 tests)",
      columns: [
        { label: 'Measure', type: 'text' },
        { label: 'Ages', type: 'text' },
        { label: "Moran's I", type: 'number', decimals: 2 },
        { label: 'p', type: 'number', decimals: 3 },
        { label: 'Adjusted p', type: 'number', decimals: 3 },
        { label: 'Imprecise state estimates (of 37)', type: 'integer' },
      ],
      rows: spatial.moran.map((m) => [m.label, m.age_group, m.moran_i, m.p_perm, m.p_bh, m.n_imprecise]),
    }),
  );
  els.moranSentences.replaceChildren(
    ...others.map((m) => {
      const li = document.createElement('li');
      li.textContent = m.sentence;
      return li;
    }),
  );
  els.lisaDetail.textContent = spatial.lisa.sentence;
  const flagged = spatial.lisa.significant_states;
  els.lisaUnderMap.textContent =
    flagged.length === 0
      ? 'The map has no hotspot outlines: an exploratory test found no state to be a ' +
        'significant local hotspot or coldspot after correcting for 37 tests.'
      : `An exploratory test flagged ${flagged.join(', ')} as local hotspots or coldspots; ` +
        'see "Local hotspots" below. The map does not outline them.';
  els.clusterSentence.textContent = spatial.clusters.sentence;
  els.clusterGroups.replaceChildren(
    ...spatial.clusters.groups.map((g) => {
      const wrap = document.createElement('div');
      const h = document.createElement('h4');
      h.textContent = `Group ${g.cluster}: ${g.n_states} states`;
      const ul = document.createElement('ul');
      ul.className = 'state-list';
      ul.replaceChildren(
        ...g.states.map((name) => {
          const li = document.createElement('li');
          li.textContent = name;
          return li;
        }),
      );
      wrap.append(h, ul);
      return wrap;
    }),
  );
  els.servicesSentence.textContent = spatial.services.sentence;
  els.servicesCaveats.replaceChildren(
    ...spatial.services.caveats.map((c) => {
      const li = document.createElement('li');
      li.textContent = c;
      return li;
    }),
  );
}

/**
 * The statistical findings for the state dot plot (disability_access_charts 0.2). Every
 * sentence comes from the chart document, where the library built it from the data and its
 * audit held it to the claim checker; the page only lays it out. Nothing here is a live
 * region: the block is ordinary text after the chart, read in document order.
 */
export function renderFindings(findings, source, els) {
  const strong = document.createElement('strong');
  strong.textContent = findings.lines.count;
  els.count.replaceChildren(strong);
  const items = findings.statements.map((s) => {
    const li = document.createElement('li');
    li.textContent = s.text;
    return li;
  });
  els.list.replaceChildren(...items);
  els.list.hidden = items.length === 0;
  const notes = [findings.lines.none, findings.lines.dropped, findings.lines.withheld].filter(Boolean);
  els.notes.replaceChildren(
    ...notes.map((text) => {
      const p = document.createElement('p');
      p.textContent = text;
      return p;
    }),
  );
  els.families.replaceChildren(
    ...findings.families
      .filter((f) => f.checked + f.dropped > 0)
      .map((f) => {
        const li = document.createElement('li');
        const dropped = f.dropped ? `, ${f.dropped} not tested` : '';
        li.textContent = `${f.label}: ${f.checked} checked, ${f.supported} supported${dropped}.`;
        return li;
      }),
  );
  const caveats = findings.caveats.filter((c) => c.id !== 'descriptive').map((c) => c.text);
  els.method.textContent = [findings.lines.method, ...caveats, `Source: ${source}.`].join(' ');
}
