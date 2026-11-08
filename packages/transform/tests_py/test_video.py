"""The walkthrough video's committed site files (P6 gate; scripts/video/publish_video.py).

CI has no access to the git-ignored video sources, so these tests check the committed
outputs: sizes git accepts, valid WebVTT captions, and a page that links every file.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VIDEO = ROOT / "site" / "public" / "video"
PAGE = ROOT / "site" / "walkthrough.html"
CUTS = ("curbcut-walkthrough", "curbcut-1min")
CUE_TIME = re.compile(r"^\d\d:\d\d:\d\d\.\d\d\d --> \d\d:\d\d:\d\d\.\d\d\d line:16%$")


def _publish():
    name = "publish_video"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "video" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _transcript() -> str:
    page = PAGE.read_text(encoding="utf-8")
    return page.split("<!-- transcript:start -->")[1].split("<!-- transcript:end -->")[0]


@pytest.mark.parametrize("cut", CUTS)
def test_video_is_committed_under_git_limits(cut: str) -> None:
    mp4 = VIDEO / f"{cut}.mp4"
    assert mp4.exists()
    # Web copies (author, 2026-11-08): small enough for slow connections and git history.
    assert 1_000_000 < mp4.stat().st_size < 40_000_000
    assert mp4.read_bytes()[4:8] == b"ftyp"


@pytest.mark.parametrize("cut", CUTS)
def test_captions_are_valid_webvtt_without_footnotes(cut: str) -> None:
    text = (VIDEO / f"{cut}.en.vtt").read_text(encoding="utf-8")
    assert text.startswith("WEBVTT\n\n")
    assert "Correction:" not in text  # burned into the picture already
    cues = [c.split("\n") for c in text.strip().split("\n\n")[1:]]
    assert len(cues) > 10
    for cue in cues:
        assert cue[0].isdigit() and CUE_TIME.match(cue[1]), cue
        assert cue[2].strip(), cue
        start, end = cue[1].split(" line:")[0].split(" --> ")
        assert start < end, cue


def test_page_links_every_file_and_has_the_transcript() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for cut in CUTS:
        assert f'src="./video/{cut}.mp4"' in page
        assert f'src="./video/{cut}.en.vtt"' in page
        assert f'href="./video/{cut}.mp4" download' in page
        size = (VIDEO / f"{cut}.mp4").stat().st_size
        assert f"MP4, {size / 1e6:.1f} MB" in page, cut
    transcript = _transcript()
    assert "clips/" not in transcript and "act4a1" not in transcript


def test_every_part_says_what_is_on_screen() -> None:
    transcript = _transcript()
    assert transcript.count("<h3>Act ") == 8
    assert transcript.count('class="transcript-shown"') == 8


def test_srt_to_vtt() -> None:
    srt = "\n".join(
        [
            "1",
            "00:00:02,500 --> 00:00:04,750",
            "Hello & <b>",
            "there",
            "",
            "2",
            "00:00:05,000 --> 00:00:08,000",
            "Correction: the range is",
            "6 to 17",
            "",
            "3",
            "00:00:05,200 --> 00:00:06,000",
            "Spoken words",
            "",
            "4",
            "00:00:08,100 --> 00:00:09,000",
            "points, not percent.",
            "",
        ]
    )
    vtt = _publish().srt_to_vtt(srt, ["Correction: the range is 6 to 17 points, not percent."])
    assert vtt == "\n".join(
        [
            "WEBVTT",
            "",
            "1",
            "00:00:02.500 --> 00:00:04.750 line:16%",
            "Hello &amp; &lt;b&gt;",
            "there",
            "",
            "2",
            "00:00:05.200 --> 00:00:06.000 line:16%",
            "Spoken words",
            "",
        ]
    )
    with pytest.raises(ValueError, match="not an SRT cue"):
        _publish().srt_to_vtt("not a cue")
    with pytest.raises(ValueError, match="no known correction"):
        _publish().srt_to_vtt("1\n00:00:01,000 --> 00:00:02,000\nCorrection: unknown\n")


def test_transcript_html_escapes_labels_and_never_hangs() -> None:
    md = "\n".join(
        [
            "# T",
            "",
            "Intro <b> & `code`, 2 * 3 and 4 * 5.",
            "",
            "## Act 5: NVDA (recorded as act4a1 and act4a2) (1:00.0)",
            "",
            "See `clips/nvda-transcript.md`.",
            "",
            "CAPTION: 3% *x*",
            "(on screen from 0:01.0)",
            "> NVDA: one",
            "> NVDA: two",
            "> a plain quote",
            ">NVDA:three",
            "After.",
            "",
            "Speech-recognition errors fixed in this transcript: a → b.",
        ]
    )
    out = _publish().transcript_html(md, {"acts": {}})
    assert "<p>Intro &lt;b&gt; &amp; <code>code</code>, 2 * 3 and 4 * 5.</p>" in out
    assert "<h3>Act 5: NVDA (1:00.0)</h3>" in out
    assert "On screen:</span> The main page" in out
    assert "What NVDA says is below." in out
    assert "On-screen caption:</span> 3% <em>x</em>" in out
    assert "(on screen from 0:01.0)" in out
    assert "NVDA:</span> one two three</p></blockquote>" in out
    assert "<blockquote><p>a plain quote</p></blockquote>" in out
    assert "<p>After.</p>" in out
    assert "<details><summary>Speech-recognition fixes" in out
