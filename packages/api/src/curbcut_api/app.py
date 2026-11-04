"""Curb Cut API: optional, read-only JSON over the public aggregates the site serves.

Run locally (from the repo root, after building the site data):
``CURBCUT_DATA_DIR=site/public/data uv run uvicorn curbcut_api.app:app``.

Environment:

* ``CURBCUT_DATA_BASE``: where to download the public files (default: the live site's
  ``/data/``); ``CURBCUT_DATA_DIR`` reads a local directory instead;
* ``CURBCUT_RATE_LIMIT``: per-client limit (default ``60/minute``);
* ``CURBCUT_TRUST_PROXY=1``: take the client address from ``X-Forwarded-For`` (set on
  Render only); ``CURBCUT_PROXY_HOPS`` (default 2) is how many entries the trusted proxies
  append, so the client is that many entries from the right (see ``docs/api.md``);
* ``RENDER_GIT_COMMIT``: shown by ``/status`` (Render sets it).
"""

from __future__ import annotations

import html
import math
import os
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from curbcut_api.data import Dataset, Store, slug, small, store_from_env

VERSION = version("curbcut-api")
SITE = "https://batestguy.github.io/curb-cut/"
REPO = "https://github.com/batestguy/curb-cut"
DEFAULT_RATE_LIMIT = "60/minute"
COLD_START = (
    "This API runs on Render's free plan, which sleeps after 15 minutes without traffic; "
    "the first request after that takes about a minute while it wakes."
)
OPTIONAL = (
    "Optional: the Curb Cut site never depends on this API; every figure here is also on "
    "the site and in its downloads."
)

DHS_CITATION = (
    "The DHS Program, Nigeria Demographic and Health Survey 2024 (National Population "
    "Commission and ICF); Curb Cut estimates from the microdata, disclosure-checked"
)
DHS_SOURCE = {
    "citation": DHS_CITATION,
    "url": "https://dhsprogram.com/",
    "terms": (
        "Survey-weighted aggregates only; no DHS microdata are published. Cells resting on "
        "fewer than 30 respondents are suppressed."
    ),
}
JONAPWD_SOURCE = {
    "citation": (
        "Joint National Association of Persons with Disabilities (JONAPWD), 2025 Assumptive "
        "Disability Disaggregated Data"
    ),
    "url": "https://jonapwdng.org/10865-2/",
    "terms": (
        "Cited, not redistributed: the report is all rights reserved. Its figures are an "
        "assumption (15% of a population projection), not a count."
    ),
}
POPULATION_SOURCE = {
    "citation": (
        "National Bureau of Statistics, Demographic Bulletin 2023, Annex 3 (source: National "
        "Population Commission)"
    ),
    "url": "https://microdata.nigerianstat.gov.ng/index.php/catalog/182",
}
MPI_SOURCE = {
    "citation": (
        "National Bureau of Statistics (NBS), Multidimensional Poverty Index Survey 2021, "
        "version 1.0 (NGA-NBS-MPI-2021-v1.0); General Household Survey-Panel Waves 4 and 5 "
        "(NBS and the World Bank); estimates by Curb Cut"
    ),
    "url": f"{SITE}poverty.html",
    "terms": (
        "Aggregated reporting only (NBS terms); no estimate rests on fewer than 30 households "
        "or people in either group."
    ),
}
POVERTY_WORDING = (
    "Pre-registered (https://osf.io/kes3p/). Each estimate is an adjusted association "
    "between disability in the household and multidimensional poverty, not a causal effect."
)

DESCRIPTION = f"""
Read-only JSON over Curb Cut's public data: Nigerian disability prevalence by state, zone
and nation (DHS 2024), the comparison with assumed figures, and the pre-registered poverty
results.

* **{OPTIONAL}** Site: <{SITE}>.
* **Public, disclosure-checked aggregates only.** No microdata: every number is a weighted
  aggregate that passed the project's disclosure check, read from the same files the site
  serves.
* **Sources and licences.** {DHS_CITATION}. JONAPWD's 2025 figures are cited, not
  redistributed (all rights reserved). NBS MPI 2021 results are aggregated reporting only,
  as NBS's terms require. Population: NBS Demographic Bulletin 2023, Annex 3.
* **Poverty results:** each is an adjusted association from a pre-registered analysis,
  not a causal effect.
* **Rate limit:** {DEFAULT_RATE_LIMIT} per client address; over it you get HTTP 429 with a
  `Retry-After` header.
* **Cold start:** {COLD_START}

Code (MIT): <{REPO}>.
"""

LEVELS = ("state", "zone", "national")
NUMBER_FIELDS = ("estimate", "se", "ci_low", "ci_high", "n_unweighted", "n_effective", "df")
UNITS = "estimate, se, ci_low and ci_high are proportions (0 to 1); ci is a 95% interval"


