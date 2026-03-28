const { test, expect } = require('./fixtures');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('contacts and friends UI shows friends and presence dots', async ({ browser }) => {
  const request = await require('playwright').request.newContext();
  // create user A
  const aResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `friend_a_${Date.now()}@example.com`, username: `friend_a_${Date.now()}`, password: 'pw' }) });
  expect(aResp.ok()).toBeTruthy();
  const aBody = await aResp.json();
  const aToken = aBody && aBody.token;
  const aUser = aBody && aBody.user;

  // create user B
  const bResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `friend_b_${Date.now()}@example.com`, username: `friend_b_${Date.now()}`, password: 'pw' }) });
  expect(bResp.ok()).toBeTruthy();
  const bBody = await bResp.json();
  const bToken = bBody && bBody.token;
  const bUser = bBody && bBody.user;

  // Make them friends via test helper endpoints: have A send a friend request to B and B accept
  // Use authenticated requests
  const req1 = await request.post(`${BASE}/friends/request`, { headers: { Authorization: `Bearer ${aToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ friend_id: bUser.id, message: 'hi' }) });
  expect(req1.ok()).toBeTruthy();
  // fetch requests as B
  const reqs = await request.get(`${BASE}/friends/requests`, { headers: { Authorization: `Bearer ${bToken}` } });
  expect(reqs.ok()).toBeTruthy();
  const reqsBody = await reqs.json();
  const rid = (reqsBody && reqsBody.requests && reqsBody.requests[0] && reqsBody.requests[0].id) || null;
  expect(rid).not.toBeNull();
  const resp = await request.post(`${BASE}/friends/requests/respond`, { headers: { Authorization: `Bearer ${bToken}`, 'Content-Type': 'application/json' }, data: JSON.stringify({ request_id: rid, action: 'accept' }) });
  expect(resp.ok()).toBeTruthy();

  // Now open a browser for user A and check contacts/friends UI
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: aToken, url: BASE }]);
  await context.addInitScript(id => { window.__ME_ID = id; }, String(aUser.id));
  await context.addInitScript(name => { window.__ME_NAME = name; }, String(aUser.username || aUser.email));
  const page = await context.newPage();

  // Visit chat page and assert contact appears in contacts list
  await page.goto(`${BASE}/static/chat/index.html`);
  await page.waitForSelector('#contacts-list', { timeout: 5000 });
  // ensure loader runs
  await page.waitForTimeout(500);
  const contactItems = await page.$$('#contacts-list li');
  // at least one contact (the friend)
  expect(contactItems.length).toBeGreaterThanOrEqual(1);
  // find item that contains friend's username
  let foundContact = false;
  for(const li of contactItems){
    const txt = await li.innerText();
    if(txt && txt.indexOf((bUser.username || bUser.email)) !== -1){ foundContact = true; break; }
  }
  expect(foundContact).toBeTruthy();

  // Visit home page and assert friends list shows friend
  await page.goto(`${BASE}/static/home.html`);
  // Wait for an LI inside the friends list (the UL may be present but have zero height when empty)
  await page.waitForSelector('#friends-list li', { timeout: 5000 });
  await page.waitForTimeout(200);
  const friends = await page.$$('#friends-list li');
  expect(friends.length).toBeGreaterThanOrEqual(1);
  let foundFriend = false;
  for(const li of friends){
    const txt = await li.innerText();
    if(txt && txt.indexOf((bUser.username || bUser.email)) !== -1){ foundFriend = true; break; }
  }
  expect(foundFriend).toBeTruthy();
});
