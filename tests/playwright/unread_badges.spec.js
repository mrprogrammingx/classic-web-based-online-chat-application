const { test, expect } = require('@playwright/test');
// Smoke test: two users, A sends message to room, B sees unread badge, opens room and badge clears

test('unread badges update on new messages and clear on open', async ({ page, context, request }) => {
  const base = 'http://127.0.0.1:8000';
  const emailA = `a${Date.now()}@example.com`;
  const emailB = `b${Date.now()}@example.com`;
  const password = 'password123';
  const roomName = `smoke-room-${Date.now()}`;

  // Register A and add token to browser context
  // use test-only helper to create users deterministically (must set TEST_MODE=1 in env)
  const aResp = await request.post(base + '/_test/create_user', { headers: {'Content-Type':'application/json'}, data: JSON.stringify({ email: emailA, username: 'userA', password }) });
  const aJs = await aResp.json().catch(()=>null);
  const tokenA = aJs && aJs.token;
  if(tokenA) await context.addCookies([{ name: 'token', value: tokenA, url: base }]);

  // Open chat page for A (rooms list is on chat.html)
  await page.goto(base + '/static/chat.html');

  // Create room as A using request with Authorization
  const createRoom = await request.post(base + '/rooms', { headers: { 'Content-Type':'application/json', 'Authorization': `Bearer ${tokenA}` }, data: JSON.stringify({ name: roomName }) });
  const roomJs = await createRoom.json().catch(()=>null);
  const roomId = roomJs && roomJs.room && roomJs.room.id;

  // Register B and set cookie in context
  const bResp = await request.post(base + '/_test/create_user', { headers: {'Content-Type':'application/json'}, data: JSON.stringify({ email: emailB, username: 'userB', password }) });
  const bJs = await bResp.json().catch(()=>null);
  const tokenB = bJs && bJs.token;
  if(tokenB) await context.addCookies([{ name: 'token', value: tokenB, url: base }]);

  const pageB = await context.newPage();
  // prevent the client from auto-selecting the first room which would mark as read
  await pageB.addInitScript(()=>{ window.__TEST_SKIP_AUTOSELECT = true; });
  await pageB.goto(base + '/static/chat.html');
  // expose token to client fetch wrapper for tests
  await pageB.evaluate((t)=>{ window.__AUTH_TOKEN = t; }, tokenB);
  await page.evaluate((t)=>{ window.__AUTH_TOKEN = t; }, tokenA);

  // Get B's user id via request
  // get B's user id from /me using Authorization header via request fixture
  const meB = await request.get(base + '/me', { headers: { 'Authorization': `Bearer ${tokenB}` } });
  const meBjs = await meB.json().catch(()=>null);
  const bId = meBjs && meBjs.user && meBjs.user.id;

  // Add B to room using A's auth
  if(roomId && bId){
    const addResp = await request.post(base + `/rooms/${roomId}/members/add`, { headers: { 'Content-Type':'application/json', 'Authorization': `Bearer ${tokenA}` }, data: JSON.stringify({ user_id: bId }) });
  await addResp.json().catch(()=>null);
  }

  // Post a message as A
  if(roomId){
    const postResp = await request.post(base + `/rooms/${roomId}/messages`, { headers: { 'Content-Type':'application/json', 'Authorization': `Bearer ${tokenA}` }, data: JSON.stringify({ text: 'hello from A' }) });
  await postResp.json().catch(()=>null);
  }
  // give client a moment and force B to refresh unread summary (await in-page promises so DOM updates finish)
  await pageB.evaluate(async ()=>{ try{ if(typeof loadRooms === 'function') await window.loadRooms(); if(typeof window.loadUnreadSummary === 'function') await window.loadUnreadSummary(); }catch(e){} });
  // ensure client updated the rooms list and unread summary
  await pageB.evaluate(async ()=>{ if(typeof window.loadRooms === 'function') await window.loadRooms(); if(typeof window.loadUnreadSummary === 'function') await window.loadUnreadSummary(); });
  // wait for the specific room's badge to appear (not hidden)
  const roomItemB = pageB.locator('#rooms-list li', { hasText: roomName }).first();
  const roomBadge = roomItemB.locator('.unread-badge');
  await roomBadge.waitFor({ state: 'visible', timeout: 30000 });
  expect(await roomBadge.isVisible()).toBeTruthy();

  // Click the room name to open it and clear unread
  await pageB.click(`text=${roomName}`);
  // wait for the specific room's badge to become hidden after opening the room
  await roomBadge.waitFor({ state: 'hidden', timeout: 7000 });
});
