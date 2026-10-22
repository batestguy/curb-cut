"""Alt-text built from the data, and a checker that tests alt-text against the data.

:func:`describe` writes a chart's description from its data. :func:`check_alt_text` reads
any description (generated, hand-written or from an LLM) and reports each problem it finds
as a :class:`Problem`, with a ``severity`` of ``"error"`` or ``"warning"``.

What the checker covers
-----------------------
**Numbers.** Every number must be in the data. A number belongs to the name just before it
when only a verb or "of / at / :" separates them ("Lagos's rate is 8.0%"), to the name after
it in "2.0% in Ibadan", and otherwise to the *nearest* category named in its part of the
clause (clauses end at ``;``, sentences at ``.``, ``!`` or ``?``, and parts at break words
such as "than", "but", ", and" or "and Ibadan has"), so "Kano, 12.3%" passes only if 12.3
is Kano's value, interval bound or share. In a "respectively" clause names and numbers
pair in order. "X to Y" next to a name with an interval must be its lower and upper bound,
in that order. A number followed by
"% of the total" must be that category's share. Chart-wide figures are read only with the
words that announce them: the number of categories or series before a counting noun ("37
bars", "4 states"), the total after "Total:" or before "in total", and the value of a
series whose values are all equal when no category is named. Rounding is allowed to the
number of decimals written. Numbers in the title, the source and the interval label are
skipped. The checker does not verify which *role* a number has (value, bound or share),
only that it is one of that category's figures.

**Claims** (English vocabulary, :mod:`disability_access_charts._lang.en`):

* extremes: *largest, highest, smallest, lowest*, and *the most, the fewest*. The groups
  named in the same part of the clause must be the extreme;
* pairwise: "A *higher / lower / more / fewer / larger / smaller / less* than B", and "A
  *trails / lags* B". Lists of names on either side ("A and B are higher than C and D")
  (joined by commas, "and" or "or") are checked pair by pair. A second comparison that
  starts with its comparator ("and higher than") is about the first subject; one with
  a new unnamed subject is warned about. A part that starts with a verb ("... and is
  the highest") is about the clause's first names;
* ratios: "*twice*", "*half*", "*double*", "*triple*", "*N times*" (digits or two to
  ten), within 5% of the actual ratio;
* ranks: "ranked N of M", "3rd", "the second-highest", "number one", "#2", with
  competition ranking (ties share a rank) and M equal to the number of categories;
* equality: "A is *the same as* B", "A and B are equal";
* differences: "the survey *can / cannot* show a difference from (or between) ...";
* "no difference", "not different" and close variants always fail.

**With intervals** (a series with ``lower`` and ``upper``), comparisons are tested, not
just read off the point estimates. "A is higher than B" passes only if
``abs(a - b) > 1.96 * sqrt(se_a**2 + se_b**2)``, where each standard error is the
interval's half-width divided by the normal quantile for the interval's level (1.96 for a
95% interval; the level is read from the interval label, e.g. "90% confidence interval"
or "90% CI", and defaults to 95%). When an interval is asymmetric, the **larger**
half-width is used, which makes the test conservative. This is a two-sided test at the 5%
level that assumes roughly normal, symmetric intervals and **independent groups**, with
**no correction for multiple comparisons**. When groups may not be independent (two series
for the same category, or categories that are parts of one whole) the checker still
applies the test but adds a warning.

* An unqualified superlative ("A is the highest") fails unless the test separates A from
  **every** other group. The hedged form "A has the highest estimate" is accepted when A
  has the highest point estimate.
* Ratios are checked on the point estimates (within 5%), and a ratio other than 1 also
  needs the difference to pass the test. Ratios of values below zero get a warning.
* Ranks are checked on the point estimates. If the test cannot separate the group from a
  neighbour in the ranking, a warning says the rank is not statistically supported.
* Equality ("the same as") always fails with intervals: a survey cannot show two groups
  are equal. The suggested wording is "the survey cannot show a difference".

What it does not cover
----------------------
No errors means that **no recognised claim was found false**. It does not mean the text is
true or complete. Wording the checker recognises but does not test gives an "unchecked"
warning: negated claims ("not higher", "isn't the highest"), qualified superlatives ("one
of the highest", "the joint highest"), words on its unchecked list (*greater, exceeds,
outnumbers, beats, similar, increased, doubled, significantly*, "as high as", "up to",
...), unknown "-er than" and "the -est" forms, numbers written as words (a count before
the label, "the four states", is checked instead), a name excluded after a comparison
("but not Abuja"), and a clause that names two or more groups without a recognised claim,
unless every named group in it has its own number (a list of values). A number in a
clause naming no category is an error if it is in nobody's data, else a warning. Wording
it does not detect at all is not checked. It does not understand causal claims, time
trends, comparisons with a stated number ("more than 5 million"), differences given as
numbers ("3 points higher"), or claims about the total.
"""

from __future__ import annotations

import functools
import itertools
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from statistics import NormalDist
from types import ModuleType
from typing import Any

from disability_access_charts import _lang

UNITS = ("count", "percent", "number")
DEFAULT_INTERVAL_LABEL = "95% confidence interval"
RATIO_TOLERANCE = 0.05
TEST_Z = 1.96  # two-sided 5% test of a difference

_MARK0 = 0xE000  # private-use characters stand in for category and series names
_MARK = "[-]"
_MARK_RE = re.compile(_MARK)
_NUMBER = re.compile(r"(?:(?<![^\s(])-)?(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\d)")
_LEVEL = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:CI\b|C\.I\.|confidence|credible|uncertainty|interval)",
    re.IGNORECASE,
)
_APOSTROPHES = "'" + chr(0x2019)  # straight and curly


@dataclass(frozen=True)
class Series:
    """One series of values, one per category, with an optional interval."""

    name: str
    values: tuple[float, ...]
    lower: tuple[float, ...] | None = None
    upper: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        if self.lower is not None:
            object.__setattr__(self, "lower", tuple(self.lower))
        if self.upper is not None:
            object.__setattr__(self, "upper", tuple(self.upper))

    @property
    def has_interval(self) -> bool:
        return self.lower is not None and self.upper is not None


@dataclass(frozen=True)
class ChartData:
    """The data behind a chart, as the describer and the checker see it.

    ``shares`` means the categories are parts of one whole: "% of the total" figures are
    allowed, and interval comparisons between categories carry an independence warning.
    ``verbatim`` strings (title, source) are quoted in the alt-text and skipped by the
    checker. ``glossary`` maps a category or series name to the name written in the
    alt-text, for translations.
    """

    categories: tuple[str, ...]
    series: tuple[Series, ...]
    unit: str = "count"
    decimals: int = 0
    shares: bool = False
    verbatim: tuple[str, ...] = ()
    interval_label: str = DEFAULT_INTERVAL_LABEL
    category_label: str = "Category"
    glossary: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(self.categories))
        object.__setattr__(self, "series", tuple(self.series))
        object.__setattr__(self, "verbatim", tuple(self.verbatim))
        _validate(self)

    @property
    def has_interval(self) -> bool:
        return any(s.has_interval for s in self.series)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "categories": list(self.categories),
            "series": [
                {
                    "name": s.name,
                    "values": list(s.values),
                    "lower": None if s.lower is None else list(s.lower),
                    "upper": None if s.upper is None else list(s.upper),
                }
                for s in self.series
            ],
            "unit": self.unit,
            "decimals": self.decimals,
            "shares": self.shares,
            "verbatim": list(self.verbatim),
            "interval_label": self.interval_label,
            "category_label": self.category_label,
        }
        if self.glossary:
            out["glossary"] = dict(self.glossary)
        return out

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ChartData:
        return cls(
            categories=tuple(d["categories"]),
            series=tuple(
                Series(
                    s["name"],
                    tuple(s["values"]),
                    None if s.get("lower") is None else tuple(s["lower"]),
                    None if s.get("upper") is None else tuple(s["upper"]),
                )
                for s in d["series"]
            ),
            unit=d.get("unit", "count"),
            decimals=int(d.get("decimals", 0)),
            shares=bool(d.get("shares", False)),
            verbatim=tuple(d.get("verbatim", ())),
            interval_label=d.get("interval_label", DEFAULT_INTERVAL_LABEL),
            category_label=d.get("category_label", "Category"),
            glossary=dict(d.get("glossary", {})),
        )


