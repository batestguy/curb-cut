# Fay-Herriot state covariates (P4a step 2)

`state_covariates.csv` holds the state-level covariates frozen in `docs/fay-herriot-covariates.md` (approved by the author on 2026-10-28, before any model was fitted), one row per state (36 + FCT). Values are raw, not standardised. They were built without looking at any disability figure: nothing here was joined, correlated or plotted against the outcome.

C4 is literacy of **women 15–49**, not 15–24 as first listed: MICS publishes 15–24 only nationally, and the author approved the change on 2026-10-28, before any fit (see C4 below and `docs/verification.md` D53).

Built on 2026-10-28 by `uv run python -I -m curbcut_ingest.covariates` (`packages/ingest/src/curbcut_ingest/covariates.py`), which reads the downloaded files from the git-ignored `data/sources/covariates/`, checks each against `source_sha256.txt`, and refuses to write if any check fails. `manifest.json` records the build checks.

## Columns

| Column | Meaning |
|---|---|
| `state`, `state_code` | Canonical state name and ISO 3166-2 code, as in seed `dim_states` |
| `c1_share_60plus` | **C1.** Share of the 2020 population aged 60+ (WorldPop) |
| `c2_urban_share` | **C2.** Share of the 2020 GHS-POP population in GHS-SMOD classes 21–30 |
| `c3_mpi_headcount` | **C3.** MPI incidence H as a proportion (NBS MPI 2022, Table D6) |
| `c4_female_literacy` | **C4.** Share of women 15–49 who are literate (MICS6 2021, Table SR.6.1W) |
| `c5_log_density` | **C5.** ln(`population_2023` / `area_km2`), people per km² |
| `population_2023` | NBS Demographic Bulletin 2023 Annex 3 total (seed `state_facts`, `docs/verification.md` D14); input to C5 |
| `area_km2` | Area of the geoBoundaries ADM1 polygon in EPSG:6933; input to C5 |
| `wp2020_pop_total` | **Benchmark weight, not an FH covariate.** WorldPop 2020 population, all age bands, both sexes |
| `wp2020_pop_18plus` | **Benchmark weight, not an FH covariate.** WorldPop 2020 population aged 18+, both sexes (see the approximation below) |

`wp2020_pop_total` and `wp2020_pop_18plus` come from the same zonal sums as C1. They are there for the benchmarking step (weighting state estimates to the national direct estimate) and must not enter the covariate selection.

**The 18+ approximation.** WorldPop publishes 5-year bands, so there is no 18+ band. `wp2020_pop_18plus` is the 20–24 to 80+ bands plus **2/5 of the 15–19 band**, which assumes the five single years of age in 15–19 are equally large. Nationally this gives 51.6% aged 18+.

## Sources

### C1: share aged 60+ (`docs/verification.md` D50)

- WorldPop, "Nigeria 100m Age structures" (constrained, UN-adjusted), 2020. Hub: https://hub.worldpop.org/geodata/summary?id=50493. Files: `nga_[f|m]_[age]_2020_constrained_UNadj.tif` from https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020_Constrained_UNadj/2020/NGA/ (36 GeoTIFFs, about 60 MB each, last modified 30 Nov 2020; downloaded 2026-10-28). SHA-256 of each is in `source_sha256.txt`.
- **Licence: CC BY 4.0.** The hub page says: "WorldPop datasets are available under the Creative Commons Attribution 4.0 International License."
- **Citation:** Bondarenko M., Kerr D., Sorichetta A., and Tatem, A.J. 2020. Estimates of total number of people per grid square, adjusted to match the corresponding UNPD 2020 estimates and broken down by gender and age groupings, produced using Ecopia.AI and Maxar Technologies building footprints. WorldPop, University of Southampton, UK. doi:10.5258/SOTON/WP00699
- WorldPop publishes no admin-1 table for this release, so the script sums each raster over the committed geoBoundaries ADM1 polygons (`data/public/geoboundaries/`). A cell belongs to the polygon containing its centre. Numerator: bands 60, 65, 70, 75 and 80 (80+), both sexes. Denominator: all 18 bands, both sexes.
- Checks: the 36 rasters sum to 206,139,587 (the UN 2020 total the product is adjusted to); 0.018% of it falls outside the simplified polygons and is dropped. The national share aged 60+ is 4.95%. State values range from 2.4% (FCT) to 7.1% (Enugu).
- The age structure is modelled (method of Pezzulo et al. 2017, Sci Data 4:170089, per the hub page), with country totals adjusted to UN WPP 2019; it is not a state census count.

