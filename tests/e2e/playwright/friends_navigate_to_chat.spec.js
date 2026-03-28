const { test, expect } = require('./fixtures');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('clicking a friend on home navigates to chat dialog', async ({ browser }) => {
  const request = await require('playwright').request.newContext();
  // create user A
  const aResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `nav_a_${Date.now()}@example.com`, username: `nav_a_${Date.now()}`, password: 'pw' }) });
  expect(aResp.ok()).toBeTruthy();
  const aBody = await aResp.json();
  const aToken = aBody && aBody.token;
  const aUser = aBody && aBody.user;

  // create user B
  const bResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `nav_b_${Date.now()}@example.com`, username: `nav_b_${Date.now()}`, password: 'pw' }) });
  expect(bResp.ok()).toBeTruthy();
  const bBody = await bResp.json();
  const bToken = bBody && bBody.token;
  const bUser = bBody && bBody.user;

  // Make them friends: A -> request, B accepts
  const req1 = await request.post(`${BASE}/friends/request`, { headers: { Authorization: `Bearer ${aToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ friend_id: bUser.id, message: 'hi' }) });
  expect(req1.ok()).toBeTruthy();
  const reqs = await request.get(`${BASE}/friends/requests`, { headers: { Authorization: `Bearer ${bToken}` } });
  expect(reqs.ok()).toBeTruthy();
  const reqsBody = await reqs.json();
  const rid = (reqsBody && reqsBody.requests && reqsBody.requests[0] && reqsBody.requests[0].id) || null;
  expect(rid).not.toBeNull();
  const accept = await request.post(`${BASE}/friends/requests/respond`, { headers: { Authorization: `Bearer ${bToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ request_id: rid, action: 'accept' }) });
  expect(accept.ok()).toBeTruthy();

  // Send a message from B to A so the dialog has content to load
  const sendMsg = await request.post(`${BASE}/messages/send`, { headers: { Authorization: `Bearer ${bToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ to_id: aUser.id, text: 'hello A' }) });
  expect(sendMsg.ok()).toBeTruthy();

  // Open browser as A
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: aToken, url: BASE }]);
  await context.addInitScript(id => { window.__ME_ID = id; }, String(aUser.id));
  await context.addInitScript(name => { window.__ME_NAME = name; }, String(aUser.username || aUser.email));
  const page = await context.newPage();

  // Visit home and wait for friend list item
  await page.goto(`${BASE}/static/home.html`);
  await page.waitForSelector('#friends-list li', { timeout: 5000 });
  await page.waitForTimeout(200);
  // find the friend LI that contains B's username/email
  const items = await page.$$('#friends-list li');
  let target = null;
  for(const li of items){ const txt = await li.innerText(); if(txt && txt.indexOf((bUser.username || bUser.email)) !== -1){ target = li; break; } }
  expect(target).not.toBeNull();

  // Click the friend item's text (not the remove/ban buttons) and expect navigation to chat dialog
  // Use a stable locator and wait for it to be attached/visible to avoid detached-element flakes.
  const textSpan = await target.waitForSelector('span', { state: 'visible', timeout: 5000 });
  expect(textSpan).not.toBeNull();
  const locator = textSpan.asElement ? textSpan : await page.locator('#friends-list li >> text=' + String(bUser.username || bUser.email));
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'load', timeout: 8000 }),
    locator.click()
  ]);
  const url = page.url();
  expect(url.indexOf('/static/chat/index.html') !== -1).toBeTruthy();
  expect(url.indexOf('dialog=') !== -1).toBeTruthy();
  // Wait for messages area to load and contain the message sent by B
  // allow more time for the messages area to populate on slower CI/machines
  await page.waitForSelector('#messages .message', { timeout: 10000 });
  const msgs = await page.$$eval('#messages .message', nodes => nodes.map(n => n.innerText || n.textContent));
  expect(msgs.some(t => t && t.indexOf('hello A') !== -1)).toBeTruthy();
  // also ensure messages area is present on the chat page
  await page.waitForSelector('#messages', { timeout: 5000 });
});
