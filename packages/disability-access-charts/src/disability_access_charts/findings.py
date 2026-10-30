"""Statistical findings: pre-declared comparisons, all counted, with false discovery rate control.

:func:`statistical_findings` builds a chart document's ``findings`` block from its data. It
is **descriptive multiple-comparison control**: it says which differences between survey
estimates are larger than their uncertainty allows, after allowing for how many
differences were looked at. It does not say why estimates differ, and it is not a causal
analysis. The full method is in ``docs/findings.md``.

The families
------------
Four families of comparisons are declared before any value is looked at, and every
comparison in them is counted, supported or not:

* ``extremes``: the highest estimate against the next one, and the lowest against the next
  one (ties are compared as a group), per series;
* ``gaps``: two series in the same category (e.g. women against men in one state), for
  every pair of series and every category;
* ``rankings``: every other pair of neighbours in the ranking (highest first, ties in chart
  order), per series; the pairs already in ``extremes`` are not counted twice. A finding
  gives each estimate's rank, from the nearer end ("the second-highest estimate", "the
  3rd-lowest estimate"; competition ranking, as the claim checker's);
* ``outliers``: each estimate against an overall value (a :class:`Reference`, e.g. the
  national estimate), per series. Without a reference this family is empty. The estimates
  in one finding are listed with semicolons between them ("A, 1%; B, 2%; and C, 3%"), and
  the claim checker checks each of them.

The test
--------
The claim checker's interval test (:func:`disability_access_charts.describe.difference_test`):
each standard error is the interval's larger half-width divided by the normal quantile of
its level, and the difference is tested against ``1.96 * sqrt(se_a**2 + se_b**2)``. Here it
is turned into a two-sided p-value, ``p = 2 * (1 - Phi(|a - b| / sqrt(se_a**2 + se_b**2)))``,
so a comparison passes the checker's test exactly when ``p < 0.05`` (up to 1.96 against
the exact quantile 1.95996). The larger half-width is conservative only when the interval
is wider than a normal one on that side; the survey design's degrees of freedom and t
quantiles are not used.

Benjamini-Hochberg controls the false discovery rate over **all** the comparisons tested in
the block (every family and series together) at ``q`` (default 0.05; at most 0.05, the
checker's own level, or a ``ValueError``). A comparison is *supported* when its
BH-adjusted p-value is at most ``q`` and the difference also passes the checker's test
(which only matters at the 1.96 edge), so every finding sentence passes the claim
checker. BH's guarantee needs the tests to be independent or positively dependent; that is
not proven for these comparisons, so ``q`` is nominal. The ``dependence`` caveat says so
and gives how many comparisons Benjamini-Yekutieli (valid under any dependence) would
support.

The chart builders also use the ``extremes`` results in the alt-text: with
``findings=True``, its "the survey can / cannot show a difference from the next estimate"
follows the ``supported`` flags (see :func:`extreme_verdicts`), so the alt-text and the
findings never disagree.

Precision
---------
A series may carry a precision flag per estimate (:class:`~disability_access_charts.describe.Series`
``precision``). A comparison that involves a "review" estimate is tested, and its finding
is hedged ("Read with care: ...'s estimate is flagged for review."). A comparison that
involves an "unreliable" or "suppressed" estimate is **not tested**: it is listed under
``dropped`` and counted there, and it is not in the BH family. So is a comparison that
involves an interval of zero width (e.g. 0 events, interval 0 to 0): it has no standard
error to test with, and a zero standard error would make any difference "supported".
Categories left out of the chart altogether (no data, or suppressed for disclosure) are
named in ``withheld``.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

from disability_access_charts import _lang
from disability_access_charts.describe import (
    TEST_Z,
    ChartData,
    Series,
    _groups,
    _Writer,
    _z_level,
    check_alt_text,
    format_value,
    verdict_key,
)

FAMILIES: tuple[str, ...] = ("extremes", "gaps", "rankings", "outliers")
FAMILY_LABELS: dict[str, str] = {
    "extremes": "Highest and lowest estimates, each against the next",
    "gaps": "Gaps between series in the same category",
    "rankings": "Neighbours in the ranking",
    "outliers": "Each estimate against the overall value",
}
DEFAULT_Q = 0.05
"""The false discovery rate the block controls by default."""
MAX_Q = 0.05
"""The largest ``q`` allowed: the claim checker's own level, which every finding must pass."""
DROPPED_FLAGS = frozenset({"unreliable", "suppressed"})
ZERO_WIDTH = "zero-width"
"""The ``reason`` of a comparison dropped for an interval of zero width."""
HEDGED_FLAGS = frozenset({"review"})
METHOD = "benjamini-hochberg"

