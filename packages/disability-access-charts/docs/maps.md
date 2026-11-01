# Maps: colour, patterns, contrast and what the audit checks

`disability_access_charts.choropleth` (also importable from `disability_access_charts.maps`) builds a shaded-map ("choropleth") document. It is **stable API since 0.2**: exported from the package, with `meta.experimental = false`. In 0.1 it was experimental. 0.2 added `patterns`, which changed the default document: `patterns=None` (the default) means "auto", a pattern per class with five classes or fewer and none with more (there are five tiles), where the audit adds a `shade-alone` **warning** that neighbouring classes differ by shade alone. `patterns=False` gives the 0.1 document (with the same warning); `patterns=True` with more than five classes raises. Curb Cut uses it for its national prevalence map.

**Changed in 0.3** (schema `"1.1"`): a new default colour scheme, `scheme="ylgnbu"`, with cased boundaries; map patterns ordered by ink weight with an ink per class; a colour-vision check; and legend-filter metadata (`legend_filter=True`). `scheme="green"` gives the 0.2 look (see [Getting the 0.2 look](#getting-the-02-look)). Every other argument is unchanged.

## The document

Like `bar()` and `dot()`, one JSON-serialisable dict:

- `map`: an SVG `viewBox` and one path per region (the page draws the SVG; no Plotly), plus optional rings for small regions and an attribution;
- `regions`, `breaks`, `classes`: each region's class, and each class's label, bounds and count;
- `themes`: light and dark `MapTheme`s (background, text, boundary `edge`, a `halo` when the boundaries are cased (0.3), one fill per class);
- `alt_text`: built from the data (see below); `alt_text_classes` is its class sentence;
- `table`: every region, sorted by name, with its value, interval, class and any extra text columns (e.g. a precision flag);
- `patterns` (when patterns are on): the tiles, each class's tile in order, `sequence` (`"ink-weight"`, or `"density-0.2"` for the green scheme), the ink (0.3 schemes: `class_ink`, each theme's ink per class, `null` where the tile draws nothing; green scheme: `ink`, one per theme, as in 0.2), and `scale` (how much to scale a 12-unit tile in map units); each entry in `classes` also names its tile as `pattern`, for the legend;
- `legend` (0.3, with `legend_filter=True`, the default): `filter: true`, `announce_all` ("Showing all 37 states.") and the sentence templates; each entry in `classes` also has `regions` (its regions, in name order) and `announce` ("Showing 6 states in 4% to under 6%: Adamawa, Ebonyi, …");
- `data`, `keyboard` (0.3 adds `legend_filter` and `legend_keys`), `audit`, `meta` (0.3 adds `scheme`: `"ylgnbu"`, `"green"`, or `"custom"` when `themes=` is given).

## Fixed classes

Classes come from fixed, rounded breaks (`breaks=[2, 3, 4, 6]`: "Under 2%", "2% to under 3%", "3% to under 4%", "4% to under 6%", "6% and over"), not from quantiles, so the legend reads as plain ranges and does not move when the data change. Each value is classed **as displayed**, rounded to `decimals`: a value shown as 2.0% is never in "Under 2%". An empty class gives an audit warning.

## Colour schemes (0.3)

`MAP_SCHEMES` holds the named schemes, each with a light and a dark theme; `MAP_THEMES` is the default scheme's themes (**changed in 0.3**: it was the greens).

| Scheme | Light fills (low to high) | Dark fills (low to high) | Boundaries |
|---|---|---|---|
| `"ylgnbu"` (default since 0.3) | ColorBrewer YlGnBu 5: `#ffffcc #a1dab4 #41b6c4 #2c7fb8 #253494` | drawn for this library: `#4a4512 #2b7340 #1b8f96 #77bdf2 #d4ebff` (olive yellow, green, teal, blue, pale blue: brighter for higher values) | cased: light, edge `#1a1a1a` on halo `#ffffff`; dark, edge `#ffffff` on halo `#121212` |
| `"green"` (the 0.2 look) | `#e4f3e9 #b5dec3 #7dc39a #3fa16f #008751` | `#1b2f23 #1e4b33 #226943 #2a8753 #34a061` | one edge: `#1a1a1a` light, `#ffffff` dark |

The YlGnBu fills take larger lightness steps than the greens (CIELAB L\* 99, 82, 68, 51, 27 in the light theme; 29, 43, 54, 74, 92 in the dark one) and change hue as well, so neighbouring classes are easier to tell apart, including under simulated colour-vision deficiency (below). The darkest dark fill is 1.92:1 against the `#121212` background and at least 17.8 CIEDE2000 from it in every simulated vision. `themes=` replaces a scheme's colours; the pattern style still follows `scheme`.

## Cased boundaries (0.3)

No single boundary colour is 3:1 against both `#ffffcc` and `#253494` (near-black is 1.66:1 on the dark blue, white 1.03:1 on the pale yellow). So a theme can carry a `halo`, and the page draws every boundary twice, **after all the fills**: a wide stroke in the halo colour (3 px on Curb Cut's page) under a narrow stroke in the edge colour (1 px). At any border, whatever the two fills, the edge or the halo stands out from each side. The legend swatches are outlined in the edge colour, which is 3:1 against the background.

The stroke widths are in the document as `map.casing`, in screen pixels: `halo` 3 and `edge` 1 for every boundary, `active_halo` 5 and `active_edge` 2 for the class a legend filter shows, `outline_halo` 6 and `outline_edge` 3 for a chosen region's outline and ring. The `casing-widths` check asks that each halo is wider than its edge.

For a theme with a halo the audit (`wcag-1.4.11`, one check per item and theme) asks that:

- the edge is at least 3:1 against the background, and against the halo;
- for the background and for **every** fill, the edge **or** the halo is at least 3:1 (both ratios are reported, as `edge_ratio` and `halo_ratio`).

A theme with no halo keeps the 0.2 rule: the edge at least 3:1 against the background and every fill. A single edge on the YlGnBu fills therefore fails (1.66:1 on `#253494`).

The defaults, edge / halo against each item:

| Theme | background | class 1 | class 2 | class 3 | class 4 | class 5 |
|---|---|---|---|---|---|---|
| light | 17.4 / 1.0 | 16.93 / 1.03 | 10.94 / 1.59 | 7.22 / 2.41 | 4.01 / 4.34 | 1.66 / 10.51 |
| dark | 18.73 / 1.0 | 9.76 / 1.92 | 5.79 / 3.24 | 3.88 / 4.83 | 2.03 / 9.23 | 1.23 / 15.28 |

Edge against halo: 17.4:1 (light), 18.73:1 (dark).

## Colour vision (0.3)

The `colour-vision` check simulates deuteranopia, protanopia and tritanopia with the matrices of Machado, Oliveira and Fernandes (2009) at severity 1.0 (on linear RGB) and measures each pair of neighbouring fills with CIEDE2000, in normal vision too. It is an **error** if any pair is under 5 in any of them (`CVD_MIN_DELTA_E`, about twice a just-noticeable difference); `colour-vision-target` is a **warning** under 10 (`CVD_TARGET_DELTA_E`). The check reports the minimum, the vision it occurs in, the minimum per vision and every difference. These are design thresholds, not WCAG numbers; the reasoning is in `disability_access_charts.vision`, which is pure Python and reproduces Sharma, Wu and Dalal's (2005) CIEDE2000 test pairs.

| Scheme, theme | Minimum CIEDE2000 between neighbours (normal / deuteranopia / protanopia / tritanopia) | Closest pair |
|---|---|---|
| ylgnbu, light | **10.3** (17.7 / 13.5 / 10.3 / 12.2) | classes 1 and 2, protanopia |
| ylgnbu, dark | **11.6** (15.8 / 11.6 / 14.0 / 13.7) | classes 1 and 2, deuteranopia |
| green, light | **7.5**: passes the error, warns | classes 1 and 2, deuteranopia |
| green, dark | **8.2**: passes the error, warns | classes 1 and 2, deuteranopia |

## Why colour alone still cannot carry a five-class map

WCAG 2.2 SC 1.4.11 asks for 3:1 contrast for the parts of a graphic needed to understand it. A sequential scale has room for about one 3:1 step, not four: the YlGnBu neighbours are 1.49 to 2.42:1 apart in contrast ratio (the greens 1.3 to 1.6:1). So the map is designed so that **colour is never the only cue** (SC 1.4.1):

| Need | How it is met | Audit check |
|---|---|---|
| Each region's shape is visible | Cased boundaries (above); with no halo, one edge 3:1 against the background and every fill | `wcag-1.4.11` (one per item and theme) |
| The legend can be found | Swatches outlined in the `edge` colour | `wcag-1.4.11` (edge against background) |
| A region's class can be read without colour | Each class has its own pattern, ordered by ink weight (plain, dots, lines, crosshatch, solid); the legend shows the pattern and gives each range in words and its count; the table has every value, interval and class; the page adds a tooltip on hover, tap and focus | `not-colour-alone` (reports the neighbouring-fill ratios), `patterns-one-to-one`, `patterns-legend` |
| The pattern can be seen on its fill | Each class's ink is black or white, whichever contrasts more with its fill, at least 3:1 (light: black at 13.2, 8.71 and 4.83:1 on classes 2 to 4; dark: white at 5.79:1 on class 2, black at 5.42 and 10.35:1 on classes 3 and 4); plain and solid draw no ink and are exempt | `patterns-ink-contrast` (error), `patterns-ink-rule` (warning) |
| Neighbours differ for colour-blind readers | CIEDE2000 under simulated colour-vision deficiency (above) | `colour-vision`, `colour-vision-target` |
| The scale reads as ordered | Fills move away from the background as the value rises (darker in light mode, brighter in dark mode) | `classes-ordered` |
| Text is readable | Text colour at least 4.5:1 | `wcag-1.4.3` |

## The legend filter (0.3)

With `legend_filter=True` (the default) the document carries what a page needs for a legend whose items are toggle buttons: each class's regions and the sentence to announce when only that class is shown, and the sentence for showing all again. The sentences come from the language table (`MAP_LEGEND` in `_lang/en.py`, kept apart from the alt-text templates so they do not change the claim checker's reserved names). `legend-filter-matches-data` regenerates the lists and sentences from the values and breaks and fails on any difference. `legend_filter=False` leaves all of this out.

## Getting the 0.2 look

`choropleth(..., scheme="green")` gives the 0.2 greens, one boundary colour, the 0.2 pattern order (dots, rings, checks, lines, crosshatch) and one ink per theme in `patterns.ink`, as in 0.2. Its audit is stricter than in 0.2: `colour-vision-target` warns (7.5 and 8.2), so `check --strict` fails on it while plain `check` passes. Add `legend_filter=False` to leave out the legend metadata too. Otherwise the document differs from 0.2's only in the version, `meta.schema` ("1.1"), `meta.scheme`, `patterns.sequence` and `keyboard.legend_filter: false`.

Custom themes: `choropleth(..., themes=...)` without `scheme` gets the 0.3 pattern style (ink-weight order, an ink per class) and every 0.3 check, so fills that passed in 0.2 can now fail `colour-vision`. Pass `scheme="green"` with them to keep the 0.2 pattern order and one ink per theme.

## Alt-text

The alt-text has three parts: an introduction ("Map: title. 37 states, each with its 95% confidence interval."), the class sentence ("Shaded in 5 classes: under 2%, 12 states; …"), and the same description a dot plot of the data gets (highest and lowest estimates, whether the survey can tell them from the next one, their intervals, the source). The audit regenerates the class sentence from the values and breaks and requires an exact match (`alt-text-classes-match-data`), then runs the claim checker on the rest (`alt-text-matches-data`), so a wrong count or a wrong number fails the build.

## What the page must do

The document cannot check the page. Curb Cut's page draws the map as one `role="img"` named by the alt-text, with the SVG hidden from assistive technology; the regions are not separate Tab stops; the tooltip closes with Esc, can be hovered, and stays until the pointer leaves (SC 1.4.13); and the table follows the map. With patterns, the page draws one SVG `<pattern>` per class (the class fill behind, the tile in the class's ink in front, scaled by `patterns.scale`; nothing in front for plain and solid), fills each region with its class's pattern, and draws the same pattern in each legend swatch. With a halo it draws every fill, then every halo, then every edge, at the widths in `map.casing`, and the ring round a small chosen region is cased the same way. On a narrow screen it raises the scale so that no tile is drawn under 8 pixels (at 320 px the map is about 288 px wide, and the document's scale alone would give tiles of about 5.5 px); the colours follow the light or dark scheme.

With a legend block, Curb Cut's legend is a vertical list of `<button type="button" aria-pressed>` items under a visible label, lowest class first, each with a 40 × 28 px patterned swatch (hidden from assistive technology) and the text "Under 2%: 12 states". Pressing one shows only that class: the other states are dimmed (their boundaries stay, faint) and the shown states keep their full fill and pattern with heavier boundaries, so the difference is not one of hue alone. Pressing it again, or Esc in the legend or on the map, shows all. One polite live region announces `announce` or `announce_all`. Its Playwright and axe tests check all of this in both schemes. The tiles, their sources and the ink rule are in [patterns.md](patterns.md).
