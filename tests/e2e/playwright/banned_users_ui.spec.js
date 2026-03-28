const { test, expect } = require('./fixtures');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('banned users UI shows banned entries and Unban works', async ({ browser }) => {
  const request = await require('playwright').request.newContext();
  // create user A (banner)
  const aResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `ban_a_${Date.now()}@example.com`, username: `ban_a_${Date.now()}`, password: 'pw' }) });
  expect(aResp.ok()).toBeTruthy();
  const aBody = await aResp.json();
  const aToken = aBody && aBody.token;
  const aUser = aBody && aBody.user;

  // create user B (banned)
  const bResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `ban_b_${Date.now()}@example.com`, username: `ban_b_${Date.now()}`, password: 'pw' }) });
  expect(bResp.ok()).toBeTruthy();
  const bBody = await bResp.json();
  const bToken = bBody && bBody.token;
  const bUser = bBody && bBody.user;

  // A bans B via API
  const banResp = await request.post(`${BASE}/ban`, { headers: { Authorization: `Bearer ${aToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ banned_id: bUser.id }) });
  expect(banResp.ok()).toBeTruthy();

  // Open browser context as A
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: aToken, url: BASE }]);
  await context.addInitScript(id => { window.__ME_ID = id; }, String(aUser.id));
  await context.addInitScript(name => { window.__ME_NAME = name; }, String(aUser.username || aUser.email));
  const page = await context.newPage();

  // Visit home page and assert banned users UI shows B
  await page.goto(`${BASE}/static/home.html`);
  // Wait for a list item inside banned users
  await page.waitForSelector('#banned-users li', { timeout: 5000 });
  await page.waitForTimeout(200);
  const items = await page.$$('#banned-users li');
  expect(items.length).toBeGreaterThanOrEqual(1);
  let found = false;
  for(const li of items){
    const txt = await li.innerText();
    if(txt && txt.indexOf((bUser.username || bUser.email)) !== -1){ found = true; break; }
  }
  expect(found).toBeTruthy();

  // Click the Unban button and assert the item is removed
  const unbanBtn = await page.$(`#banned-users li button[data-id="${bUser.id}"]`);
  expect(unbanBtn).not.toBeNull();
  await unbanBtn.click();
  // Wait a small bit for the UI to refresh
  await page.waitForTimeout(500);
  const itemsAfter = await page.$$('#banned-users li');
  // The banned user should no longer be present
  let stillThere = false;
  for(const li of itemsAfter){
    const txt = await li.innerText();
    if(txt && txt.indexOf((bUser.username || bUser.email)) !== -1){ stillThere = true; break; }
  }
  expect(stillThere).toBeFalsy();

  // After unban, B should be able to send a friend request to A
  const reqAfter = await request.post(`${BASE}/friends/request`, { headers: { Authorization: `Bearer ${bToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ friend_id: aUser.id, message: 'hello after unban' }) });
  expect(reqAfter.ok()).toBeTruthy();
});