_CAVEATS: dict[str, str] = {
    "descriptive": (
        "Descriptive comparisons of survey estimates, with the false discovery rate "
        "controlled across all of them; not a causal analysis."
    ),
    "independence": (
        "The test treats the two estimates as independent. Series in the same category, or "
        "parts of one whole, come from the same survey, so the test is approximate for them."
    ),
    "reference": (
        "Each estimate is part of the overall value it is compared with. The test ignores "
        "that overlap, which makes it conservative (it finds fewer differences)."
    ),
    "dependence": (
        "Benjamini-Hochberg keeps the false discovery rate at {q}% when the tests are "
        "independent or positively dependent. That is not proven for these comparisons, "
        "which share estimates, so the {q}% is nominal. Benjamini-Yekutieli, which holds "
        "under any dependence, would support {by} of the {checked}."
    ),
}


@dataclass(frozen=True)
class Reference:
    """An overall value to compare every estimate with (the ``outliers`` family).

    ``value``, ``lower`` and ``upper`` are one number each for a one-series chart, or one per
    series. ``label`` is how the findings name it ("Nigeria as a whole"); like a category
    name, it must not be a claim word.
    """

    label: str
    value: float | Sequence[float]
    lower: float | Sequence[float]
    upper: float | Sequence[float]

    def per_series(self, n_series: int) -> tuple[list[float], list[float], list[float]]:
        """(values, lowers, uppers), one per series."""

        def norm(x: float | Sequence[float], what: str) -> list[float]:
            items = [float(x)] if isinstance(x, (int, float)) else [float(v) for v in x]
            if len(items) != n_series:
                raise ValueError(f"reference {what}: {len(items)} given for {n_series} series")
            return items

        values, lowers, uppers = (
            norm(self.value, "value"),
            norm(self.lower, "lower"),
            norm(self.upper, "upper"),
        )
        for v, lo, hi in zip(values, lowers, uppers, strict=True):
            if not all(math.isfinite(x) for x in (v, lo, hi)) or not lo <= v <= hi:
                raise ValueError("reference: need finite lower <= value <= upper")
        return values, lowers, uppers

    def to_dict(self, n_series: int) -> dict[str, Any]:
        values, lowers, uppers = self.per_series(n_series)
        return {"label": self.label, "values": values, "lower": lowers, "upper": uppers}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Reference:
        return cls(d["label"], tuple(d["values"]), tuple(d["lower"]), tuple(d["upper"]))


# --- The numbers ---------------------------------------------------------------------------


def difference_p(difference: float, sd: float) -> float:
    """Two-sided normal p-value for ``difference`` with standard error ``sd``."""
    if sd <= 0:
        return 0.0 if difference > 0 else 1.0
    return min(1.0, 2.0 * (1.0 - NormalDist().cdf(abs(difference) / sd)))


