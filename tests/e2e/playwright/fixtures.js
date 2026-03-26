const base = require('@playwright/test');
const { test: baseTest, expect } = base;

// Extend the base test to start tracing for each test and save artifacts only when the test fails.
const test = baseTest.extend({
  // internal fixture that runs per-test
  traceOnFailure: async ({ page }, use, testInfo) => {
    // start tracing (best-effort) for richer artifacts
    try {
      await page.context().tracing.start({ screenshots: true, snapshots: true, sources: true });
    } catch (e) {
      // tracing might not be supported in certain contexts; ignore errors
      // console.debug('tracing start failed', e);
    }

    await use();

    // if the test failed, save trace and screenshot to the test's output path
    if (testInfo.status !== 'passed') {
      try {
        const tracePath = testInfo.outputPath('trace.zip');
        await page.context().tracing.stop({ path: tracePath });
      } catch (e) {
        // ignore
      }
      try {
        const screenshotPath = testInfo.outputPath('screenshot.png');
        await page.screenshot({ path: screenshotPath, fullPage: false });
      } catch (e) {
        // ignore
      }
    } else {
      // if passed, stop tracing without saving
      try {
        await page.context().tracing.stop();
      } catch (e) {
        // ignore
      }
    }
  }
});

module.exports = { test, expect, request: base.request };
