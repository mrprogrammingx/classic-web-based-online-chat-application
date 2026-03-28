const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

test('two users chat in a room and reply (UI)', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // register two users via API
  const a = await helpers.registerUser(request, 'chatA');
  const b = await helpers.registerUser(request, 'chatB');

  // create a public room as A
  const roomResp = await request.post(`${BASE}/rooms`, {
    data: { name: `pw-room-${Date.now()}`, visibility: 'public' },
    headers: { Authorization: `Bearer ${a.token}` }
  });
  expect(roomResp.ok()).toBeTruthy();
  const roomJson = await roomResp.json();
  const roomId = roomJson.room.id;

  // make B join the public room so it appears in their UI
  const joinResp = await request.post(`${BASE}/rooms/${roomId}/join`, { headers: { Authorization: `Bearer ${b.token}` } });
  expect(joinResp.ok()).toBeTruthy();

  // Post an original message as A via API (this ensures it exists in DB and will appear in UI)
  const postOrig = await request.post(`${BASE}/rooms/${roomId}/messages`, { headers: { Authorization: `Bearer ${a.token}` }, data: { text: 'hello from A' } });
  expect(postOrig.ok()).toBeTruthy();

  // open browser contexts for both users and set token cookie
  const contextA = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await contextA.addCookies([{
    name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax'
  }]);
  const pageA = await contextA.newPage();
  await pageA.goto(BASE);
  await pageA.waitForSelector('#composer');

  const contextB = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await contextB.addCookies([{
    name: 'token', value: b.token, url: BASE, httpOnly: true, sameSite: 'Lax'
  }]);
  const pageB = await contextB.newPage();
  await pageB.goto(BASE);
  await pageB.waitForSelector('#composer');

  // Helper to wait for room to appear in rooms list on a page
  async function waitForRoomOnPage(page, roomId) {
    const start = Date.now();
    while (Date.now() - start < 30000) {
      const items = await page.$$eval('#rooms-list li', els => els.map(e => ({ id: e.dataset.id, text: e.textContent.trim() })));
      if (items.some(t => String(t.id) === String(roomId))) return;
      await page.waitForTimeout(300);
    }
    throw new Error('room did not appear in rooms list: ' + roomId);
  }

  // ensure both pages see the room and click into it
  await waitForRoomOnPage(pageA, roomId);
  await waitForRoomOnPage(pageB, roomId);
  await pageA.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();
  await pageB.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();

  // ensure both pages load the room and the original message appears
  const aMsg = pageA.locator('.message', { hasText: 'hello from A' }).first();
  await aMsg.waitFor({ state: 'visible', timeout: 5000 });
  const bSeesA = pageB.locator('.message', { hasText: 'hello from A' }).first();
  await bSeesA.waitFor({ state: 'visible', timeout: 5000 });

  // B clicks the original message to set reply preview in the composer
  // B clicks the original message to set reply preview in the composer (UI behaviour)
  await bSeesA.click();
  // assert reply preview appears in B's composer
  const replyPreviewEl = pageB.locator('#reply-preview .reply-text');
  await replyPreviewEl.waitFor({ state: 'visible', timeout: 5000 });
  await expect(replyPreviewEl).toHaveText('hello from A');

  // Post the reply via API to verify backend persistence (keeps the test deterministic)
  const msgsResp = await request.get(`${BASE}/rooms/${roomId}/messages?per_page=50`, { headers: { Authorization: `Bearer ${b.token}` } });
  expect(msgsResp.ok()).toBeTruthy();
  const msgsJson = await msgsResp.json();
  const orig = msgsJson.messages.find(m => m.text === 'hello from A');
  expect(orig).toBeTruthy();
  const replyResp = await request.post(`${BASE}/rooms/${roomId}/messages`, { headers: { Authorization: `Bearer ${b.token}` }, data: { text: 'reply from B', reply_to: orig.id } });
  expect(replyResp.ok()).toBeTruthy();

  // sanity-check via API that the reply exists in the room messages
  const afterMsgs = await request.get(`${BASE}/rooms/${roomId}/messages?per_page=50`, { headers: { Authorization: `Bearer ${a.token}` } });
  expect(afterMsgs.ok()).toBeTruthy();
  const afterJson = await afterMsgs.json();
  const foundReply = afterJson.messages.find(m => m.text === 'reply from B');
  expect(foundReply).toBeTruthy();
  await contextA.close();
  await contextB.close();
});
