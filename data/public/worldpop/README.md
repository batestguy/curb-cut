# WorldPop state population totals (cross-check only)

`states_pop_total_scaled.csv` is copied unchanged (apart from line endings, CRLF → LF) from WorldPop's Nigeria population v3.0 release, file `NGA_population_v3_0_admin/states_pop_total_scaled.csv` inside `NGA_population_v3_0_admin.zip`. It gives 2025 state totals from the bottom-up gridded model, scaled to the UN World Population Prospects July 2025 median for Nigeria (237,527,782).

- Release: https://data.worldpop.org/repo/wopr/NGA/population/v3.0/ (zip last modified 2025-08-29; downloaded 2026-10-24)
- Zip SHA-256: `99ac8a6b09edfeecc8a90526b69d0c95882a52cacce8b4446d39731ed8d0004d`
- CSV SHA-256 as published (CRLF): `707f4a48ff045431cfe9da8e770dcbdfea4d9122441d4cad596a921d896a1ebc`; as committed (LF): `66f4e8a26de9dc5d53cc626e04b0f7d86bba28e735e9e45126ec46bd9d8f36c6`
- **Licence: CC BY 4.0.** The release README says the data "may be redistributed following the terms of a Creative Commons Attribution 4.0 International (CC BY 4.0) license".
- **Attribution:** Nnanatu C.C., Gadiaga A., Abbott T.J., Chamberlain H., Lazar A.N., Tatem A.J. (2025). Bottom-up gridded population estimates for Nigeria, version 3.0. WorldPop, University of Southampton. https://dx.doi.org/10.5258/SOTON/WP00782

State names are as WorldPop prints them ("Cross-River", "Federal Capital", "plateau"); the warehouse matches them through the alias seed (`stg_worldpop__state_population`).

**Use:** only to cross-check the NBS 2023 state denominators (`mart_state_population_check`, `docs/verification.md` D44). The project's denominators stay the NBS Demographic Bulletin 2023 Annex 3 projections. The two disagree a lot for some states (largest: Ogun, +99%), so WorldPop is not a drop-in substitute.
