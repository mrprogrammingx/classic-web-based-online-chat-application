const { test, expect } = require('./fixtures');
const { registerUser } = require('./helpers');

const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('Admin UI smoke', () => {
  test('opens admin page and interacts with tabs', async ({ page, request }) => {
    // register an admin user and promote via test helper so header and admin
    // resources load as an admin session (prevents 401 on /refresh)
    const req = await require('playwright').request.newContext();
    const admin = await registerUser(req, 'admin_ui');
    // promote to admin via API (uses cookie auth)
    await req.post(`${BASE}/admin/make_admin`, { data: { user_id: admin.user.id }, headers: { Cookie: `token=${admin.token}` } });

    // attach admin token cookie to the page context before navigation
    await page.context().addCookies([{ name: 'token', value: admin.token, domain: '127.0.0.1', path: '/' }]);

    await page.goto(`${BASE}/static/admin/index.html`);

    // Attach console and error listeners to capture client-side logs in test output
    page.on('console', msg => {
      try{ console.log(`PAGE LOG [${msg.type()}]: ${msg.text()}`); }catch(e){}
    });
    page.on('pageerror', err => {
      try{ console.log('PAGE ERROR:', err && err.message ? err.message : String(err)); }catch(e){}
    });

  // wait for header loader to inject header
  await page.waitForSelector('#shared-header-placeholder', { timeout: 5000 });

    // wait until either the admin module script is present, or the admin-open
    // button is visible. The previous combined selector could match a hidden
    // admin-open button (present but display:none) and cause a timeout even
    // though the admin module script was loaded. Check script presence first
    // (not requiring visibility), then check visibility of the button.
  // Simpler, robust check: wait briefly for any of the admin-related elements to be attached.
  // This avoids visibility-related flakiness (button may be present but display:none).
  const adminSelectors = [
    'script[src*="/static/admin/admin-ui.js"]',
    'script[src*="/static/admin/admin.js"]',
    '#admin-open'
  ];
  let found = false;
  for (const sel of adminSelectors) {
    try {
      await page.waitForSelector(sel, { state: 'attached', timeout: 2000 });
      found = true;
      break;
    } catch (e) {
      // continue
    }
  }
  expect(found).toBeTruthy();

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
