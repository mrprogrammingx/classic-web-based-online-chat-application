const { test, expect, request } = require('@playwright/test');
const helpers = require('./helpers');

const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('user dropdown shows sessions and revoke flow displays modal and toast', async ({ page }) => {
  // register a user via API
  const api = await request.newContext();
  const { user, token } = await helpers.registerUser(api, 'uiuser');
  // create a second session for the same user via login endpoint to have an extra session to revoke
  const resp = await api.post(`${BASE}/login`, { data: { email: user.email, password: 'pw' } });
  expect(resp.ok()).toBeTruthy();

  // set the token cookie in the browser context
  await page.context().addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true }]);
  await page.goto(`${BASE}/`);
  // wait for user toggle to appear
  await page.waitForSelector('#user-toggle', { timeout: 5000 });
  // open dropdown
  await page.click('#user-toggle');
  // sessions list should show at least one item
  await page.waitForSelector('.sessions-list li', { timeout: 5000 });
  // find a Revoke button and click it (this will open the modal)
  const revokeBtn = await page.$('.sessions-list li button');
  expect(revokeBtn).not.toBeNull();
  // click revoke and accept modal
  await revokeBtn.click();
  // wait for modal and click confirm (button with text 'Revoke')
  const modalBtn = await page.waitForSelector('.modal-box .confirm', { timeout: 3000 });
  await modalBtn.click();
  // wait for toast
  await page.waitForSelector('.toast.success', { timeout: 4000 });
  // success
});