def benjamini_yekutieli(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Yekutieli adjusted p-values: Benjamini-Hochberg's times
    ``c(m) = 1 + 1/2 + ... + 1/m``, capped at 1. They control the false discovery rate under
    any dependence between the tests (Benjamini and Yekutieli, 2001)."""
    c = sum(1 / k for k in range(1, len(p_values) + 1))
    return [min(1.0, p * c) for p in benjamini_hochberg(p_values)]


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values, in the input order.

    ``p_adj[(i)] = min over j >= i of (m / j) * p[(j)]``, capped at 1, for the p-values
    sorted ascending. Rejecting every hypothesis with ``p_adj <= q`` controls the false
    discovery rate at ``q`` (Benjamini and Hochberg, 1995).
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        adjusted[i] = min(1.0, running)
    return adjusted


@dataclass(frozen=True)
class _Cell:
    series: int
    category: int | None  # None: the reference

    def key(self) -> tuple[int, int]:
        return (self.series, -1 if self.category is None else self.category)


class _Builder:
    def __init__(
        self,
        data: ChartData,
        reference: Reference | None,
        withheld: Sequence[str],
        q: float,
        lang: str,
    ) -> None:
        if not 0 < q <= MAX_Q:
            raise ValueError(
                f"q must be above 0 and at most {MAX_Q}: a supported finding must also pass "
                f"the claim checker's own {100 * MAX_Q:g}% test, so a larger q would not "
                "support more"
            )
        self.data = data
        self.lang = _lang.get(lang)
        self.lang_code = lang
        self.t = self.lang.TEMPLATES
        self.f = self.lang.FINDINGS
        self.q = q
        self.writer = _Writer(data, lang)
        self.ci = [j for j, s in enumerate(data.series) if s.has_interval]
        if not self.ci:
            raise ValueError("findings need at least one series with intervals")
        self.reference = reference
        self.ref_values: tuple[list[float], list[float], list[float]] | None = None
        if reference is not None:
            if reference.label in data.categories or reference.label in [
                s.name for s in data.series
            ]:
                raise ValueError("the reference label must differ from every name in the data")
            self.ref_values = reference.per_series(len(data.series))
            self.check_data = _with_reference(data, reference, self.ref_values)
        else:
            self.check_data = data
        self.withheld = [str(w) for w in withheld]
        overlap = set(self.withheld) & set(data.categories)
        if overlap:
            raise ValueError(f"withheld names are in the chart: {', '.join(sorted(overlap))}")
        _refuse_colliding_names(data, reference, self.lang)

    # Cells.
    def flag(self, cell: _Cell) -> str | None:
        if cell.category is None:
            return None
        precision = self.data.series[cell.series].precision
        return None if precision is None else precision[cell.category]

    def numbers(self, cell: _Cell) -> tuple[float, float | None, float | None]:
        if cell.category is None:
            assert self.ref_values is not None
            values, lowers, uppers = self.ref_values
            return values[cell.series], lowers[cell.series], uppers[cell.series]
        s = self.data.series[cell.series]
        i = cell.category
        lower = None if s.lower is None else s.lower[i]
        upper = None if s.upper is None else s.upper[i]
        return s.values[i], lower, upper

    def zero_width(self, cell: _Cell) -> bool:
        _, lower, upper = self.numbers(cell)
        return lower is not None and upper is not None and upper - lower <= 0

    def se(self, cell: _Cell) -> float:
        value, lower, upper = self.numbers(cell)
        assert lower is not None and upper is not None
        return max(value - lower, upper - value) / _z_level(self.data)

    def name(self, cell: _Cell) -> str:
        if cell.category is None:
            assert self.reference is not None
            return self.data.glossary.get(self.reference.label, self.reference.label)
        return self.writer.name(cell.category)

    def cell_dict(self, cell: _Cell) -> dict[str, Any]:
        value, lower, upper = self.numbers(cell)
        return {
            "series": self.data.series[cell.series].name,
            "category": (
                self.reference.label
                if cell.category is None and self.reference is not None
                else self.data.categories[cell.category or 0]
            ),
            "reference": cell.category is None,
            "value": value,
            "lower": lower,
            "upper": upper,
            "precision": self.flag(cell),
        }

    # The plan: every comparison, declared from the structure of the data.
    def plan(self) -> list[tuple[str, _Cell, _Cell, str]]:
        """(family, a, b, group key). Within a pair, ``a`` is the higher estimate."""
        planned: list[tuple[str, _Cell, _Cell, str]] = []
        n = len(self.data.categories)
        for s in self.ci:
            values = self.data.series[s].values
            if n < 2:
                continue
            top, next_top, bottom, next_bottom = _groups(values)
            seen: set[frozenset[int]] = set()
            if len(top) < n:
                two = len(set(values)) == 2 and len(top) + len(bottom) == n
                for i in top:
                    for j in next_top:
                        planned.append(("extremes", _Cell(s, i), _Cell(s, j), f"{s}:highest"))
                        seen.add(frozenset((i, j)))
                if not two:
                    for i in bottom:
                        for j in next_bottom:
                            planned.append(("extremes", _Cell(s, j), _Cell(s, i), f"{s}:lowest"))
                            seen.add(frozenset((i, j)))
            order = sorted(range(n), key=lambda i: (-values[i], i))
            for a, b in itertools.pairwise(order):
                if frozenset((a, b)) not in seen:
                    planned.append(("rankings", _Cell(s, a), _Cell(s, b), f"{s}:{a}:{b}"))
        for k, s1 in enumerate(self.ci):
            for s2 in self.ci[k + 1 :]:
                for i in range(n):
                    a, b = _Cell(s1, i), _Cell(s2, i)
                    if self.numbers(b)[0] > self.numbers(a)[0]:
                        a, b = b, a
                    planned.append(("gaps", a, b, f"{i}:{s1}:{s2}"))
        if self.reference is not None:
            for s in self.ci:
                for i in range(n):
                    a, b = _Cell(s, i), _Cell(s, None)
                    up = self.numbers(a)[0] >= self.numbers(b)[0]
                    if not up:
                        a, b = b, a
                    planned.append(("outliers", a, b, f"{s}:{'higher' if up else 'lower'}"))
        order_of = {f: k for k, f in enumerate(FAMILIES)}
        planned.sort(key=lambda p: order_of[p[0]])  # stable: plan order within a family
        return planned

    def build(self) -> dict[str, Any]:
        planned = self.plan()
        tested: list[dict[str, Any]] = []
        cells: list[tuple[_Cell, _Cell, str]] = []
        dropped: list[dict[str, Any]] = []
        for family, a, b, group in planned:
            flags = {f for f in (self.flag(a), self.flag(b)) if f in DROPPED_FLAGS}
            if not flags and (self.zero_width(a) or self.zero_width(b)):
                flags = {ZERO_WIDTH}
            if flags:
                dropped.append(
                    {
                        "family": family,
                        "a": self.cell_dict(a),
                        "b": self.cell_dict(b),
                        "reason": sorted(flags)[0],
                    }
                )
                continue
            va, vb = self.numbers(a)[0], self.numbers(b)[0]
            sd = math.sqrt(self.se(a) ** 2 + self.se(b) ** 2)
            difference = abs(va - vb)
            tested.append(
                {
                    "family": family,
                    "a": self.cell_dict(a),
                    "b": self.cell_dict(b),
                    "difference": difference,
                    "threshold": TEST_Z * sd,
                    "p": difference_p(difference, sd),
                    "hedged": bool({self.flag(a), self.flag(b)} & HEDGED_FLAGS),
                }
            )
            cells.append((a, b, group))
        adjusted = benjamini_hochberg([c["p"] for c in tested])
        for c, p_adj in zip(tested, adjusted, strict=True):
            c["p_adjusted"] = p_adj
            # q <= 0.05, so p_adj <= q already implies p < 0.05; the threshold test only
            # matters at the edge, where 1.96 is a little above the exact quantile.
            c["supported"] = p_adj <= self.q and c["difference"] > c["threshold"]
        by_supported = sum(
            1
            for c, p_by in zip(tested, benjamini_yekutieli([c["p"] for c in tested]), strict=True)
            if p_by <= self.q and c["difference"] > c["threshold"]
        )
        statements = self.statements(tested, cells)
        families = []
        for family in FAMILIES:
            fam_tested = [c for c in tested if c["family"] == family]
            fam_dropped = [d for d in dropped if d["family"] == family]
            families.append(
                {
                    "id": family,
                    "label": FAMILY_LABELS[family],
                    "checked": len(fam_tested),
                    "supported": sum(1 for c in fam_tested if c["supported"]),
                    "dropped": len(fam_dropped),
                }
            )
        checked = len(tested)
        supported = sum(1 for c in tested if c["supported"])
        caveats = ["descriptive"]
        if len(self.ci) > 1 or self.data.shares:
            caveats.append("independence")
        if self.reference is not None:
            caveats.append("reference")
        if checked:
            caveats.append("dependence")
        caveat_values = {"q": f"{100 * self.q:g}", "by": by_supported, "checked": checked}
        return {
            "method": {
                "test": "two-sided normal test of the difference, as the claim checker's",
                "z": TEST_Z,
                "se_from": "the interval: its larger half-width over the normal quantile",
                "correction": METHOD,
                "q": self.q,
                "families": list(FAMILIES),
                "lang": self.lang_code,
            },
            "reference": (
                None if self.reference is None else self.reference.to_dict(len(self.data.series))
            ),
            "withheld": list(self.withheld),
            "checked": checked,
            "supported": supported,
            "dropped": len(dropped),
            "families": families,
            "comparisons": tested,
            "dropped_comparisons": dropped,
            "statements": statements,
            "lines": lines(
                checked,
                supported,
                len(dropped),
                self.withheld,
                q=self.q,
                lang=self.lang_code,
            ),
            "caveats": [{"id": c, "text": _CAVEATS[c].format(**caveat_values)} for c in caveats],
        }

    # Sentences.
    def item(self, cell: _Cell) -> str:
        value = format_value(self.numbers(cell)[0], self.data)
        return self.f["finding_item"].format(name=self.name(cell), value=value)

    def rank_item(self, cell: _Cell) -> str:
        """The estimate with its rank from the nearer end: "Abia, the second-highest
        estimate (10.6%)". Competition ranking, as the claim checker's."""
        f = self.f
        values = self.data.series[cell.series].values
        v = values[cell.category or 0]
        from_top = 1 + sum(1 for x in values if x > v)
        from_bottom = 1 + sum(1 for x in values if x < v)
        if from_top <= from_bottom:
            rank = (
                f["rank_top"]
                if from_top == 1
                else f["rank_high"].format(ordinal=self.lang.ordinal(from_top))
            )
        else:
            rank = (
                f["rank_bottom"]
                if from_bottom == 1
                else f["rank_low"].format(ordinal=self.lang.ordinal(from_bottom))
            )
        return f["finding_rank_item"].format(
            name=self.name(cell), rank=rank, value=format_value(v, self.data)
        )

    def prefix(self, s: int) -> str:
        if len(self.data.series) == 1:
            return ""
        return self.f["finding_prefix"].format(series=self.writer.series_name(s))

    def hedges(self, cells: Sequence[_Cell]) -> list[str]:
        out: list[str] = []
        seen: set[tuple[int, int]] = set()
        for cell in cells:
            if self.flag(cell) in HEDGED_FLAGS and cell.key() not in seen:
                seen.add(cell.key())
                if len(self.data.series) == 1:
                    out.append(self.f["finding_review"].format(name=self.name(cell)))
                else:
                    out.append(
                        self.f["finding_review_series"].format(
                            name=self.name(cell), series=self.writer.series_name(cell.series)
                        )
                    )
        return out

    def statement(
        self, family: str, text: str, indices: Sequence[int], cells: Sequence[_Cell]
    ) -> dict[str, Any]:
        hedges = self.hedges(cells)
        return {
            "family": family,
            "text": " ".join([text, *hedges]),
            "comparisons": list(indices),
            "hedged": bool(hedges),
        }

    def statements(
        self, tested: Sequence[dict[str, Any]], cells: Sequence[tuple[_Cell, _Cell, str]]
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[int]] = {}
        for k, (c, (_, _, group)) in enumerate(zip(tested, cells, strict=True)):
            groups.setdefault((c["family"], group), []).append(k)
        out: list[dict[str, Any]] = []
        w, t, f = self.writer, self.t, self.f
        for (family, group), ks in groups.items():
            if family == "extremes":
                if not all(tested[k]["supported"] for k in ks):
                    continue
                s = cells[ks[0]][0].series
                highest = group.endswith(":highest")
                extreme = sorted(
                    {(cells[k][0] if highest else cells[k][1]).category or 0 for k in ks}
                )
                nxt = sorted({(cells[k][1] if highest else cells[k][0]).category or 0 for k in ks})
                values = self.data.series[s].values
                two = len(set(values)) == 2
                difference = t["difference"].format(
                    can=t["can"], which=t["other" if two else "next"], clause=w.clause(s, nxt)
                )
                if len(self.data.series) == 1:
                    key = "highest_ci" if highest else "lowest_ci"
                    text = t[key].format(clause=w.clause(s, extreme), difference=difference)
                elif highest:
                    text = t["series_highest_ci"].format(
                        series=w.series_name(s),
                        high=w.clause(s, extreme),
                        high_difference=difference,
                    )
                else:
                    text = f["series_lowest_ci"].format(
                        series=w.series_name(s), low=w.clause(s, extreme), low_difference=difference
                    )
                involved = [x for k in ks for x in cells[k][:2]]
                out.append(self.statement(family, text, ks, involved))
            elif family in ("rankings", "gaps"):
                for k in ks:
                    if not tested[k]["supported"]:
                        continue
                    a, b, _ = cells[k]
                    if family == "rankings":
                        text = f["finding_one"].format(
                            prefix=self.prefix(a.series),
                            items=self.rank_item(a),
                            direction=f["higher"],
                            other=self.rank_item(b),
                        )
                    else:
                        text = f["finding_gap"].format(
                            name=w.name(a.category or 0),
                            a=w.series_name(a.series),
                            va=format_value(self.numbers(a)[0], self.data),
                            direction=f["higher"],
                            b=w.series_name(b.series),
                            vb=format_value(self.numbers(b)[0], self.data),
                        )
                    out.append(self.statement(family, text, [k], [a, b]))
            else:  # outliers: one sentence per series and direction, in chart order
                hits = [k for k in ks if tested[k]["supported"]]
                if not hits:
                    continue
                higher = group.endswith(":higher")
                own = [cells[k][0] if higher else cells[k][1] for k in hits]
                ref = cells[hits[0]][1] if higher else cells[hits[0]][0]
                order = sorted(range(len(hits)), key=lambda x: own[x].category or 0)
                hits = [hits[x] for x in order]
                own = [own[x] for x in order]
                key = "finding_one" if len(own) == 1 else "finding_many"
                text = f[key].format(
                    prefix=self.prefix(ref.series),
                    items=self.lang.items([self.item(c) for c in own]),
                    direction=f["higher" if higher else "lower"],
                    other=self.item(ref),
                )
                out.append(self.statement(family, text, hits, own))
        return out


def _with_reference(
    data: ChartData, reference: Reference, numbers: tuple[list[float], list[float], list[float]]
) -> ChartData:
    """The data with the reference as one more category, to check the outlier sentences."""
    values, lowers, uppers = numbers
    series = []
    for j, s in enumerate(data.series):
        lower = None if s.lower is None else (*s.lower, lowers[j])
        upper = None if s.upper is None else (*s.upper, uppers[j])
        series.append(Series(s.name, (*s.values, values[j]), lower, upper))
    return ChartData(
        categories=(*data.categories, reference.label),
        series=tuple(series),
        unit=data.unit,
        decimals=data.decimals,
        shares=False,
        verbatim=data.verbatim,
        interval_label=data.interval_label,
        category_label=data.category_label,
        glossary=dict(data.glossary),
    )


def _checked_templates(lang: Any) -> list[str]:
    """The findings templates whose text the claim checker reads: the finding sentences and
    the words put into them (not the count, method or left-out lines)."""
    return [
        v
        for k, v in lang.FINDINGS.items()
        if k.startswith(("finding_", "rank_")) or k in ("higher", "lower", "series_lowest_ci")
    ]


def _refuse_colliding_names(data: ChartData, reference: Reference | None, lang: Any) -> None:
    """A name that is also a word of the finding sentences ("care", "review") would be read
    as that name by the claim checker; refuse it. Only the sentences the checker reads count,
    and the hedge words; the count, method and left-out lines do not ("Rate", "Survey")."""
    text = " ".join(re.sub(r"\{\w+\}", " ", v) for v in _checked_templates(lang))
    words = set(re.findall(r"[a-z]+", text.lower())) | {w.lower() for w in lang.HEDGES}
    names = [*data.categories, *(s.name for s in data.series)]
    if reference is not None:
        names.append(reference.label)
    bad = [n for n in names if " ".join(n.lower().split()) in words]
    if bad:
        raise ValueError(
            f"name(s) {', '.join(bad)} are also words of the findings sentences; "
            "rename them (for example 'Care group') to use findings"
        )


def extreme_verdicts(block: Mapping[str, Any], data: ChartData) -> dict[tuple[int, int, int], bool]:
    """The ``extremes`` results as :data:`~disability_access_charts.describe.Verdicts` for
    the alt-text: each tested pair's ``supported`` flag, and False for a dropped pair (it was
    not tested, so the survey cannot show the difference). Cells not in ``data`` are skipped.
    """
    series = {s.name: j for j, s in enumerate(data.series)}
    categories = {c: i for i, c in enumerate(data.categories)}
    out: dict[tuple[int, int, int], bool] = {}
    rows = [(c, bool(c.get("supported"))) for c in block.get("comparisons", [])]
    rows += [(d, False) for d in block.get("dropped_comparisons", [])]
    for c, supported in rows:
        if not isinstance(c, Mapping) or c.get("family") != "extremes":
            continue
        a, b = c.get("a") or {}, c.get("b") or {}
        s = series.get(str(a.get("series")))
        i = categories.get(str(a.get("category")))
        j = categories.get(str(b.get("category")))
        if s is None or i is None or j is None or b.get("series") != a.get("series"):
            continue
        out[verdict_key(s, i, j)] = supported
    return out


def lines(
    checked: int,
    supported: int,
    dropped: int,
    withheld: Sequence[str],
    *,
    q: float,
    lang: str = "en",
) -> dict[str, str | None]:
    """The block's plain-words lines: the count, the method, and what was left out."""
    f = _lang.get(lang).FINDINGS

    def noun(n: int) -> str:
        return f["comparison" if n == 1 else "comparisons"]

    return {
        "count": f["findings_count"].format(
            checked=checked, comparisons=noun(checked), supported=supported
        ),
        "method": f["findings_method"].format(q=f"{100 * q:g}"),
        "none": f["findings_none"] if checked and not supported else None,
        "dropped": (
            f["findings_dropped"].format(
                dropped=dropped, comparisons=noun(dropped), they="it" if dropped == 1 else "they"
            )
            if dropped
            else None
        ),
        "withheld": (
            f["findings_withheld"].format(count=len(withheld), names=", ".join(withheld))
            if withheld
            else None
        ),
    }


def statistical_findings(
    data: ChartData,
    *,
    reference: Reference | None = None,
    withheld: Sequence[str] = (),
    q: float = DEFAULT_Q,
    lang: str = "en",
) -> dict[str, Any]:
    """The ``findings`` block for ``data`` (see the module docstring).

    Needs at least one series with intervals. ``reference`` adds the ``outliers`` family;
    ``withheld`` names categories left out of the chart (suppressed or no data), which the
    block reports; ``q`` is the false discovery rate, above 0 and at most 0.05.
    """
    return _Builder(data, reference, withheld, q, lang).build()


# --- Audit --------------------------------------------------------------------------------


def _check(
    check_id: str, severity: str, description: str, passed: bool, **extra: Any
) -> dict[str, Any]:
    # Not a WCAG criterion: these check the statistics, not the accessibility.
    return {
        "id": check_id,
        "wcag": "n/a",
        "severity": severity,
        "description": description,
        "passed": passed,
        **extra,
    }


def _close(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))


