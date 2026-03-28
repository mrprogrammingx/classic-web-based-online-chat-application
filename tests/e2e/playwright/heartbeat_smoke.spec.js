const { test, expect, request } = require('./fixtures');
const helpers = require('./helpers');

test('heartbeat smoke: browser triggers heartbeat and server marks user as online', async ({ page, request }) => {
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  // register a fresh user via direct request helper
  const { user, token } = await helpers.registerUser(request, 'hbsmoke');

  // capture console messages from the page so we can assert heartbeat was attempted
  const consoleMsgs = [];
  page.on('console', msg => {
    try{ consoleMsgs.push({ type: msg.type(), text: msg.text() }); }catch(e){}
  });

  // open the home page so static scripts load
  await page.goto(BASE + '/static/home.html');

  // Inject the token so client code will use authorization path and start heartbeat
  await page.evaluate((t) => {
    window.appState = window.appState || {};
    window.appState.token = t;
    // ensure startHeartbeat is available from main.js
    try{ if(typeof startHeartbeat === 'function') startHeartbeat(t); }catch(e){}
  }, token);

  // call heartbeat once explicitly from the page context
  await page.evaluate(() => {
    try{ if(typeof heartbeat === 'function') return heartbeat(); }catch(e){}
  });

  // give the client and server a moment to process
  await page.waitForTimeout(500);

  // assert we saw the client-side debug log indicating heartbeat was sent
  const sawHeartbeatLog = consoleMsgs.some(m => m.text && m.text.includes('heartbeat sending'));
  expect(sawHeartbeatLog).toBeTruthy();

  // now query the presence endpoint for this user
  const resp = await request.get(`${BASE}/presence/${user.id}`);
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  // presence should be online or afk (recent activity)
  expect(body).toHaveProperty('status');
  const s = String(body.status || '').toLowerCase();
  expect(['online','afk']).toContain(s);
});
