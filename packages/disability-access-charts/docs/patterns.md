# Patterns: adire-inspired tiles, and the rules they meet

`disability_access_charts.patterns` adds a second, non-colour cue to bar series and map classes (WCAG 2.2 SC 1.4.1, use of colour). A pattern is added **to** the colour, never instead of it, and the chart keeps its direct labels or legend.

## The tiles

Each tile is an SVG path of the regions to fill in a 12 × 12 square: the form Plotly's `marker.pattern.path` takes, and the same path draws the map's SVG `<pattern>` fills. In `PATTERNS` order, from the sparsest ink to the densest (bars, and maps with `scheme="green"`):

| id | Drawing | After |
|---|---|---|
| `dots` | two small dots per tile, on a diagonal | the small tied dots of *oniko* (tie-resist adire) |
| `rings` | one ring per tile | *oniko*'s tie-resist circles |
| `checks` | a square grid of thin lines | the checked layouts of adire cloths |
| `lines` | diagonal lines | the line work of adire |
| `crosshatch` | diagonal lines both ways | the same line work, drawn both ways |

### The map sequence (new in 0.3)

In 0.2 the map's lightest pattern pair (dots, rings) looked alike and the order did not follow ink weight. Since 0.3, maps (any scheme but `"green"`) use `MAP_PATTERNS`, **ordered by ink weight**, so the lowest class is the lightest:

| id | Ink (share of the tile) | Note |
|---|---|---|
| `plain` | none | the fill alone; the lowest class |
| `dots` | about 7% | as above |
| `lines` | about 22% | as above |
| `crosshatch` | about 33% | as above |
| `solid` | none | the fill alone; the highest class, whose fill is the darkest in the light theme |

`plain` and `solid` draw nothing (an empty `path`), so they are told apart by their fills only: they are never neighbours, and the audit checks that their fills are 3:1 apart in every theme (light: `#ffffcc` and `#253494`, 10.2:1). Fewer classes take an ordered subset (`MAP_SEQUENCES`, `assign_map()`): 2 classes, plain and crosshatch; 3, plain, lines and solid; 4, plain, dots, crosshatch and solid; 5, all of them. More than five classes get no patterns (as in 0.2). Bars keep `PATTERNS` and look the same as in 0.2.

### Respectful use (verification.md D31)

