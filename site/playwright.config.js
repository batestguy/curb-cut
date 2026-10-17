import { defineConfig, devices } from '@playwright/test';

// Tests run against `vite preview` of the production build (run `npm run build` first).
const base = process.env.SITE_BASE ?? '/curb-cut/';
const origin = 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  // Each test downloads the ~35 MB DuckDB wasm; more workers than this starve the preview
  // server on small machines and CI runners.
  workers: 2,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `${origin}${base}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1',
    url: `${origin}${base}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
