"""LLM polish: tests use fake providers only (urlopen raises, see conftest)."""

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from disability_access_charts import bar
from disability_access_charts.llm import (
    GROQ_URL,
    GeminiProvider,
    GroqProvider,
    build_prompt,
    default_providers,
    polish_alt_text,
)

KW: dict[str, Any] = {"title": "T", "value_label": "V", "category_label": "Group", "source": "S"}


class Fake:
    def __init__(self, reply: str, name: str = "fake") -> None:
        self.name = name
        self.model = "fake-1"
        self.reply = reply
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return self.reply


class Broken:
    name = "broken"
    model = "x"

    def complete(self, prompt: str) -> str:
        raise OSError("offline")


def ratio_doc() -> dict:
    # A is 1.7 times B.
    return bar(["A", "B"], [17.0, 10.0], unit="number", **KW)


def ci_doc() -> dict:
    # A and B overlap: "higher" is not supported.
    return bar(["A", "B", "C"], [12.3, 11.9, 4.1], lower=[10.1, 9.8, 3.0],
               upper=[14.5, 14.0, 5.2], unit="percent", **KW)  # fmt: skip


def test_a_wrong_ratio_falls_back_to_the_data_text(tmp_path: Path) -> None:
    doc = ratio_doc()
    out = polish_alt_text(
        doc, [Fake("T: A, 17.0, is twice B, 10.0.")], cache_dir=tmp_path, disclosure_checked=True
    )
    assert out["alt_text"] == doc["alt_text"]
    assert out["meta"]["alt_text_source"] == "data"
    assert out["meta"]["alt_text_rejected"][0]["problems"][0]["kind"] == "ratio"


def test_higher_with_an_overlapping_interval_falls_back(tmp_path: Path) -> None:
    doc = ci_doc()
    out = polish_alt_text(
        doc,
        [Fake("A, 12.3%, is higher than B, 11.9%.")],
        cache_dir=tmp_path,
        disclosure_checked=True,
    )
    assert out["alt_text"] == doc["alt_text"]
    assert out["meta"]["alt_text_source"] == "data"


def test_a_wrong_number_falls_back(tmp_path: Path) -> None:
    doc = ratio_doc()
    out = polish_alt_text(doc, [Fake("A has 18.0.")], cache_dir=tmp_path, disclosure_checked=True)
    assert out["alt_text"] == doc["alt_text"]


def test_a_good_output_is_kept_and_the_audit_rerun(tmp_path: Path) -> None:
    doc = ci_doc()
    good = doc["alt_text"].replace("Bar chart: T.", "This bar chart shows T.")
    out = polish_alt_text(
        doc,
        [Broken(), Fake("A is twice C."), Fake(good, "ok")],
        tmp_path,
        disclosure_checked=True,
    )
    assert out["alt_text"] == good
    assert out["meta"]["alt_text_source"] == "llm:ok:fake-1"
    assert [r["provider"] for r in out["meta"]["alt_text_rejected"]] == ["broken", "fake"]
    assert out["audit"]["passed"] is True
    assert doc["alt_text"] != good  # the input is not changed


def test_an_output_with_unchecked_wording_falls_back(tmp_path: Path) -> None:
    doc = ci_doc()
    vague = doc["alt_text"].replace("Bar chart: T.", "Bar chart: T. A exceeds C.")
    out = polish_alt_text(doc, [Fake(vague)], tmp_path, disclosure_checked=True)
    assert out["alt_text"] == doc["alt_text"]
    assert out["meta"]["alt_text_rejected"][0]["problems"][0]["kind"] == "unchecked"


def test_an_output_that_drops_facts_falls_back(tmp_path: Path) -> None:
    doc = ci_doc()
    short = "A has the highest estimate, 12.3%; C has the lowest estimate, 4.1%. Source: S."
    out = polish_alt_text(doc, [Fake(short)], tmp_path, disclosure_checked=True)
    assert out["alt_text"] == doc["alt_text"]
    missing = out["meta"]["alt_text_rejected"][0]["missing"]
    assert "B" in missing and "95% confidence interval" in missing and "10.1%" not in missing
    assert "10.1" in missing


def test_a_document_without_data_is_not_sent(tmp_path: Path) -> None:
    doc = ci_doc()
    del doc["data"]
    fake = Fake("anything")
    out = polish_alt_text(doc, [fake], tmp_path, disclosure_checked=True)
    assert fake.calls == 0
    assert out["alt_text"] == doc["alt_text"]
    assert out["meta"]["alt_text_source"] == "data"


def test_disclosure_check_must_be_confirmed(tmp_path: Path) -> None:
    fake = Fake("anything")
    with pytest.raises(ValueError, match="disclosure_checked=True"):
        polish_alt_text(ci_doc(), [fake], tmp_path)
    assert fake.calls == 0


def test_outputs_are_cached(tmp_path: Path) -> None:
    fake = Fake("A has the highest estimate, 12.3%.")
    polish_alt_text(ci_doc(), [fake], cache_dir=tmp_path, disclosure_checked=True)
    polish_alt_text(ci_doc(), [fake], cache_dir=tmp_path, disclosure_checked=True)
    assert fake.calls == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_the_prompt_holds_only_public_aggregates() -> None:
    doc = ci_doc()
    prompt = build_prompt(doc)
    assert json.dumps(doc["data"], sort_keys=True) in prompt
    assert "plotly" not in prompt and "themes" not in prompt


def test_no_keys_means_no_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert default_providers() == []
    doc = ratio_doc()
    assert (
        polish_alt_text(doc, cache_dir=None, disclosure_checked=True)["alt_text"] == doc["alt_text"]
    )


def test_real_providers_go_through_urlopen_which_tests_block() -> None:
    for provider in (GeminiProvider("k"), GroqProvider("k")):
        with pytest.raises(AssertionError, match="network"):
            provider.complete("hi")


def test_provider_request_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    class Response:
        def __init__(self, body: dict) -> None:
            self.body = body

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.body).encode()

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> Response:
        seen.append(request)
        if "groq" in request.full_url:
            return Response({"choices": [{"message": {"content": " hi "}}]})
        return Response({"candidates": [{"content": {"parts": [{"text": "h"}, {"text": "i"}]}}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert GeminiProvider("g-key").complete("x") == "hi"
    assert GroqProvider("q-key").complete("x") == "hi"
    gemini, groq = seen
    assert gemini.full_url.endswith("/models/gemini-3.8-flash:generateContent")
    assert gemini.get_header("X-goog-api-key") == "g-key"
    assert groq.full_url == GROQ_URL
    assert groq.get_header("Authorization") == "Bearer q-key"


def test_an_invented_statistic_falls_back(tmp_path: Path) -> None:
    # 12.3 is A's value, not an average: the checker only warns, and the gate must reject.
    doc = ci_doc()
    invented = doc["alt_text"] + " The national average is 12.3%."
    out = polish_alt_text(doc, [Fake(invented)], tmp_path, disclosure_checked=True)
    assert out["alt_text"] == doc["alt_text"]
    assert out["meta"]["alt_text_source"] == "data"
