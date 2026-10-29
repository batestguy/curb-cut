# Fay-Herriot small-area estimation (P4a step 2)

The record of the Fay-Herriot attempt for DHS 2024 DISABILITY3, adults 18+, by state. **No model passed the pre-declared diagnostics, and the direct estimates are the headline** (author, 2026-10-28). The rules, the result and the decision are in `docs/fay-herriot-covariates.md`.

Built from public files only (`data/public/aggregates/`, `data/public/covariates/`, `data/public/geoboundaries/`) by `uv run python -I -m curbcut_ingest.sae`, which runs `packages/ingest/R/fay_herriot.R` (R `sae` 1.3, `docs/verification.md` D47).

| File | Contents |
|---|---|
| `fh_model_selection.csv` | All 26 candidate models (every subset of the five standardised covariates with at most 3 terms), fitted by ML: log-likelihood, BIC, σ²ᵤ, coefficients with p-values, area-level R² (`r2_area`: 1 − σ²ᵤ / σ²ᵤ of the intercept-only model, floored at 0) and the rank after the tie rule |
| `fh_diagnostics_failed.json` | The failure rule; Shapiro-Wilk p, large-state test and states outside their direct interval for each model in rank order; GVF R²; for the top-ranked model, shrinkage γ, median MSE over the smoothed variance, and the relative change of each model estimate from the direct one; `raw_variance_sensitivity`, a refit with the raw direct variances (γ, MSE over direct variance, Shapiro-Wilk p), which is a check and not part of the declared rule |

If a later run passes the diagnostics (for example after the direct estimates change), the script writes `fh_state.csv` and `fh_summary.json` instead. In that path, `use_direct` and `fh_cv` refer to the unbenchmarked `fh`, and the spatial estimate `sfh` is back-transformed using its own analytic MSE on the arcsine scale as the variance (an approximation).
