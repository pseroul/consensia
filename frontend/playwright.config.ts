import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration for Brainiac5 frontend.
 *
 * Setup:
 *   npm install --save-dev @playwright/test
 *   npx playwright install chromium
 *   npm run test:e2e
 *
 * All API calls are intercepted via page.route() – no real backend required.
 * The Vite dev server is started automatically by the webServer block.
 */
export default defineConfig({
  testDir: './e2e',

  // Run tests sequentially – the Raspberry Pi has limited CPU/memory.
  fullyParallel: false,
  workers: 1,
  retries: 0,

  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    // Capture a trace on the first retry so failures are diagnosable.
    trace: 'on-first-retry',
    // Short timeout: our mocked responses are instant.
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    // Reuse an already-running dev server during local development.
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
