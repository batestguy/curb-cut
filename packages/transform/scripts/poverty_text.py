"""Numbers and wording shared by the P5 poverty page and the policy brief.

Both are built from ``site/public/data/poverty.json`` (``export_marts.py``), so no number is
typed by hand. :class:`Numbers` looks every value up by its path in that document and
formats it; in HTML mode each number is wrapped in ``<span class="n" data-key=...>`` so the
site tests can check every shown number against the exported data (``site/tests/
poverty.spec.js``). The sentences that must appear wherever the result appears (the
pre-registration's section 7: the two reasons, the misclassification note, the measure's
name) live here once.

:func:`forbidden` is the wording guard: the page and the brief are refused if they say
"effect of disability", "impact of", "causes", "caused by", "event study", or "causal
effect" other than in "not a causal effect".
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any

OSF_TEMPLATE = "Secondary Data Preregistration"
REPO = "https://github.com/batestguy/curb-cut"
PREREG_AT_FREEZE = f"{REPO}/blob/p5-freeze/docs/preregistration.md"

FORBIDDEN = (
    r"effect of disability",
    r"impact of",
    r"\bcauses\b",
    r"caused by",
    r"event stud(?:y|ies)",
)
CAUSAL_EFFECT = re.compile(r"causal effects?", re.I)
ALLOWED_CAUSAL = re.compile(r"not a causal effect$", re.I)


def forbidden(text: str) -> list[str]:
    """Every forbidden phrase in ``text`` (case-insensitive), as found."""
    flat = re.sub(r"\s+", " ", text)
    found = [m.group(0) for p in FORBIDDEN for m in re.finditer(p, flat, re.I)]
    for m in CAUSAL_EFFECT.finditer(flat):
        if not ALLOWED_CAUSAL.search(flat[: m.end()]):
            found.append(m.group(0))
    return found


def fixed(value: float, decimals: int) -> str:
    """Fixed decimals, never "-0.0". Python and JavaScript round the same double the same
    way, so the site tests can redo this."""
    text = f"{value:.{decimals}f}"
    if float(text) == 0:
        text = text.lstrip("-")
    return text


class Numbers:
    """Look values up in the poverty payload by path ("estimates.primary.ci_low") and
    format them; ``html=True`` wraps each in a checkable span."""

    def __init__(self, payload: Mapping[str, Any], *, html_mode: bool) -> None:
        self.payload = payload
        self.html = html_mode

    def raw(self, path: str) -> Any:
        node: Any = self.payload
        for part in path.split("."):
            node = node[part]
        return node

    def _wrap(self, path: str, text: str, factor: float, decimals: int, fmt: str) -> str:
        if not self.html:
            return text
        return (
            f'<span class="n" data-key="{html.escape(path)}" data-factor="{factor:g}" '
            f'data-decimals="{decimals}" data-format="{fmt}">{html.escape(text)}</span>'
        )

    def num(self, path: str, factor: float = 100, decimals: int = 1) -> str:
        value = self.raw(path)
        if value is None:
            raise ValueError(f"{path} is missing or suppressed")
        return self._wrap(path, fixed(factor * float(value), decimals), factor, decimals, "fixed")

    def count(self, path: str) -> str:
        value = self.raw(path)
        if value is None:
            raise ValueError(f"{path} is missing or suppressed")
        return self._wrap(path, f"{round(float(value)):,}", 1, 0, "int")

    def text(self, path: str) -> str:
        value = self.raw(path)
        if value is None:
            raise ValueError(f"{path} is missing")
        return self._wrap(path, str(value), 1, 0, "text")

    # Shorthands --------------------------------------------------------------------------

    def est(self, eid: str, field: str = "estimate", decimals: int = 1) -> str:
        factor = self.raw(f"estimates.{eid}.display_factor")
        return self.num(f"estimates.{eid}.{field}", factor, decimals)

    def ci(self, eid: str, decimals: int = 1) -> str:
        return f"{self.est(eid, 'ci_low', decimals)} to {self.est(eid, 'ci_high', decimals)}"

    def s(self, item: str, analysis: str = "mpi") -> str:
        return f"summary.{analysis}.{item}.value"

    def share(self, item: str, analysis: str = "mpi", decimals: int = 1) -> str:
        return f"{self.num(self.s(item, analysis), 100, decimals)}%"

    def value(self, item: str, analysis: str = "mpi", decimals: int = 2) -> str:
        return self.num(self.s(item, analysis), 1, decimals)

    def n(self, item: str, analysis: str = "mpi") -> str:
        return self.count(self.s(item, analysis))

    def p(self, path: str) -> str:
        """A p-value to 4 decimals; below 0.0001 it reads "<0.0001"."""
        value = self.raw(path)
        if value is None:
            raise ValueError(f"{path} is missing or suppressed")
        shown = "<0.0001" if float(value) < 0.0001 else fixed(float(value), 4)
        return self._wrap(path, shown, 1, 4, "p")

    def flag(self, item: str, analysis: str = "mpi") -> bool:
        return bool(self.raw(self.s(item, analysis)))

    def link(self, text: str, href: str) -> str:
        if self.html:
            return f'<a href="{html.escape(href)}">{text}</a>'
        return f"[{text}]({href})"


# --- Sentences that must appear wherever the result appears (section 7) ----------------------

MEMBER = "a member aged 5 or older who has a severe difficulty"
MEASURE = "MPI's own disability questions (not the Washington Group's DISABILITY3 measure)"


def headline(nums: Numbers) -> str:
    """The registered wording (section 7) with the section 4 verdict, from the data."""
    verdict = nums.raw("derived.verdict")
    est, ci = nums.est("primary"), nums.ci("primary")
    interval = f"(95% confidence interval {ci} points)"
    who = f"People in households with {MEMBER}"
    if verdict == "higher":
        return (
            f"{who} are {est} percentage points more likely to be multidimensionally poor "
            f"than people in comparable households {interval}."
        )
    if verdict == "lower":
        return (
            f"{who} are {est} percentage points less likely to be multidimensionally poor "
            f"than people in comparable households {interval}."
        )
    if verdict == "no meaningful difference":
        return (
            f"{who} are about as likely to be multidimensionally poor as people in comparable "
            f"households: the difference is {est} percentage points {interval}, within 2 "
            "points either way."
        )
    return (
        "The survey cannot tell whether people in households with "
        f"{MEMBER} are more or less likely to be multidimensionally poor than people in "
        f"comparable households: the difference is {est} percentage points {interval}."
    )


def verdict_rule(nums: Numbers) -> str:
    """Why the headline is worded as it is (section 4), from the data."""
    verdict = nums.raw("derived.verdict")
    if verdict in ("higher", "lower"):
        side = "above" if verdict == "higher" else "below"
        lo, hi = nums.raw("estimates.primary.ci_low"), nums.raw("estimates.primary.ci_high")
        beyond = (lo > 0.02) if verdict == "higher" else (hi < -0.02)
        extra = (
            f", and wholly {side} the smallest difference of interest fixed in advance, "
            f"{'+' if verdict == 'higher' else '-'}2 points"
            if beyond
            else ""
        )
        return (
            "The wording follows a rule fixed before the analysis: the whole 95% interval "
            f"lies {side} zero{extra}."
        )
    if verdict == "no meaningful difference":
        return (
            "The wording follows a rule fixed before the analysis: the whole 95% interval "
            "lies within 2 points either way."
        )
    return (
        "The wording follows a rule fixed before the analysis: the 95% interval includes "
        "zero but goes beyond 2 points, so the result is inconclusive."
    )


def comparison_rates(nums: Numbers) -> str:
    return (
        f"In comparable households without such a member, {nums.num('estimates.primary.mu0')}% "
        "of people are multidimensionally poor. With the difference added, the figure for "
        f"households with such a member is {nums.num('derived.primary_implied')}%."
    )


def reasons(nums: Numbers, sensitivity_href: str) -> list[str]:
    """The two mandatory reasons (section 7)."""
    return [
        "Poverty can come first. Earlier poverty can lead to disability, for example "
        "through poor nutrition, unsafe work or little health care, and earlier poverty also "
        "goes with poverty today. A survey at one point in time cannot tell which came first.",
        "Some shared factors were not measured. Religion, ethnicity, conflict, local health "
        "services and the household's earlier poverty are not in the survey, and a factor "
        "like these could account for part or all of the difference. "
        + nums.link("How strong such a factor would need to be", sensitivity_href)
        + ".",
    ]


def misclassification(nums: Numbers) -> str:
    """Section 3.2 / 7: the exposure misclassification, with S5 as the other bound."""
    return (
        f"Who counts as having a severe difficulty comes from {MEASURE}. For seeing, hearing "
        "and walking, the survey asks how hard it is only of people who said yes to a "
        "difficulty and use glasses, a hearing aid or walking equipment. People who said yes "
        "but have no aid were not asked, and here they count as not severe. Aids cost money, "
        "so this probably puts some severely disabled people from poorer households in the "
        "comparison group; the pre-registration expected this to pull the estimate towards "
        "zero. Counting all of them as severe instead (secondary question S5, "
        f"{nums.count('estimates.s5_unasked_severe.n_exposed')} households with such a "
        f"member) gives {nums.est('s5_unasked_severe')} points "
        f"(95% confidence interval {nums.ci('s5_unasked_severe')}). The pre-registration "
        "treats the two definitions as two bounds. S5's group is much larger and includes "
        "people whose difficulty was never graded, so many of them may have only some "
        "difficulty."
    )
