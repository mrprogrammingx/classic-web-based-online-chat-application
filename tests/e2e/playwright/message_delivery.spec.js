const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

// Verify that when a user sends a message, recipients see it within 3 seconds.
test('message delivered to recipients within 3s', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // register two users via API
  const a = await helpers.registerUser(request, 'deliverA');
  const b = await helpers.registerUser(request, 'deliverB');

  // create a public room as A
  const roomResp = await request.post(`${BASE}/rooms`, {
    data: { name: `deliver-room-${Date.now()}`, visibility: 'public' },
    headers: { Authorization: `Bearer ${a.token}` }
  });
  expect(roomResp.ok()).toBeTruthy();
  const roomJson = await roomResp.json();
  const roomId = roomJson.room.id;

  // make B join the public room so it appears in their UI
  const joinResp = await request.post(`${BASE}/rooms/${roomId}/join`, { headers: { Authorization: `Bearer ${b.token}` } });
  expect(joinResp.ok()).toBeTruthy();

  // open browser contexts for both users and set token cookie
  const contextA = await browser.newContext({ viewport: { width: 1000, height: 800 } });
  await contextA.addCookies([ { name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax' } ]);
  const pageA = await contextA.newPage();
  await pageA.goto(BASE);
  await pageA.waitForSelector('#composer');

  const contextB = await browser.newContext({ viewport: { width: 1000, height: 800 } });
  await contextB.addCookies([ { name: 'token', value: b.token, url: BASE, httpOnly: true, sameSite: 'Lax' } ]);
  const pageB = await contextB.newPage();
  await pageB.goto(BASE);
  await pageB.waitForSelector('#composer');

  // wait for room to appear in both pages and select it
  async function waitForRoom(page){
    const start = Date.now();
    while(Date.now() - start < 30000){
      const items = await page.$$eval('#rooms-list li', els => els.map(e => ({ id: e.dataset.id, text: e.textContent.trim() })));
      if(items.some(t => String(t.id) === String(roomId))) return;
      await page.waitForTimeout(200);
    }
    throw new Error('room did not appear');
  }

  await waitForRoom(pageA);
  await waitForRoom(pageB);
  await pageA.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();
  await pageB.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();

  // ensure composer and message input are ready on A
  await pageA.waitForSelector('#message-input');
  await pageB.waitForSelector('#message-input');

  // send a message from A using the UI
  const text = `timely message ${Date.now()}`;
  await pageA.fill('#message-input', text);
  // click send button (assumes #send-btn exists in app)
  const sendBtn = pageA.locator('#send-btn');
  await sendBtn.click();

  // measure how long until B sees the message; must be <= 3000ms
  const start = Date.now();
  let seen = false;
  try{
    // wait up to 3000ms for the message to appear in B's UI
    await pageB.locator('.message', { hasText: text }).first().waitFor({ state: 'visible', timeout: 3000 });
    seen = true;
  }catch(e){ seen = false; }
  const elapsed = Date.now() - start;

  // cleanup
  await contextA.close();
  await contextB.close();

  expect(seen).toBeTruthy();
  // also assert elapsed <= 3000 (delivery within 3s)
  expect(elapsed).toBeLessThanOrEqual(3000);
});
