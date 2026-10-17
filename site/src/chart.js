// Render a chart document built by disability_access_charts (see build_charts.py).
// The chart is a static image to assistive technology: its container has role="img" and is
// named by the data-derived alt-text, and the Plotly SVG inside is aria-hidden. Every value
// is also in the HTML table rendered from the same document.
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

function themed(doc, themeName) {
  const theme = doc.themes[themeName] ?? doc.themes.light;
  const data = doc.plotly.data.map((trace) => ({
    ...trace,
    marker: { ...trace.marker, color: theme.mark },
    textfont: { color: theme.text },
  }));
  const base = doc.plotly.layout;
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
    autosize: true,
  };
  return { data, layout };
}

const config = { staticPlot: true, displayModeBar: false, responsive: true };

export async function renderChart(doc, { container, titleEl, descEl, tableEl }) {
  titleEl.textContent = doc.title;
  descEl.textContent = doc.alt_text;
  tableEl.replaceChildren(renderTable(doc.table));

  const plot = container.querySelector('.chart-plot');
  const draw = () => {
    let { data, layout } = themed(doc, darkQuery.matches ? 'dark' : 'light');
    if (narrowQuery.matches) ({ data, layout } = compact(layout, data));
    return Plotly.react(plot, data, layout, config);
  };
  await draw();
  darkQuery.addEventListener('change', draw);
  narrowQuery.addEventListener('change', draw);
}
