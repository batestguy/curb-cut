# Maps (experimental): colour, contrast and what the audit checks

`disability_access_charts.maps.choropleth` builds a shaded-map ("choropleth") document. It is **experimental**: not exported from the package, marked `meta.experimental = true`, and liable to change before stable map support in 0.2. Curb Cut uses it for its national prevalence map.

## The document

Like `bar()` and `dot()`, one JSON-serialisable dict:

- `map`: an SVG `viewBox` and one path per region (the page draws the SVG; no Plotly), plus optional rings for small regions and an attribution;
- `regions`, `breaks`, `classes`: each region's class, and each class's label, bounds and count;
- `themes`: light and dark `MapTheme`s (background, text, boundary `edge`, one fill per class);
- `alt_text`: built from the data (see below); `alt_text_classes` is its class sentence;
- `table`: every region, sorted by name, with its value, interval, class and any extra text columns (e.g. a precision flag);
- `data`, `keyboard`, `audit`, `meta`.

## Fixed classes

Classes come from fixed, rounded breaks (`breaks=[2, 3, 4, 6]`: "Under 2%", "2% to under 3%", "3% to under 4%", "4% to under 6%", "6% and over"), not from quantiles, so the legend reads as plain ranges and does not move when the data change. Each value is classed **as displayed**, rounded to `decimals`: a value shown as 2.0% is never in "Under 2%". An empty class gives an audit warning.

## Why colour alone cannot carry a five-class map

WCAG 2.2 SC 1.4.11 asks for 3:1 contrast for the parts of a graphic needed to understand it. A sequential scale has room for about one 3:1 step between white and the darkest fill that still contrasts with the boundaries, not four. Between neighbouring classes the default fills differ by only 1.3 to 1.6:1, in both themes. So the map is designed so that **colour is never the only cue** (SC 1.4.1):

| Need | How it is met | Audit check |
|---|---|---|
| Each region's shape is visible | Boundaries in the theme's `edge` colour, at least 3:1 against the background **and against every fill** (light: near-black on greens up to the flag green `#008751`, 3.8:1 at the darkest; dark: white on greens up to `#34a061`, 3.3:1) | `wcag-1.4.11` (one per fill and theme) |
| The legend can be found | Swatches outlined in the same `edge` colour | `wcag-1.4.11` (edge against background) |
| A region's class can be read without colour | The legend gives each range in words and its count; the table has every value, interval and class; the page adds a tooltip on hover, tap and focus | `not-colour-alone` (reports the neighbouring-fill ratios and this reasoning in its `note`) |
| The scale reads as ordered | Fills move away from the background as the value rises (darker in light mode, brighter in dark mode) | `classes-ordered` |
| Text is readable | Text colour at least 4.5:1 | `wcag-1.4.3` |

## Alt-text

The alt-text has three parts: an introduction ("Map: title. 37 states, each with its 95% confidence interval."), the class sentence ("Shaded in 5 classes: under 2%, 12 states; …"), and the same description a dot plot of the data gets (highest and lowest estimates, whether the survey can tell them from the next one, their intervals, the source). The audit regenerates the class sentence from the values and breaks and requires an exact match (`alt-text-classes-match-data`), then runs the claim checker on the rest (`alt-text-matches-data`), so a wrong count or a wrong number fails the build.

## What the page must do

The document cannot check the page. Curb Cut's page draws the map as one `role="img"` named by the alt-text, with the SVG hidden from assistive technology; the regions are not separate Tab stops; the tooltip closes with Esc, can be hovered, and stays until the pointer leaves (SC 1.4.13); and the table follows the map. Its Playwright and axe tests check those.
