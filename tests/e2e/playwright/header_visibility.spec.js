const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('Header visibility', () => {
  test('anonymous user should not see user-toggle or admin button', async ({ page }) => {
    await page.goto(BASE);
    // wait for header area to be available before checking for injected elements
    await page.waitForSelector('#shared-header-placeholder', { timeout: 5000 }).catch(()=>null);
    // user-toggle should not exist for anonymous users
    const userToggle = await page.$('.user-toggle');
    expect(userToggle).toBeNull();
    // admin button may exist but must be hidden
    const adminBtn = page.locator('#admin-open');
    const visible = await adminBtn.isVisible().catch(()=>false);
    expect(visible).toBeFalsy();
  });

  test('logged-in user sees their username and not admin by default; admin sees admin button', async ({ browser, request }) => {
    // register a fresh user and set cookie on context
    const created = await helpers.registerUser(request, 'headerv');
    const user = created.user;
    const token = created.token;

    // browser context with cookie (match header_smoke pattern)
    const context = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    await context.addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
    const page = await context.newPage();
    // Pre-populate sessionStorage so the header can bootstrap immediately
    await page.addInitScript((user, token) => {
      try { sessionStorage.setItem('boot_user', JSON.stringify(user)); } catch (e) {}
      try { sessionStorage.setItem('boot_token', token || ''); } catch (e) {}
    }, user, token);
    await page.goto(BASE);

  // user-toggle should show username (allow longer for header injection)
  page.on('console', msg => { try{ console.log(`PAGE LOG [${msg.type()}]: ${msg.text()}`); }catch(e){} });
  page.on('pageerror', err => { try{ console.log('PAGE ERROR:', err && err.message ? err.message : String(err)); }catch(e){} });
  await page.waitForSelector('.user-toggle strong', { timeout: 15000 });
    const shown = await page.textContent('.user-toggle strong');
    expect(shown && shown.trim()).toBe(user.username);

    // admin button must be hidden for normal users
    const adminBtn = page.locator('#admin-open');
    const adminVisible = await adminBtn.isVisible().catch(()=>false);
    expect(adminVisible).toBeFalsy();

    // promote user to admin via admin endpoint using request context with cookie auth
    const req = await require('playwright').request.newContext();
    await req.post(`${BASE}/admin/make_admin`, { data: { user_id: user.id }, headers: { Cookie: `token=${token}` } });
    await context.close();

    // new context with admin cookie (use same url-based cookie pattern)
    const adminCtx = await browser.newContext();
    await adminCtx.addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
    const adminPage = await adminCtx.newPage();
    await adminPage.addInitScript((user, token) => {
      try { sessionStorage.setItem('boot_user', JSON.stringify(user)); } catch (e) {}
      try { sessionStorage.setItem('boot_token', token || ''); } catch (e) {}
    }, user, token);
    await adminPage.goto(BASE);
  // admin button should now be visible (wait a bit for injection)
  await adminPage.waitForSelector('#admin-open', { state: 'visible', timeout: 5000 }).catch(()=>{});
  const adminVisibleNow = await adminPage.locator('#admin-open').isVisible().catch(()=>false);
  expect(adminVisibleNow).toBeTruthy();

    await adminCtx.close();
  });
});