def client_key(
    trust_proxy: bool, hops: int, on_short: Callable[[], None] | None = None
) -> Callable[[Request], str]:
    """The rate limit's client key.

    Without ``trust_proxy`` it is the TCP peer. With it, it is the ``X-Forwarded-For``
    entry ``hops`` places from the right: proxies append, so entries a client sends
    itself sit to the left of the ones the trusted proxies add and can't move the key.
    A header with fewer entries than ``hops`` means the proxy chain is shorter than
    configured: the key is then the rightmost entry (added by the last proxy, never the
    client's own leftmost one) and ``on_short`` is called so ``/status`` can say so.
    """

    def key(request: Request) -> str:
        if trust_proxy:
            header = request.headers.get("x-forwarded-for", "")
            entries = [e.strip() for e in header.split(",") if e.strip()]
            if len(entries) >= hops:
                return entries[-hops]
            if entries:
                if on_short is not None:
                    on_short()
                return entries[-1]
        return request.client.host if request.client else "unknown"

    return key


def _error(status: int, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"message": message, **extra})


def _cell(row: Mapping[str, Any]) -> dict[str, Any]:
    """A survey cell as served: a suppressed or empty cell keeps null numbers, never a value.

    A cell resting on fewer than 30 respondents is also served as suppressed, whatever the
    file says (the disclosure gate already does this; this is a second check).
    """
    cell = dict(row)
    if small(cell.get("n_unweighted")):
        cell["suppressed"] = True
    if cell.get("suppressed") or cell.get("has_data") is False:
        for name in NUMBER_FIELDS:
            cell[name] = None
    return cell


def _choose(parameter: str, value: str, allowed: list[str]) -> str:
    if value not in allowed:
        raise _error(
            422, f"'{value}' is not a valid {parameter}.", parameter=parameter, allowed=allowed
        )
    return value