def _finite(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _validate(data: ChartData) -> None:
    n = len(data.categories)
    if n == 0:
        raise ValueError("categories must not be empty")
    if len(set(data.categories)) != n:
        raise ValueError("category names must be unique")
    if not data.series:
        raise ValueError("there must be at least one series")
    names = [s.name for s in data.series]
    if len(set(names)) != len(names):
        raise ValueError("series names must be unique")
    if len(names) > 1 and set(names) & set(data.categories):
        raise ValueError("a series must not share its name with a category")
    if data.unit not in UNITS:
        raise ValueError(f"unit must be one of {UNITS}, got {data.unit!r}")
    if data.decimals < 0:
        raise ValueError("decimals must be 0 or more")
    for s in data.series:
        if len(s.values) != n:
            raise ValueError(f"series {s.name!r} has {len(s.values)} values for {n} categories")
        if not all(_finite(v) for v in s.values):
            raise ValueError(f"series {s.name!r}: values must be finite numbers")
        if (s.lower is None) != (s.upper is None):
            raise ValueError(f"series {s.name!r}: give both lower and upper, or neither")
        if s.lower is not None and s.upper is not None:
            if len(s.lower) != n or len(s.upper) != n:
                raise ValueError(f"series {s.name!r}: one lower and upper bound per category")
            for v, lo, hi in zip(s.values, s.lower, s.upper, strict=True):
                if not (_finite(lo) and _finite(hi)):
                    raise ValueError(f"series {s.name!r}: bounds must be finite numbers")
                if not lo <= v <= hi:
                    raise ValueError(f"series {s.name!r}: need lower <= value <= upper")
        if data.unit == "count" and any(v < 0 for v in s.values):
            raise ValueError("counts must be non-negative")
        if data.shares and sum(s.values) <= 0:
            raise ValueError("values must sum to a positive total")
    checked = [*data.categories, *data.glossary.values()]
    if len(names) > 1:
        checked += names
    for language in _lang.LANGUAGES.values():
        reserved = reserved_names(language)
        for name in checked:
            if " ".join(name.lower().split()) in reserved:
                raise ValueError(
                    language.MESSAGES["reserved_name"].format(name=name, example=f"{name} group")
                )


def _display(data: ChartData, lang: ModuleType, name: str) -> str:
    return data.glossary.get(name) or lang.GLOSSARY.get(name, name)


# --- Formatting (digits in every language) ---------------------------------------------


def format_number(value: float) -> str:
    """Thousands separators; integers stay integers."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return _no_minus_zero(f"{value:,.1f}")


def _no_minus_zero(text: str) -> str:
    """'-0', '-0.0' and '-0.00' (a tiny negative or -0.0, rounded) lose the minus."""
    return text[1:] if text.startswith("-") and not text.strip("-0.,") else text


def format_percent(value: float) -> str:
    return f"{value:.1f}"


def format_value(value: float, data: ChartData, *, suffix: bool = True) -> str:
    """A value as the alt-text and the table write it: counts as in P1, others to
    ``data.decimals`` places, percentages with a % sign."""
    if data.unit == "count":
        return format_number(value)
    text = _no_minus_zero(f"{value:,.{data.decimals}f}")
    return text + ("%" if suffix and data.unit == "percent" else "")


def shares_of(values: Sequence[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        raise ValueError("values must sum to a positive total")
    return [100 * v / total for v in values]


# --- The interval test -----------------------------------------------------------------


def _z_level(data: ChartData) -> float:
    match = _LEVEL.search(data.interval_label)
    level = float(match.group(1)) if match else 95.0
    if not 0 < level < 100 or level == 95:
        return TEST_Z  # the conventional 1.96 for a 95% interval
    return NormalDist().inv_cdf(0.5 + level / 200)


def _se(data: ChartData, s: Series, i: int) -> float | None:
    if s.lower is None or s.upper is None:
        return None
    v = s.values[i]
    half = max(v - s.lower[i], s.upper[i] - v)  # the larger half-width: conservative
    return half / _z_level(data)


def difference_test(
    data: ChartData, a: tuple[int, int], b: tuple[int, int]
) -> tuple[bool, float, float] | None:
    """Whether the interval test separates two estimates.

    ``a`` and ``b`` are (series index, category index). Returns (supported, abs
    difference, threshold), or None when either estimate has no interval.
    """
    sa, sb = data.series[a[0]], data.series[b[0]]
    se_a, se_b = _se(data, sa, a[1]), _se(data, sb, b[1])
    if se_a is None or se_b is None:
        return None
    diff = abs(sa.values[a[1]] - sb.values[b[1]])
    threshold = TEST_Z * math.sqrt(se_a**2 + se_b**2)
    return diff > threshold, diff, threshold


def _all_supported(data: ChartData, s: int, group: Iterable[int], other: Iterable[int]) -> bool:
    other = list(other)
    for i in group:
        for j in other:
            result = difference_test(data, (s, i), (s, j))
            if result is None:
                if data.series[s].values[i] == data.series[s].values[j]:
                    return False
            elif not result[0]:
                return False
    return True


# --- Describing -------------------------------------------------------------------------


def _groups(values: Sequence[float]) -> tuple[list[int], list[int], list[int], list[int]]:
    """Indices of the top group, the next below it, the bottom group, the next above it."""
    hi, lo = max(values), min(values)
    top = [i for i, v in enumerate(values) if v == hi]
    bottom = [i for i, v in enumerate(values) if v == lo]
    rest_top = [v for i, v in enumerate(values) if i not in top]
    rest_bottom = [v for i, v in enumerate(values) if i not in bottom]
    nxt = max(rest_top) if rest_top else hi
    prv = min(rest_bottom) if rest_bottom else lo
    next_top = [i for i, v in enumerate(values) if i not in top and v == nxt]
    next_bottom = [i for i, v in enumerate(values) if i not in bottom and v == prv]
    return top, next_top, bottom, next_bottom


class _Writer:
    def __init__(self, data: ChartData, lang: str) -> None:
        self.data = data
        self.lang = _lang.get(lang)
        self.t = self.lang.TEMPLATES

    def name(self, i: int) -> str:
        return _display(self.data, self.lang, self.data.categories[i])

    def series_name(self, s: int) -> str:
        return _display(self.data, self.lang, self.data.series[s].name)

    def clause(self, s: int, indices: Sequence[int], *, share: bool = False) -> str:
        series = self.data.series[s]
        i = indices[0]
        text = self.t["clause"].format(
            names=self.lang.join([self.name(j) for j in indices]),
            each=self.t["each"] if len(indices) > 1 else "",
            value=format_value(series.values[i], self.data),
        )
        if share:
            text += self.t["share"].format(share=format_percent(shares_of(series.values)[i]))
        return text

    def bound(self, value: float) -> str:
        return format_value(value, self.data)

    def interval_items(self, s: int, indices: Iterable[int]) -> str:
        series = self.data.series[s]
        assert series.lower is not None and series.upper is not None
        seen = sorted(set(indices))  # chart order
        return "; ".join(
            self.t["interval_item"].format(
                name=self.name(i),
                lower=self.bound(series.lower[i]),
                upper=self.bound(series.upper[i]),
            )
            for i in seen
        )

    def difference(self, s: int, group: Sequence[int], other: Sequence[int], which: str) -> str:
        can = _all_supported(self.data, s, group, other)
        return self.t["difference"].format(
            can=self.t["can"] if can else self.t["cannot"],
            which=self.t[which],
            clause=self.clause(s, other),
        )

    def single(self, kind: str, title: str, source: str, things: str) -> str:
        """One series: a bar chart, or a dot plot with one dot per category."""
        data, t = self.data, self.t
        series = data.series[0]
        values = series.values
        n = len(values)
        ci = series.has_interval
        counts = data.unit == "count"
        share = data.shares and counts
        label = self.lang.label(data.category_label)
        kind_text = t[f"kind_{kind}"]
        parts: list[str] = []
        if n == 1:
            clause = self.clause(0, [0], share=share)
            if ci:
                assert series.lower is not None and series.upper is not None
                clause += t["interval_inline"].format(
                    interval=data.interval_label,
                    lower=self.bound(series.lower[0]),
                    upper=self.bound(series.upper[0]),
                )
            parts.append(t[f"one_{kind}"].format(kind=kind_text, title=title, clause=clause))
        else:
            intro = f"intro_{things}" + ("_ci" if ci else "")
            parts.append(
                t[intro].format(
                    kind=kind_text, title=title, n=n, label=label, interval=data.interval_label
                )
            )
            top, next_top, bottom, next_bottom = _groups(values)
            if len(top) == n:
                value = format_value(values[0], data)
                if share:
                    value += t["share"].format(share=format_percent(100 / n))
                parts.append(
                    t["all_equal"].format(
                        n=n, things=t["things_estimates" if ci else f"things_{things}"], value=value
                    )
                )
                if ci:
                    parts.append(
                        t["intervals"].format(
                            interval=data.interval_label, items=self.interval_items(0, range(n))
                        )
                    )
            elif not ci:
                high, low = ("largest", "smallest") if counts else ("highest", "lowest")
                parts.append(t[high].format(clause=self.clause(0, top, share=share)))
                parts.append(t[low].format(clause=self.clause(0, bottom, share=share)))
            else:
                two = len(set(values)) == 2 and len(top) + len(bottom) == n
                parts.append(
                    t["highest_ci"].format(
                        clause=self.clause(0, top, share=share),
                        difference=self.difference(0, top, next_top, "other" if two else "next"),
                    )
                )
                mentioned = [*top, *next_top]
                if not two:
                    parts.append(
                        t["lowest_ci"].format(
                            clause=self.clause(0, bottom, share=share),
                            difference=self.difference(0, bottom, next_bottom, "next"),
                        )
                    )
                    mentioned += [*bottom, *next_bottom]
                parts.append(
                    t["intervals"].format(
                        interval=data.interval_label, items=self.interval_items(0, mentioned)
                    )
                )
        if counts and data.shares:
            parts.append(t["total"].format(total=format_number(sum(values))))
        parts.append(t["source"].format(source=source))
        return " ".join(parts)

    def multi(self, title: str, source: str) -> str:
        """Several series: a dot plot with one row per category."""
        data, t = self.data, self.t
        n = len(data.categories)
        ci = data.has_interval
        label = self.lang.label(data.category_label)
        names = self.lang.join([self.series_name(s) for s in range(len(data.series))])
        common = {
            "kind": t["kind_dot"],
            "title": title,
            "n": n,
            "label": label,
            "k": len(data.series),
            "names": names,
            "interval": data.interval_label,
            "name": self.name(0),
        }
        if n == 1:
            parts = [t["intro_series_one"].format(**common)]
        else:
            parts = [t["intro_series_ci" if ci else "intro_series"].format(**common)]
        for s, series in enumerate(data.series):
            sname = self.series_name(s)
            values = series.values
            has = series.has_interval
            if n == 1:
                clause = self.clause(s, [0])
                if has:
                    assert series.lower is not None and series.upper is not None
                    clause += t["interval_inline"].format(
                        interval=data.interval_label,
                        lower=self.bound(series.lower[0]),
                        upper=self.bound(series.upper[0]),
                    )
                parts.append(t["series_value"].format(series=sname, clause=clause))
                continue
            top, next_top, bottom, next_bottom = _groups(values)
            if len(top) == n:
                things = t["things_estimates" if has else "things_dots"]
                parts.append(
                    t["series_all_equal"].format(
                        series=sname, n=n, things=things, value=format_value(values[0], data)
                    )
                )
                mentioned: list[int] = list(range(n))
            elif not has:
                parts.append(
                    t["series_extremes"].format(
                        series=sname, high=self.clause(s, top), low=self.clause(s, bottom)
                    )
                )
                mentioned = []
            else:
                two = len(set(values)) == 2 and len(top) + len(bottom) == n
                if two:
                    parts.append(
                        t["series_highest_ci"].format(
                            series=sname,
                            high=self.clause(s, top),
                            high_difference=self.difference(s, top, next_top, "other"),
                        )
                    )
                    mentioned = [*top, *next_top]
                else:
                    parts.append(
                        t["series_extremes_ci"].format(
                            series=sname,
                            high=self.clause(s, top),
                            high_difference=self.difference(s, top, next_top, "next"),
                            low=self.clause(s, bottom),
                            low_difference=self.difference(s, bottom, next_bottom, "next"),
                        )
                    )
                    mentioned = [*top, *next_top, *bottom, *next_bottom]
            if has and mentioned:
                parts.append(
                    t["series_intervals"].format(
                        series=sname,
                        interval=data.interval_label,
                        items=self.interval_items(s, mentioned),
                    )
                )
        parts.append(t["source"].format(source=source))
        return " ".join(parts)


def describe(
    data: ChartData, *, chart_type: str = "bar", title: str, source: str, lang: str = "en"
) -> str:
    """Alt-text for a chart, built only from ``data``, in ``lang`` (only "en" ships).

    Summary first, detail second (as screen-reader users asked for in a preliminary
    interview study, Sharif et al., ASSETS 2023): the extremes, then (with intervals)
    whether the survey can show a difference from the next estimate, then the intervals
    themselves. With
    intervals, superlatives are hedged ("highest estimate"). The text passes
    :func:`check_alt_text` by construction, and the tests hold it to that.
    """
    writer = _Writer(data, lang)
    if chart_type == "bar":
        if len(data.series) != 1:
            raise ValueError("a bar chart has exactly one series")
        return writer.single("bar", title, source, "bars")
    if chart_type == "dot":
        if len(data.series) == 1:
            return writer.single("dot", title, source, "dots")
        return writer.multi(title, source)
    raise ValueError(f"unknown chart type {chart_type!r}; expected 'bar' or 'dot'")


def describe_bar(data: ChartData, *, title: str, source: str, lang: str = "en") -> str:
    return describe(data, chart_type="bar", title=title, source=source, lang=lang)


def describe_dot(data: ChartData, *, title: str, source: str, lang: str = "en") -> str:
    return describe(data, chart_type="dot", title=title, source=source, lang=lang)


# --- Checking ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Problem:
    """One thing the checker found in an alt-text.

    ``number`` is the number as written (None for claim problems), ``clause`` the clause it
    was found in, ``kind`` what was checked ("number", "extreme", "comparison", "ratio",
    "rank", "equality", "no-difference", "difference", "independence" or "unchecked"),
    ``severity`` "error" or "warning", and ``suggestion`` a wording that would pass.
    """

    number: str | None
    clause: str
    reason: str
    kind: str = "number"
    severity: str = "error"
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "clause": self.clause,
            "reason": self.reason,
            "kind": self.kind,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


def errors(problems: Iterable[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]


def warnings(problems: Iterable[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "warning"]


@dataclass(frozen=True)
class _Mark:
    kind: str  # "c" category, "s" series
    index: int
    text: str  # as written in the alt-text


def _words(words: Iterable[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


def _regex_words(patterns: Iterable[str]) -> set[str]:
    """The plain words inside a list of regex fragments (r"\\bfar\\s+from\\b" -> far, from)."""
    out: set[str] = set()
    for p in patterns:
        out |= set(re.findall(r"[a-z]+", re.sub(r"\\[a-zA-Z]", " ", p).lower()))
    return out


@functools.cache
def _template_words(lang: ModuleType) -> frozenset[str]:
    """Lower-case words the templates and the claim vocabulary use (matched exact-case)."""
    text = " ".join(re.sub(r"\{\w+\}", " ", t) for t in lang.TEMPLATES.values())
    words = set(re.findall(r"[a-z]+", text.lower())) | set(reserved_names(lang))
    return frozenset(words)


@functools.cache
def reserved_names(lang: ModuleType) -> frozenset[str]:
    """Names a category or series may not have in ``lang``.

    They are the claim checker's vocabulary (superlatives, comparatives, ratio, rank,
    negation and qualifier words, spelled numbers, the unchecked-word list and phrases such
    as "the same") and the words the templates write with a capital letter ("Highest",
    "Total", "Source"). A category with such a name could not be told apart from the word.
    """
    words: set[str] = set()
    for group in (
        lang.MAX_WORDS,
        lang.MIN_WORDS,
        lang.MAX_WORDS_AFTER_THE,
        lang.MIN_WORDS_AFTER_THE,
        lang.HEDGES,
        lang.UP_WORDS,
        lang.DOWN_WORDS,
        lang.DOWN_VERBS,
        lang.UNCHECKED,
        lang.SPELLED_NUMBERS,
        lang.CANNOT,
        tuple(lang.RATIO_WORDS),
        tuple(lang.NUMBER_WORDS),
        tuple(lang.ORDINAL_WORDS),
        tuple(lang.RANK_NUMBER_WORDS),
        lang.RESERVED_PHRASES,
        (lang.THAN, lang.BETWEEN, lang.FROM, lang.TIMES, "can"),
    ):
        words |= {w.lower() for w in group}
    words |= _regex_words(lang.NEGATORS) | _regex_words(lang.QUALIFIERS)
    words |= _regex_words(lang.CONTRASTS) | {lang.LABEL_STANDIN}
    capitals = " ".join(re.sub(r"\{\w+\}", " ", t) for t in lang.TEMPLATES.values())
    words |= {w.lower() for w in re.findall(r"\b[A-Z][a-z]+\b", capitals)}
    return frozenset(words)


class _Checker:
    def __init__(self, text: str, data: ChartData, lang: str) -> None:
        self.data = data
        self.lang = _lang.get(lang)
        lang_ = self.lang
        self.problems: list[Problem] = []
        self.has_ci = data.has_interval
        self.marks: list[_Mark] = []
        self.skel = self._skeleton(text)
        self.consumed_numbers: set[int] = set()
        self.recognised = 0
        flags = re.IGNORECASE
        self.re_breaks = [re.compile(p, flags) for p in lang_.BREAKS]
        self.re_strong = [re.compile(p, flags) for p in lang_.STRONG_BREAKS]
        extremes = _words(
            (
                *lang_.MAX_WORDS,
                *lang_.MIN_WORDS,
                *lang_.MAX_WORDS_AFTER_THE,
                *lang_.MIN_WORDS_AFTER_THE,
            )
        )
        verbs = _words(lang_.AND_SPLIT_VERBS)
        self.re_and_split = re.compile(
            # "and" or "," before a new subject: "and Ibadan has", ", Lagos the second"
            r"(?:\band\b|,)(?=\s+(?:the\s+)?"
            + _MARK
            + r"\s+(?:"
            + verbs
            + r"|the|"
            + extremes
            + r")\b)"
            # "and" before a second superlative: "... and the lowest is Ibadan"
            + r"|\band\b(?=\s+(?:the\s+)?(?:"
            + extremes
            + r")\b)"
            # "and" before an elided subject: "... and is the highest"
            + r"|\band\b(?="
            + lang_.ELLIPSIS
            + r")",
            flags,
        )
        self.re_neg = re.compile("|".join(lang_.NEGATORS), flags)
        self.re_qual = re.compile("|".join(lang_.QUALIFIERS), flags)
        self.re_contrast = re.compile("|".join(lang_.CONTRASTS), flags)
        self.re_ratio_qual = re.compile(r"(?:" + "|".join(lang_.RATIO_QUALIFIERS) + r")\s*$", flags)
        self.re_excluded = re.compile(
            r"(?:" + "|".join(lang_.EXCLUDERS) + r")\s+(?:the\s+)?$", flags
        )
        self.re_list_sep = re.compile(lang_.LIST_SEPARATOR, flags)
        self.re_connector = re.compile(lang_.CONNECTOR, flags)
        self.re_ellipsis = re.compile(lang_.ELLIPSIS, flags)
        self.re_not_name = re.compile(r"(?:\bbut\s+)?\bnot\s+(?:the\s+)?" + _MARK, flags)
        self.re_link = re.compile(lang_.LINK_AFTER_NAME, flags)
        self.re_in_name = re.compile(lang_.IN_NAME + r"(" + _MARK + r")", flags)
        self.re_range = re.compile(lang_.RANGE_JOIN, flags)
        self.re_joiner = re.compile(lang_.LIST_JOINERS, flags)

    # Building the skeleton: verbatim strings removed, names replaced by one marker each.
    def _skeleton(self, text: str) -> str:
        data, lang = self.data, self.lang
        quoted = [(f, 0) for f in data.verbatim] + [(data.interval_label, re.IGNORECASE)]
        for fixed, flags in sorted(quoted, key=lambda x: len(x[0]), reverse=True):
            if fixed:
                pattern = r"(?<!\w)" + re.escape(fixed) + r"(?!\w)"
                text = re.sub(pattern, " ", text, flags=flags)
        names: list[tuple[str, str, int]] = [
            (_display(data, lang, c), "c", i) for i, c in enumerate(data.categories)
        ]
        if len(data.series) > 1:
            names += [(_display(data, lang, s.name), "s", j) for j, s in enumerate(data.series)]
        names.sort(key=lambda x: len(x[0]), reverse=True)
        template = _template_words(lang)
        taken: list[tuple[int, int, str, int]] = []
        for name, kind, index in names:
            # Names are matched in any case, except names that are also template words
            # ("Other", "A"): those only in their exact case.
            flags = 0 if name.lower() in template else re.IGNORECASE
            pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", flags)
            for m in pattern.finditer(text):
                if all(m.end() <= a or m.start() >= b for a, b, _, _ in taken):
                    taken.append((m.start(), m.end(), kind, index))
        taken.sort()
        out: list[str] = []
        pos = 0
        for a, b, kind, index in taken:
            out.append(text[pos:a])
            out.append(chr(_MARK0 + len(self.marks)))
            self.marks.append(_Mark(kind, index, text[a:b]))
            pos = b
        out.append(text[pos:])
        skel = "".join(out)
        label = data.category_label.strip()
        if label:
            pattern = r"(?<!\w)" + re.escape(label) + r"(?!\w)"
            skel = re.sub(pattern, lang.LABEL_STANDIN, skel, flags=re.IGNORECASE)
        return skel

    def unmask(self, a: int, b: int) -> str:
        text = _MARK_RE.sub(lambda m: self.marks[ord(m.group()) - _MARK0].text, self.skel[a:b])
        return " ".join(text.split())

    def marks_in(self, a: int, b: int, kind: str | None = None) -> list[tuple[int, _Mark]]:
        out = []
        for m in _MARK_RE.finditer(self.skel, a, b):
            mark = self.marks[ord(m.group()) - _MARK0]
            if kind is None or mark.kind == kind:
                out.append((m.start(), mark))
        return out

    def side(self, a: int, b: int, kind: str) -> list[_Mark]:
        out: list[_Mark] = []
        for _, mark in self.marks_in(a, b, kind):
            if mark.index not in [m.index for m in out]:
                out.append(mark)
        return out

    def add(self, clause: tuple[int, int], reason: str, kind: str, **kw: Any) -> None:
        problem = Problem(
            number=kw.pop("number", None),
            clause=self.unmask(*clause),
            reason=reason,
            kind=kind,
            severity=kw.pop("severity", "error"),
            suggestion=kw.pop("suggestion", None),
        )
        if problem not in self.problems:
            self.problems.append(problem)

    def msg(self, key: str, **kw: Any) -> str:
        return self.lang.MESSAGES[key].format(**kw)

    def warn_unchecked(self, clause: tuple[int, int], key: str, **kw: Any) -> None:
        self.add(clause, self.msg(key, **kw), "unchecked", severity="warning")

    # Sentences, clauses and the parts of a clause.
    def clauses(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        bounds = [0, *(m.end() for m in re.finditer(r"[.!?](?=\s)", self.skel)), len(self.skel)]
        out = []
        for a, b in itertools.pairwise(bounds):
            start = a
            for m in re.finditer(";", self.skel[a:b]):
                out.append(((a, b), (start, a + m.start())))
                start = a + m.end()
            out.append(((a, b), (start, b)))
        return [(s, c) for s, c in out if self.skel[c[0] : c[1]].strip()]

    def segment(
        self, pos: int, clause: tuple[int, int], *, strong: bool = False
    ) -> tuple[int, int]:
        """The part of the clause around ``pos``, between break words."""
        patterns = self.re_strong if strong else [*self.re_breaks, self.re_and_split]
        a, b = clause
        for p in patterns:
            for m in p.finditer(self.skel, clause[0], clause[1]):
                if m.end() <= pos:
                    a = max(a, m.end())
                elif m.start() >= pos:
                    b = min(b, m.start())
        return a, b

    def negator(self, pos: int, clause: tuple[int, int]) -> str | None:
        a, _ = self.segment(pos, clause)
        found = None
        for m in self.re_neg.finditer(self.skel, a, pos):
            found = m.group()
        return found

    def contrast(self, pos: int, clause: tuple[int, int]) -> str | None:
        """A contrast marker earlier in the clause ("Kano, rather than Lagos, ...")."""
        m = self.re_contrast.search(self.skel, clause[0], pos)
        return m.group() if m else None

    def qualifier(self, pos: int, clause: tuple[int, int]) -> str | None:
        a, _ = self.segment(pos, clause)
        m = self.re_qual.search(self.skel, max(a, pos - 25), pos)
        return m.group() if m else None

    def chain_before(self, start: int, end: int, kind: str) -> list[_Mark]:
        """The list of names ending nearest ``end``: "Kano, Abuja and Lagos are ..."."""
        marks = self.marks_in(start, end, kind)
        if not marks:
            return []
        chain = [marks[-1]]
        seps: list[str] = []
        for pos, mark in reversed(marks[:-1]):
            between = self.skel[pos + 1 : chain[0][0]]
            if not self.re_list_sep.fullmatch(between):
                break
            chain.insert(0, (pos, mark))
            seps.insert(0, between)
        if len(chain) > 1 and not self.re_joiner.search(seps[-1]):
            chain = chain[-1:]
        return self._unique(chain)

    def chain_after(self, start: int, end: int, kind: str) -> list[tuple[int, _Mark]]:
        """The list of names starting nearest ``start``: "... than Lagos and Abuja"."""
        marks = self.marks_in(start, end, kind)
        if not marks:
            return []
        chain = [marks[0]]
        seps: list[str] = []
        for pos, mark in marks[1:]:
            between = self.skel[chain[-1][0] + 1 : pos]
            if not self.re_list_sep.fullmatch(between):
                break
            chain.append((pos, mark))
            seps.append(between)
        if len(chain) > 1 and not self.re_joiner.search(seps[-1]):
            chain = chain[:1]
        return chain

    @staticmethod
    def _unique(chain: Iterable[tuple[int, _Mark]]) -> list[_Mark]:
        out: list[_Mark] = []
        for _, mark in chain:
            if mark.index not in [m.index for m in out]:
                out.append(mark)
        return out

    def name(self, kind: str, index: int) -> str:
        if kind == "c":
            return _display(self.data, self.lang, self.data.categories[index])
        return _display(self.data, self.lang, self.data.series[index].name)

    def fmt(self, value: float) -> str:
        return format_value(value, self.data)

    # Which series (or category) a claim is about, when it is not one of the compared names.
    def context(self, kind: str, clause: tuple[int, int], sentence: tuple[int, int]) -> int | None:
        total = len(self.data.series) if kind == "s" else len(self.data.categories)
        for a, b in (clause, sentence):
            found = {m.index for _, m in self.marks_in(a, b, kind)}
            if len(found) == 1:
                return found.pop()
            if len(found) > 1:
                return None
        return 0 if total == 1 else None

    def pair(
        self, left: _Mark, right: _Mark, clause: tuple[int, int], sentence: tuple[int, int]
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """(series, category) for both sides of a comparison, or None if unresolved."""
        if left.kind == "c":
            s = self.context("s", clause, sentence)
            return None if s is None else ((s, left.index), (s, right.index))
        c = self.context("c", clause, sentence)
        return None if c is None else ((left.index, c), (right.index, c))

    def value(self, ref: tuple[int, int]) -> float:
        return self.data.series[ref[0]].values[ref[1]]

    def independence(self, clause: tuple[int, int], kind: str) -> None:
        if kind == "s":
            why = self.msg("why_series")
        elif self.data.shares:
            why = self.msg("why_shares")
        else:
            return
        self.add(clause, self.msg("independence", why=why), "independence", severity="warning")

    # The checks.
    def run(self) -> list[Problem]:
        for sentence, clause in self.clauses():
            consumed: list[tuple[int, int]] = []
            problems, recognised = len(self.problems), self.recognised
            self.no_difference(clause, consumed)
            self.differences(clause, sentence, consumed)
            self.ratios(clause, sentence, consumed)
            self.ranks(clause, sentence, consumed)
            self.equalities(clause, sentence, consumed)
            self.comparisons(clause, sentence, consumed)
            self.extremes(clause, sentence, consumed)
            self.unchecked(clause, consumed)
            self.respectively(clause, sentence)
            if len(self.problems) == problems and self.recognised == recognised:
                self.relation(clause)
            self.numbers(clause, sentence)
        return self.problems

    def finditer(self, pattern: str, clause: tuple[int, int]) -> Iterable[re.Match[str]]:
        return re.compile(pattern, re.IGNORECASE).finditer(self.skel, clause[0], clause[1])

    @staticmethod
    def inside(pos: int, consumed: list[tuple[int, int]]) -> bool:
        return any(a <= pos < b for a, b in consumed)

    def no_difference(self, clause: tuple[int, int], consumed: list[tuple[int, int]]) -> None:
        for pattern in self.lang.NO_DIFFERENCE:
            for m in self.finditer(pattern, clause):
                consumed.append(m.span())
                self.recognised += 1
                if self.has_ci:
                    suggestion = self.msg("suggest_cannot")
                else:
                    marks = self.marks_in(*clause)
                    suggestion = (
                        self.msg("suggest_same", left=marks[0][1].text, right=marks[1][1].text)
                        if len(marks) >= 2
                        else None
                    )
                self.add(clause, self.msg("no_difference"), "no-difference", suggestion=suggestion)

    def break_after(self, pos: int, clause: tuple[int, int]) -> int:
        return self.segment(pos, clause)[1]

    def differences(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        for m in self.finditer(lang.DIFFERENCE, clause):
            self.recognised += 1
            modal = " ".join(m.group("modal").lower().split())
            cannot = modal in lang.CANNOT
            rest = self.skel[m.end() : clause[1]]
            lead = re.match(r"\s+(" + lang.BETWEEN + "|" + lang.FROM + r")\b", rest, re.I)
            left: list[_Mark] = []
            right: list[_Mark] = []
            end = m.end()
            if lead and lead.group(1).lower() == lang.BETWEEN:
                start = m.end() + lead.end()
                end = self.break_after(start, clause)
                after = self.marks_in(start, end)
                if len(after) >= 2:
                    kind = after[0][1].kind
                    both = self.side(start, end, kind)
                    left, right = both[:1], both[1:2]
            elif lead:
                start = m.end() + lead.end()
                end = self.break_after(start, clause)
                after = self.marks_in(start, end)
                if after:
                    kind = after[0][1].kind
                    right = self.side(start, end, kind)
                    left = self.side(clause[0], m.start(), kind)
            else:
                before = self.marks_in(clause[0], m.start())
                if before:
                    kind = before[-1][1].kind
                    both = self.side(clause[0], m.start(), kind)
                    if len(both) == 2:
                        left, right = both[:1], both[1:]
            consumed.append((m.start(), end))
            if not left or not right:
                self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
                continue
            refs = [self.pair(lm, rm, clause, sentence) for lm in left for rm in right]
            if any(r is None for r in refs):
                self.warn_unchecked(clause, "unchecked_series", word=m.group())
                continue
            supported = True
            for ref in refs:
                assert ref is not None
                result = difference_test(self.data, ref[0], ref[1])
                if result is None:
                    supported = supported and self.value(ref[0]) != self.value(ref[1])
                else:
                    supported = supported and result[0]
            kind = left[0].kind
            names_l = lang.join([self.name(kind, x.index) for x in left])
            names_r = lang.join([self.name(kind, x.index) for x in right])
            if cannot and supported:
                self.add(
                    clause, self.msg("cannot_wrong", left=names_l, right=names_r), "difference"
                )
            elif not cannot and not supported:
                self.add(clause, self.msg("can_wrong", left=names_l, right=names_r), "difference")
            if self.has_ci:
                self.independence(clause, kind)

    def check_pairs(
        self,
        left: Sequence[_Mark],
        right: Sequence[_Mark],
        up: bool,
        word: str,
        clause: tuple[int, int],
        sentence: tuple[int, int],
    ) -> None:
        """Check "every name on the left is higher (or lower) than every name on the right"."""
        tested = False
        compared = False
        for lm in left:
            for rm in right:
                if lm.index == rm.index:
                    continue
                compared = True
                ref = self.pair(lm, rm, clause, sentence)
                if ref is None:
                    self.warn_unchecked(clause, "unchecked_series", word=word)
                    return
                a, b = self.value(ref[0]), self.value(ref[1])
                if not (a > b if up else a < b):
                    self.add(
                        clause,
                        self.msg(
                            "not_comparative",
                            left=lm.text,
                            right=rm.text,
                            word=word,
                            a=self.fmt(a),
                            b=self.fmt(b),
                        ),
                        "comparison",
                    )
                    continue
                result = difference_test(self.data, ref[0], ref[1])
                if result is None:
                    continue
                tested = True
                if not result[0]:
                    self.add(
                        clause,
                        self.msg(
                            "comparative_unsupported",
                            left=lm.text,
                            right=rm.text,
                            word=word,
                            diff=f"{result[1]:.{self.data.decimals + 1}f}",
                            threshold=f"{result[2]:.{self.data.decimals + 1}f}",
                        ),
                        "comparison",
                        suggestion=self.msg("suggest_cannot"),
                    )
        if not compared:
            self.warn_unchecked(clause, "unchecked_unresolved", word=word)
        elif tested and left:
            self.independence(clause, left[0].kind)

    def comparisons(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        pattern = (
            r"\b(?:(?P<w>"
            + _words((*lang.UP_WORDS, *lang.DOWN_WORDS))
            + r")|(?P<v>"
            + _words(lang.DOWN_VERBS)
            + r"))\b"
        )
        than = re.compile(r"\b" + lang.THAN + r"\b", re.IGNORECASE)
        # The previous comparison in the clause: its left-hand names and where its right-hand
        # names end. "Lagos is lower than Kano and higher than Abuja" reuses Lagos.
        previous: tuple[list[_Mark], int] | None = None
        for m in self.finditer(pattern, clause):
            if self.inside(m.start(), consumed):
                continue
            self.recognised += 1
            verb = m.group("v") is not None
            word = (m.group("w") or m.group("v")).lower()
            up = not verb and word in lang.UP_WORDS
            negator = self.negator(m.start(), clause) or self.contrast(m.start(), clause)
            if verb:
                right_start, left_limit = m.end(), m.start()
            else:
                _, limit = self.segment(m.end(), clause, strong=True)
                t = than.search(self.skel, m.end(), min(limit, m.end() + 80))
                if t is None:
                    consumed.append(m.span())
                    key = "negated" if negator else "unchecked_unresolved"
                    self.warn_unchecked(clause, key, negator=negator, word=m.group())
                    previous = None
                    continue
                right_start, left_limit = t.end(), t.start()
            _, seg_end = self.segment(right_start, clause)
            after = self.marks_in(right_start, seg_end)
            if negator:
                consumed.append((m.start(), after[0][0] + 1 if after else right_start))
                self.warn_unchecked(clause, "negated", negator=negator, word=m.group())
                previous = None
                continue
            gap = self.skel[right_start : after[0][0]] if after else ""
            if (
                not after
                or not re.fullmatch(r"[\s\w" + _APOSTROPHES + "]*", gap)
                or re.search(r"\d", gap)
            ):
                consumed.append((m.start(), right_start))
                key = "unchecked_unresolved" if verb else "unchecked_than"
                self.warn_unchecked(clause, key, word=m.group())
                previous = None
                continue
            kind = after[0][1].kind
            right_chain = self.chain_after(right_start, seg_end, kind)
            right_end = right_chain[-1][0] + 1
            consumed.append((m.start(), right_end))
            left = self.comparison_subject(m.start(), left_limit, kind, clause, previous)
            if not left:
                self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
                previous = None
                continue
            previous = (left, right_end)
            self.excluded_after(right_end, clause, consumed, m.group())
            self.check_pairs(
                left,
                self._unique(right_chain),
                up,
                lang.DOWN_WORDS[0] if verb else word,
                clause,
                sentence,
            )

    def comparison_subject(
        self,
        pos: int,
        limit: int,
        kind: str,
        clause: tuple[int, int],
        previous: tuple[list[_Mark], int] | None,
    ) -> list[_Mark]:
        """The names a comparison at ``pos`` is about (before ``limit``, its "than")."""
        seg_start, _ = self.segment(pos, clause)
        if previous is not None:
            prev_left, prev_end = previous
            if not self.marks_in(prev_end, pos):
                # No new name since the last comparison. Reuse its subject only when the
                # new part starts with the comparator ("and higher", "but it is higher").
                if self.re_connector.fullmatch(self.skel[prev_end:pos]):
                    return prev_left if prev_left[0].kind == kind else []
                return self.chain_before(pos, limit, kind)
            seg_start = max(seg_start, prev_end)
        left = self.chain_before(seg_start, limit, kind)
        if left:
            return left
        if self.re_ellipsis.match(self.skel, seg_start):
            return self.clause_subject(clause, pos, kind)
        return []

    def clause_subject(self, clause: tuple[int, int], pos: int, kind: str) -> list[_Mark]:
        """The first names in the clause, for "Kano is higher than Lagos and is the highest"."""
        return self._unique(self.chain_after(clause[0], pos, kind))

    def excluded_after(
        self, end: int, clause: tuple[int, int], consumed: list[tuple[int, int]], word: str
    ) -> None:
        """'Kano is higher than Lagos but not Abuja': the excluded name is not checked."""
        m = self.re_not_name.search(self.skel, end, clause[1])
        if m and not self.inside(m.start(), consumed):
            consumed.append(m.span())
            self.warn_unchecked(clause, "negated", negator=self.unmask(*m.span()), word=word)

    def ratios(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        number_words = _words(lang.NUMBER_WORDS)
        pattern = (
            r"\b(?P<word>" + _words(lang.RATIO_WORDS) + r")\b"
            r"|(?<![\w.,])(?P<n>\d+(?:\.\d+)?|" + number_words + r")\s+" + lang.TIMES + r"\b"
        )
        for m in self.finditer(pattern, clause):
            if self.inside(m.start(), consumed):
                continue
            self.recognised += 1
            if m.group("word"):
                claimed = lang.RATIO_WORDS[m.group("word").lower()]
            else:
                token = m.group("n").lower()
                claimed = float(lang.NUMBER_WORDS.get(token, 0) or token)
                if token[0].isdigit():
                    self.consumed_numbers.add(m.start("n"))
            seg_start, _ = self.segment(m.start(), clause, strong=True)
            _, end = self.segment(m.end(), clause, strong=True)
            after = self.marks_in(m.end(), end)
            negator = self.negator(m.start(), clause)
            qualifier = self.re_ratio_qual.search(self.skel, seg_start, m.start())
            if negator or qualifier or not after:
                consumed.append((m.start(), after[0][0] + 1 if after else m.end()))
                if qualifier and not negator:
                    self.warn_unchecked(
                        clause, "qualified", qualifier=qualifier.group().strip(), word=m.group()
                    )
                else:
                    key = "negated" if negator else "unchecked_unresolved"
                    self.warn_unchecked(clause, key, negator=negator, word=m.group())
                continue
            kind = after[0][1].kind
            right_chain = self.chain_after(m.end(), end, kind)
            consumed.append((m.start(), right_chain[-1][0] + 1))
            left = self.chain_before(seg_start, m.start(), kind)
            if not left:
                self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
                continue
            pairs = [(lm, rm) for lm in left for rm in self._unique(right_chain)]
            pairs = [(lm, rm) for lm, rm in pairs if lm.index != rm.index]
            if not pairs:
                self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
            for lm, rm in pairs:
                self.check_ratio(lm, rm, claimed, clause, sentence, m.group())

    def check_ratio(
        self,
        left: _Mark,
        right: _Mark,
        claimed: float,
        clause: tuple[int, int],
        sentence: tuple[int, int],
        word: str,
    ) -> None:
        ref = self.pair(left, right, clause, sentence)
        if ref is None:
            self.warn_unchecked(clause, "unchecked_series", word=word)
            return
        a, b = self.value(ref[0]), self.value(ref[1])
        if a < 0 or b < 0:
            self.add(clause, self.msg("ratio_negative"), "ratio", severity="warning")
        names = {"left": left.text, "right": right.text}
        if b == 0 or abs((a / b) / claimed - 1) > RATIO_TOLERANCE:
            actual = "infinite" if b == 0 else f"{a / b:.2f}"
            self.add(
                clause,
                self.msg("ratio_wrong", actual=actual, claimed=f"{claimed:g}", **names),
                "ratio",
            )
            return
        result = difference_test(self.data, ref[0], ref[1])
        if result is not None:
            if claimed != 1 and not result[0]:
                self.add(
                    clause,
                    self.msg("ratio_unsupported", **names),
                    "ratio",
                    suggestion=self.msg("suggest_cannot"),
                )
            self.independence(clause, left.kind)

    def rank_of(self, s: int, i: int, ascending: bool) -> int:
        values = self.data.series[s].values
        v = values[i]
        return 1 + sum(1 for x in values if (x < v if ascending else x > v))

    def _rank_number(self, token: str) -> int | None:
        token = token.lower()
        digits = re.match(r"\d+", token)
        if digits:
            return int(digits.group())
        return self.lang.ORDINAL_WORDS.get(token) or self.lang.RANK_NUMBER_WORDS.get(token)

    def ranks(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        for pattern in lang.RANK_PATTERNS:
            for m in self.finditer(pattern, clause):
                if self.inside(m.start(), consumed) or self.inside(m.start("rank"), consumed):
                    continue
                consumed.append(m.span())
                self.recognised += 1
                if m.group("rank")[0].isdigit():
                    self.consumed_numbers.add(m.start("rank"))
                if m.group("of"):
                    self.consumed_numbers.add(m.start("of"))
                negator = self.negator(m.start(), clause)
                if negator:
                    self.warn_unchecked(clause, "negated", negator=negator, word=m.group())
                    continue
                qualifier = self.qualifier(m.start(), clause)
                if qualifier:
                    self.warn_unchecked(clause, "qualified", qualifier=qualifier, word=m.group())
                    continue
                seg_start, seg_end = self.segment(m.start(), clause)
                before = self.marks_in(seg_start, m.start(), "c")
                after = self.marks_in(m.end(), seg_end, "c")
                elided = self.re_ellipsis.match(self.skel, seg_start)
                if before:
                    mark = before[-1][1]
                elif elided and self.clause_subject(clause, m.start(), "c"):
                    mark = self.clause_subject(clause, m.start(), "c")[0]
                elif after:
                    mark = after[0][1]
                else:
                    self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
                    continue
                s = self.context("s", clause, sentence)
                claimed = self._rank_number(m.group("rank"))
                if s is None or claimed is None:
                    self.warn_unchecked(clause, "unchecked_series", word=m.group())
                    continue
                direction = (m.group("dir") or "").lower()
                ascending = direction in lang.ASCENDING_WORDS
                actual = self.rank_of(s, mark.index, ascending)
                if actual != claimed:
                    self.add(
                        clause,
                        self.msg("rank_wrong", name=mark.text, actual=actual, claimed=claimed),
                        "rank",
                    )
                n = len(self.data.categories)
                if m.group("of") and int(m.group("of")) != n:
                    self.add(
                        clause,
                        self.msg("rank_count_wrong", actual=n, claimed=m.group("of")),
                        "rank",
                    )
                if actual == claimed and self.data.series[s].has_interval:
                    values = self.data.series[s].values
                    order = sorted(range(n), key=lambda j: values[j], reverse=not ascending)
                    pos = order.index(mark.index)
                    for j in (pos - 1, pos + 1):
                        if 0 <= j < n:
                            result = difference_test(self.data, (s, mark.index), (s, order[j]))
                            if result is not None and not result[0]:
                                self.add(
                                    clause,
                                    self.msg(
                                        "rank_unsupported",
                                        name=mark.text,
                                        neighbour=self.name("c", order[j]),
                                    ),
                                    "rank",
                                    severity="warning",
                                )
                                break
                    self.independence(clause, "c")

    def equalities(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        found: list[tuple[re.Match[str], _Mark | None, _Mark | None]] = []
        for pattern in lang.EQUALITY_BINARY:
            for m in self.finditer(r"\b" + pattern + r"\b", clause):
                if self.inside(m.start(), consumed):
                    continue
                before = self.marks_in(clause[0], m.start())
                after = self.marks_in(m.end(), clause[1])
                right = after[0][1] if after else None
                left = None
                if right is not None:
                    same = [mk for _, mk in before if mk.kind == right.kind]
                    left = same[-1] if same else None
                end = after[0][0] + 1 if after else m.end()
                consumed.append((m.start(), end))
                found.append((m, left, right))
        for pattern in lang.EQUALITY_PAIR:
            for m in self.finditer(r"\b" + pattern + r"\b", clause):
                if self.inside(m.start(), consumed):
                    continue
                consumed.append(m.span())
                before = self.marks_in(clause[0], m.start())
                left = right = None
                if before:
                    same = self.side(clause[0], m.start(), before[-1][1].kind)
                    if len(same) == 2:
                        left, right = same
                found.append((m, left, right))
        for m, left, right in found:
            self.recognised += 1
            negator = self.negator(m.start(), clause)
            if negator:
                self.warn_unchecked(clause, "negated", negator=negator, word=m.group())
                continue
            if left is None or right is None:
                self.warn_unchecked(clause, "unchecked_unresolved", word=m.group())
                continue
            ref = self.pair(left, right, clause, sentence)
            if ref is None:
                self.warn_unchecked(clause, "unchecked_series", word=m.group())
                continue
            if difference_test(self.data, ref[0], ref[1]) is not None:
                self.add(
                    clause,
                    self.msg("equal_ci"),
                    "equality",
                    suggestion=self.msg("suggest_cannot"),
                )
                continue
            a, b = self.value(ref[0]), self.value(ref[1])
            d = self.data.decimals
            if round(a, d) != round(b, d):
                self.add(
                    clause,
                    self.msg(
                        "equal_wrong",
                        left=left.text,
                        right=right.text,
                        a=self.fmt(a),
                        b=self.fmt(b),
                    ),
                    "equality",
                )

    def extremes(
        self, clause: tuple[int, int], sentence: tuple[int, int], consumed: list[tuple[int, int]]
    ) -> None:
        lang = self.lang
        maxes = (*lang.MAX_WORDS, *lang.MAX_WORDS_AFTER_THE)
        after_the = _words((*lang.MAX_WORDS_AFTER_THE, *lang.MIN_WORDS_AFTER_THE))
        patterns = [
            r"\b(?P<w>" + _words((*lang.MAX_WORDS, *lang.MIN_WORDS)) + r")\b",
            r"\bthe\s+(?P<w>" + after_the + r")\b",
            r"(?:^|(?<=[.;!?]))\s*(?P<w>" + after_the + r")\s*:",
        ]
        hedge = re.compile(
            r"\W+(?:[\w" + _APOSTROPHES + r"]+\W+)?(?:" + _words(lang.HEDGES) + r")\b",
            re.IGNORECASE,
        )
        for pattern in patterns:
            for m in self.finditer(pattern, clause):
                start = m.start("w")
                if self.inside(start, consumed):
                    continue
                consumed.append(m.span())
                self.recognised += 1
                word = m.group("w").lower()
                negator = self.negator(start, clause) or self.contrast(start, clause)
                if negator:
                    self.warn_unchecked(clause, "negated", negator=negator, word=m.group("w"))
                    continue
                qualifier = self.qualifier(start, clause)
                if qualifier:
                    self.warn_unchecked(clause, "qualified", qualifier=qualifier, word=m.group("w"))
                    continue
                is_max = word in maxes
                hedged = hedge.match(self.skel, m.end(), clause[1]) is not None
                a, b = self.segment(start, clause)
                # Names after "not" are left out: "Kano is the highest, not Lagos".
                claimed = self._unique(
                    (pos, mk)
                    for pos, mk in self.marks_in(a, b, "c")
                    if not self.re_excluded.search(self.skel, max(a, pos - 15), pos)
                )
                if not claimed and self.re_ellipsis.match(self.skel, a):
                    claimed = self.clause_subject(clause, start, "c")
                if not claimed:
                    self.warn_unchecked(clause, "unchecked_unresolved", word=m.group("w"))
                    continue
                s = self.context("s", clause, sentence)
                if s is None:
                    self.warn_unchecked(clause, "unchecked_series", word=m.group("w"))
                    continue
                self.check_extreme(claimed, s, word, is_max, hedged, clause)

    def check_extreme(
        self,
        claimed: list[_Mark],
        s: int,
        word: str,
        is_max: bool,
        hedged: bool,
        clause: tuple[int, int],
    ) -> None:
        lang = self.lang
        values = self.data.series[s].values
        target = max(values) if is_max else min(values)
        extreme = [i for i, v in enumerate(values) if v == target]
        wrong = [mk for mk in claimed if values[mk.index] != target]
        for mk in wrong:
            self.add(
                clause,
                self.msg(
                    "not_extreme",
                    name=mk.text,
                    word=word,
                    actual=lang.join([self.name("c", i) for i in extreme]),
                    value=self.fmt(target),
                ),
                "extreme",
            )
        if wrong:
            return
        missing = [i for i in extreme if i not in [mk.index for mk in claimed]]
        if missing:
            self.add(
                clause,
                self.msg(
                    "tied",
                    name=claimed[0].text,
                    word=word,
                    others=lang.join([self.name("c", i) for i in missing]),
                ),
                "extreme",
                severity="warning",
            )
        if hedged or not self.data.series[s].has_interval:
            return
        # An unqualified superlative must be separated from every other group.
        rest = [i for i in range(len(values)) if i not in extreme]
        suggestion = self.msg("suggest_hedge", name=claimed[0].text, word=word)
        if not rest:
            if len(values) > 1:
                self.add(
                    clause,
                    self.msg(
                        "superlative_unsupported",
                        name=claimed[0].text,
                        word=word,
                        runner=lang.join([self.name("c", i) for i in extreme[1:]]),
                    ),
                    "extreme",
                    suggestion=suggestion,
                )
            return
        unseparated = [j for j in rest if not _all_supported(self.data, s, extreme, [j])]
        if unseparated:
            self.add(
                clause,
                self.msg(
                    "superlative_unsupported",
                    name=claimed[0].text,
                    word=word,
                    runner=lang.join([self.name("c", i) for i in unseparated]),
                ),
                "extreme",
                suggestion=suggestion,
            )
        else:
            self.independence(clause, "c")

    def structural_start(self, clause: tuple[int, int]) -> int:
        """Where the generator's own wording starts in the clause ("one per", "2 series:")."""
        starts = [clause[1]]
        for pattern in self.lang.STRUCTURAL:
            for m in self.finditer(pattern, clause):
                starts.append(m.start())
        return min(starts)

    def unchecked(self, clause: tuple[int, int], consumed: list[tuple[int, int]]) -> None:
        lang = self.lang
        known = {*lang.MAX_WORDS, *lang.MIN_WORDS, *lang.UP_WORDS, *lang.DOWN_WORDS}
        for m in self.finditer(r"\b(?P<w>" + _words(lang.UNCHECKED) + r")\b", clause):
            if not self.inside(m.start(), consumed):
                self.warn_unchecked(clause, "unchecked", word=m.group("w"))
        for pattern in lang.UNCHECKED_PATTERNS:
            for m in self.finditer(pattern, clause):
                if not self.inside(m.start(), consumed):
                    self.warn_unchecked(clause, "unchecked", word=m.group())
        for m in self.finditer(r"\b(?P<w>[a-z]+)\s+" + lang.THAN + r"\b", clause):
            if not self.inside(m.start(), consumed) and m.group("w").lower() not in known:
                self.warn_unchecked(clause, "unchecked", word=m.group("w") + " " + lang.THAN)
        for m in self.finditer(r"\bthe\s+(?P<w>[a-z]+est)\b", clause):
            word = m.group("w").lower()
            if (
                not self.inside(m.start("w"), consumed)
                and word not in known
                and word not in lang.NOT_SUPERLATIVE
            ):
                self.warn_unchecked(clause, "unchecked", word=m.group("w"))
        # Numbers written as words: a count before the label is checked ("the four
        # states"); any other spelled number next to a named group gives a warning.
        named = bool(self.marks_in(clause[0], clause[1], "c"))
        structural = [m.span() for p in lang.STRUCTURAL for m in self.finditer(p, clause)]
        count_re = self.count_noun_re()
        for m in self.finditer(r"\b(?P<w>" + _words(lang.SPELLED_NUMBERS) + r")\b", clause):
            if self.inside(m.start(), consumed + structural):
                continue
            word = m.group("w").lower()
            noun = count_re.match(self.skel, m.end())
            if noun and word in lang.SPELLED_VALUES:
                claimed = lang.SPELLED_VALUES[word]
                series = noun.group().strip().lower() == "series"
                actual = len(self.data.series if series else self.data.categories)
                if claimed != actual:
                    self.add(
                        clause,
                        self.msg("count_wrong", actual=actual, claimed=m.group("w")),
                        "number",
                        number=m.group("w"),
                    )
                continue
            if named:
                self.add(
                    clause,
                    self.msg("spelled", word=m.group("w")),
                    "unchecked",
                    severity="warning",
                )

    def relation(self, clause: tuple[int, int]) -> None:
        """A clause naming two or more groups that no check recognised: warn."""
        end = self.structural_start(clause)
        names = self.side(clause[0], end, "c")
        if len(names) < 2:
            names = self.side(clause[0], end, "s")
        if len(names) < 2:
            return
        rest = _MARK_RE.sub(" ", self.skel[clause[0] : clause[1]])
        rest = _NUMBER.sub(" ", rest)
        words = re.findall(r"[a-z]+", rest.lower())
        attached = {
            mk.index
            for m in _NUMBER.finditer(self.skel, clause[0], clause[1])
            if (mk := self.attach(m, clause)) is not None
        }
        if all(w in self.lang.NEUTRAL_WORDS for w in words) and all(
            mk.index in attached for mk in names if mk.kind == "c"
        ):
            return  # a list of values: "Kano has 12.0% and Lagos has 8.0%"
        self.warn_unchecked(clause, "relation", names=self.lang.join([mk.text for mk in names]))

    # Numbers.
    def constants(self, share: bool) -> list[float]:
        """Values that hold for every category of a series whose values are all equal."""
        data = self.data
        out: list[float] = []
        for s in data.series:
            if len(set(s.values)) != 1:
                continue
            if share:
                if data.shares:
                    out.append(100 / len(s.values))
                continue
            out.append(s.values[0])
            for bounds in (s.lower, s.upper):
                if bounds is not None and len(set(bounds)) == 1:
                    out.append(bounds[0])
        return out

    def candidates(self, s: int, i: int, *, share: bool = False) -> list[float]:
        series = self.data.series[s]
        if share:
            return [shares_of(series.values)[i]] if self.data.shares else []
        out = [series.values[i]]
        if series.lower is not None and series.upper is not None:
            out += [series.lower[i], series.upper[i]]
        if self.data.shares:
            out.append(shares_of(series.values)[i])
        return out

    def count_noun_re(self) -> re.Pattern[str]:
        """Counting nouns and the category label (and its plural): "4 states", "37 bars"."""
        lang = self.lang
        label = lang.label(self.data.category_label)
        nouns = (*lang.COUNT_NOUNS, label + "s", label + "es")
        return re.compile(r"\s*(?:" + _words(nouns) + r")\b", re.IGNORECASE)

    def parse(self, m: re.Match[str]) -> tuple[str, float, float, int]:
        """A number token: (as written, value, rounding tolerance, end incl. scale word)."""
        lang = self.lang
        token = m.group()
        value = float(token.replace(",", ""))
        decimals = len(token.split(".")[1]) if "." in token else 0
        tol = 0.5 * 10**-decimals
        end = m.end()
        scale = re.compile(r"\s*(" + _words(lang.SCALES) + r")\b", re.IGNORECASE).match(
            self.skel, end
        )
        if scale:
            factor = lang.SCALES[scale.group(1).lower()]
            value *= factor
            tol *= factor
            end = scale.end()
        return token, value, tol + 1e-9 * max(1.0, abs(value)), end

    def attach(self, m: re.Match[str], clause: tuple[int, int]) -> _Mark | None:
        """The category a number belongs to, or None if the clause names none.

        "2.0% in Ibadan": the name after. "Lagos's rate is 8.0%", "Kano (12.0%)": the name
        just before. Otherwise the nearest name in the part of the clause (ties: before).
        """
        seg = self.segment(m.start(), clause)
        cats = self.marks_in(seg[0], seg[1], "c") or self.marks_in(clause[0], clause[1], "c")
        if not cats:
            return None
        follow = self.re_in_name.match(self.skel, m.end())
        if follow:
            mark = self.marks[ord(follow.group(1)) - _MARK0]
            if mark.kind == "c":
                return mark
        before = [(p, mk) for p, mk in cats if p < m.start()]
        if before and self.re_link.fullmatch(self.skel, before[-1][0] + 1, m.start()):
            return before[-1][1]
        return min(
            cats,
            key=lambda pm: (
                m.start() - pm[0] - 1 if pm[0] < m.start() else pm[0] - m.end(),
                pm[0] > m.start(),
            ),
        )[1]

    def scope(
        self, part: tuple[int, int], clause: tuple[int, int], sentence: tuple[int, int]
    ) -> list[int]:
        """The series a number is read in: named in its part, clause or sentence, else all."""
        for a, b in (part, clause, sentence):
            found = sorted({mk.index for _, mk in self.marks_in(a, b, "s")})
            if found:
                return found
        return list(range(len(self.data.series)))

    def respectively(self, clause: tuple[int, int], sentence: tuple[int, int]) -> None:
        """ "A, B and C have 12.0%, 8.0% and 4.0% respectively": pair names and numbers."""
        if not re.search(self.lang.RESPECTIVELY, self.skel[clause[0] : clause[1]], re.I):
            return
        self.recognised += 1
        names = self.side(clause[0], clause[1], "c")
        numbers = [
            m
            for m in _NUMBER.finditer(self.skel, clause[0], clause[1])
            if m.start() not in self.consumed_numbers
        ]
        for m in numbers:
            self.consumed_numbers.add(m.start())
        if len(names) < 2 or len(names) != len(numbers):
            self.warn_unchecked(
                clause, "respectively_mismatch", names=len(names), numbers=len(numbers)
            )
            return
        scope = self.scope(clause, clause, sentence)
        for mark, m in zip(names, numbers, strict=True):
            token, value, tol, _ = self.parse(m)
            if any(abs(x - value) <= tol for s in scope for x in self.candidates(s, mark.index)):
                continue
            owner = self.owner(lambda x, v=value, t=tol: abs(x - v) <= t, [], scope, False)
            reason = (
                self.msg("belongs_to", right=owner, wrong=mark.text)
                if owner
                else self.msg("not_in_data")
            )
            self.add(clause, reason, "number", number=token)

    def numbers(self, clause: tuple[int, int], sentence: tuple[int, int]) -> None:
        data, lang = self.data, self.lang
        count_re = self.count_noun_re()
        total_before = re.compile(lang.TOTAL_BEFORE, re.IGNORECASE)
        total_after = re.compile(lang.TOTAL_AFTER, re.IGNORECASE)
        share_after = re.compile(lang.SHARE_AFTER, re.IGNORECASE)
        n_categories, n_series = len(data.categories), len(data.series)
        totals = [sum(s.values) for s in data.series] if data.shares else []
        in_data = [
            x
            for s in data.series
            for bounds in (s.values, s.lower or (), s.upper or ())
            for x in bounds
        ]
        tokens = [
            m
            for m in _NUMBER.finditer(self.skel, clause[0], clause[1])
            if m.start() not in self.consumed_numbers
        ]
        skip: set[int] = set()
        for k, m in enumerate(tokens):
            if m.start() in skip:
                continue
            token, value, tol, end = self.parse(m)

            def close(x: float, value: float = value, tol: float = tol) -> bool:
                return abs(x - value) <= tol

            after = self.skel[end : end + 40]
            before = self.skel[max(clause[0], m.start() - 30) : m.start()]
            # Chart-wide figures, only with the words that announce them.
            if count_re.match(self.skel, end) and (
                close(n_categories) or (n_series > 1 and close(n_series))
            ):
                continue
            seg = self.segment(m.start(), clause)
            # The total, only when no category is named next to it ("Total: 1,000", not
            # "A has 1,000 in total").
            if (
                totals
                and (total_before.search(before) or total_after.match(after))
                and any(close(t) for t in totals)
                and not self.marks_in(seg[0], seg[1], "c")
            ):
                continue
            share = share_after.match(after) is not None
            series_scope = self.scope(seg, clause, sentence)
            nearest = self.attach(m, clause)
            if nearest is None:
                if any(close(g) for g in self.constants(share)):
                    continue
                if any(close(x) for x in in_data):
                    self.add(
                        clause,
                        self.msg("no_category_known"),
                        "number",
                        number=token,
                        severity="warning",
                    )
                else:
                    self.add(clause, self.msg("no_category"), "number", number=token)
                continue
            # "Kano 10.1% to 14.5%": an interval, lower then upper.
            nxt = tokens[k + 1] if k + 1 < len(tokens) else None
            if (
                nxt is not None
                and self.re_range.fullmatch(self.skel, m.end(), nxt.start())
                and self.attach(nxt, clause) is nearest
            ):
                bounded = [
                    s
                    for s in series_scope
                    if self.data.series[s].lower is not None
                    and self.data.series[s].upper is not None
                ]
                if bounded:
                    skip.add(nxt.start())
                    _, upper, upper_tol, _ = self.parse(nxt)
                    if not any(
                        close(self.data.series[s].lower[nearest.index])  # type: ignore[index]
                        and abs(self.data.series[s].upper[nearest.index] - upper)  # type: ignore[index]
                        <= upper_tol
                        for s in bounded
                    ):
                        s0 = self.data.series[bounded[0]]
                        assert s0.lower is not None and s0.upper is not None
                        self.add(
                            clause,
                            self.msg(
                                "interval_pair",
                                name=nearest.text,
                                lower=self.fmt(s0.lower[nearest.index]),
                                upper=self.fmt(s0.upper[nearest.index]),
                                claimed=f"{token} to {nxt.group()}",
                            ),
                            "number",
                            number=token,
                        )
                    continue
            if any(
                close(x)
                for s in series_scope
                for x in self.candidates(s, nearest.index, share=share)
            ):
                continue
            cats = self.marks_in(seg[0], seg[1], "c") or self.marks_in(clause[0], clause[1], "c")
            owner = self.owner(close, cats, series_scope, share)
            if owner is None:
                self.add(clause, self.msg("not_in_data"), "number", number=token)
            else:
                self.add(
                    clause,
                    self.msg("belongs_to", right=owner, wrong=nearest.text),
                    "number",
                    number=token,
                )

    def owner(
        self, close: Any, cats: list[tuple[int, _Mark]], scope: list[int], share: bool
    ) -> str | None:
        data = self.data
        order = [mk.index for _, mk in cats] + list(range(len(data.categories)))
        for scoped in (scope, range(len(data.series))):
            for i in order:
                for s in scoped:
                    if any(close(x) for x in self.candidates(s, i, share=share)):
                        name = self.name("c", i)
                        if s not in scope:
                            name += f" ({self.name('s', s)})"
                        return name
        return None


def check_alt_text(text: str, data: ChartData, *, lang: str = "en") -> list[Problem]:
    """Check every number and every recognised claim in ``text`` against ``data``.

    Returns errors and warnings (see :class:`Problem`). No errors means no recognised claim
    was found false; see the module docstring for what is and is not checked.
    """
    return _Checker(text, data, lang).run()


def mentioned_categories(text: str, data: ChartData, *, lang: str = "en") -> set[int]:
    """Indices of the categories named in ``text`` (verbatim strings excluded)."""
    checker = _Checker(text, data, lang)
    return {mk.index for mk in checker.marks if mk.kind == "c"}


def number_tokens(text: str, data: ChartData, *, lang: str = "en") -> list[str]:
    """The numbers in ``text`` as written, outside names and verbatim strings."""
    checker = _Checker(text, data, lang)
    return [m.group() for m in _NUMBER.finditer(checker.skel)]
