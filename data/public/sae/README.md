# Fay-Herriot small-area estimation (P4a step 2)

The record of the Fay-Herriot attempt for DHS 2024 DISABILITY3, adults 18+, by state. **No model passed the pre-declared diagnostics, and the direct estimates are the headline** (author, 2026-10-28). The rules, the result and the decision are in `docs/fay-herriot-covariates.md`.

Built from public files only (`data/public/aggregates/`, `data/public/covariates/`, `data/public/geoboundaries/`) by `uv run python -I -m curbcut_ingest.sae`, which runs `packages/ingest/R/fay_herriot.R` (R `sae` 1.3, `docs/verification.md` D47).

| File | Contents |
|---|---|
| `fh_model_selection.csv` | All 26 candidate models (every subset of the five standardised covariates with at most 3 terms), fitted by ML: log-likelihood, BIC, σ²ᵤ, coefficients with p-values, and the rank after the tie rule |
| `fh_diagnostics_failed.json` | The failure rule; Shapiro-Wilk p, large-state test and states outside their direct interval for each model in rank order; GVF R²; shrinkage γ and median MSE ratios of the top-ranked model |

If a later run passes the diagnostics (for example after the direct estimates change), the script writes `fh_state.csv` and `fh_summary.json` instead.
