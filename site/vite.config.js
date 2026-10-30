import { readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';

// The state pages are generated before the build (packages/transform/scripts/
// build_state_pages.py writes site/states/*.html); each one is an input of its own, so it gets
// the shared stylesheet and the base path. Without them (no data built yet) the build still
// works, with the two hand-written pages only.
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

// GitHub Pages serves the site at /curb-cut/. Override with SITE_BASE=/ for other hosts.
export default defineConfig({
  base: process.env.SITE_BASE ?? '/curb-cut/',
  build: {
    target: 'es2022',
    // Plotly and the DuckDB-WASM bundles are large by nature; they are loaded once.
    chunkSizeWarningLimit: 4000,
    // The main page, the methodology note and the 37 state pages with their index.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        methodology: resolve(import.meta.dirname, 'methodology.html'),
        ...statePages,
      },
    },
  },
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
});
