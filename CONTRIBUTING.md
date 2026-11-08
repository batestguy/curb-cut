# Contributing to Curb Cut

Thank you for helping. Curb Cut is run by one person, so the most useful contributions are the ones listed first.

## 1. Tell us what doesn't work (no account needed)

If anything on the site is hard to use with a screen reader, keyboard, magnifier, phone or slow connection, or if a figure looks wrong, please say so. These reports matter more than code.

- **Email:** batesthommie@gmail.com (backup: jzbannister@atbu.edu.ng). Say which page, what went wrong, and your browser and screen reader if you use one.
- **GitHub:** [open an issue](https://github.com/batestguy/curb-cut/issues/new).

If you use a screen reader every day and would give 30 minutes to a guided test, see [`docs/screen-reader-testing.md`](docs/screen-reader-testing.md).

## 2. Review a translation

The chart descriptions in Hausa, Yorùbá, Igbo and Nigerian Pidgin were **drafted by an AI model and have not been reviewed by a native speaker**. If you speak one of these languages, a review is very welcome: start with ["What to check first with a native speaker"](packages/disability-access-charts/docs/languages.md#what-to-check-first-with-a-native-speaker), and send corrections by email or as an issue. Numbers stay as digits; only the wording changes.

## 3. Code and documentation

### Rules that are never relaxed

- **No microdata.** Household- and person-level survey data are licensed and may not be published, committed, or sent to any online service (including LLMs). Only aggregates that pass the disclosure check (`packages/ingest/src/curbcut_ingest/disclosure.py`; no cell from fewer than 30 respondents) are public. CI never uses restricted data; it runs on synthetic fixtures.
- **Accessibility is a requirement, not a feature.** Every page change must keep axe clean, Lighthouse accessibility at 100, and full keyboard use. Charts go through `disability-access-charts`, never around it.
- **Every number names its source**, and claims about the data are checked against it.
- **$0 to run.** No paid services.

### Set-up

Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js for the site, and R for the restricted-zone estimation (not needed for most changes).

```bash
uv sync                      # Python workspace (dbt, the chart library, ingest, API)
uv run ruff check . && uv run ruff format . && uv run pyright
uv run pytest
cd site && npm ci && npm run build && npm test     # the site: unit, Playwright + axe
npm run lighthouse                                  # accessibility must stay at 100
```

Building the site's data from the public aggregates (dbt on DuckDB, chart JSON, state pages) is described in [`CLAUDE.md`](CLAUDE.md) under "Commands", and the full pipeline from licensed microdata in [`docs/reproduce.md`](docs/reproduce.md).

### Pull requests

- Branch from `main`; one change per pull request.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(site): …`, `fix(charts): …`, `docs: …`), and user-visible changes get a line in [`CHANGELOG.md`](CHANGELOG.md).
- CI must pass: lint, types, tests, the dbt build on fixtures, the chart audit (`disability-access-charts check --strict`), Playwright + axe, and Lighthouse.
- For a change people will see or hear, say how you checked it by keyboard and, if you can, with a screen reader.
- Check that any new package exists, is maintained, and is free before adding it.

## 4. The chart library

`disability-access-charts` lives in [`packages/disability-access-charts/`](packages/disability-access-charts/) and is published to PyPI from tags `charts-v<version>`. Bug reports with a minimal chart document are especially useful, above all a claim the checker wrongly accepts or rejects.

## Conduct

Be respectful and patient. Disability is the subject of this project and part of many contributors' lives: write about people the way you would want to be written about. Harassment of any kind is not tolerated; report it to batesthommie@gmail.com.

By contributing you agree that your contribution is released under the project's [MIT licence](LICENSE).
