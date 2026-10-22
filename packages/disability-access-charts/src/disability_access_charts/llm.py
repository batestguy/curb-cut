"""Optional LLM polish for alt-text, gated by the number and claim checker.

The data-derived alt-text is always the default. :func:`polish_alt_text` asks a model to
make it read better and keeps the result **only if** all of these hold:

* :func:`check_alt_text` finds no errors and no warnings in it, apart from the
  "independence" warning that the data-built text can carry too (no number outside the
  data or not tied to a category, no recognised claim found false, no wording it cannot
  check);
* it keeps every category named, every number written, the interval label and the source
  of the data-built text (so the polish cannot drop facts).

Otherwise it falls back to the data-derived text. Passing the checker means no recognised
claim was found false; it does not prove the text is true (see :mod:`describe`).
Providers are tried in order (Gemini, then Groq, by default).

**Only disclosure-checked aggregates.** What is sent: the chart document's ``data`` block,
its title and source, and the data-derived alt-text. The library cannot know whether those
figures are safe to publish (for example, cells under about 30 respondents suppressed), so
callers must pass ``disclosure_checked=True`` to confirm the document holds only public,
disclosure-checked aggregates. Never pass microdata.

**Cache.** Raw outputs are written to ``cache_dir`` (default
``.disability_access_charts_cache/`` in the current working directory), keyed by
sha256(provider | model | prompt), so the same chart is not sent twice. Pass
``cache_dir=None`` to turn it off.

Free tiers: Gemini's unpaid tier may use prompts to improve Google's products
(verification.md L2), which is another reason only public aggregates are ever sent. Keys
come from ``GEMINI_API_KEY`` and ``GROQ_API_KEY``. Every HTTP call goes through
``urllib.request.urlopen``, looked up when called, so tests can replace it. The default
models, ``gemini-3.8-flash`` and ``llama-3.3-70b-versatile``, were listed as current on the
providers' model pages on 2026-10-21 (verification.md D36, D37).
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from disability_access_charts.audit import audit
from disability_access_charts.describe import (
    ChartData,
    check_alt_text,
    mentioned_categories,
    number_tokens,
)

DEFAULT_CACHE = Path(".disability_access_charts_cache")
TIMEOUT = 30

# Endpoints confirmed against the official docs on 2026-10-21 (verification.md D36, D37).
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str) -> str: ...


def _post(url: str, body: Mapping[str, Any], headers: Mapping[str, str]) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


class GeminiProvider:
    """Google Gemini ``generateContent`` (REST, ``x-goog-api-key`` header)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str) -> str:
        reply = _post(
            GEMINI_URL.format(model=self.model),
            {"contents": [{"parts": [{"text": prompt}]}]},
            {"x-goog-api-key": self.api_key},
        )
        parts = reply["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()


class GroqProvider:
    """Groq's OpenAI-compatible chat completions (Bearer key)."""

    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str) -> str:
        reply = _post(
            GROQ_URL,
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            {"Authorization": f"Bearer {self.api_key}"},
        )
        return reply["choices"][0]["message"]["content"].strip()


def default_providers() -> list[Provider]:
    """Gemini then Groq, for whichever API keys are set; empty if none are."""
    providers: list[Provider] = []
    if key := os.environ.get("GEMINI_API_KEY"):
        providers.append(GeminiProvider(key))
    if key := os.environ.get("GROQ_API_KEY"):
        providers.append(GroqProvider(key))
    return providers


PROMPT = """You rewrite chart descriptions (alt-text) for screen-reader users.
Rewrite the description below so it reads naturally. Rules:
- Use only numbers that appear in the description, written as digits, exactly as given.
- Do not add comparisons, rankings, causes or trends that are not in the description.
- Keep words like "estimate" and phrases like "the survey cannot show a difference".
- Keep the interval label, the title and the source exactly as written.
- Summary first, detail second. Plain text, one paragraph, no markdown.

Title: {title}
Source: {source}
Data (JSON): {data}
Description: {alt_text}

Rewritten description:"""


