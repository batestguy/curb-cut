import { resolve } from 'node:path';
import { defineConfig } from 'vite';

// GitHub Pages serves the site at /curb-cut/. Override with SITE_BASE=/ for other hosts.
export default defineConfig({
  base: process.env.SITE_BASE ?? '/curb-cut/',
  build: {
    target: 'es2022',
    // Plotly and the DuckDB-WASM bundles are large by nature; they are loaded once.
    chunkSizeWarningLimit: 4000,
    // Two pages: the main page and the methodology note.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        methodology: resolve(import.meta.dirname, 'methodology.html'),
      },
    },
  },
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
});
