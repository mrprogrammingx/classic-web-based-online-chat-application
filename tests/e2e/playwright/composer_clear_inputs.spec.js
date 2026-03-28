const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

test('message input is cleared after sending text message', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';
  const a = await helpers.registerUser(request, 'clearA');
  const b = await helpers.registerUser(request, 'clearB');
  const roomResp = await request.post(`${BASE}/rooms`, { data: { name: `clear-room-${Date.now()}`, visibility: 'public' }, headers: { Authorization: `Bearer ${a.token}` } });
  expect(roomResp.ok()).toBeTruthy();
  const roomId = (await roomResp.json()).room.id;
  await request.post(`${BASE}/rooms/${roomId}/join`, { headers: { Authorization: `Bearer ${b.token}` } });

  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  await page.goto(BASE);
  await page.waitForSelector('#composer');
  // wait for room and select
  const start = Date.now();
  while(Date.now() - start < 15000){
    const items = await page.$$eval('#rooms-list li', els => els.map(e => e.dataset.id));
    if(items && items.includes(String(roomId))) break;
    await page.waitForTimeout(200);
  }
  await page.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();

  // type message and send
  const text = 'clear-input-test ' + Date.now();
  await page.fill('#message-input', text);
  await page.click('#send-btn');

  // assert input cleared (wait up to 3s to allow send round-trip)
  await page.waitForFunction(() => { const el = document.getElementById('message-input'); return el && el.value === ''; }, null, { timeout: 3000 });
  await context.close();
});

test('file input is cleared after sending attachment', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';
  const a = await helpers.registerUser(request, 'clearFileA');
  const b = await helpers.registerUser(request, 'clearFileB');
  const roomResp = await request.post(`${BASE}/rooms`, { data: { name: `clear-file-room-${Date.now()}`, visibility: 'public' }, headers: { Authorization: `Bearer ${a.token}` } });
  expect(roomResp.ok()).toBeTruthy();
  const roomId = (await roomResp.json()).room.id;
  await request.post(`${BASE}/rooms/${roomId}/join`, { headers: { Authorization: `Bearer ${b.token}` } });

  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  await page.goto(BASE);
  await page.waitForSelector('#composer');
  // wait for room and select
  const start = Date.now();
  while(Date.now() - start < 15000){
    const items = await page.$$eval('#rooms-list li', els => els.map(e => e.dataset.id));
    if(items && items.includes(String(roomId))) break;
    await page.waitForTimeout(200);
  }
  await page.locator(`#rooms-list li[data-id="${roomId}"]`).first().click();

  // attach a file and send
  const fileInput = page.locator('#file-input');
  await fileInput.setInputFiles({ name: 'send.txt', mimeType: 'text/plain', buffer: Buffer.from('hello') });
  await page.fill('#message-input', 'sending file');
  await page.click('#send-btn');

  // assert file input cleared (wait up to 3s to allow send round-trip)
  await page.waitForFunction(() => { const el = document.getElementById('file-input'); return el && el.files && el.files.length === 0; }, null, { timeout: 3000 });
  await context.close();
});
