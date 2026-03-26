const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

// Regression test: ensure the shared header is injected and that the sessions
// UI upgrades after the library loads (sessions list appears when opening user toggle).
test('header injects and sessions UI upgrades (regression)', async ({ browser, request }) => {
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

  // create a fresh user via API helper
  const created = await helpers.registerUser(request, 'sess');
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
  const selUser = '.user-toggle strong';
  await page.waitForSelector(selUser, { timeout: 15000 });
  const shown = await page.textContent(selUser);
  expect(shown && shown.trim()).toBe(user.username);

  // open the user toggle to reveal the sessions UI
  // tests expect #user-toggle to be present in the header; click it or the user-toggle wrapper
  const toggle = page.locator('#user-toggle, .user-toggle');
  await toggle.first().click();

  // wait for sessions list element to be injected (it may be present but hidden initially)
  const sessListSel = '.sessions-list';
  await page.waitForSelector(sessListSel, { state: 'attached', timeout: 15000 });

  // wait for at least one <li> to appear inside the sessions list (current session)
  await page.waitForFunction(() => {
    return document.querySelectorAll('.sessions-list li').length > 0;
  }, null, { timeout: 15000 });

  const items = await page.$$(`${sessListSel} li`);
  expect(items.length).toBeGreaterThan(0);

  await context.close();
});
