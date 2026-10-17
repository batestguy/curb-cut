// Self-host the DuckDB Parquet extension so the browser never fetches from a CDN at runtime.
//
// DuckDB-WASM autoloads extensions from extensions.duckdb.org by default. This build step
// downloads the pinned builds once, checks their SHA-256, and writes them under
// public/duckdb-extensions/ (git-ignored), mirroring the repository layout DuckDB expects:
//   <repository>/<duckdb version>/<platform>/<name>.duckdb_extension.wasm
// The page then sets `custom_extension_repository` to the site's own copy.
//
// When @duckdb/duckdb-wasm is upgraded, update DUCKDB_VERSION and the hashes; the Playwright
// test "DuckDB-WASM is not downloaded until a state is chosen" fails if anything still
// comes from another origin.
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DUCKDB_VERSION = 'v1.4.3'; // bundled by @duckdb/duckdb-wasm 1.32.0
const SOURCE = 'https://extensions.duckdb.org';
const FILES = {
  'wasm_eh/parquet.duckdb_extension.wasm':
    '22765c8f7dc741cda2b571a66ac7bb355295d7d69a6c37e5315b265672984f55',
  'wasm_mvp/parquet.duckdb_extension.wasm':
    '0785c6c95d003eff4faa7b3b4b660f02c9c92f6d68d135ddf330d42e3a650600',
};

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'duckdb-extensions');
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

for (const [path, expected] of Object.entries(FILES)) {
  const target = join(root, DUCKDB_VERSION, path);
  if (existsSync(target) && sha256(await readFile(target)) === expected) {
    console.log(`ok (cached) ${DUCKDB_VERSION}/${path}`);
    continue;
  }
  const url = `${SOURCE}/${DUCKDB_VERSION}/${path}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const actual = sha256(bytes);
  if (actual !== expected) {
    throw new Error(`${url}: SHA-256 ${actual} does not match pinned ${expected}`);
  }
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, bytes);
  console.log(`ok (downloaded) ${DUCKDB_VERSION}/${path}`);
}
