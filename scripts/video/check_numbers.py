# ruff: noqa: RUF001  (the script uses en dashes and minus signs; claims must match it exactly)
"""Check every number in the walkthrough script against the published files.

Usage: uv run python -I scripts/video/check_numbers.py [--local] [FILE ...]

FILE defaults to data/sources/video/script.md (git-ignored); pass the transcript and
SRT too once they exist.
Reads the live site's JSON (or site/public/data with --local) and the committed
P5 CSVs. Exit 1 if a claim's text is missing from the script, a claim's value
differs from the published one, or a caption (or "Correction:" footnote) line has a
number no claim covers.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LIVE = "https://batestguy.github.io/curb-cut/data/"
LOCAL = "--local" in sys.argv
files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or [
    ROOT / "data/sources/video/script.md"
]


def site(name: str):
    if LOCAL:
        return json.loads((ROOT / "site/public/data" / name).read_text(encoding="utf-8"))
    with urllib.request.urlopen(LIVE + name, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def rows(name: str) -> dict[str, dict[str, str]]:
    with (ROOT / "data/public/aggregates" / name).open(encoding="utf-8") as f:
        return {r["estimate_id"]: r for r in csv.DictReader(f)}


prev = site("prevalence.json")
pov = site("poverty.json")
spat = site("spatial.json")
chart = site("charts/prevalence_by_state.json")
jon = site("charts/national_by_type.json")
mpi = rows("p5_mpi_estimates.csv")
ghs = rows("p5_ghs_estimates.csv")
summ = pov["summary"]["mpi"]
der = pov["derived"]

nat = prev["national"]
moran = next(m for m in spat["moran"] if m["role"] == "primary")
cmp_ = chart["findings"]["comparisons"]
ref = chart["findings"]["reference"]["values"][0]
out = [
    next(x for x in (c["a"], c["b"]) if not x["reference"])
    for c in cmp_
    if c["family"] == "outliers" and c["supported"]
]
vals = dict(zip(chart["data"]["categories"], chart["data"]["series"][0]["values"], strict=True))
m = re.search(r"Total: ([\d,]+)", jon["alt_text"])
assert m, "JONAPWD total not in the chart description"
jon_total = int(m[1].replace(",", ""))
JONAPWD_PRINTED = 34901403  # the publication's printed national total (docs/STATUS.md, P1)
jon_pct = next(c["value_percent"] for c in prev["comparison"] if c["figure_id"] == "jonapwd_2025")
methodology = (ROOT / "site/methodology.html").read_text(encoding="utf-8")
status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
ndhs_cells = 1360 if "reproduces all 1,360 transcribed report cells" in status else -1
svy_cells = 5816 if "covers all 5,816 published DHS cells" in status else -1
p = lambda x: 100 * float(x)  # noqa: E731

# (text in the script, value it states, published value, tolerance)
CLAIMS = [
    ("thirty-five million", 35, jon_total / 1e6, 0.5),
    # JONAPWD PDF p. 7 (docs/verification.md D66): NPC 2025 projection x 15% = printed total;
    # the per-state sum (jon_total) is 3 higher, as printed (STATUS P1).
    ("232,676,020 (NPC 2025 projection)", 232676020 * 0.15, JONAPWD_PRINTED, 0.5),
    ("= 34,901,403", 34901403, jon_total, 3),
    ("about two hundred and thirty-three million", 233, 232.676020, 0.5),
    ("× 15% (WHO and World Bank global estimate)", 15, jon_pct, 0),
    ("fifteen percent", 15, jon_pct, 0),
    ("3.0% (95% CI 2.8–3.2)", 3.0, p(nat["estimate"]), 0.05),
    ("3.0% (95% CI 2.8–3.2)", 2.8, p(nat["ci_low"]), 0.05),
    ("3.0% (95% CI 2.8–3.2)", 3.2, p(nat["ci_high"]), 0.05),
    ("Three in a hundred", 3, p(nat["estimate"]), 0.5),
    (
        "any difficulty 15.5%",
        15.5,
        15.5
        if "15.5% of people aged 15 and over, against 2.8% at the cut-off" in methodology
        else -1,
        0,
    ),
    ("cut-off 2.8%", 2.8, 2.8 if "against 2.8% at the cut-off" in methodology else -1, 0),
    ("fifteen in a hundred people aged fifteen", 15, 15.5, 0.5),
    ("1,360 official report cells", 1360, ndhs_cells, 0),
    ("(5,816 cells)", 5816, svy_cells, 0),
    ("ages 15+", 15, 15 if "aged 15 and over" in methodology else -1, 0),
    ("six to seventeen", 6, p(mpi["primary"]["ci_low"]), 0.5),
    ("six to seventeen", 17, p(mpi["primary"]["ci_high"]), 0.5),
    (
        "between 2018 and 2023",
        2018,
        2018
        if "2018" in ghs["ghs_dwork"]["dataset_version"]
        and "2023" in ghs["ghs_dwork"]["dataset_version"]
        else -1,
        0,
    ),
    ("Taraba 11.3%", 11.3, vals["Taraba"], 0.05),
    ("Lagos 0.8%", 0.8, vals["Lagos"], 0.05),
    ("Taraba it's about eleven in a hundred", 11, vals["Taraba"], 0.5),
    ("in Lagos, under one", 1, 1 if vals["Lagos"] < 1 else -1, 0),
    ("7 above", 7, sum(x["value"] > ref for x in out), 0),
    ("Seven states", 7, sum(x["value"] > ref for x in out), 0),
    ("12 below", 12, sum(x["value"] < ref for x in out), 0),
    ("twelve clearly below", 12, sum(x["value"] < ref for x in out), 0),
    ("FDR 5%", 5, 100 * chart["findings"]["method"]["q"], 0),
    ("Moran's I 0.13", 0.13, moran["moran_i"], 0.005),
    ("adjusted p 0.105", 0.105, moran["p_bh"], 0.0005),
    ("37 states", 37, len(vals), 0),
    ("+11.7 points (95% CI 6.1–17.2)", 11.7, p(mpi["primary"]["estimate"]), 0.05),
    ("+11.7 points (95% CI 6.1–17.2)", 6.1, p(mpi["primary"]["ci_low"]), 0.05),
    ("+11.7 points (95% CI 6.1–17.2)", 17.2, p(mpi["primary"]["ci_high"]), 0.05),
    ("about twelve percentage points", 12, p(mpi["primary"]["estimate"]), 0.5),
    ("100 placebo shuffles", 100, summ["placebo_n"]["value"], 0),
    ("a hundred times", 100, summ["placebo_n"]["value"], 0),
    ("mean 0.6 points", 0.6, p(summ["placebo_mean"]["value"]), 0.05),
    ("p = 0.010", 0.010, summ["placebo_empirical_p"]["value"], 0.0005),
    ("robustness value 1.8%", 1.8, p(summ["rv"]["value"]), 0.05),
    ("−26.4 points", -26.4, p(ghs["ghs_dwork"]["estimate"]), 0.05),
    ("(−33.2 to −19.7)", -33.2, p(ghs["ghs_dwork"]["ci_low"]), 0.05),
    ("(−33.2 to −19.7)", -19.7, p(ghs["ghs_dwork"]["ci_high"]), 0.05),
    ("about twenty-six points", -26, p(ghs["ghs_dwork"]["estimate"]), 0.5),
    (
        "consumption: survey cannot show a difference",
        0,
        0
        if float(ghs["ghs_dlog_consumption"]["ci_low"])
        < 0
        < float(ghs["ghs_dlog_consumption"]["ci_high"])
        else 1,
        0,
    ),
    (
        "2018/19 → 2023/24",
        2018,
        2018
        if "2018" in ghs["ghs_dwork"]["dataset_version"]
        and "2023" in ghs["ghs_dwork"]["dataset_version"]
        else -1,
        0,
    ),
    (
        "osf.io/kes3p",
        0,
        0 if "kes3p" in (ROOT / "docs/preregistration.md").read_text(encoding="utf-8") else 1,
        0,
    ),
    ("Nigeria DHS 2024", 2024, 2024 if "2024" in prev["source"] else -1, 0),
    ("NBS MPI 2021", 2021, 2021 if mpi["primary"]["source"] == "mpi2021" else -1, 0),
    (
        "JONAPWD 2025",
        2025,
        2025 if any(c["label"] == "JONAPWD 2025" for c in prev["comparison"]) else -1,
        0,
    ),
    ("adults 18+", 18, 18 if prev["age_group"] == "18+" else -1, 0),
]
lhci = (ROOT / "site/lighthouserc.cjs").read_text(encoding="utf-8")
ext = next(
    c
    for c in cmp_
    if c["family"] == "extremes" and {c["a"]["category"], c["b"]["category"]} == {"Taraba", "Abia"}
)
CLAIMS += [
    ("73 comparisons tested", 73, chart["findings"]["checked"], 0),
    ("seventy-three comparisons", 73, chart["findings"]["checked"], 0),
    ("20 significant", 20, chart["findings"]["supported"], 0),
    ("only twenty held up", 20, chart["findings"]["supported"], 0),
    ("Taraba vs Abia: no detectable difference", 0, 0 if not ext["supported"] else 1, 0),
    (
        "Taraba, the highest, can't be told apart from Abia",
        0,
        0 if not ext["supported"] and max(vals, key=vals.get) == "Taraba" else 1,
        0,
    ),
    (
        "can't show one for education or living standards",
        0,
        0
        if all(
            float(mpi[k]["ci_low"]) < 0 < float(mpi[k]["ci_high"])
            for k in ("s4_education", "s4_living_standards")
        )
        else 1,
        0,
    ),
    (
        "clear for health and for work and shocks",
        0,
        0 if all(float(mpi[k]["ci_low"]) > 0 for k in ("s4_health", "s4_work_and_shocks")) else 1,
        0,
    ),
    ("(difference 0.70, needs more than 3.74)", 0.70, ext["difference"], 0.005),
    ("(difference 0.70, needs more than 3.74)", 3.74, ext["threshold"], 0.005),
    (
        "accessibility 100 on every page type",
        100,
        100 if "'categories:accessibility': ['error', { minScore: 1 }]" in lhci else -1,
        0,
    ),
    (
        "Lighthouse accessibility 100",
        100,
        100 if "'categories:accessibility': ['error', { minScore: 1 }]" in lhci else -1,
        0,
    ),
]
# Optional claims (the sensitivity benchmark; the NBS gap) if a file mentions them.
OPTIONAL = [
    ("10.7–12.7", 10.7, p(der["benchmarks"]["min"]), 0.05),
    ("10.7–12.7", 12.7, p(der["benchmarks"]["max"]), 0.05),
    ("10.1 vs 9.6", 10.1, summ["table7_gap"]["value"], 0.05),
    ("10.1 vs 9.6", 9.6, summ["table7_gap_nbs"]["value"], 0),
    # The video's on-screen correction footnotes (make_video.py).
    ("6 to 17 percentage points (95% CI 6.1–17.2)", 6, p(mpi["primary"]["ci_low"]), 0.5),
    ("6 to 17 percentage points (95% CI 6.1–17.2)", 17, p(mpi["primary"]["ci_high"]), 0.5),
    ("6 to 17 percentage points (95% CI 6.1–17.2)", 6.1, p(mpi["primary"]["ci_low"]), 0.05),
    ("6 to 17 percentage points (95% CI 6.1–17.2)", 17.2, p(mpi["primary"]["ci_high"]), 0.05),
    ("the 73 comparisons", 73, chart["findings"]["checked"], 0),
    # Wordings of earlier script drafts and of the author's recording (the transcript).
    ("thirty-seven states", 37, len(vals), 0),
    ("thirteen hundred and sixty", 1360, ndhs_cells, 0),
    (
        "scores a hundred on Lighthouse's accessibility check",
        100,
        100 if "minScore: 1" in lhci else -1,
        0,
    ),
    (
        "score a hundred on the Lighthouse accessibility checks",
        100,
        100 if "minScore: 1" in lhci else -1,
        0,
    ),
    ("about twenty held up", 20, chart["findings"]["supported"], 0),
]

NUM = re.compile(r"[−-]?\d[\d,]*(?:\.\d+)?")
bad = 0
for f in files:
    text = f.read_text(encoding="utf-8")
    if f.suffix == ".srt":  # one line per cue: a caption's line breaks are only wrapping
        cues = text.strip().split("\n\n")
        text = "\n".join(" ".join(b.split("\n")[2:]) for b in cues)
    used = []
    for snippet, stated, actual, tol in CLAIMS:
        if snippet not in text:
            if f.name == "script.md":
                print(f"MISSING  {f.name}: {snippet!r}")
                bad += 1
            continue
        used.append(snippet)
        if abs(stated - actual) > tol + 1e-9:
            print(f"WRONG    {f.name}: {snippet!r} says {stated}, published {actual:.4g}")
            bad += 1
    for snippet, stated, actual, tol in OPTIONAL:
        if snippet in text:
            used.append(snippet)
            if abs(stated - actual) > tol + 1e-9:
                print(f"WRONG    {f.name}: {snippet!r} says {stated}, published {actual:.4g}")
                bad += 1
    # Every number on a caption or correction-footnote line must sit inside a checked snippet.
    for line in text.splitlines():
        if not line.lstrip().startswith(("CAPTION:", "Correction:")):
            continue
        rest = line
        for s in sorted(set(used), key=len, reverse=True):
            rest = rest.replace(s, " ")
        rest = re.sub(r"^\s*CAPTION:\s*\d\.\s*", "", rest)  # list markers in act 5
        left = [n for n in NUM.findall(rest.replace("CAPTION:", "").replace("Correction:", ""))]
        if left:
            print(f"UNCHECKED {f.name}: {left} in {line.strip()!r}")
            bad += 1
    print(f"{f.name}: {len(set(used))} claims checked")

print("FAIL" if bad else "OK: every number matches the published files")
sys.exit(1 if bad else 0)
