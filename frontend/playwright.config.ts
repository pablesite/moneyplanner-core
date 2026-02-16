import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  use: {
    baseURL: process.env.PW_BASE_URL || 'http://localhost:5174',
    headless: true,
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev -- --host 0.0.0.0 --port 5174 --mode e2e',
    url: process.env.PW_BASE_URL || 'http://localhost:5174',
    reuseExistingServer: false,
    env: {
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || 'http://host.docker.internal:8000',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
