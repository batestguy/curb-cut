import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import sensitivityStatic from './scripts/sensitivity-static.mjs';

// The state pages are generated before the build (packages/transform/scripts/
// build_state_pages.py writes site/states/*.html); each one is an input of its own, so it gets
// the shared stylesheet and the base path. Without them (no data built yet) the build still
// works, with the three hand-written pages only.
const statesDir = resolve(import.meta.dirname, 'states');
let statePages = {};
try {
  statePages = Object.fromEntries(
    readdirSync(statesDir)
      .filter((file) => file.endsWith('.html'))
      .map((file) => [`states/${file.slice(0, -5)}`, resolve(statesDir, file)]),
  );
} catch {
  statePages = {};
}

// The poverty page and the data dictionary are generated too
// (packages/transform/scripts/build_poverty_page.py, build_data_dictionary.py).
const generated = Object.fromEntries(
  [
    ['poverty', 'poverty.html'],
    ['dataDictionary', 'data-dictionary.html'],
  ]
    .map(([name, file]) => [name, resolve(import.meta.dirname, file)])
    .filter(([, path]) => existsSync(path)),
);

// GitHub Pages serves the site at /curb-cut/. Override with SITE_BASE=/ for other hosts.
export default defineConfig({
  base: process.env.SITE_BASE ?? '/curb-cut/',
  // The sensitivity page's definitions, <noscript> version and static downloads, written
  // from public/data/sensitivity.json at build time (scripts/sensitivity-static.mjs).
  plugins: [
    sensitivityStatic({
      root: import.meta.dirname,
      siteUrl: process.env.SITE_URL ?? 'https://batestguy.github.io/curb-cut/',
    }),
  ],
  build: {
    target: 'es2022',
    // Plotly and the DuckDB-WASM bundles are large by nature; they are loaded once.
    chunkSizeWarningLimit: 4000,
    // The main page, the methodology note, the data explorer, the sensitivity page, the
    // poverty page, the data dictionary and the 37 state pages with their index.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        methodology: resolve(import.meta.dirname, 'methodology.html'),
        explorer: resolve(import.meta.dirname, 'explorer.html'),
        sensitivity: resolve(import.meta.dirname, 'sensitivity.html'),
        walkthrough: resolve(import.meta.dirname, 'walkthrough.html'),
        ...generated,
        ...statePages,
      },
    },
  },
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
});
