const { test, expect } = require('./fixtures');
const helpers = require('./helpers');

// Ensure that when a user has an existing (but idle) tab, loading home.html
// immediately shows AFK (not online). We simulate by creating a tab, starting
// heartbeats, stopping them, waiting for server to mark AFK, then loading a
// fresh page and asserting the initial presence text is AFK.
test('home page initial presence shows AFK when user idle', async ({ browser, request }) => {
  const BASE = 'http://127.0.0.1:8000';

  // register user
  const u = await helpers.registerUser(request, 'homeafk');
  const decodeJti = (token) => {
    try{
      const parts = token.split('.'); if(parts.length < 2) return null;
      const payload = JSON.parse(Buffer.from(parts[1].replace(/-/g,'+').replace(/_/g,'/'), 'base64').toString('utf8'));
      return payload.jti || null;
    }catch(e){ return null; }
  };
  const jti = decodeJti(u.token);
  const tabA = 'tab-' + Math.random().toString(36).slice(2,8);

  // open context A and start heartbeat (becomes online)
  const ctxA = await browser.newContext();
  await ctxA.addCookies([{ name: 'token', value: u.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const pageA = await ctxA.newPage();
  await pageA.addInitScript(() => { window.__TEST_MODE = true; });
  await pageA.goto(BASE + '/static/home.html');
  await pageA.waitForSelector('#my-presence');

  await pageA.evaluate(({ token, jti, tabId }) => { try{ if(window && window.startHeartbeat) window.startHeartbeat(token, jti, tabId); }catch(e){} }, { token: u.token, jti, tabId: tabA });

  // wait for server to observe online
  let sawOnline = false;
  const t0 = Date.now();
  while(Date.now() - t0 < 3000){
    const r = await request.get(BASE + `/presence/${u.user.id}`);
    if(r.status() === 200){ const d = await r.json(); if((d.status || '').toLowerCase().includes('online')){ sawOnline = true; break; } }
    await new Promise(r => setTimeout(r, 200));
  }
  expect(sawOnline).toBeTruthy();

  // stop heartbeats on A to simulate idle tab
  await pageA.evaluate(() => { try{ if(window._hb) clearInterval(window._hb); }catch(e){} });

  // wait for server to mark AFK (wait up to 10s)
  let sawAfk = false;
  const t1 = Date.now();
  while(Date.now() - t1 < 10000){
    const r = await request.get(BASE + `/presence/${u.user.id}`);
    if(r.status() === 200){ const d = await r.json(); if((d.status || '').toLowerCase().includes('afk')){ sawAfk = true; break; } }
    await new Promise(r => setTimeout(r, 250));
  }
  expect(sawAfk).toBeTruthy();

  // now open a fresh context (new page) and load home.html; initial render should show AFK
  const ctxB = await browser.newContext();
  await ctxB.addCookies([{ name: 'token', value: u.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const pageB = await ctxB.newPage();
  await pageB.addInitScript(() => { window.__TEST_MODE = true; });
  await pageB.goto(BASE + '/static/home.html');
  await pageB.waitForSelector('#my-presence');
  // Ensure presence polling starts on the observer page immediately
  await pageB.evaluate((userId) => { try{ if(window && window.startPresencePolling) window.startPresencePolling(userId); }catch(e){} }, u.user.id);

  // allow presence polling on the freshly loaded page to run and update the UI
  let sawAfkOnLoad = false;
  const t2 = Date.now();
  while(Date.now() - t2 < 5000){
    const txt = await pageB.evaluate(() => { const el = document.getElementById('my-presence'); return el ? el.textContent.trim().toLowerCase() : null; });
    if(txt && txt.includes('afk')){ sawAfkOnLoad = true; break; }
    await pageB.waitForTimeout(200);
  }
  expect(sawAfkOnLoad).toBeTruthy();

  await ctxA.close();
  await ctxB.close();
});