Adire is Yoruba resist-dyed cloth, and *oniko* is its tie-resist style of rings and dots. These tiles are **abstract geometric interpretations drawn for this library**: plain circles, lines and grids, not copies of any cloth or motif. They are **never nsibidi or Ukara signs**: those are a writing and symbol system whose signs carry meanings (some restricted to members of societies) that are not ours to use as decoration. A review by a Nigerian designer or textile practitioner is welcome but was not a condition of the release (author's decision, 2026-10-29).

Sources consulted for the styles (verification.md D31, 2026-10-21):

- MOMAA, "Adire textile art": https://momaa.org/adire-textile-art/
- Wikipedia, "Adire (textile art)": https://en.wikipedia.org/wiki/Adire_(textile_art)

## Where they work

Plotly supports `marker.pattern` (including a custom `path`) on bar, pie, histogram, barpolar, treemap, icicle and sunburst traces, but **not** on scatter, funnel or choropleth (Plotly 7.1.0, checked 2026-10-29, verification.md D30). So:

- **Bars:** `bar(..., patterns=True)` gives the bars one tile (off by default, so 0.1 documents are unchanged). `grouped_bar(...)` gives each series its own tile and colour, **on by default**, and the Plotly legend draws each series' pattern next to its name.
- **Dot plots** keep their marker shapes (circle, diamond, square, …), which already separate the series.
- **Maps:** `choropleth()` gives each class its own tile, **on by default**, drawn by the page as SVG `<pattern>` fills (`svg_pattern()` shows the markup and takes `ink=None` for plain and solid; Curb Cut's `map.js` builds the same thing with DOM calls). Since 0.3 the tiles follow the map sequence above, unless `scheme="green"`. `patterns=False` gives the 0.1 document. The document's `patterns.scale` sizes a tile to 1/52 of the map's width, about 12 pixels on a 630-pixel map.

## The ink rule (SC 1.4.11)

Where the pattern is what tells two neighbouring classes or series apart, it is a graphical object needed to understand the chart, so SC 1.4.11 asks for **3:1 between the ink and the fill it sits on**, in every theme. Two rules meet it:

- **One ink per theme** (bars, and maps with `scheme="green"`): black or white, whichever has the **higher lowest contrast** against all the fills (`ink_for()`), stored as `patterns.ink`. The audit asks 3:1 against every fill.
- **One ink per class** (maps, new in 0.3): black or white, whichever contrasts more with **that class's** fill (`best_ink()`, `class_inks()`), stored as `patterns.class_ink` (`null` where the tile draws nothing). The YlGnBu fills run from near-white to dark blue, so no single ink could reach 3:1 on all of them; per class, every inked class does. The audit asks 3:1 per inked class (classes whose tile has no ink are exempt) and warns if an ink is not the better of the two.

The default colours give, ink against each fill:

| Theme | Ink | Ratios |
|---|---|---|
| Map, YlGnBu light | none, black, black, black, none | –, 13.2, 8.71, 4.83, – |
| Map, YlGnBu dark | none, white, black, black, none | –, 5.79, 5.42, 10.35, – |
| Map, green light (0.2) | black | lowest 4.58:1 (on `#008751`) |
| Map, green dark (0.2) | white | lowest 3.31:1 (on `#34a061`) |
| Grouped bars, light (the four series colours) | black | lowest 4.05:1 (on `#0072b2`) |
| Grouped bars, dark (the six series colours) | black | lowest 5.43:1 (on `#d55e00`) |
| One-series bars, light / dark (`#008751` / `#198754`) | black | 4.58:1 / 4.63:1 |

Any single colour has black or white at 4.58:1 or better, so a one-colour chart, and every class with its own ink, always passes. A set of fills mixing very dark and very light colours can leave no single ink at 3:1, and the audit fails it.

Neighbouring map classes are only 1.49 to 2.42:1 apart in colour with YlGnBu (1.3 to 1.6:1 with the greens; see `maps.md`); with patterns, they also differ in a 3:1 pattern, except where the plain or solid class sits next to a patterned one (which differs from it by the pattern itself).

## What the audit checks

For a bar document with a `patterns` block, and for a map document with one:

| Check | WCAG | Fails when |
|---|---|---|
| `patterns-one-to-one` | 1.4.1 | a series or class has no pattern, two share a pattern or two inked tiles draw the same path, two share a colour, a pattern id has no tile, two neighbouring classes both have a no-ink tile, two no-ink classes have fills under 3:1 apart, or (bars) a trace draws a different tile from the one assigned to it |
| `patterns-ink-contrast` | 1.4.11 | one ink per theme: in any theme the ink is under 3:1 against a fill, or the theme has no ink; one ink per class (0.3 maps): an inked class's ink is under 3:1 against its fill or missing (one check per theme; the ratios are reported, `null` for exempt classes) |
| `patterns-legend` | 1.4.1 | the legend does not show each series' or class's pattern: for grouped bars, the Plotly legend is off; for maps, a class's `pattern` (what the legend draws) differs from its tile |
| `patterns-ink-rule` (warning) | 1.4.11 | bars: the stored ink is not the one `ink_for()` picks for the theme; 0.3 maps: a class's ink is not the better of black and white for its fill |

For bars, the light theme's ink and fills are read from the Plotly traces themselves, so the check tests what is drawn. Grouped bars **without** patterns get a `not-colour-alone` warning.

The page has to draw what the document says; the document cannot check the page. Curb Cut's Playwright tests check that every state on the map is filled with its class's pattern, that each pattern draws the class's fill and the class's ink from the document in light and dark mode (and no ink for plain and solid), that each legend swatch draws the same, and that axe finds no violations in either mode.