### C2: urban share (D51)

- JRC GHSL, **GHS-SMOD R2023A V2-0** (`GHS_SMOD_E2020_GLOBE_R2023A_54009_1000_V2_0.tif`) and **GHS-POP R2023A V1-0** (`GHS_POP_E2020_GLOBE_R2023A_54009_1000_V1_0.tif`), 2020 epoch, 1 km, World Mollweide (ESRI:54009). Downloaded on 2026-10-28 from the JRC's AWS open-data bucket (https://jrc-ghsl.s3.amazonaws.com/, keys `ghs-smod/r2023a/54009/1000m/2020/…` and `ghs-pop/r2023a/54009/1000m/2020/…`), because the JRC FTP server (jeodpp.jrc.ec.europa.eu) timed out. The bucket holds global files, not tiles; the script reads only the window around Nigeria.
- **Licence**, from the GHSL Data Package 2023 (JRC133256, doi:10.2760/098587, p. 10, "Terms of Use"): "The data in this data package are provided free-of-charge © European Union, 2023. Reuse is authorised, provided the source is acknowledged. The reuse policy of the European Commission is implemented by a Decision of 12 December 2011 (2011/833/EU)." The AWS registry entries (`ghs-smod`, `ghs-pop`) say: "GHSL data are provided under the Creative Commons Attribution 4.0 International (CC BY 4.0) license." Both require only acknowledgement of the source, which this README and the methodology note give.
- **Citations** (from the Data Package, pp. 53 and 66):
  - Schiavina, Marcello; Melchiorri, Michele; Pesaresi, Martino (2023): GHS-SMOD R2023A - GHS settlement layers, application of the Degree of Urbanisation methodology (stage I) to GHS-POP R2023A and GHS-BUILT-S R2023A, multitemporal (1975-2030). European Commission, Joint Research Centre (JRC) [Dataset] doi: 10.2905/A0DF7A6F-49DE-46EA-9BDE-563437A6E2BA
  - Schiavina, Marcello; Freire, Sergio; Alessandra Carioli; MacManus, Kytt (2023): GHS-POP R2023A - GHS population grid multitemporal (1975-2030). European Commission, Joint Research Centre (JRC) [Dataset] doi: 10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE
- Urban = SMOD classes 21 (suburban or peri-urban), 22 (semi-dense urban cluster), 23 (dense urban cluster) and 30 (urban centre), as fixed before any fit. Cells are assigned to the polygon containing their centre. Results range from 0.555 (Taraba) to 0.992 (Lagos). These shares are high because Degree of Urbanisation level 1 counts dense rural settlements as urban clusters; they are not comparable with census "urban" definitions.

### C3: MPI headcount (D52)

- NBS, *Nigeria Multidimensional Poverty Index (2022)* (survey November 2021 – February 2022), **Table D6 "Multidimensional poverty by State (Nigeria MPI)"**, printed pp. 100–101 (PDF pp. 122–123). PDF from the OPHI mirror: https://ophi.org.uk/sites/default/files/2024-05/Nigeria_MPI_2022_report.pdf (linked from https://ophi.org.uk/node/3733), 184 pages, SHA-256 `0fcfe91740781bbd0f4755fc08e24a7c69c5d65c3dd1ee181e362eac67a02111`. Figures are cited; the PDF is not redistributed.
- `nbs_mpi2022_table_d6.csv` is the full table as printed (MPI, H and A with their 95% confidence intervals, population share, number of poor), with the PDF page of each row. State labels are as printed ("FCT Abuja" matches through the alias seed).
- **Hand validation:** both pages were rendered (pypdfium2, not committed) and compared with the CSV by eye on 2026-10-28. An independent review then found every value of all 37 rows in the PDF text layer of those pages. The script also checks that MPI = H × A for every row (within rounding), that every value lies inside its confidence interval, that Ondo (27.2%) and Sokoto (90.5%) are the lowest and highest, as in the press release, and that the population-share-weighted mean of H is within 1 point of the national 62.9% (Table D4, printed p. 99).
- The report notes that results are representative at state level for every state except Borno.

