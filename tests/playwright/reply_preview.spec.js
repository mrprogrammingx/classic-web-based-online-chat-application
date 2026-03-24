const { test, expect } = require('@playwright/test');
const helpers = require('./helpers');

// Full E2E: register two users via API, create a private room, post an original message as A,
// then open the UI as B (set cookie automatically), reply-to the original message with a file
// using the composer, and assert the reply preview appears in the posted message without a page reload.

test('reply with attachment shows preview without reload', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // helper: register user via API and return { user, token }
  async function registerUser(prefix){
    const suffix = Math.random().toString(36).slice(2,8);
    const email = `${prefix}_${suffix}@example.com`;
    const username = `${prefix}_${suffix}`;
    const resp = await request.post(`${BASE}/register`, { data: { email, username, password: 'pw' } });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    return { user: body.user, token: body.token };
  }

  // register A and B
  const a = await helpers.registerUser(request, 'playA');
  const b = await helpers.registerUser(request, 'playB');

  // create a public room as A (public rooms are listed in the UI)
  const roomResp = await request.post(`${BASE}/rooms`, {
    data: { name: `pw-room-${Date.now()}`, visibility: 'public' },
    headers: { Authorization: `Bearer ${a.token}` }
  });
  expect(roomResp.ok()).toBeTruthy();
  const room = await roomResp.json();
  const roomId = room.room.id;

  // make B join the public room so it appears in their UI
  const joinResp = await request.post(`${BASE}/rooms/${roomId}/join`, { headers: { Authorization: `Bearer ${b.token}` } });
  expect(joinResp.ok()).toBeTruthy();

  // post an original message as A
  const postOrig = await request.post(`${BASE}/rooms/${roomId}/messages`, { headers: { Authorization: `Bearer ${a.token}` }, data: { text: 'original msg' } });
  expect(postOrig.ok()).toBeTruthy();
  const origJson = await postOrig.json();
  const mid = origJson.message.id;

  // Now open a browser context as user B by setting the HttpOnly cookie returned by /register
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  // Add the `token` cookie so the UI bootstraps as authenticated B
  await context.addCookies([{
    name: 'token',
    value: b.token,
    url: BASE,
    httpOnly: true,
    sameSite: 'Lax'
  }]);

  const page = await context.newPage();
  // navigate to the app (root redirects to static index)
  await page.goto(BASE);
  // wait for composer to be visible indicating app loaded and bootstrapped
  await page.waitForSelector('#composer');

  // wait for the room to appear in rooms list and click it. The UI may take a bit; poll and log list contents.
  const roomName = room.room.name;
  console.log('waiting for room item:', roomName);
  const start = Date.now();
  let found = false;
  while(Date.now() - start < 30000){
    // get list items text and data-id
    const items = await page.$$eval('#rooms-list li', els => els.map(e => ({ id: e.dataset.id, text: e.textContent.trim() })));
    console.log('rooms_list:', items);
    if(items.some(t => String(t.id) === String(roomId))){ found = true; break; }
    await page.waitForTimeout(500);
  }
  if(!found) throw new Error('room did not appear in rooms list: ' + roomId);
  const roomItem = page.locator(`#rooms-list li[data-id="${roomId}"]`).first();
  await roomItem.click();

  // wait for the original message to appear
  const origMsg = page.locator('.message', { hasText: 'original msg' }).first();
  await origMsg.waitFor({ state: 'visible', timeout: 5000 });

  // click the original message to set reply preview
  await origMsg.click();

  // attach a file and send a reply
  const fileInput = page.locator('#file-input');
  await fileInput.setInputFiles({ name: 'reply.txt', mimeType: 'text/plain', buffer: Buffer.from('reply content') });
  await page.fill('#message-input', 'replying with file');
  // click send
  await page.click('#send-btn');

  // wait for the reply message to appear and assert reply preview is present
  const replyMsg = page.locator('.message', { hasText: 'replying with file' }).first();
  await replyMsg.waitFor({ state: 'visible', timeout: 5000 });
  const replyPreviewText = replyMsg.locator('.reply-preview .reply-text');
  await expect(replyPreviewText).toHaveText('original msg');

  // ensure we didn't navigate away (simple sanity: URL still begins with BASE)
  expect(page.url().startsWith(BASE)).toBeTruthy();
  await context.close();
});
