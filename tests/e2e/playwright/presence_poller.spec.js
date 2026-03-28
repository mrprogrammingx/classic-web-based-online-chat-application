const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

test('presence poller auto-calls GET /presence and updates UI', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // register a user
  const a = await helpers.registerUser(request, 'pollA');

  // create a browser context with the session cookie and set TEST_MODE early
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  await page.addInitScript(() => { window.__TEST_MODE = true; });

  // intercept presence GETs so we can assert they happened automatically
  const calls = [];
  await page.route('**/presence/*', async (route) => {
    try{ calls.push(route.request().url()); }catch(e){}
    await route.continue();
  });

  await page.goto(BASE + '/static/home.html');
  await page.waitForSelector('#my-presence');

  // Wait up to 3s for the poller (test mode interval = 1s) to make a request
  const start = Date.now();
  while(Date.now() - start < 3000 && calls.length === 0){ await page.waitForTimeout(100); }
  expect(calls.length).toBeGreaterThan(0);

  // verify the UI text matches the server-reported status
  const resp = await request.get(`${BASE}/presence/${a.user.id}`);
  const body = await resp.json();
  const expected = body.status;
  const uiStatus = await page.evaluate(() => { const el = document.getElementById('my-presence'); return el ? el.textContent.trim() : ''; });
  expect(uiStatus.toLowerCase()).toContain(String(expected).toLowerCase());

  await context.close();
});