def create_app(env: Mapping[str, str] | None = None, store: Store | None = None) -> FastAPI:
    env = os.environ if env is None else env
    store = store or store_from_env(env)
    rate_limit = env.get("CURBCUT_RATE_LIMIT") or DEFAULT_RATE_LIMIT
    trust_proxy = env.get("CURBCUT_TRUST_PROXY") == "1"
    hops = max(1, int(env.get("CURBCUT_PROXY_HOPS") or 2))
    # Requests whose X-Forwarded-For had fewer entries than `hops` (a count, no addresses).
    short_chains = [0]

    def on_short() -> None:
        short_chains[0] += 1

    limiter = Limiter(
        key_func=client_key(trust_proxy, hops, on_short),
        # One budget per client across all routes (default_limits would be per route).
        application_limits=[rate_limit],
        # Off: slowapi would add Retry-After to every response and overwrite the 503's.
        headers_enabled=False,
        storage_uri="memory://",
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Deliberately blocks start-up until the first load finishes (or fails), so the
        # first health check sees loaded data; a failure is kept for /status, never raised.
        store.ensure()
        yield

    app = FastAPI(
        title="Curb Cut API",
        version=VERSION,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.state.store = store

    def rate_limited(request: Request, exc: Exception) -> JSONResponse:
        limit = request.state.view_rate_limit
        reset, _ = limiter.limiter.get_window_stats(limit[0], *limit[1])
        wait = max(1, math.ceil(reset - time.time()))
        detail = exc.detail if isinstance(exc, RateLimitExceeded) else str(exc)
        return JSONResponse(
            {
                "detail": {
                    "message": f"Rate limit exceeded ({detail} per client); try again later.",
                    "retry_after_seconds": wait,
                }
            },
            status_code=429,
            headers={"Retry-After": str(wait)},
        )

    app.add_exception_handler(RateLimitExceeded, rate_limited)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_credentials=False
    )

    def data() -> Dataset:
        dataset = store.ensure()
        if dataset is None:
            wait = math.ceil(store.retry_in() or 0)
            raise HTTPException(
                status_code=503,
                detail={
                    "message": (
                        "The public data are not loaded yet; try again shortly. "
                        "GET /status says why."
                    ),
                    "retry_after_seconds": wait,
                },
                headers={"Retry-After": str(max(wait, 1))},
            )
        return dataset

    def find_state(dataset: Dataset, value: str) -> dict[str, Any]:
        key = value.strip().lower()
        state = dataset.state_index.get(key) or dataset.state_index.get(slug(key))
        if state is None:
            raise _error(
                404,
                f"No state matches '{value}'. Use the state's slug (e.g. 'akwa-ibom', "
                "'federal-capital-territory') or its ISO 3166-2 code (e.g. 'NG-AK' or 'AK'); "
                "GET /states lists all 37.",
            )
        return state

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home() -> str:
        return HOME_HTML

    @app.get(
        "/status",
        summary="Whether the data are loaded, from where, and file checksums",
        description=(
            "HTTP 200 when the public files are loaded and checked, 503 when not (the "
            f"reason is in `error`). Not rate limited: it is the health check. {COLD_START}"
        ),
    )
    @limiter.exempt
    def status() -> JSONResponse:
        dataset = store.ensure()
        retry = store.retry_in()
        body = {
            "ready": dataset is not None,
            "data_source": store.source,
            "loaded_at": dataset.loaded_at if dataset else None,
            "files": (
                {name: vars(info) for name, info in dataset.files.items()} if dataset else None
            ),
            "error": store.error,
            "load_attempts": store.attempts,
            "next_retry_in_seconds": math.ceil(retry) if retry is not None else None,
            "version": VERSION,
            "git_commit": env.get("RENDER_GIT_COMMIT") or None,
            "rate_limit": f"{rate_limit} per client address",
            "proxy_hops": hops if trust_proxy else None,
            # Non-zero means the proxy chain looks shorter than proxy_hops (docs/api.md).
            "proxy_chain_shorter_than_hops_seen": short_chains[0] if trust_proxy else None,
            "cold_start": COLD_START,
            "site": SITE,
        }
        return JSONResponse(body, status_code=200 if dataset else 503)

    @app.get(
        "/states",
        summary="The 37 states (36 and the FCT) with their facts and DHS 2024 headline",
        description=(
            "Zone, capital, 2023 population projection, JONAPWD's assumed 2025 total and "
            "share, and the DHS 2024 headline cell (DISABILITY3, adults 18+, both sexes; "
            "a proportion, null where not published)."
        ),
    )
    def states() -> dict[str, Any]:
        dataset = data()
        return {
            "count": len(dataset.states),
            "states": dataset.states,
            "units": f"dhs2024: {UNITS}",
            "source": {
                "dhs2024": DHS_SOURCE,
                "jonapwd": JONAPWD_SOURCE,
                "population": POPULATION_SOURCE,
            },
        }

    @app.get(
        "/states/{state}",
        summary="One state, by slug or ISO 3166-2 code",
        description=(
            "`state` is the site's slug (`akwa-ibom`, `federal-capital-territory`) or the "
            "ISO code (`NG-AK` or `AK`), in any case. Unknown values give 404."
        ),
    )
    def one_state(state: str) -> dict[str, Any]:
        dataset = data()
        record = find_state(dataset, state)
        return {
            "state": record,
            "slug": slug(record["state"]),
            "page": f"{SITE}states/{slug(record['state'])}.html",
            "units": f"dhs2024: {UNITS}",
            "source": {
                "dhs2024": DHS_SOURCE,
                "jonapwd": JONAPWD_SOURCE,
                "population": POPULATION_SOURCE,
            },
        }

    @app.get(
        "/prevalence",
        summary="DHS 2024 disability prevalence cells by state, zone or nation",
        description=(
            "Defaults to the headline: DISABILITY3 (a lot of difficulty or worse in at least "
            "one Washington Group domain), adults 18+, both sexes, for every state. Values "
            "not present at the chosen level give 422 with the allowed values. Suppressed "
            "cells (fewer than 30 respondents) come back with `suppressed: true` and null "
            "numbers; every cell carries its precision flag and reason. Write `18+` as "
            "`18%2B` in a URL."
        ),
    )
    def prevalence(
        level: Annotated[str, Query(description="state, zone or national")] = "state",
        state: Annotated[
            str | None, Query(description="level=state only: a slug or ISO code")
        ] = None,
        geography: Annotated[
            str | None, Query(description="level=zone: a zone name (e.g. 'North West')")
        ] = None,
        measure: Annotated[str, Query(description="e.g. disability3, seeing_3plus")] = (
            "disability3"
        ),
        age_group: Annotated[str, Query(description="18+ or 5-17")] = "18+",
        sex: Annotated[str, Query(description="all, female or male")] = "all",
    ) -> dict[str, Any]:
        dataset = data()
        level = _choose("level", level.strip().lower(), list(LEVELS))
        if level == "state":
            if geography is not None:
                raise _error(422, "Use 'state', not 'geography', with level=state.")
            rows = dataset.state_cells
        else:
            if state is not None:
                raise _error(422, "'state' needs level=state; use 'geography' for a zone.")
            rows = [r for r in dataset.national_zone_cells if r["geography_level"] == level]
        measure = _choose("measure", measure.strip().lower(), sorted({r["measure"] for r in rows}))
        age_group = _choose(
            "age_group",
            # An unencoded "+" in a query string arrives as a space.
            age_group.replace(" ", "+").strip().lower(),
            sorted({r["age_group"] for r in rows}),
        )
        sex = _choose("sex", sex.strip().lower(), sorted({r["sex"] for r in rows}))
        query: dict[str, Any] = {
            "level": level,
            "measure": measure,
            "age_group": age_group,
            "sex": sex,
        }
        if state is not None:
            code = find_state(dataset, state)["state_code"]
            rows = [r for r in rows if r["state_code"] == code]
            query["state"] = code
        if geography is not None:
            names = sorted({r["geography"] for r in rows})
            match = [n for n in names if slug(n) == slug(geography)]
            if not match:
                raise _error(
                    422,
                    f"'{geography}' is not a valid geography.",
                    parameter="geography",
                    allowed=names,
                )
            rows = [r for r in rows if r["geography"] == match[0]]
            query["geography"] = match[0]
        cells = [
            _cell(r)
            for r in rows
            if r["measure"] == measure and r["age_group"] == age_group and r["sex"] == sex
        ]
        if not cells:
            raise _error(
                404,
                "No cells for this combination at this level (some breakdowns exist only "
                "for both sexes).",
                query=query,
            )
        return {
            "query": query,
            "count": len(cells),
            "units": UNITS,
            "cells": cells,
            "notes": [
                "Suppressed cells have null numbers; they are never estimated or filled.",
                "precision_flag: reliable, review or unreliable; precision_reason says why.",
            ],
            "source": DHS_SOURCE,
        }

    @app.get(
        "/compare",
        summary="Assumed and survey disability figures side by side",
        description=(
            "The comparison rows exactly as the site shows them (JONAPWD's assumed 15%, "
            "global estimates and survey figures), in the site's order, each with its "
            "definition, population and source. Values are percentages."
        ),
    )
    def compare() -> dict[str, Any]:
        dataset = data()
        return {
            "count": len(dataset.comparison),
            "rows": dataset.comparison,
            "units": "value_percent, ci_low_percent and ci_high_percent are percentages",
            "source": {
                "per_row": "each row's source and source_url",
                "dhs2024": DHS_SOURCE,
                "jonapwd": JONAPWD_SOURCE,
            },
        }

    @app.get(
        "/poverty",
        summary="The pre-registered poverty results (P5)",
        description=(
            "Estimates and scalar results of the pre-registered analysis of disability and "
            "household multidimensional poverty (NBS MPI 2021) and the exploratory GHS-Panel "
            f"comparison, as published on the site. {POVERTY_WORDING}"
        ),
    )
    def poverty() -> dict[str, Any]:
        dataset = data()
        return {
            "wording": POVERTY_WORDING,
            "note": dataset.poverty["note"],
            "estimates": dataset.poverty["estimates"],
            "summary": dataset.poverty["summary"],
            "page": f"{SITE}poverty.html",
            "source": MPI_SOURCE,
        }

    return app


def _home_html() -> str:
    links = "\n".join(
        f'<li><a href="{href}">{html.escape(text)}</a></li>'
        for href, text in (
            ("/docs", "Interactive documentation (OpenAPI)"),
            ("/status", "/status: whether the data are loaded"),
            ("/states", "/states: the 37 states"),
            ("/states/kano", "/states/kano: one state, by slug or ISO code"),
            ("/prevalence", "/prevalence: DHS 2024 prevalence (headline by default)"),
            ("/compare", "/compare: assumed and survey figures side by side"),
            ("/poverty", "/poverty: the pre-registered poverty results"),
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Curb Cut API</title>
<style>
body{{font-family:system-ui,sans-serif;line-height:1.5;max-width:42rem;margin:0 auto;
padding:1rem}}
</style>
</head>
<body>
<main>
<h1>Curb Cut API</h1>
<p>Read-only JSON over Curb Cut's public data on disability in Nigeria. {html.escape(OPTIONAL)}
The site is at <a href="{SITE}">{SITE}</a>.</p>
<p>{html.escape(COLD_START)}</p>
<h2>Endpoints</h2>
<ul>
{links}
</ul>
<h2>Data and licences</h2>
<ul>
<li>Only public, disclosure-checked aggregates; no microdata.</li>
<li>{html.escape(DHS_CITATION)}.</li>
<li>JONAPWD's 2025 figures are cited, not redistributed (all rights reserved).</li>
<li>NBS Multidimensional Poverty Index Survey 2021: aggregated reporting only.
Poverty results are adjusted associations from a pre-registered analysis.</li>
<li>Rate limit: {DEFAULT_RATE_LIMIT} per client address (HTTP 429 with Retry-After).</li>
<li>Code: <a href="{REPO}">{REPO}</a> (MIT).</li>
</ul>
</main>
</body>
</html>
"""


HOME_HTML = _home_html()

app = create_app()