def build_prompt(doc: Mapping[str, Any]) -> str:
    """The prompt for a chart document: only its public data block, title and source."""
    return PROMPT.format(
        title=doc["title"],
        source=doc.get("meta", {}).get("source", ""),
        data=json.dumps(doc["data"], sort_keys=True),
        alt_text=doc["alt_text"],
    )


def _cached(provider: Provider, prompt: str, cache_dir: Path | None) -> str:
    if cache_dir is None:
        return provider.complete(prompt)
    key = hashlib.sha256(f"{provider.name}|{provider.model}|{prompt}".encode()).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["output"]
    output = provider.complete(prompt)
    cache_dir.mkdir(parents=True, exist_ok=True)
    record = {"provider": provider.name, "model": provider.model, "output": output}
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return output


def missing_facts(base: str, text: str, data: ChartData, *, lang: str = "en") -> list[str]:
    """What the data-built ``base`` text says that ``text`` leaves out.

    Every category named, every number written, the interval label (when ``base`` gives it)
    and the source must survive.
    """
    missing: list[str] = []
    kept = mentioned_categories(text, data, lang=lang)
    for i in sorted(mentioned_categories(base, data, lang=lang) - kept):
        missing.append(data.categories[i])
    numbers = number_tokens(text, data, lang=lang)
    for token in number_tokens(base, data, lang=lang):
        if token in numbers:
            numbers.remove(token)
        else:
            missing.append(token)
    for fixed in (data.interval_label, *data.verbatim[1:]):
        if fixed and fixed.lower() in base.lower() and fixed.lower() not in text.lower():
            missing.append(fixed)
    return missing


def polish_alt_text(
    doc: Mapping[str, Any],
    providers: Sequence[Provider] | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE,
    *,
    disclosure_checked: bool = False,
) -> dict[str, Any]:
    """A copy of ``doc`` with LLM-polished alt-text, if any provider's output is accepted.

    ``disclosure_checked=True`` is required: it confirms the document holds only public,
    disclosure-checked aggregates (see the module docstring). Each output must pass the
    checker with no errors and no warnings other than "independence", and keep every fact of the
    data-built text. The first accepted output is used and ``meta.alt_text_source`` becomes
    "llm:<provider>:<model>"; otherwise the data-derived text stays ("data"). A provider
    that fails (network error, bad reply) is skipped. A document without a ``data`` block
    is not sent anywhere. The audit is re-run on the result.
    """
    if disclosure_checked is not True:
        raise ValueError(
            "polish_alt_text sends the chart's data to an external service: pass "
            "disclosure_checked=True to confirm it holds only public, disclosure-checked "
            "aggregates"
        )
    out = json.loads(json.dumps(doc))
    meta = out.setdefault("meta", {})
    rejected: list[dict[str, Any]] = []
    if "data" not in out:
        meta["alt_text_source"] = "data"
        meta["alt_text_rejected"] = [{"reason": "no data block, so nothing was sent"}]
        out["audit"] = audit(out)
        return out
    data = ChartData.from_dict(out["data"])
    lang = meta.get("alt_text_lang", "en")
    prompt = build_prompt(out)
    cache = None if cache_dir is None else Path(cache_dir)
    for provider in default_providers() if providers is None else providers:
        try:
            text = " ".join(_cached(provider, prompt, cache).split())
        except Exception as exc:  # any failure means: try the next provider
            rejected.append({"provider": provider.name, "error": type(exc).__name__})
            continue
        problems = [p for p in check_alt_text(text, data, lang=lang) if p.kind != "independence"]
        missing = missing_facts(out["alt_text"], text, data, lang=lang)
        if not text or problems or missing:
            rejected.append(
                {
                    "provider": provider.name,
                    "problems": [p.to_dict() for p in problems],
                    "missing": missing,
                }
            )
            continue
        out["alt_text"] = text
        meta["alt_text_source"] = f"llm:{provider.name}:{provider.model}"
        break
    else:
        meta["alt_text_source"] = "data"
    if rejected:
        meta["alt_text_rejected"] = rejected
    out["audit"] = audit(out)
    return out
