# geoBoundaries: Nigeria states (ADM1)

`geoBoundaries-NGA-ADM1_simplified.geojson` is the simplified gbOpen ADM1 boundary file for
Nigeria: 37 units (36 states and the Federal Capital Territory). It is committed unchanged
so that CI can build the site's locator map without network access.

- **Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Attribution (shown on the site):** "Boundaries: geoBoundaries (CC BY 4.0)".
- **Citation:** Runfola, D. et al. (2020) geoBoundaries: A global database of political
  administrative boundaries. *PLoS ONE* 15(4): e0231866. doi:10.1371/journal.pone.0231866
- **Boundary source:** GRID3 Nigeria state boundaries, year represented 2022; geoBoundaries
  build date 12 December 2023; boundary ID `NGA-ADM1-27671186`.
- **Metadata:** https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM1/
- **Downloaded:** 2026-10-17 from
  https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/NGA/ADM1/geoBoundaries-NGA-ADM1_simplified.geojson
- **Size:** 827,817 bytes. **SHA-256:**
  `edd28050c7f1ae40471424605f74e4d2df83502e4f301089761ae18f8ae2fbbf`

The site uses it only through `packages/transform/scripts/build_map.py`, which projects
the shapes, simplifies them further (sub-pixel at card size) and writes
`site/public/data/nigeria-states.json`. Its one non-canonical name, "Abuja Federal Capital
Territory", is mapped in the `state_name_aliases` seed.
