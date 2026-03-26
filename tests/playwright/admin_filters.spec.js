const { test, expect } = require('./fixtures');
const { registerUser } = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

// Simple E2E: create an admin and some users, then visit admin page and click filters
test('admin filters update user list', async ({ browser }) => {
  const request = await require('playwright').request.newContext();
  // register admin user
  const admin = await registerUser(request, 'admin');
  // promote to admin via API
  const promote = await request.post(`${BASE}/admin/make_admin`, { data: { user_id: admin.user.id } , headers: { Cookie: `token=${admin.token}` } });
  // create several users
  const u1 = await registerUser(request, 'u1');
  const u2 = await registerUser(request, 'u2');
  const u3 = await registerUser(request, 'u3');

  // ban u3 via API as admin
  await request.post(`${BASE}/admin/ban_user`, { data: { user_id: u3.user.id }, headers: { Cookie: `token=${admin.token}` } });

  // create page with admin cookie
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: admin.token, domain: '127.0.0.1', path: '/' }]);
  const page = await context.newPage();
  await page.goto(`${BASE}/static/admin/index.html`);

  // wait for users table to appear
  await page.waitForSelector('.admin-list');
  const allText = await page.locator('.admin-list').innerText();
  expect(allText).toContain(u1.user.username);
  expect(allText).toContain(u2.user.username);
  expect(allText).toContain(u3.user.username);

  // click Banned filter
  await page.click('text=Banned');
  await page.waitForTimeout(300); // small wait for fetch
  const bannedText = await page.locator('.admin-list').innerText();
  expect(bannedText).toContain(u3.user.username);
  expect(bannedText).not.toContain(u1.user.username);

  // click Admins filter (only admin user should appear)
  await page.click('text=Admins');
  await page.waitForTimeout(300);
  const adminsText = await page.locator('.admin-list').innerText();
  expect(adminsText).toContain(admin.user.username);
});
