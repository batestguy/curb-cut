// Lighthouse CI (P6 item 3): the accessibility category must score 100 on every page type.
// Runs against `vite preview` of the production build (run `npm run build` first), with
// Playwright's Chromium unless CHROME_PATH is set. Reports go to .lighthouseci/ (git-ignored);
// nothing is uploaded to a public server.
const base = process.env.SITE_BASE ?? '/curb-cut/';
const port = process.env.LHCI_PORT ?? '4318';
const origin = `http://127.0.0.1:${port}${base}`;

const pages = [
  '',
  'methodology.html',
  'explorer.html',
  'poverty.html',
  'data-dictionary.html',
  'states/',
  'states/kano.html',
  'states/lagos.html',
  'states/federal-capital-territory.html',
];

module.exports = {
  ci: {
    collect: {
      startServerCommand: `npm run preview -- --host 127.0.0.1 --port ${port} --strictPort`,
      startServerReadyPattern: 'Local',
      url: pages.map((p) => `${origin}${p}`),
      numberOfRuns: 1,
      settings: {
        onlyCategories: ['accessibility', 'best-practices'],
        chromeFlags: '--headless=new --no-sandbox',
      },
    },
    assert: {
      assertions: {
        'categories:accessibility': ['error', { minScore: 1 }],
        // Reported, not gated: best practices include third-party and console checks.
        'categories:best-practices': ['warn', { minScore: 0.9 }],
      },
    },
    upload: { target: 'filesystem', outputDir: '.lighthouseci/reports' },
  },
};
