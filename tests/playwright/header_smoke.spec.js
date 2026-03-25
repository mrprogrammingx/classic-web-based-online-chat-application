const { test, expect } = require('@playwright/test');
const helpers = require('./helpers');

// Smoke test: register a user via API, set the server-issued token cookie in the browser
// and assert the shared header displays the authenticated user's name.
test('header shows user after login (smoke)', async ({ browser, request }) => {
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

  // create a fresh user via API helper
  const created = await helpers.registerUser(request, 'smoke');
  const user = created.user;
  const token = created.token;

  // create a browser context and set the HttpOnly token cookie so the UI bootstraps authenticated
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.addCookies([{
    name: 'token',
    value: token,
    url: BASE,
    httpOnly: true,
    sameSite: 'Lax'
  }]);

  const page = await context.newPage();
  await page.goto(BASE);

  // wait for the header user-toggle to appear and show the registered username
  const sel = '.user-toggle strong';
  await page.waitForSelector(sel, { timeout: 15000 });
  const shown = await page.textContent(sel);
  expect(shown && shown.trim()).toBe(user.username);

  // ensure the unread button exists in header
  const unread = await page.$('#unread-total');
  expect(unread).not.toBeNull();

  // the newly-registered user should not see the admin button
  const adminBtn = page.locator('#admin-open');
  // admin button may exist but should be hidden for non-admin users
  const adminVisible = await adminBtn.isVisible().catch(()=>false);
  expect(adminVisible).toBeFalsy();

  await context.close();
});
