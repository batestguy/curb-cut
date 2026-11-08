# ruff: noqa: RUF001  (captions use en dashes and minus signs; they must match script.md exactly)
"""Assemble the narrated walkthrough from the author's voice files, the site and act 5.

Usage: uv run python -I scripts/video/make_video.py [--no-shots]
  -> data/sources/video/out/curbcut-walkthrough.mp4 (+ .en.srt, -transcript.md)
     data/sources/video/out/curbcut-1min.mp4 (+ .en.srt)
Everything is git-ignored and local; nothing is uploaded. Steps:
  1. run the public demos (demo_library.py, `disability-access-charts check --strict`) and
     `gh run view` for the terminal cards; read the captions from script.md;
  2. node shots.mjs: screenshots of the site (local build, checked against the live site) and
     the cards and overlays;
  3. word timestamps (whisper_words.py, cached in build/words.json);
  4. per act: trim the voice to its speech plus 0.4 s, loudness -16 LUFS (TP -1.5), shots cut on
     the words with a slow zoom, captions and correction footnotes timed to the words;
  5. title, acts, act 5 (clips/act5.mp4, as it is), end card, joined with 0.5 s crossfades;
     closed captions (SRT, also muxed as a mov_text track) and a transcript.
No restricted data is read: the shots are the public site, and the two validation scripts that
need microdata are shown as cards quoting docs/verification.md.
"""

from __future__ import annotations

import difflib
import itertools
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VID = ROOT / "data/sources/video"
VOICE = VID / "voice"
BUILD = VID / "build"
OUT = VID / "out"
ACT5 = VID / "clips/act5.mp4"
FPS = 30
XF = 0.2  # crossfade between acts (short: several joins are between text-heavy screens)
SXF = 0.2  # crossfade between shots within an act
LEAD, TAIL, PAD = 0.4, 0.4, 0.35  # speech margins kept; digital silence added after the tail
ZOOM = 0.04  # slow zoom per shot

# What the author says, lightly corrected for the speech recogniser's mishearings (listed in
# the transcript's note). Square brackets are notes for the transcript only: not spoken, given
# no time of their own, and left out of the SRT (which repeats each footnote as its own cue).
COR = {
    "abia": "Correction: Taraba can't be told apart from Abia: their intervals overlap.",
    # findings.families: 2 extremes + 34 neighbours in the ranking + 37 against Nigeria = 73.
    "pairs": "Correction: the 73 comparisons are states next to each other in the ranking, the "
    "highest and lowest, and each state against the national figure.",
    "range": "Correction: 6 to 17 percentage points (95% CI 6.1–17.2).",
    "fh": "Correction: the small-area model failed the checks set in advance.",
}
TEXT = {
    "act1": "How many disabled people live in Nigeria? You often hear thirty-five million. "
    "That's a figure from the Joint National Association of People with Disabilities in 2025, "
    "which itself is an estimate from the global prevalence of fifteen percent of the "
    "population in Nigeria. That global rate was found in a study by the World Bank and the "
    "World Health Organization in 2011. My name is Jerry Bannister. I'm a statistician in "
    "Bauchi and a wheelchair user. Come along with me to see what the surveys actually "
    "measured.",
    "act2": "Nigeria's 2024 Demographic and Health Survey asked the Washington Group questions. "
    "That's the international standard. Three in a hundred adults have a lot of difficulty or "
    "completely lack the ability to engage in seeing, hearing, walking, remembering, caring for "
    "themselves or communicating. The official report, counting those with any difficulty at "
    "all, gets about fifteen in a hundred people that are aged fifteen and over. But that's a "
    "different question. The report already publishes state figures for men and women "
    "separately, without any margins of error. I combined them into one figure per state, "
    "which roughly doubles each state's sample, and gave every state a confidence interval "
    "using the survey data and sampling weights.",
    "act3": "The states are not alike. In Taraba, it's about eleven in a hundred. In Lagos, it's "
    "under one in a hundred. Seven states are clearly above the national figure, and twelve "
    "clearly below after correcting for multiple testing. But two things I expected didn't "
    "hold. Neighbouring states don't show a clear pattern of being alike. A spatial test was "
    "conducted, Moran's I, and it found none of the claims survives correction. As a "
    "follow-up, a small-area model meant to sharpen the state figures failed the checks I set "
    "in advance {fh}, so I also left it out.",
    "act4a1": "So, does disability go with poverty? I registered the plan publicly before I "
    "split poverty by disability. Our results were expected. Using double machine learning on "
    "the national poverty survey, people in households with a member who has severe difficulty "
    "are about twelve percentage points more likely to be poor on the national "
    "multidimensional poverty index than people in comparable households. The range is six to "
    "seventeen percent {range}. When I shuffled who was disabled a hundred "
    "times, the fake results averaged almost about zero.",
    "act4a2": "But I'll be honest about the weak spots. In the worst case, a hidden factor I "
    "didn't measure, even a small one, could explain it away. A factor as strong as the head of "
    "household's education would barely move it, but it would be impossible to rule out "
    "something stronger. So it's an association, and not proof of cause. A smaller panel "
    "survey looks at work. Among people whose severe difficulty began between 2018 and 2023, "
    "the proportion working fell about twenty-six points more than among comparable people "
    "whose difficulty didn't begin during that time period. That part is exploratory, and it "
    "can't say which came first.",
    "act4b": "A lot of what I tested wasn't significant, and the site says so. The state chart "
    "tested seventy-three comparisons: neighbouring states and each state were tested against "
    "the national figure {pairs}. Only about twenty held up after corrections "
    "for multiple testing. Taraba, being the highest, can't [this word is unclear in the "
    "recording; the on-screen footnote states the finding] be told apart "
    "from Abia, the second highest. Looking at where the poverty difference sits, the "
    "deprivation gap is clear for health, for work and shocks, but the survey can't show one "
    "for education or living standards. The panel survey also fails to show a difference in "
    "how household consumption changed. As a check, the site can't deploy unless every page "
    "and its types score a hundred on the Lighthouse accessibility checks.",
    "act5b": "This is my open-source Python library. It's called disability-access-charts. It "
    "builds each chart with a description written from the data, and then checks that text "
    "against the data, with intervals and all. Let's take a look. The check: “Taraba has a "
    "higher rate than Lagos” passes, but “Taraba has a higher rate than Abia” is rejected. The "
    "gap is small, and the uncertainty doesn't allow it. The site's descriptions are built "
    "only from the differences that held up, and this check runs in strict mode on every chart "
    "before the site is built, as a second guard.",
    "act6": "Every chart describes itself, and my open-source library checks the numbers and "
    "comparisons in those words against the data before the site is built. It's free, every "
    "figure names its source, and it hasn't yet been tested by a regular screen-reader user. "
    "If you use one, tell me what works and what doesn't. Thank you.",
}
# Each "{k}" marker becomes "[correction: <footnote text>]".
for _k in TEXT:
    for _c, _v in COR.items():
        TEXT[_k] = TEXT[_k].replace(
            f"{{{_c}}}", "[correction:" + _v.split(":", 1)[1].rstrip(".") + "]"
        )

