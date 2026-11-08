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
CUE_TIME = re.compile(r"^\d\d:\d\d:\d\d\.\d\d\d --> \d\d:\d\d:\d\d\.\d\d\d$")


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


@pytest.mark.parametrize("cut", CUTS)
def test_video_is_committed_under_git_limits(cut: str) -> None:
    mp4 = VIDEO / f"{cut}.mp4"
    assert mp4.exists()
    assert 1_000_000 < mp4.stat().st_size < 90_000_000  # git rejects files over 100 MiB
    assert mp4.read_bytes()[4:8] == b"ftyp"


@pytest.mark.parametrize("cut", CUTS)
def test_captions_are_valid_webvtt(cut: str) -> None:
    text = (VIDEO / f"{cut}.en.vtt").read_text(encoding="utf-8")
    assert text.startswith("WEBVTT\n\n")
    cues = [c.split("\n") for c in text.strip().split("\n\n")[1:]]
    assert len(cues) > 10
    for cue in cues:
        assert cue[0].isdigit() and CUE_TIME.match(cue[1]), cue
        assert cue[2].strip(), cue
        # Correction footnotes are cues of their own and may overlap the speech.
        start, end = cue[1].split(" --> ")
        assert start < end, cue


def test_page_links_every_file_and_has_the_transcript() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for cut in CUTS:
        assert f'src="./video/{cut}.mp4"' in page
        assert f'src="./video/{cut}.en.vtt"' in page
        assert f'href="./video/{cut}.mp4" download' in page
        size = (VIDEO / f"{cut}.mp4").stat().st_size
        assert f"MP4, {size / 1e6:.1f} MB" in page, cut
    transcript = page.split("<!-- transcript:start -->")[1].split("<!-- transcript:end -->")[0]
    assert transcript.count("<h3>") >= 8
    assert "clips/" not in transcript and "act4a1" not in transcript


def test_srt_to_vtt() -> None:
    vtt = _publish().srt_to_vtt(
        "1\n00:00:02,500 --> 00:00:04,750\nHello\nthere\n\n"
        "2\n00:00:05,000 --> 00:00:06,000\nAgain\n"
    )
    assert vtt == (
        "WEBVTT\n\n1\n00:00:02.500 --> 00:00:04.750\nHello\nthere\n\n"
        "2\n00:00:05.000 --> 00:00:06.000\nAgain\n"
    )
    with pytest.raises(ValueError):
        _publish().srt_to_vtt("not a cue")


def test_transcript_html_escapes_and_labels() -> None:
    md = (
        "# T\n\nIntro <b> & `code`.\n\n## Act 5 (recorded as act4a1 and act4a2) (1:00.0)\n\n"
        "See `clips/nvda-transcript.md`.\n\nCAPTION: 3% *x*\n(on screen from 0:01.0)\n"
        "> NVDA: one\n> NVDA: two\n"
    )
    out = _publish().transcript_html(md)
    assert "<p>Intro &lt;b&gt; &amp; <code>code</code>.</p>" in out
    assert "<h3>Act 5 (1:00.0)</h3>" in out
    assert "What NVDA says is below." in out
    assert "On-screen caption:</span> 3% <em>x</em>" in out
    assert "(on screen from 0:01.0)" in out
    assert "NVDA:</span> one two</p></blockquote>" in out
