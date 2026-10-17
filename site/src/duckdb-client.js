// DuckDB-WASM, self-hosted: Vite emits the wasm and worker files as assets (no CDN).
// Loaded with a dynamic import, so none of this is fetched until a state is chosen.
import * as duckdb from '@duckdb/duckdb-wasm';
import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import ehWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import ehWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';

const BUNDLES = {
  mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
  eh: { mainModule: ehWasm, mainWorker: ehWorker },
};

/**
 * Start DuckDB, register a Parquet file fetched from the site, and return a function that
 * runs a prepared query with positional parameters.
 *
 * `extensionsUrl` is the site's own copy of the DuckDB extension repository (see
 * scripts/fetch-duckdb-extensions.mjs), so the Parquet extension is not fetched from a CDN.
 */
export async function openParquet(url, name, sql, extensionsUrl) {
  const bundle = await duckdb.selectBundle(BUNDLES);
  const worker = new Worker(bundle.mainWorker);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  // The file is small, so fetch it whole rather than relying on HTTP range requests.
  const response = await fetch(url);
  if (!response.ok) throw new Error(`could not fetch ${name} (HTTP ${response.status})`);
  await db.registerFileBuffer(name, new Uint8Array(await response.arrayBuffer()));
  const conn = await db.connect();
  const repository = new URL(extensionsUrl, window.location.href).href.replace(/\/$/, '');
  await conn.query(`SET custom_extension_repository = '${repository.replaceAll("'", "''")}'`);
  const statement = await conn.prepare(sql);
  return async (...params) => (await statement.query(...params)).toArray();
}