def _same_cell(got: Mapping[str, Any], want: Mapping[str, Any]) -> bool:
    return (
        got.get("series") == want["series"]
        and got.get("category") == want["category"]
        and bool(got.get("reference")) == want["reference"]
        and got.get("precision") == want["precision"]
        and all(_close(got.get(k), want[k]) for k in ("value", "lower", "upper"))
    )


def findings_checks(doc: Mapping[str, Any], data: ChartData) -> list[dict[str, Any]]:
    """The audit's checks of a document's ``findings`` block against its ``data`` block."""
    block = doc["findings"]
    checks: list[dict[str, Any]] = []
    comparisons = list(block.get("comparisons", []))
    dropped = list(block.get("dropped_comparisons", []))
    statements = list(block.get("statements", []))

    # Counts add up, and the count line says them.
    problems: list[str] = []
    if block.get("checked") != len(comparisons):
        problems.append(f"checked is {block.get('checked')}, but {len(comparisons)} are listed")
    n_supported = sum(1 for c in comparisons if c.get("supported"))
    if block.get("supported") != n_supported:
        problems.append(f"supported is {block.get('supported')}, but {n_supported} are marked")
    if block.get("dropped") != len(dropped):
        problems.append(f"dropped is {block.get('dropped')}, but {len(dropped)} are listed")
    families = block.get("families", [])
    for key, total in (
        ("checked", block.get("checked")),
        ("supported", block.get("supported")),
        ("dropped", block.get("dropped")),
    ):
        if sum(int(f.get(key, 0)) for f in families) != total:
            problems.append(f"the families' {key} counts do not add up to {total}")
    method = block.get("method", {})
    try:
        want_lines = lines(
            int(block.get("checked", -1)),
            int(block.get("supported", -1)),
            int(block.get("dropped", -1)),
            list(block.get("withheld", [])),
            q=float(method.get("q", DEFAULT_Q)),
            lang=str(method.get("lang", "en")),
        )
    except (TypeError, ValueError) as exc:
        problems.append(f"the lines cannot be rebuilt: {exc}")
    else:
        if block.get("lines") != want_lines:
            problems.append("the count, method or left-out lines differ from the counts")
    checks.append(
        _check(
            "findings-counts",
            "error",
            "The findings' counts add up, and the count line ('N comparisons checked, K "
            "supported') states them",
            not problems,
            problems=problems,
        )
    )

    # Every comparison cites cells that are in the data, with the data's numbers.
    problems = []
    ref = block.get("reference")
    index = {c: i for i, c in enumerate(data.categories)}
    series_index = {s.name: j for j, s in enumerate(data.series)}
    for k, c in enumerate([*comparisons, *dropped]):
        for side in ("a", "b"):
            cell = c.get(side) or {}
            j = series_index.get(str(cell.get("series")))
            if j is None:
                problems.append(
                    f"comparison {k + 1}: series {cell.get('series')!r} is not in the data"
                )
                continue
            s = data.series[j]
            if cell.get("reference"):
                if not ref or cell.get("category") != ref.get("label"):
                    problems.append(f"comparison {k + 1}: the reference is not the block's")
                    continue
                want = (ref["values"][j], ref["lower"][j], ref["upper"][j])
                flag = None
            else:
                i = index.get(str(cell.get("category")))
                if i is None:
                    problems.append(
                        f"comparison {k + 1}: {cell.get('category')!r} is not in the data"
                    )
                    continue
                want = (
                    s.values[i],
                    None if s.lower is None else s.lower[i],
                    None if s.upper is None else s.upper[i],
                )
                flag = None if s.precision is None else s.precision[i]
            got = (cell.get("value"), cell.get("lower"), cell.get("upper"))
            if not all(_close(g, w_) for g, w_ in zip(got, want, strict=True)):
                problems.append(f"comparison {k + 1}: {cell.get('category')}'s numbers differ")
            if cell.get("precision") != flag:
                problems.append(f"comparison {k + 1}: {cell.get('category')}'s flag differs")
    for st in statements:
        for k in st.get("comparisons", []):
            if not (isinstance(k, int) and 0 <= k < len(comparisons)):
                problems.append(f"a statement cites comparison {k}, which is not listed")
            elif not comparisons[k].get("supported"):
                problems.append(f"a statement cites comparison {k + 1}, which is not supported")
    checks.append(
        _check(
            "findings-cite-data",
            "error",
            "Every comparison and every finding cites cells in the data block, with its numbers",
            not problems,
            problems=problems,
        )
    )

    # Recomputed from the data: the same plan, tests, BH result and sentences.
    problems = []
    try:
        reference = Reference.from_dict(ref) if ref else None
        want = statistical_findings(
            data,
            reference=reference,
            withheld=list(block.get("withheld", [])),
            q=float(method.get("q", DEFAULT_Q)),
            lang=str(method.get("lang", "en")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"the findings cannot be recomputed from the data: {exc}")
        want = None
    if want is not None:
        if method.get("correction") != METHOD or method.get("families") != list(FAMILIES):
            problems.append("the method is not Benjamini-Hochberg over the declared families")
        if len(comparisons) != len(want["comparisons"]):
            problems.append(
                f"{len(comparisons)} comparisons listed; the data give {len(want['comparisons'])}"
            )
        else:
            for k, (got, exp) in enumerate(zip(comparisons, want["comparisons"], strict=True)):
                same = (
                    got.get("family") == exp["family"]
                    and _same_cell(got.get("a") or {}, exp["a"])
                    and _same_cell(got.get("b") or {}, exp["b"])
                    and all(
                        _close(got.get(x), exp[x])
                        for x in ("difference", "threshold", "p", "p_adjusted")
                    )
                    and got.get("supported") == exp["supported"]
                    and got.get("hedged") == exp["hedged"]
                )
                if not same:
                    problems.append(f"comparison {k + 1} differs from the data's")
        if len(dropped) != len(want["dropped_comparisons"]):
            problems.append("the dropped comparisons differ from the data's")
        if [s.get("text") for s in statements] != [s["text"] for s in want["statements"]]:
            problems.append("the finding sentences differ from the ones the data give")
        if block.get("caveats") != want["caveats"]:
            problems.append("the caveats differ from the ones the data need")
    checks.append(
        _check(
            "findings-match-data",
            "error",
            "Recomputed from the data block, the findings have the same comparisons, tests, "
            "Benjamini-Hochberg result and sentences",
            not problems,
            problems=problems,
        )
    )

    # Hedging: a finding with a "review" estimate says so; no tested comparison involves an
    # unreliable or suppressed estimate, or an interval of zero width. The hedge is found by
    # its English wording ("'s", "flagged for review"); another language would need its own.
    problems = []
    for k, c in enumerate(comparisons):
        flags = {(c.get(side) or {}).get("precision") for side in ("a", "b")}
        if flags & DROPPED_FLAGS:
            problems.append(f"comparison {k + 1} involves an unreliable or suppressed estimate")
        for side in ("a", "b"):
            cell = c.get(side) or {}
            lo, hi = cell.get("lower"), cell.get("upper")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and hi - lo <= 0:
                problems.append(f"comparison {k + 1} involves an interval of zero width")
        if bool(flags & HEDGED_FLAGS) != bool(c.get("hedged")):
            problems.append(f"comparison {k + 1}: 'hedged' does not match its flags")
    for st in statements:
        reviewed = [
            (c.get(side) or {})
            for k in st.get("comparisons", [])
            if isinstance(k, int) and 0 <= k < len(comparisons)
            for c in [comparisons[k]]
            for side in ("a", "b")
            if (c.get(side) or {}).get("precision") in HEDGED_FLAGS
        ]
        text = st.get("text", "")
        for cell in reviewed:
            if f"{cell.get('category')}'s" not in text or "flagged for review" not in text:
                problems.append(f"the finding about {cell.get('category')} is not hedged")
    checks.append(
        _check(
            "findings-hedged",
            "error",
            "Findings that involve a 'review' estimate are hedged; comparisons that involve an "
            "unreliable or suppressed estimate, or an interval of zero width, are dropped, "
            "not tested",
            not problems,
            problems=problems,
        )
    )

    # The sentences, through the claim checker.
    lang = str(method.get("lang", "en"))
    allow_independence = any(c.get("id") == "independence" for c in block.get("caveats", []))
    try:
        check_data = (
            _with_reference(
                data,
                Reference.from_dict(ref),
                Reference.from_dict(ref).per_series(len(data.series)),
            )
            if ref
            else data
        )
    except (KeyError, TypeError, ValueError):
        check_data = data
    errs: list[dict[str, Any]] = []
    warns: list[dict[str, Any]] = []
    for st in statements:
        use = check_data if st.get("family") == "outliers" else data
        for p in check_alt_text(st.get("text", ""), use, lang=lang):
            if p.severity == "error":
                errs.append(p.to_dict())
            elif not (p.kind == "independence" and allow_independence):
                warns.append(p.to_dict())
    checks.append(
        _check(
            "findings-claims",
            "error",
            "No number or recognised claim in the finding sentences contradicts the data",
            not errs,
            problems=errs,
        )
    )
    checks.append(
        _check(
            "findings-unchecked-claims",
            "warning",
            "Claims in the finding sentences that the checker could not test",
            not warns,
            problems=warns,
        )
    )
    return checks
