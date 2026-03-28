const { test, expect } = require('./fixtures');
const { registerUser } = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test('current user messages show me class and you-badge', async ({ browser }) => {
  // create a request context to register/login a user and post messages
  const request = await require('playwright').request.newContext();
  // create a test user via the test-only helper so we can get a token and set cookie
  const createResp = await request.post(`${BASE}/_test/create_user`, { headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ email: `mebadge_${Date.now()}@example.com`, username: `mebadge_${Date.now()}`, password: 'pw' }) });
  expect(createResp.ok()).toBeTruthy();
  const createBody = await createResp.json();
  const token = createBody && createBody.token;
  const meUser = createBody && createBody.user;
  const meId = meUser && meUser.id;
  const meName = meUser && (meUser.username || meUser.email);
  // create a room using Authorization header
  const roomResp = await request.post(`${BASE}/rooms`, { data: { name: `mebadge-room-${Date.now()}`, visibility: 'public' }, headers: { Authorization: `Bearer ${token}` } });
  expect(roomResp.ok()).toBeTruthy();
  const roomBody = await roomResp.json();
  const roomId = roomBody.room.id;

  // post messages via API
  await request.post(`${BASE}/rooms/${roomId}/messages`, { data: { text: 'hello from me' }, headers: { Authorization: `Bearer ${token}` } });
  await request.post(`${BASE}/rooms/${roomId}/messages`, { data: { text: 'another message' }, headers: { Authorization: `Bearer ${token}` } });


  // open browser page and set cookie token so the server recognizes the session during refresh
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: token, url: BASE }]);
  // ensure client-side knows current user id and name before scripts run
  await context.addInitScript(id => { window.__ME_ID = id; }, String(meId));
  if(meName) await context.addInitScript(name => { window.__ME_NAME = name; }, String(meName));
  const page = await context.newPage();
  // navigate to the canonical chat page that includes the header and app
  await page.goto(`${BASE}/static/chat/index.html`);
  // wait for the messages container to be injected and for the text to appear
  // select the room we created so the client loads messages for it
  await page.waitForSelector('#rooms-list', { timeout: 5000 });
  // click the room list item that matches the room name (may be slightly delayed)
  await page.click(`li[data-id=\"${roomId}\"]`).catch(()=>null);
  await page.waitForSelector('#messages .message', { state: 'attached', timeout: 15000 });
  await page.waitForFunction(() => document.body && document.body.innerText.includes('hello from me'), null, { timeout: 15000 });

  // find messages that contain our text and assert they have .me class and .you-badge
  const messages = await page.$$('#messages .message');
  expect(messages.length).toBeGreaterThanOrEqual(2);
  // check that at least one message has the 'me' class and contains a .you-badge
  let found = false;
  for(const m of messages){
    const cls = await m.getAttribute('class');
    if(cls && cls.indexOf('me') !== -1){
      const badge = await m.$('.you-badge');
      expect(badge).not.toBeNull();
      found = true;
      break;
    }
  }
  expect(found).toBeTruthy();
});
