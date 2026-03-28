const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

// Verify that presence updates propagate to other clients within 2 seconds (test-mode fast polling)
test('presence updates propagate within 2s', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // register two users
  const a = await helpers.registerUser(request, 'presA');
  const b = await helpers.registerUser(request, 'presB');

  // open contexts for both and set window.__TEST_MODE so presence polling is fast
  const contextA = await browser.newContext();
  await contextA.addCookies([{ name: 'token', value: a.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const pageA = await contextA.newPage();
  // set TEST_MODE early before app boot
  await pageA.addInitScript(() => { window.__TEST_MODE = true; });
  await pageA.goto(BASE + '/static/home.html');
  await pageA.waitForSelector('#my-presence');

  const contextB = await browser.newContext();
  await contextB.addCookies([{ name: 'token', value: b.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const pageB = await contextB.newPage();
  await pageB.addInitScript(() => { window.__TEST_MODE = true; });
  await pageB.goto(BASE + '/static/home.html');
  await pageB.waitForSelector('#my-presence');

  // helper to decode JWT and extract jti
  function decodeJti(token){
    try{
      const parts = token.split('.'); if(parts.length < 2) return null;
      const payload = JSON.parse(Buffer.from(parts[1].replace(/-/g,'+').replace(/_/g,'/'), 'base64').toString('utf8'));
      return payload.jti || null;
    }catch(e){ return null; }
  }

  const jtiA = decodeJti(a.token);
  const tabId = 'tab-' + Math.random().toString(36).slice(2,8);

  // start heartbeat on A's page so server marks A online
  // await the initial heartbeat in test mode to avoid racing with presence GET
  await pageA.evaluate(async ({ token, jti, tabId }) => {
    try{ if(window && window.startHeartbeat) await window.startHeartbeat(token, jti, tabId); }catch(e){}
  }, { token: a.token, jti: jtiA, tabId });

  // small warm-up so server has a moment to persist presence before B polls
  await pageA.waitForTimeout(500);

  // On B, start presence polling for A's user id
  await pageB.evaluate((userId) => { try{ if(window && window.startPresencePolling) window.startPresencePolling(userId); }catch(e){} }, a.user.id);

  // Wait up to 2s for B to show A as online
  const start = Date.now();
  let seenOnline = false;
  while(Date.now() - start < 2000){
    const status = await pageB.evaluate(() => { const el = document.getElementById('my-presence'); return el ? el.textContent.trim().toLowerCase() : null; });
    if(status && status.includes('online')){ seenOnline = true; break; }
    await pageB.waitForTimeout(200);
  }

  // assert online observed
  expect(seenOnline).toBeTruthy();

  await contextA.close();
  await contextB.close();
});
