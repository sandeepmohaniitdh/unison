import { defineConfig, devices } from '@playwright/test'

// End-to-end tests: a real browser against the whole stack started with `docker compose up`.
// They use the seeded demo data and Mailpit, so start the stack first (see README.md).
//
//   E2E_BASE_URL   the app (default http://localhost:8080)
//   MAILPIT_URL    Mailpit, to read the emails the app sends (default http://localhost:8025)
export default defineConfig({
  testDir: './tests',
  // The tests change shared seed data (join requests, finals), so they run one after another.
  workers: 1,
  fullyParallel: false,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    timezoneId: 'Asia/Kolkata',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
