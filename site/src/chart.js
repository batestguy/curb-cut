// Render a chart document built by disability_access_charts (see build_charts.py).
// The chart is a static image to assistive technology: its container has role="img" and is
// named by the data-derived alt-text, and the Plotly SVG inside is aria-hidden. Every value
// is also in the HTML table rendered from the same document.
//
// One bar can be highlighted (the state chosen in the explorer). That is visual only: the
// chart's description stays as built, and the state card says the same thing in words. The
// highlighted bar differs in colour (theme.highlight, audited at 3:1 against the bars and
// the background) and also without colour: a thick outline and a bold label and value.
import Plotly from 'plotly.js-basic-dist-min';
import { renderTable } from './format.js';

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
const narrowQuery = window.matchMedia('(max-width: 30rem)');

// Narrow screens: smaller text, fewer ticks and a tighter right margin for the value labels.
function compact(layout, data) {
  return {
    layout: {
      ...layout,
      font: { ...layout.font, size: 12 },
      margin: { ...layout.margin, r: 64, b: 50 },
      xaxis: { ...layout.xaxis, nticks: 3 },
    },
    data: data.map((trace) => ({ ...trace, textfont: { ...trace.textfont, size: 11 } })),
  };
}

function themed(doc, themeName, highlight) {
  const theme = doc.themes[themeName] ?? doc.themes.light;
  const marked = (trace) => highlight != null && trace.y.includes(highlight);
  // Dot plots colour each series from theme.series (each also has its own marker shape);
  // bars use theme.mark. Dot whiskers take their series colour, bar whiskers the text colour.
  const dots = doc.meta?.chart_type === 'dot';
  const data = doc.plotly.data.map((trace, index) => {
    const color = dots ? (theme.series?.[index] ?? theme.mark) : theme.mark;
    const whisker = dots ? color : theme.text;
    const errorX = trace.error_x ? { error_x: { ...trace.error_x, color: whisker } } : {};
    if (!marked(trace)) {
      return {
        ...trace,
        ...errorX,
        marker: { ...trace.marker, color },
        textfont: { color: theme.text },
      };
    }
    const on = trace.y.map((category) => category === highlight);
    return {
      ...trace,
      ...errorX,
      marker: {
        ...trace.marker,
        color: on.map((o) => (o ? (theme.highlight ?? color) : color)),
        line: { color: theme.text, width: on.map((o) => (o ? 3 : 0)) },
      },
      text: trace.text ? trace.text.map((t, i) => (on[i] && t ? `<b>${t}</b>` : t)) : trace.text,
      textfont: { color: theme.text },
    };
  });
  const base = doc.plotly.layout;
  const highlightedTrace = doc.plotly.data.find(marked);
  const yaxis = highlightedTrace
    ? {
        ...base.yaxis,
        tickmode: 'array',
        tickvals: highlightedTrace.y,
        ticktext: highlightedTrace.y.map((c) => (c === highlight ? `<b>${c}</b>` : c)),
      }
    : base.yaxis;
  const layout = {
    ...base,
    paper_bgcolor: theme.background,
    plot_bgcolor: theme.background,
    font: { ...base.font, color: theme.text },
    xaxis: {
      ...base.xaxis,
      gridcolor: theme.grid,
      title: { ...base.xaxis.title, font: { ...base.xaxis.title.font, color: theme.text } },
    },
    yaxis,
    ...(base.legend
      ? { legend: { ...base.legend, font: { ...base.legend.font, color: theme.text } } }
      : {}),
    autosize: true,
  };
  return { data, layout };
}

const config = { staticPlot: true, displayModeBar: false, responsive: true };

/**
 * Render a chart document. Returns a handle whose highlight(category) redraws the chart with
 * that bar highlighted (null clears it); unknown categories highlight nothing.
 */
export async function renderChart(doc, { container, titleEl, descEl, tableEl, highlight = null }) {
  titleEl.textContent = doc.title;
  descEl.textContent = doc.alt_text;
  tableEl.replaceChildren(renderTable(doc.table));

  const plot = container.querySelector('.chart-plot');
  let current = highlight;
  const draw = () => {
    let { data, layout } = themed(doc, darkQuery.matches ? 'dark' : 'light', current);
    if (narrowQuery.matches) ({ data, layout } = compact(layout, data));
    return Plotly.react(plot, data, layout, config);
  };
  await draw();
  darkQuery.addEventListener('change', draw);
  narrowQuery.addEventListener('change', draw);
  return {
    highlight(category) {
      current = category;
      return draw();
    },
  };
}
