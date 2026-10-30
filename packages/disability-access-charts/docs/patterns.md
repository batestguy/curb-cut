# Patterns: five adire-inspired tiles, and the rules they meet

`disability_access_charts.patterns` adds a second, non-colour cue to bar series and map classes (WCAG 2.2 SC 1.4.1, use of colour). A pattern is added **to** the colour, never instead of it, and the chart keeps its direct labels or legend.

## The tiles

Each tile is an SVG path of the regions to fill in a 12 × 12 square: the form Plotly's `marker.pattern.path` takes, and the same path draws the map's SVG `<pattern>` fills. In `PATTERNS` order, from the sparsest ink to the densest, so a sequential map also reads as ordered without colour:

| id | Drawing | After |
|---|---|---|
| `dots` | two small dots per tile, on a diagonal | the small tied dots of *oniko* (tie-resist adire) |
| `rings` | one ring per tile | *oniko*'s tie-resist circles |
| `checks` | a square grid of thin lines | the checked layouts of adire cloths |
| `lines` | diagonal lines | the line work of adire |
| `crosshatch` | diagonal lines both ways | the same line work, drawn both ways |

### Respectful use (verification.md D31)

Adire is Yoruba resist-dyed cloth, and *oniko* is its tie-resist style of rings and dots. These tiles are **abstract geometric interpretations drawn for this library**: plain circles, lines and grids, not copies of any cloth or motif. They are **never nsibidi or Ukara signs**: those are a writing and symbol system whose signs carry meanings (some restricted to members of societies) that are not ours to use as decoration. A review by a Nigerian designer or textile practitioner is welcome but was not a condition of the release (author's decision, 2026-10-29).

Sources consulted for the styles (verification.md D31, 2026-10-21):

- MOMAA, "Adire textile art": https://momaa.org/adire-textile-art/
- Wikipedia, "Adire (textile art)": https://en.wikipedia.org/wiki/Adire_(textile_art)

## Where they work

Plotly supports `marker.pattern` (including a custom `path`) on bar, pie, histogram, barpolar, treemap, icicle and sunburst traces, but **not** on scatter, funnel or choropleth (Plotly 7.1.0, checked 2026-10-29, verification.md D30). So:

- **Bars:** `bar(..., patterns=True)` gives the bars one tile (off by default, so 0.1 documents are unchanged). `grouped_bar(...)` gives each series its own tile and colour, **on by default**, and the Plotly legend draws each series' pattern next to its name.
- **Dot plots** keep their marker shapes (circle, diamond, square, …), which already separate the series.
- **Maps:** `choropleth()` gives each class its own tile, **on by default**, drawn by the page as SVG `<pattern>` fills (`svg_pattern()` shows the markup; Curb Cut's `map.js` builds the same thing with DOM calls). `patterns=False` gives the 0.1 document. The document's `patterns.scale` sizes a tile to 1/52 of the map's width, about 12 pixels on a 630-pixel map.

## The ink rule (SC 1.4.11)

The pattern is drawn in one ink per theme, black or white: whichever has the **higher lowest contrast** against the fills it sits on (`ink_for()`). Where the pattern is what tells two neighbouring classes or series apart, it is a graphical object needed to understand the chart, so SC 1.4.11 asks for **3:1 between the ink and every fill it sits on**, in every theme. The audit checks exactly that.

The default colours give, ink against each fill:

| Theme | Ink | Lowest ratio |
|---|---|---|
| Map, light (pale green to `#008751`) | black | 4.58:1 (on `#008751`) |
| Map, dark (`#1b2f23` to `#34a061`) | white | 3.31:1 (on `#34a061`) |
| Grouped bars, light (the four series colours) | black | 4.05:1 (on `#0072b2`) |
| Grouped bars, dark (the six series colours) | black | 5.43:1 (on `#d55e00`) |
| One-series bars, light / dark (`#008751` / `#198754`) | black | 4.58:1 / 4.63:1 |

Any single colour has black or white at 4.58:1 or better, so a one-colour chart always passes. A set of fills mixing very dark and very light colours can leave no ink at 3:1, and the audit fails it.

Neighbouring map classes are only 1.3 to 1.6:1 apart in colour (see `maps.md`); with patterns, they also differ in a 3:1 pattern.

## What the audit checks

For a bar document with a `patterns` block, and for a map document with one:

| Check | WCAG | Fails when |
|---|---|---|
| `patterns-one-to-one` | 1.4.1 | a series or class has no pattern, two share a pattern or draw the same tile, two share a colour, a pattern id has no tile, or (bars) a trace draws a different tile from the one assigned to it |
| `patterns-ink-contrast` | 1.4.11 | in any theme, the ink is under 3:1 against a fill it sits on, or the theme has no ink (one check per theme; the ratios are reported) |
| `patterns-legend` | 1.4.1 | the legend does not show each series' or class's pattern: for grouped bars, the Plotly legend is off; for maps, a class's `pattern` (what the legend draws) differs from its tile |
| `patterns-ink-rule` (bars, warning) | 1.4.11 | the stored ink is not the one `ink_for()` picks for the theme |

For bars, the light theme's ink and fills are read from the Plotly traces themselves, so the check tests what is drawn. Grouped bars **without** patterns get a `not-colour-alone` warning.

The page has to draw what the document says; the document cannot check the page. Curb Cut's Playwright tests check that every state on the map is filled with its class's pattern, that the drawn ink is the document's ink in light and dark mode, that each legend swatch shows its class's pattern, and that axe finds no violations in either mode.
