const { test, expect } = require('@playwright/test');
const { registerUser } = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('admin page exposes .admin-list (smoke)', async ({ browser }) => {
  const request = await require('playwright').request.newContext();
  // create an admin user and promote via API
  const admin = await registerUser(request, 'smoke_admin');
  const promote = await request.post(`${BASE}/admin/make_admin`, { data: { user_id: admin.user.id } , headers: { Cookie: `token=${admin.token}` } });
  if(!promote.ok()) throw new Error('promote failed: ' + promote.status());

  // open page with admin cookie
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: admin.token, domain: '127.0.0.1', path: '/' }]);
  const page = await context.newPage();
  await page.goto(`${BASE}/static/admin/index.html`);

  // smoke: ensure the legacy selector exists
  await page.waitForSelector('.admin-list', { timeout: 5000 });
  const exists = await page.locator('.admin-list').count();
  expect(exists).toBeGreaterThan(0);
});
