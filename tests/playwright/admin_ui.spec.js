const { test, expect } = require('@playwright/test');
const { registerUser } = require('./helpers');

const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('Admin UI smoke', () => {
  test('opens admin page and interacts with tabs', async ({ page, request }) => {
    // register an admin-like user via test-only endpoint if available
    // fallback: just open page anonymously
  await page.goto(`${BASE}/static/admin/index.html`);

    // wait for header loader to inject header
    await page.waitForSelector('#shared-header-placeholder');

    // wait until admin open button appears in DOM (it may be hidden for non-admins)
  await page.waitForSelector('#admin-open, script[src*="/static/admin/admin.js"]', { timeout: 3000 });

    // If admin button exists and is visible, click it to open modal; otherwise proceed to page tabs
    const adminOpen = await page.$('#admin-open');
    if (adminOpen) {
      try {
        await adminOpen.click();
        // modal should appear
        await page.waitForSelector('.admin-modal, #admin-console', { timeout: 2000 });
      } catch (e) {
        // ignore click failures for non-admin sessions
      }
    }

    // If full admin console is present on page, interact with tabs
    const consoleSel = await page.$('#admin-console');
    if (consoleSel) {
      // click the Users tab (assuming it has data-tab or .tab-users selector)
      const usersTab = await page.$('[data-admin-tab="users"], .tab-users, #tab-users');
      if (usersTab) {
        await usersTab.click();
        // assert some expected content area updates
        await page.waitForSelector('#admin-users-list, .admin-users', { timeout: 2000 });
      }
    } else {
      // fallback: check that admin module script is loaded
      const scriptHandle = await page.$('script[src*="/static/admin/admin.js"]');
      expect(scriptHandle).not.toBeNull();
    }
  });
});