# Acts: voice files, the script.md section its captions come from, shots (still, phrase where
# it starts), captions (index in the section, start phrase, end phrase or None = act end) and
# correction footnotes (key, phrase). Phrases are matched in TEXT.
ACTS = [
    {
        "id": "act1",
        "voice": ["act1"],
        "section": "Act 1",
        "shots": [("jonapwd", None), ("jonapwd-chart", "which itself"), ("home-top", "My name")],
        "captions": [(0, "That's a figure", "My name")],
        "corrections": [],
    },
    {
        "id": "act2",
        "voice": ["act2"],
        "section": "Act 2",
        "shots": [
            ("home-top", None),
            ("comparison", "The official report"),
            ("meth-new", "The report already"),
            ("card-ndhs", "I combined"),
            ("card-svy", "and gave every"),
        ],
        "captions": [
            (0, "Three in a hundred", "The official report"),
            (1, "The official report", "The report already"),
            (2, "I combined", None),
        ],
        "corrections": [],
    },
    {
        "id": "act3",
        "voice": ["act3"],
        "section": "Act 3",
        "shots": [
            ("dots", None),
            ("dots-findings", "Seven states"),
            ("map", "But two things"),
            ("spatial", "A spatial test"),
            ("meth-fh", "As a follow-up"),
        ],
        "captions": [
            (0, "In Taraba", "But two things"),
            (1, "Neighbouring states", "As a follow-up"),
            (2, "As a follow-up", None),
        ],
        "corrections": [("fh", "failed the checks")],
    },
    {
        "id": "act4",
        "voice": ["act4a1", "act4a2"],
        "section": "Act 4",
        "shots": [
            ("pov-top", None),
            ("osf", "I registered"),
            ("pov-headline-chart", "Using double"),
            ("pov-refute", "When I shuffled"),
            ("pov-sens", "But I'll be honest"),
            ("pov-bench", "A factor as strong"),
            ("pov-ghs", "A smaller panel"),
            ("pov-ghs-cons", "Among people whose"),
        ],
        "captions": [
            (0, "Using double", "When I shuffled"),
            (1, "When I shuffled", "But I'll be honest"),
            (2, "In the worst case", "A smaller panel"),
            (3, "A smaller panel", None),
        ],
        "corrections": [("range", "The range is")],
    },
    {
        "id": "act4b",
        "voice": ["act4b"],
        "section": "Act 4b",
        "shots": [
            ("dots-findings", None),
            ("dots", "Taraba, being"),
            ("pov-dims", "Looking at where"),
            ("pov-ghs-cons", "The panel survey"),
            ("code-lhci", "As a check"),
            ("gha", "every page"),
        ],
        "captions": [
            (0, "The state chart", "Looking at where"),
            (1, "Looking at where", "As a check"),
            (2, "As a check", None),
        ],
        "corrections": [("pairs", "neighbouring states and each"), ("abia", "Taraba, being")],
    },
    {
        "id": "act5b",
        "voice": ["act5b"],
        "section": "Act 5b",
        "shots": [
            ("pypi", None),
            ("term-demo-0", "Let's take a look"),
            ("term-demo-1", "The check:"),
            ("term-demo-2", "but “Taraba"),
            ("code-checker", "The site's descriptions"),
            ("term-check", "and this check runs"),
        ],
        "captions": [
            (0, "This is my", "Let's take a look"),
            (1, "The check:", "The site's descriptions"),
            (2, "and this check runs", None),
        ],
        "corrections": [],
    },
    {
        "id": "act6",
        "voice": ["act6"],
        "section": "Act 6",
        "shots": [("home-top", None)],
        "captions": [(0, "It's free", None)],
        "corrections": [],
    },
]
TITLE_SUB = "Nigerian disability data, measured"
END = ["batestguy.github.io/curb-cut", "pip install disability-access-charts"]
TITLE_S, END_S = 3.0, 4.0
FOOTNOTE_S = 5.0  # at least; a longer footnote stays up for 20 characters a second
# Full paths: on this machine a bare "ffprobe" can resolve to a broken entry earlier on PATH.
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def ff(*args):
    run([FFMPEG, "-hide_banner", "-v", "error", "-y", *map(str, args)])


def duration(path) -> float:
    r = run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
    )
    return float(r.stdout)


