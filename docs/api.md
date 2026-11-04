# Curb Cut API

An optional, read-only JSON API over the same public files the site serves. **The site never depends on it**: every number here is also on the site and in its CSV/JSON downloads. It serves public, disclosure-checked aggregates only; no microdata ever reach it.

Code: `packages/api` (`curbcut-api`, FastAPI). Hosting: Render's free plan, from the `render.yaml` Blueprint at the repo root ($0).

## Endpoints

All are `GET` and return JSON, except `/`, a short HTML page with links. Every data response carries a `source` block with the citation and terms. Interactive documentation (OpenAPI) is at `/docs`.

| Path | What | Example |
|---|---|---|
| `/status` | Whether the data are loaded (200) or not (503, with the reason), where from, when, each file's row count and SHA-256, version, deployed commit | `/status` |
| `/states` | The 37 states (36 and the FCT): zone, capital, 2023 population, JONAPWD's assumed 2025 total, and the DHS 2024 headline | `/states` |
| `/states/{state}` | One state, by the site's slug or the ISO 3166-2 code, any case; 404 otherwise | `/states/akwa-ibom`, `/states/NG-FC`, `/states/kn` |
| `/prevalence` | DHS 2024 cells. `level` = `state` (default), `zone` or `national`; `state` (slug or code, state level) or `geography` (zone name); `measure`, `age_group`, `sex`. Defaults to the headline: `disability3`, `18+`, `all`. A value not present at that level gives 422 with the allowed values | `/prevalence?state=kano&sex=female`, `/prevalence?level=zone&geography=North%20West`, `/prevalence?level=national&measure=hearing_3plus` |
| `/compare` | The comparison rows (JONAPWD's assumed figure, global estimates, survey figures) as the site shows them, in its order | `/compare` |
| `/poverty` | The pre-registered P5 results: `note`, `estimates`, `summary`. Each estimate is an adjusted association, not a causal effect | `/poverty` |

Notes:
- Proportions are 0 to 1 in `/prevalence` and `/states` (`dhs2024`); `/compare` is in percent.
- Suppressed cells (fewer than 30 respondents) come back with `suppressed: true` and every number null; they are never estimated or filled. Every cell carries `precision_flag` and `precision_reason`. As a second check behind the disclosure gate, the API also serves any cell with `n_unweighted` under 30 as suppressed, and drops a state's `dhs2024` headline under 30.
- `level`, `measure`, `age_group` and `sex` are case-insensitive.
- Write `18+` as `18%2B` in a URL (an unencoded `+` arrives as a space; the API accepts that too).

## Rate limit and cold start

- **60 requests a minute per client address**, across all endpoints (`CURBCUT_RATE_LIMIT`). Over it: HTTP 429 with a `Retry-After` header (seconds). `/status` is not limited: it is Render's health check.
- **Cold start:** Render's free plan stops the service after 15 minutes without traffic; the next request wakes it, which takes about a minute (https://render.com/docs/free, checked 2026-11-04).

### Client address behind Render's proxy

Render does not document how it sets `X-Forwarded-For`. What we found (2026-11-04):
- Render staff (2021): "we set the first IP in the list to the real client IP" (https://feedback.render.com/features/p/send-the-correct-xforwardedfor).
- A user's test on the same thread (2024) and a write-up (https://rohitpaulk.com/articles/render-rails-remote-ip): Render's proxy **appends** and keeps whatever the client sent, so the first entry can be forged. Requests reach Render through Cloudflare; the write-up's unforged example is `client, Cloudflare edge`.
- Cloudflare appends the address connecting to it (https://developers.cloudflare.com/fundamentals/reference/http-headers/).

So the first entry is the one a client controls. With `CURBCUT_TRUST_PROXY=1` (set in `render.yaml`) the API keys the limit on the entry `CURBCUT_PROXY_HOPS` (default 2) places from the right: the address Cloudflare saw, which a client can't move by sending its own header. If a request's header has fewer entries than that, the API uses the rightmost entry (added by the last proxy, never the client's own) and counts it: `/status` shows the count as `proxy_chain_shorter_than_hops_seen` (no addresses). Without the flag it uses the TCP peer and ignores the header (right for local runs).

### Check the client address after the first deploy

Two checks, within the same minute. In each command, replace `curb-cut-api.onrender.com` with your service's address if Render gave it a different one.

**Step 1: a forged header must not buy extra requests.** In Git Bash on your computer, run:

```
for i in $(seq 1 61); do curl -s -o /dev/null -w '%{http_code}\n' -H "X-Forwarded-For: 192.0.2.$i" https://curb-cut-api.onrender.com/compare; done | sort | uniq -c
```

- Good: two lines, `60 200` and `1 429`.
- Bad: one line, `61 200`. The limit follows the forged entry, so `CURBCUT_PROXY_HOPS` is too large: Render's chain adds fewer entries. Set it to 1 (below) and repeat both steps.

**Step 2: a different real client must still get through.** Straight after step 1 (while your computer is limited), on a phone using mobile data (Wi-Fi off), open:

```
https://curb-cut-api.onrender.com/compare
```

- Good: the page shows JSON starting `{"count":`.
- Bad: it shows `Rate limit exceeded`. Your phone and computer share one key, so `CURBCUT_PROXY_HOPS` is too small: the key is a proxy's address, not yours. Set it to 3 (below) and repeat both steps.

Then open this and check `proxy_chain_shorter_than_hops_seen` is `0`:

```
https://curb-cut-api.onrender.com/status
```

A number above 0 also means `CURBCUT_PROXY_HOPS` is too large for some requests; tell Claude.

**To set `CURBCUT_PROXY_HOPS`:** in the Render Dashboard open `curb-cut-api`, choose **Environment**, add a variable with key `CURBCUT_PROXY_HOPS` and the value (1 or 3), and save it so the service redeploys. Then tell Claude the value, so it goes into `render.yaml` too. If neither 1, 2 nor 3 passes both steps, tell Claude and don't rely on the limit until it's fixed.

## Data source and refresh

At start-up the API downloads five files the site publishes from `CURBCUT_DATA_BASE` (default `https://batestguy.github.io/curb-cut/data/`): `dhs2024_state_prevalence.parquet`, `dhs2024_national_zone.parquet`, `prevalence_comparison.parquet`, `states.json`, `poverty.json`. It checks each (expected columns or keys, not empty, 37 states, a national cell) and holds them in memory. If that fails, the API still starts: `/status` and the data endpoints return 503. `/status` says which file failed and which check (for example `could not fetch states.json`); the underlying error goes only to the service log. It tries again on a later request after 30 s, doubling to at most 10 minutes. A request that arrives while a load is running is not held up: it gets the 503 at once. In `CURBCUT_DATA_DIR` mode `/status` shows the source as `local directory`, not the path.

The data change only when the service restarts. `render.yaml` sets `autoDeployTrigger: checksPass`, so each commit to `main` redeploys the API once its GitHub checks (including the Pages deploy) pass; the free plan's sleep and wake also restart it. `/status` shows the SHA-256 of what it loaded, to compare with the site.

## Licences and citations

- The DHS Program, Nigeria Demographic and Health Survey 2024 (National Population Commission and ICF); Curb Cut estimates from the microdata, disclosure-checked. Aggregates only, for the registered project.
- JONAPWD 2025 Assumptive Disability Disaggregated Data: cited, not redistributed (all rights reserved). Its figures are an assumption, not a count.
- NBS Multidimensional Poverty Index Survey 2021: aggregated reporting only (NBS terms). GHS-Panel W4/W5: NBS and the World Bank.
- Population: NBS Demographic Bulletin 2023, Annex 3 (source: National Population Commission).
- Code: MIT.

## Deploy on Render (author)

Once the branch is merged to `main`:

1. Go to https://dashboard.render.com and sign in.
2. Click **New** (top right), then **Blueprint**.
3. Click **Connect** next to `batestguy/curb-cut` (if it isn't listed, connect GitHub first and allow the repo).
4. Enter a Blueprint name (for example `curb-cut`), keep branch `main`, and leave **Blueprint Path** as `render.yaml`.
5. Check the list shows one free web service, `curb-cut-api`, in Frankfurt, then click **Deploy Blueprint**.
6. Open the service (**Dashboard** → `curb-cut-api`). The build runs `uv sync --locked --package curbcut-api --no-default-groups`; wait for **Live** in the Events list.
7. The URL is under the service name at the top of its page, of the form `https://curb-cut-api.onrender.com` (Render may add a suffix if the name is taken). Open `<URL>/status`: it should show `"ready": true` and five files.
8. Run the two client-address checks above, then give Claude the URL so the README and methodology page can link it.

Render's Blueprint steps were checked against https://render.com/docs/infrastructure-as-code on 2026-11-04.

## Run locally

From the repo root, after building the site data (`site/public/data/`, see `CLAUDE.md`):

```
CURBCUT_DATA_DIR=site/public/data uv run uvicorn curbcut_api.app:app --port 8000
```

Then open http://127.0.0.1:8000/. Without `CURBCUT_DATA_DIR` it downloads from the live site. Tests: `uv run pytest packages/api` (synthetic files, no network).

## Packages (checked 2026-11-04)

Pinned in `packages/api/pyproject.toml`; nothing younger than two weeks:
- `fastapi==0.156.4` (2026-10-20): the newest release at least two weeks old (0.157.0 to 0.162.0 all came out from 2026-10-21 on).
- `uvicorn==0.54.0` (2026-09-25), `slowapi==0.1.10` (2026-06-13), `duckdb==1.5.6` (the root environment's pin).
- `httpx==0.28.1` (2024-12-06), dev only, for FastAPI's test client.
- Held back in `uv.lock` because the newest release was under two weeks old: `starlette` 1.9.0 (not 1.10.0), `anyio` 4.15.1 (not 4.16.0), `deprecated` 3.0.0 (not 3.0.1).
