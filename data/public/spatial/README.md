# Spatial analysis (P4a step 3)

Spatial analysis of the DHS 2024 **direct** state estimates (both sexes, no breakdown). Fay-Herriot failed its pre-declared diagnostics (`docs/verification.md` D56), so nothing here uses model estimates. **No spatial method is run on JONAPWD** (D17): its state totals are about 15% of population, so a spatial result would only reflect population. Results are recorded in D58; the facilities source in D57.

Built from public files only (`data/public/aggregates/dhs2024_state.csv`, `data/public/geoboundaries/`, `facilities_state.csv` here) by `uv run python -I -m curbcut_ingest.spatial`, which runs `packages/ingest/R/spatial.R` (R `spdep` 1.4-2, D47). Permutation tests use 9,999 permutations and seed 20261028; a rerun reproduces every file byte for byte. `facilities_state.csv` is built separately, from the git-ignored GRID3 GeoPackage, by `uv run python -I -m curbcut_ingest.grid3`.

| File | Contents |
|---|---|
| `neighbours.csv` | Queen contiguity from the committed simplified polygons (`spdep::poly2nb`, default snap), as a directed edge list with row-standardised weights. 172 links (86 pairs); every state has 1–10 neighbours; the list is symmetric; Lagos–Ogun, Kano–Jigawa, FCT–Niger and Borno–Yobe are adjacent. No snap tolerance was needed. |
| `moran_global.csv` | Global Moran's I (`spdep::moran.mc`, one-sided, positive autocorrelation) for 8 measures: DISABILITY3 and the six WG-SS domains for adults 18+, and DISABILITY3 for ages 5–17 (secondary). Raw permutation p, Benjamini-Hochberg adjusted p across the 8, and how many states are `reliable` or `review` |
| `lisa_disability3_18plus.csv` | **Exploratory.** Local Moran's I (`spdep::localmoran_perm`, two-sided, conditional permutation) for DISABILITY3 18+; Benjamini-Hochberg q across the 37 states; quadrant; class (High-High, Low-Low, High-Low, Low-High, or Not significant at q < 0.05) |
| `profile_clusters.csv` | **Descriptive.** Each state's six 18+ domain prevalences, their z-scores, and its cluster (Ward.D2 on Euclidean distance of the z-scores) |
| `profile_silhouette.csv` | Mean silhouette for k = 2–6 and the chosen k (highest mean silhouette; a tie goes to the smaller k) |
| `facilities_state.csv` | GRID3 NGA - Health Facilities v2.0 (CC BY 4.0, D57) counted by state, with NBS 2023 population and facilities per 100,000 |
| `services_vs_need.json` | **Ecological, descriptive.** Spearman correlation of facilities per 100,000 with DISABILITY3 18+ prevalence; two-sided permutation p; caveats |
| `summary.json` | Every headline number, plus one plain-English sentence per result for the site |

## Results

- **Global Moran's I.** After the Benjamini-Hochberg correction, no measure is significantly clustered at 0.05. DISABILITY3 18+: I = 0.13, p = 0.071 (adjusted 0.105); all 37 states reliable. Four domains have raw p below 0.05 (communication 0.009, walking 0.0205, hearing 0.025, cognition 0.041) but adjusted p of 0.067–0.082. Children 5–17: I = −0.02, p = 0.36.
- **Precision.** Many single-domain cells have few events (21–28 of 37 states flagged `review` for hearing, cognition, self-care and communication). Independent sampling noise biases Moran's I towards 0, so "no clear clustering" for those measures is not evidence that there is no pattern.
- **LISA (exploratory).** No state is significant after the FDR correction (smallest q = 0.32). The 37 states are all "Not significant".
- **Profile clusters (descriptive).** k = 2 has the highest mean silhouette (0.56). Seven states (Abia, Adamawa, Benue, Enugu, Imo, Kano, Taraba) are, on average, above the state average in all six domains; the other 30 are, on average, below it in all six. Because each domain is standardised and Ward clustering is driven by distance, the split mostly reflects overall level of reported difficulty, not a different mix of difficulties.
- **Services against needs (ecological).** Spearman ρ = 0.29 between facilities per 100,000 and DISABILITY3 18+ prevalence, two-sided permutation p = 0.078. This compares state averages only: no causal claim, no inference about individuals. General health facilities are not disability services, and GRID3 v2.0 is non-exhaustive and not validated by government.