# ---------------------------------------------------------------- 1. inputs for the cards
def script_captions() -> dict[str, list[str]]:
    caps: dict[str, list[str]] = {}
    section = None
    for line in (VID / "script.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (Act \w+):", line)
        if m:
            section = m[1]
        elif line.startswith("CAPTION:") and section:
            caps.setdefault(section, []).append(line[len("CAPTION:") :].strip())
    return caps


def source_lines(path: Path, first: int, last: int) -> list[list]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [[n, lines[n - 1]] for n in range(first, last + 1)]


def terminal() -> dict:
    demo_cmd = "uv run python -I scripts/video/demo_library.py"
    demo = run(demo_cmd.split(), cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    charts = sorted(
        p.relative_to(ROOT).as_posix() for p in (ROOT / "site/public/data/charts").glob("*.json")
    )
    check = subprocess.run(
        ["uv", "run", "disability-access-charts", "check", "--strict", *charts],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    t = {
        "demo_cmd": demo_cmd,
        "demo": demo.stdout.rstrip(),
        "check_cmd": "uv run disability-access-charts check --strict "
        "site/public/data/charts/*.json",
        "check": (check.stdout + check.stderr).rstrip().replace("\\", "/"),
        "check_exit": check.returncode,
        "gha": None,
    }
    try:
        runs = json.loads(
            run(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    "ci.yml",
                    "--branch",
                    "main",
                    "--limit",
                    "1",
                    "--json",
                    "databaseId,conclusion,url",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            ).stdout
        )[0]
        view = run(
            ["gh", "run", "view", str(runs["databaseId"])],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
        t["gha"] = view.split("ANNOTATIONS")[0].strip()
        t["gha_cmd"] = f"gh run view {runs['databaseId']}"
        t["gha_url"] = runs["url"]
        t["gha_conclusion"] = runs["conclusion"]
    except (subprocess.CalledProcessError, OSError, IndexError, KeyError) as e:
        print("gh run view failed:", e)
    return t


def api(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        print("could not read", url, e)
        return None


def pypi_card() -> dict:
    """Used when the PyPI page cannot be screenshotted (it challenges automated browsers)."""
    d = api("https://pypi.org/pypi/disability-access-charts/json")
    if d is None:
        sys.exit("PyPI's JSON API did not answer: no PyPI card")
    i = d["info"]
    up = min(u["upload_time_iso_8601"] for u in d["urls"])[:10]
    return {
        "fallback_for": "pypi",
        "kicker": "PyPI · pypi.org/project/disability-access-charts",
        "title": "pip install disability-access-charts",
        "body": f"Version {i['version']}, released {up}. Licence: "
        f"{i.get('license_expression') or i.get('license')}. Python {i['requires_python']}. "
        f"“{i['summary']}”",
        "src": "From PyPI's JSON API on the day the video was built (pypi.org shows automated "
        "browsers a challenge page, so the page itself could not be screenshotted).",
    }


def osf_card() -> dict:
    """Used when the OSF page does not render in time (a heavy app on a slow connection)."""
    d = api("https://api.osf.io/v2/registrations/kes3p/")
    if d is None:
        sys.exit("OSF's API did not answer: no OSF card")
    a = d["data"]["attributes"]
    return {
        "fallback_for": "osf",
        "kicker": "Registered before the analysis · osf.io/kes3p",
        "title": a["title"],
        "body": f"Registered {a['date_registered'][:10]} at {a['date_registered'][11:16]} UTC "
        f"({a['registration_supplement']}), public, before any poverty outcome was split by "
        "disability.",
        "src": "From OSF's public API on the day the video was built (the OSF page did not "
        "load in time for a screenshot).",
    }


def write_overlays() -> dict:
    caps = script_captions()
    term = terminal()
    if term["check_exit"] != 0:
        sys.exit("disability-access-charts check --strict failed: " + term["check"])
    spec = {
        "title_sub": TITLE_SUB,
        "end": END,
        "terminal": term,
        "gha": {"url": term.get("gha_url")} if term.get("gha_conclusion") == "success" else {},
        "captions": [],
        "corrections": [{"id": f"cor-{k}", "text": v} for k, v in COR.items()],
        "code": [
            {
                "id": "code-checker",
                "title": "packages/disability-access-charts/src/"
                "disability_access_charts/describe.py",
                "lines": source_lines(
                    ROOT
                    / "packages/disability-access-charts/src/disability_access_charts/describe.py",
                    399,
                    417,
                ),
                "highlight": [416, 417],
            },
            {
                "id": "code-lhci",
                "title": "site/lighthouserc.cjs (the deploy job needs this to pass)",
                "lines": source_lines(ROOT / "site/lighthouserc.cjs", 1, 2)
                + source_lines(ROOT / "site/lighthouserc.cjs", 9, 20)
                + source_lines(ROOT / "site/lighthouserc.cjs", 35, 37),
                "highlight": [1, 37],
            },
        ],
        "textcards": [
            {
                "id": "card-ndhs",
                "kicker": "Reproducing the official report",
                "title": "validate_ndhs: all 1,360 transcribed report cells match",
                "body": "All 112 cells of Table 14.1 and all 1,248 transcribed cells of Tables "
                "14.2.1 and 14.2.2 of the NDHS 2024 report (37 states, six zones, urban and "
                "rural, both sexes) match to the published decimal.",
                "src": "Result as recorded in docs/verification.md (D48), local run of "
                "2026-10-27. Not re-run for this video: it reads the licensed DHS microdata, "
                "which never leave the author's machine.",
            },
            {
                "id": "card-svy",
                "kicker": "Two independent implementations",
                "title": "crosscheck_svy: R survey and Python svy agree on all 5,816 cells",
                "body": "Every published DHS cell (state, zone and national, every sex and "
                "breakdown): estimates identical, unweighted counts identical, standard errors "
                "0.01% apart at the median and 2.19% at most.",
                "src": "Result as recorded in docs/verification.md (D48) and docs/STATUS.md. "
                "Not re-run for this video: it reads the licensed DHS microdata.",
            },
            pypi_card(),
            osf_card(),
        ],
    }
    for act in ACTS:
        texts = caps[act["section"]]
        for i, *_ in act["captions"]:
            spec["captions"].append({"id": f"cap-{act['id']}-{i}", "text": texts[i]})
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "overlays.json").write_text(
        json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return spec


# ---------------------------------------------------------------- 3. words and alignment
def whisper_words() -> dict:
    cache = BUILD / "words.json"
    if not cache.exists():
        run(
            [
                "uv",
                "run",
                "--no-project",
                "--python",
                "3.12",
                "--with",
                "faster-whisper",
                "python",
                "-I",
                str(HERE / "whisper_words.py"),
                str(cache),
            ],
            cwd=BUILD,
        )
    return json.loads(cache.read_text(encoding="utf-8"))


def key(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def align(text: str, words: list[dict]) -> list[dict]:
    """Give each token of the corrected text a start and end from the recogniser's words."""
    merged: list[dict] = []
    for w in words:
        if w["w"].strip().startswith("-") and merged:
            merged[-1] = {**merged[-1], "w": merged[-1]["w"] + w["w"].strip(), "e": w["e"]}
        else:
            merged.append({**w, "w": w["w"].strip()})
    toks = re.findall(r"\[[^\]]*\]\S*|\S+", text)
    spoken = [i for i, t in enumerate(toks) if not t.startswith("[")]
    sm = difflib.SequenceMatcher(
        None, [key(toks[i]) for i in spoken], [key(w["w"]) for w in merged], autojunk=False
    )
    times: dict[int, tuple[float, float]] = {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            times[spoken[a + k]] = (merged[b + k]["s"], merged[b + k]["e"])
    out = []
    for idx, t in enumerate(toks):
        out.append({"t": t, "s": None, "e": None, "note": t.startswith("[")})
        if idx in times:
            out[-1]["s"], out[-1]["e"] = times[idx]
    # Unmatched spoken tokens: spread evenly between their matched neighbours.
    sp = [i for i in range(len(out)) if not out[i]["note"]]
    j = 0
    while j < len(sp):
        if out[sp[j]]["s"] is not None:
            j += 1
            continue
        k = j
        while k < len(sp) and out[sp[k]]["s"] is None:
            k += 1
        lo = out[sp[j - 1]]["e"] if j > 0 else merged[0]["s"]
        hi = out[sp[k]]["s"] if k < len(sp) else merged[-1]["e"]
        n = k - j
        for m in range(n):
            out[sp[j + m]]["s"] = lo + (hi - lo) * m / n
            out[sp[j + m]]["e"] = lo + (hi - lo) * (m + 1) / n
        j = k
    for i, t in enumerate(out):  # notes take the time of the word before them
        if t["note"]:
            t["s"] = t["e"] = out[i - 1]["e"]
    return out


def find(tokens: list[dict], phrase: str) -> float:
    want = [key(p) for p in phrase.split()]
    spoken = [t for t in tokens if not t["note"]]
    keys = [key(t["t"]) for t in spoken]
    hits = [i for i in range(len(keys)) if keys[i : i + len(want)] == want]
    if len(hits) != 1:
        raise SystemExit(f"phrase {phrase!r}: {len(hits)} matches")
    return spoken[hits[0]]["s"]


# ---------------------------------------------------------------- 4. audio
def speech_bounds(wav: Path) -> tuple[float, float, float]:
    raw = run(
        [FFMPEG, "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True,
    ).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 320  # 20 ms
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    loud = db > np.percentile(db, 10) + 15
    run3 = np.convolve(loud.astype(int), np.ones(3, int), "valid") == 3  # 60 ms of speech
    idx = np.flatnonzero(run3)
    return idx[0] * 0.02, (idx[-1] + 3) * 0.02, len(x) / 16000


def loudnorm(src: Path, dst: Path) -> dict:
    # TP -2.0 before AAC encoding, which adds about 0.5 dB of true peak (-1.5 after).
    target = "I=-16:TP=-2.0:LRA=11"
    r = subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-i",
            str(src),
            "-af",
            f"loudnorm={target}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    block = r.stderr[r.stderr.rindex("{") :]
    m = json.loads(block[: block.index("}") + 1])
    ff(
        "-i",
        src,
        "-af",
        f"loudnorm={target}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
        f":offset={m['target_offset']},aresample=48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        dst,
    )
    return m


def act_audio(act: dict, words: dict) -> tuple[Path, list[dict], float, list[dict]]:
    """Trimmed, joined, normalised voice; the act's tokens on the act's own clock."""
    pieces, tokens, clock, info = [], [], 0.0, []
    for v in act["voice"]:
        wav = BUILD / "audio" / f"src-{v}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        if not wav.exists():
            ff("-i", VOICE / f"{v}.aac", "-ar", 48000, wav)
        s, e, d = speech_bounds(wav)
        w = words[v]
        t0, t1 = max(0.0, min(s, w[0]["s"]) - LEAD), min(d, max(e, w[-1]["e"]) + TAIL)
        info.append(
            {"file": v, "speech": [round(s, 2), round(e, 2)], "kept": [round(t0, 2), round(t1, 2)]}
        )
        for t in align(TEXT[v], w):
            tokens.append({**t, "s": t["s"] - t0 + clock, "e": t["e"] - t0 + clock})
        pieces.append((wav, t0, t1))
        clock += t1 - t0
    raw = BUILD / "audio" / f"act-{act['id']}-raw.wav"
    inputs, fc = [], []
    for i, (wav, t0, t1) in enumerate(pieces):
        inputs += ["-i", wav]
        # Mono: the phone's two channels are near-identical (correlation 0.97-0.98), and
        # slightly different channels made the AAC encoder overshoot full scale.
        fc.append(
            f"[{i}:a]atrim={t0:.3f}:{t1:.3f},asetpts=PTS-STARTPTS,"
            f"pan=mono|c0=0.5*c0+0.5*c1,highpass=f=70[p{i}]"
        )
    fc.append("".join(f"[p{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[c]")
    fc.append(f"[c]apad=pad_dur={PAD}[a]")
    ff(
        *inputs,
        "-filter_complex",
        ";".join(fc),
        "-map",
        "[a]",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        raw,
    )
    norm = BUILD / "audio" / f"act-{act['id']}.wav"
    m = loudnorm(raw, norm)
    info.append({"loudnorm_input_i": m["input_i"], "normalization_type": m["normalization_type"]})
    return norm, tokens, duration(norm), info


# ---------------------------------------------------------------- 4. video per act
def zoom_clip(frames: int, inward: bool, zoom: float = ZOOM) -> str:
    z = (
        f"1+{zoom}*on/{max(frames - 1, 1)}"
        if inward
        else f"{1 + zoom}-{zoom}*on/{max(frames - 1, 1)}"
    )
    return (
        f"scale=2560:1440,zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
        f":d=1:s=1280x720:fps={FPS},setsar=1,format=yuv420p"
    )


def render_act(act: dict, audio: Path, tokens: list[dict], dur: float) -> tuple[Path, list[dict]]:
    shots = BUILD / "shots"
    starts = [0.0] + [find(tokens, p) - 0.15 for _, p in act["shots"][1:]]
    ends = [*starts[1:], dur]
    inputs, fc, timeline = [], [], []
    for i, ((sid, _), b0, b1) in enumerate(zip(act["shots"], starts, ends, strict=True)):
        length = (b1 - b0) + (SXF / 2 if i > 0 else 0) + (SXF / 2 if i < len(starts) - 1 else 0)
        frames = round(length * FPS)
        inputs += [
            "-loop",
            "1",
            "-framerate",
            FPS,
            "-t",
            f"{frames / FPS:.4f}",
            "-i",
            shots / f"{sid}.png",
        ]
        fc.append(f"[{i}:v]{zoom_clip(frames, i % 2 == 0)}[s{i}]")
        timeline.append({"shot": sid, "start": round(b0, 2), "end": round(b1, 2)})
    last = "[s0]"
    for i in range(1, len(starts)):
        fc.append(
            f"{last}[s{i}]xfade=transition=fade:duration={SXF}"
            f":offset={starts[i] - SXF / 2:.4f}[x{i}]"
        )
        last = f"[x{i}]"
    n = len(starts)
    overlays = []
    for i, a, b in act["captions"]:
        t0 = find(tokens, a) - 0.1
        t1 = (find(tokens, b) - 0.35) if b else dur - 0.25
        overlays.append((BUILD / "overlays" / f"cap-{act['id']}-{i}.png", t0, t1, "caption", i))
    for k, phrase in act["corrections"]:
        show = max(FOOTNOTE_S, len(COR[k]) / MAX_CPS + 0.5)
        t0 = min(find(tokens, phrase) - 0.2, dur - show - 0.2)
        overlays.append((BUILD / "overlays" / f"cor-{k}.png", t0, t0 + show, "correction", k))
    for j, (png, t0, t1, kind, ref) in enumerate(overlays):
        inputs += ["-loop", "1", "-framerate", FPS, "-t", f"{dur:.4f}", "-i", png]
        fc.append(
            f"[{n + j}:v]format=rgba,fade=in:st={t0:.3f}:d=0.3:alpha=1,"
            f"fade=out:st={t1 - 0.3:.3f}:d=0.3:alpha=1[o{j}]"
        )
        fc.append(f"{last}[o{j}]overlay=format=auto[y{j}]")
        last = f"[y{j}]"
        timeline.append({kind: ref, "start": round(t0, 2), "end": round(t1, 2)})
    fc.append(f"{last}format=yuv420p,tpad=stop_mode=clone:stop_duration=0.3[v]")
    inputs += ["-i", audio]
    out = BUILD / f"{act['id']}.mkv"
    ff(
        *inputs,
        "-filter_complex",
        ";".join(fc),
        "-map",
        "[v]",
        "-map",
        f"{n + len(overlays)}:a",
        "-c:v",
        "libx264",
        "-crf",
        16,
        "-preset",
        "medium",
        "-c:a",
        "pcm_s16le",
        "-t",
        f"{dur:.4f}",
        out,
    )
    return out, timeline


def card_clip(name: str, seconds: float) -> Path:
    out = BUILD / f"{name}.mkv"
    frames = round(seconds * FPS)
    ff(
        "-loop", 1, "-framerate", FPS, "-t", f"{seconds:.4f}",
        "-i", BUILD / "shots" / f"{name}.png",
        "-f", "lavfi", "-t", f"{seconds:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-filter_complex", f"[0:v]{zoom_clip(frames, True, 0.015)}[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", 16, "-c:a", "pcm_s16le",
        "-t", f"{seconds:.4f}", out,
    )  # fmt: skip
    return out


def act5_clip() -> Path:
    out = BUILD / "act5.mkv"
    ff("-i", ACT5, "-vf", f"fps={FPS},format=yuv420p,setsar=1", "-ar", 48000, "-ac", 2,
       "-c:v", "libx264", "-crf", 16, "-c:a", "pcm_s16le", out)  # fmt: skip
    return out


def join(parts: list[Path], out: Path) -> list[float]:
    """Crossfade the parts; returns each part's start time in the result."""
    durs = [duration(p) for p in parts]
    inputs, fc, starts, off = [], [], [0.0], 0.0
    for p in parts:
        inputs += ["-i", p]
        fc.append(f"[{len(inputs) // 2 - 1}:v]settb=AVTB,fps={FPS}[v{len(inputs) // 2 - 1}in]")
    vl, al = "[v0in]", "[0:a]"
    for i in range(1, len(parts)):
        off += durs[i - 1] - XF
        starts.append(off)
        fc.append(f"{vl}[v{i}in]xfade=transition=fade:duration={XF}:offset={off:.4f}[v{i}]")
        fc.append(f"{al}[{i}:a]acrossfade=d={XF}:c1=tri:c2=tri[a{i}]")
        vl, al = f"[v{i}]", f"[a{i}]"
    fc.append(f"{al}aresample=48000[aout]")
    ff(
        *inputs, "-filter_complex", ";".join(fc), "-map", vl, "-map", "[aout]",
        "-c:v", "libx264", "-crf", 20, "-preset", "slow", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", 48000,
        "-movflags", "+faststart", out,
    )  # fmt: skip
    return starts


# ---------------------------------------------------------------- 5. captions
def ts(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


MAX_LINE, MAX_CPS = 42, 20.0  # caption lines and reading speed
FOOTNOTE_TEXT: set[str] = set()  # SRT texts of the footnote cues (shown below speech)


def two_lines(text: str) -> str | None:
    """The text on one line, or on two balanced lines of at most MAX_LINE; None if it can't."""
    if len(text) <= MAX_LINE:
        return text
    words = text.split()
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        fits = len(a) <= MAX_LINE and len(b) <= MAX_LINE
        if fits and (best is None or abs(len(a) - len(b)) < abs(len(best[0]) - len(best[1]))):
            best = (a, b)
    return None if best is None else f"{best[0]}\n{best[1]}"


def chunks_that_fit(words: list[str]) -> list[list[str]]:
    out, cur = [], []
    for w in words:
        if cur and two_lines(" ".join([*cur, w])) is None:
            out.append(cur)
            cur = []
        cur.append(w)
    return [*out, cur] if cur else out


UTTERANCE_END = "\u2063"  # invisible marker: a logged NVDA line ends a cue
SENTENCE_END = re.compile(r"[.?!][”\]]?[.?!]?$")


def spoken_only(tokens: list[dict]) -> list[dict]:
    """Drop the transcript's bracketed notes; punctuation after a note goes to the word before."""
    out: list[dict] = []
    for t in tokens:
        if t["note"]:
            tail = t["t"][t["t"].rindex("]") + 1 :]
            if tail and out:
                out[-1] = {**out[-1], "t": out[-1]["t"] + tail}
        else:
            out.append(t)
    return out


LAGS: list[float] = []  # how far each speech cue starts after its first word (seconds)


def timed(cues: list[tuple[float, float, str]], offset: float) -> list[list]:
    """Cue times: at least 1 s and at most 20 characters a second, never overlapping.

    A cue may start up to 0.3 s before its words; in a fast stretch it starts when the one
    before it ends, so it can run a little behind the speech and catch up in the next pause.
    """
    out: list[list] = []
    prev_e = -1.0
    for s, e_speech, text in cues:
        need = max(len(text) / MAX_CPS + 0.05, 1.0)
        start = max(prev_e + 0.05, s - 0.3)
        end = max(e_speech + 0.25, start + need)
        LAGS.append(start - s)
        out.append([offset + start, offset + end, two_lines(text) or text, "speech"])
        prev_e = end
    return out


def cues_from_tokens(tokens: list[dict], offset: float) -> list[list]:
    tokens = spoken_only(tokens)
    cues, cur = [], []
    for i, t in enumerate(tokens):
        cur.append(t)
        text = " ".join(x["t"] for x in cur)
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is None:
            cues.append(cur)
            break
        rest = []  # the rest of this sentence
        for x in tokens[i + 1 :]:
            rest.append(x["t"])
            if SENTENCE_END.search(x["t"]):
                break
        whole = two_lines(f"{text} {' '.join(rest)}") is not None
        if (
            (SENTENCE_END.search(t["t"]) and len(text) >= 18)
            or (t["t"].endswith((",", ":", ";")) and len(text) >= 24 and not whole)
            or two_lines(f"{text} {nxt['t']}") is None
            or nxt["s"] - t["e"] > 1.0
        ):
            cues.append(cur)
            cur = []
    return timed([(c[0]["s"], c[-1]["e"], " ".join(x["t"] for x in c)) for c in cues], offset)


def correction_cues(text: str, t0: float, t1: float) -> list[list]:
    """An on-screen footnote as its own cue(s), at the footnote's time."""
    parts = [" ".join(c) for c in chunks_that_fit(text.split())]
    total = sum(len(p) for p in parts)
    out, s = [], t0
    for p in parts:
        e = s + (t1 - t0) * len(p) / total
        out.append([s, e - 0.04, two_lines(p) or p, "correction"])
        s = e
    return out


def act5_cues(offset: float) -> list[list]:
    """NVDA's speech, scene by scene, timed from the step times in nvda-transcript.md."""
    scenes: list[list[tuple[float, str]]] = []
    for line in (VID / "clips/nvda-transcript.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            scenes.append([])
        m = re.match(r"-\s+([\d.]+) s · [^\"]*\"(.*)\"$", line)
        if m and scenes:
            text = re.sub(r"\s*\[[^\]]*\]$", "", m[2]).strip()
            scenes[-1].append((float(m[1]), re.sub(r"\s+\)", ")", text)))
    scenes = [sc for sc in scenes if sc]
    act5_len = duration(ACT5)
    out = []
    for k, sc in enumerate(scenes):
        end = scenes[k + 1][0][0] - 0.3 if k + 1 < len(scenes) else act5_len - 0.4
        # Character position -> time, linear within each logged line.
        marks, pos, words = [], 0, []
        for j, (t, text) in enumerate(sc):
            t1 = sc[j + 1][0] if j + 1 < len(sc) else end
            marks.append((pos, pos + len(text) + 1, t, t1))
            pos += len(text) + 1
            nxt = sc[j + 1][1] if j + 1 < len(sc) else ""
            ws = text.split()
            if re.search(r"[\d.)]$", text) and nxt[:1].isupper():
                ws[-1] += UTTERANCE_END  # the logged line is a whole utterance ("..., level 2")
            words += ws

        def at(c: int, marks=marks, end=end) -> float:
            for p0, p1, t0, t1 in marks:
                if c < p1:
                    return t0 + (t1 - t0) * (c - p0) / (p1 - p0)
            return end

        chunks, cur = [], []
        for w in words:
            head = "NVDA: " if not chunks else ""
            if cur and two_lines(head + " ".join([*cur, w]).replace(UTTERANCE_END, "")) is None:
                chunks.append(cur)
                cur = []
            cur.append(w)
            if w.endswith(UTTERANCE_END) or (SENTENCE_END.search(w) and len(" ".join(cur)) > 30):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        c = 0
        for n, ch in enumerate(chunks):
            text = " ".join(ch).replace(UTTERANCE_END, "")
            s0, s1 = at(c), at(c + len(text) + 1)
            c += len(text) + 1
            label = "NVDA: " if n == 0 else ""
            line = two_lines(label + text) or label + text
            out.append([offset + s0, offset + s1 - 0.04, line, "speech"])
    return out


def write_srt(cues: list[list], path: Path) -> None:
    """Speech cues never overlap each other; a footnote cue runs alongside them."""
    speech = sorted((c for c in cues if c[3] == "speech"), key=lambda c: c[0])
    for a, b in itertools.pairwise(speech):
        a[1] = min(a[1], b[0] - 0.04)
    cues = sorted(cues, key=lambda c: c[0])
    path.write_text(
        "\n".join(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n" for i, (s, e, t, _) in enumerate(cues, 1)),
        encoding="utf-8",
    )


def flatten(srt: Path, path: Path) -> None:
    """The SRT without overlapping cues, for the mp4's mov_text track (which cannot hold
    overlaps): while a footnote cue runs alongside speech, one cue shows both, speech first."""

    def sec(t: str) -> float:
        h, m, s = t.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    cues = []
    for block in srt.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.split("\n")
        a, b = lines[1].split(" --> ")
        cues.append((sec(a), sec(b), "\n".join(lines[2:])))
    edges = sorted({t for a, b, _ in cues for t in (a, b)})
    flat: list[list] = []
    for t0, t1 in itertools.pairwise(edges):
        on = [c for c in cues if c[0] <= t0 and c[1] >= t1]
        if not on:
            continue
        text = "\n".join(c[2] for c in sorted(on, key=lambda c: c[2] in FOOTNOTE_TEXT))
        joined = flat and abs(flat[-1][1] - t0) < 1e-6
        if joined and (flat[-1][2] == text or t1 - t0 < 0.3):
            flat[-1][1] = t1  # same text, or a sliver (a gap between cues): no flicker
        else:
            flat.append([t0, t1, text])
    path.write_text(
        "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(flat, 1)),
        encoding="utf-8",
    )


def mux(video: Path, srt: Path, out: Path) -> None:
    ff("-i", video, "-i", srt, "-map", "0:v", "-map", "0:a", "-map", "1:s", "-c:v", "copy",
       "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
       "-metadata:s:s:0", "title=English", "-movflags", "+faststart", out)  # fmt: skip


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def transcript(acts_done: list[dict], starts: dict[str, float], spec: dict, path: Path) -> None:
    caps = {c["id"]: c["text"] for c in spec["captions"]}
    names = {
        "act1": "Act 1: Hook",
        "act2": "Act 2: The measured answer",
        "act3": "Act 3: What was found, and what wasn't",
        "act4": "Act 4: Poverty (recorded as act4a1 and act4a2)",
        "act4b": "Act 4b: What wasn't significant",
        "act5b": "Act 5b: My library, in action",
        "act6": "Act 6: Close",
    }
    out = [
        "# Curb Cut walkthrough: transcript",
        "",
        "Narrated by Jerry Bannister (the author). Times are positions in "
        "`curbcut-walkthrough.mp4`. The words are what is said, lightly corrected for "
        "speech-recognition errors (listed at the end); a correction shown on screen as a "
        "footnote is given in square brackets where it applies. "
        "`CAPTION:` lines are the on-screen captions (text exactly as in the script) and "
        "`Correction:` lines the on-screen footnotes.",
        "",
        f"## Title card ({mmss(0)})",
        "",
        "Curb Cut: " + TITLE_SUB,
        "",
    ]
    for act in acts_done:
        aid = act["id"]
        if aid == "act5b":
            out += [f"## Act 5: The site, in a screen reader's voice ({mmss(starts['act5'])})", ""]
            out += ["No narration: NVDA reads the live site. See `clips/nvda-transcript.md`.", ""]
            for line in (VID / "clips/nvda-transcript.md").read_text(encoding="utf-8").splitlines():
                if line.startswith("On-screen card:"):
                    out.append("CAPTION: " + line.split('"')[1])
                elif re.match(r"-\s+[\d.]+ s", line):
                    out.append("> NVDA: " + re.sub(r"^-\s+[\d.]+ s · [^\"]*", "", line).strip('"'))
            out.append("")
        out += [f"## {names[aid]} ({mmss(starts[aid])})", ""]
        out += [" ".join(TEXT[v] for v in act["voice"]), ""]
        for item in act["timeline"]:
            if "caption" in item:
                at = mmss(starts[aid] + item["start"])
                out.append(f"CAPTION: {caps[f'cap-{aid}-{item["caption"]}']}")
                out.append(f"(on screen from {at})")
                out.append("")
            elif "correction" in item:
                out.append(COR[item["correction"]])
                out.append(f"(footnote on screen {mmss(starts[aid] + item['start'])}–"
                           f"{mmss(starts[aid] + item['end'])})")  # fmt: skip
                out.append("")
    out += [
        f"## End card ({mmss(starts['end'])})",
        "",
        " · ".join(END),
        "",
        "## Note on corrections and transcription",
        "",
        "The author chose on-screen correction footnotes over re-recording. Four footnotes "
        "are shown on screen: in act 3, the small-area model *failed* the checks set in "
        'advance (the recording may sound like "filled"); in act 4, the range is 6 to 17 '
        "percentage points, not percent (95% CI 6.1–17.2); in act 4b, the 73 comparisons are "
        "states next to each other in the ranking, the highest and lowest, and each state "
        'against the national figure (said as "neighbouring states and each state were '
        'tested against the national figure"). Also in act 4b, whether the author says '
        '"can" or "can\'t" before "be told apart from Abia" is unclear in the recording; '
        "the footnote states the finding (Taraba can't be told apart from Abia). "
        "Act 1's opening "
        "differs from the script by the author's choice; it is not corrected.",
        "",
        "Speech-recognition errors fixed in this transcript (what the recogniser heard → "
        "what was said): Gerry → Jerry; survey is → surveys; Maran's eye → Moran's I; "
        "special test → spatial test; shoveled → shuffled; proof of course → proof of cause; "
        "Smaller panels of A → A smaller panel survey; which game first → which came first; "
        "them in three → seventy-three; Tarabah → Taraba; The panels will be also filled to "
        "show → The panel survey also fails to show; every pitch and its types cause a "
        "hundred → every page and its types score a hundred; The checked error bar has a "
        "higher read than Legos → The check: “Taraba has a higher rate than Lagos”; error bar "
        "has a higher read than RBIs → “Taraba has a higher rate than Abia”; side "
        "descriptions → site's descriptions; the difference that I held up → the differences "
        "that held up; strict mood → strict mode; every forgot name is its source → every "
        "figure names its source. Spoken numbers are written in words, as in the script.",
        "",
    ]
    path.write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------- main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = write_overlays()
    if "--no-shots" not in sys.argv or not (BUILD / "shots/home-top.png").exists():
        run(["node", str(HERE / "shots.mjs"), str(BUILD)], cwd=HERE)
    words = whisper_words()
    report = {"acts": {}}
    segs = {
        "title": card_clip("title", TITLE_S),
        "end": card_clip("end", END_S),
        "act5": act5_clip(),
    }
    tok_by_act = {}
    for act in ACTS:
        audio, tokens, dur, info = act_audio(act, words)
        segs[act["id"]], act["timeline"] = render_act(act, audio, tokens, dur)
        tok_by_act[act["id"]] = tokens
        report["acts"][act["id"]] = {
            "seconds": round(dur, 2),
            "audio": info,
            "timeline": act["timeline"],
        }
        print(act["id"], f"{dur:.2f}s")

    def build(order: list[str], name: str, with_transcript: bool) -> dict:
        tmp = BUILD / f"{name}-nosubs.mp4"
        st = join([segs[k] for k in order], tmp)
        starts = dict(zip(order, st, strict=True))
        cues = []
        for k in order:
            if k in tok_by_act:
                cues += cues_from_tokens(tok_by_act[k], starts[k])
            elif k == "act5":
                cues += act5_cues(starts[k])
        for act in ACTS:
            if act["id"] in starts:
                for item in act["timeline"]:
                    if "correction" in item:
                        t0 = starts[act["id"]] + item["start"]
                        t1 = starts[act["id"]] + item["end"]
                        cues += correction_cues(COR[item["correction"]], t0, t1)
        srt = OUT / f"{name}.en.srt"
        write_srt(cues, srt)
        FOOTNOTE_TEXT.update(c[2] for c in cues if c[3] == "correction")
        flat = BUILD / f"{name}-mov_text.srt"
        flatten(srt, flat)
        mux(tmp, flat, OUT / f"{name}.mp4")
        tmp.unlink()
        if with_transcript:
            transcript(ACTS, starts, spec, OUT / f"{name}-transcript.md")
        return {k: round(v, 2) for k, v in starts.items()} | {
            "total": round(duration(OUT / f"{name}.mp4"), 2)
        }

    full = ["title", "act1", "act2", "act3", "act4", "act4b", "act5", "act5b", "act6", "end"]
    report["walkthrough_starts"] = build(full, "curbcut-walkthrough", True)
    report["one_minute_starts"] = build(["title", "act1", "act2", "end"], "curbcut-1min", False)
    report["caption_lag_max_s"] = round(max(LAGS), 2)
    report["caption_lag_over_0_5s"] = sum(lag > 0.5 for lag in LAGS)
    (BUILD / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "acts"}, indent=1))
    shutil.copy(BUILD / "shots-report.json", OUT / "shots-report.json")


if __name__ == "__main__":
    main()
