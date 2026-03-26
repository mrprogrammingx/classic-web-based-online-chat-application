// Playwright config to collect traces and screenshots on failure
const { devices } = require('@playwright/test');

/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: 'tests/e2e/playwright',
  timeout: 60 * 1000,
  expect: { timeout: 5000 },
  reporter: [ ['list'], ['html', { open: 'never' }] ],
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    baseURL: process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000',
  },
};
