// Shared by the main page's state explorer (explore.js) and the data explorer (explorer.js):
// a time limit for DuckDB-WASM's start-up, which never settles if the wasm fails to download
// inside its worker.

// Generous: the wasm is about 8 MB compressed, and a slow phone connection must not fail.
export const START_TIMEOUT_MS = 90_000;

export function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}