### C5: population density (D54)

- Population: NBS Demographic Bulletin 2023, Annex 3, 2023 projection (seed `state_facts.population_2023`, D14).
- Area: the committed geoBoundaries ADM1 polygons (simplified file, D11; CC BY 4.0; Runfola et al. 2020, "geoBoundaries: A global database of political administrative boundaries", PLoS ONE 15(4): e0231866; boundaries from GRID3, 2022; attribution in `data/public/geoboundaries/README.md`) reprojected to EPSG:6933 (equal area) with GDAL, then the planar area of each polygon. The 37 areas sum to 912,729 km². Areas come from the simplified boundaries, so each is approximate; no official state-area table was found.
- Lagos is the densest state (ln density 8.20, about 3,640 people per km²) and Taraba the least dense (4.14).

### C4: literacy of women 15–49 (D53)

- NBS/UNICEF, *Nigeria Multiple Indicator Cluster Survey 2021 (MICS6), Survey Findings Report* (August 2022), **Table SR.6.1W "Literacy (women)" (continued), printed p. 46 (PDF p. 61)**: total percentage literate among women aged 15–49, by state. Obtained from UNICEF Nigeria (https://www.unicef.org/nigeria/media/6316/file/2021%20MICS%20full%20report%20.pdf, 804 pages, SHA-256 `a09c74cb7f7c7439297b56626a206824aacc4add4db8686b1c3291399a42cf23`), because the MICS S3 link returns 403. Figures are cited; the PDF is not redistributed. Women who attended higher or tertiary school count as literate without a test; the others read a sentence aloud.
- **Change from the frozen list, approved by the author on 2026-10-28.** The list named women aged **15–24** (MICS indicator SR.2), but MICS publishes that rate only nationally (50.5%, printed p. 45). The author chose the same table's **15–49** state figures over the pre-declared fallback (NDHS 2024 literacy), because NDHS literacy shares the outcome's sample. The choice was made before any model was fitted.
- `mics2021_table_sr61w.csv` is the full state block of the table as printed (the distribution by school level and literacy, the total literate and the number of women). The script checks that every row adds to 100 and that the literate columns add to the total literate, within rounding. The page was rendered and compared by eye with the transcription on 2026-10-28.
- **Borno caveat:** MICS surveyed only 7 LGAs of Borno ("Borno (7 LGAs)"), so its value is not state-representative.
- Values range from 0.067 (Jigawa) to 0.835 (Imo).

## Files

- `state_covariates.csv`: the covariates (37 rows).
- `nbs_mpi2022_table_d6.csv`: transcription of NBS MPI 2022 Table D6.
- `mics2021_table_sr61w.csv`: transcription of the state rows of MICS6 2021 Table SR.6.1W.
- `source_sha256.txt`: SHA-256 of every downloaded file (36 WorldPop rasters, 2 GHSL rasters, the MPI and MICS reports and the GHSL Data Package), paths relative to `data/sources/covariates/`.
- `manifest.json`: build date and checks, written by the script.

## Dependency

The raster work uses `rasterio` 1.5.2 (BSD-3-Clause, wheels bundle GDAL), added to `packages/ingest` (`docs/verification.md` D55). Polygon areas use rasterio's GDAL reprojection and a plain shoelace sum, so no `shapely` or `pyproj` is needed.
