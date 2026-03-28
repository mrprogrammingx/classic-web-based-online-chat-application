const { test, expect, request } = require('./fixtures');
const helpers = require('./helpers');

test('heartbeat smoke: browser triggers heartbeat and server marks user as online', async ({ page, request }) => {
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  // register a fresh user via direct request helper
  const { user, token } = await helpers.registerUser(request, 'hbsmoke');
  // decode jti from token so we can supply it to the client heartbeat helper
  const decodeJti = (tok) => {
    try{
      const parts = tok.split('.'); if(parts.length < 2) return null;
      const payload = JSON.parse(Buffer.from(parts[1].replace(/-/g,'+').replace(/_/g,'/'), 'base64').toString('utf8'));
      return payload.jti || null;
    }catch(e){ return null; }
  };
  const jti = decodeJti(token);

  // capture console messages from the page so we can assert heartbeat was attempted
  const consoleMsgs = [];
  page.on('console', msg => {
    try{ consoleMsgs.push({ type: msg.type(), text: msg.text() }); }catch(e){}
  });

  // open the home page so static scripts load and set the session cookie for cookie-based auth
  await page.context().addCookies([{ name: 'token', value: token, url: BASE }]);
  await page.goto(BASE + '/static/home.html');

  // Inject the token and jti so client code will use authorization path and start heartbeat
  await page.evaluate(({ t, j }) => {
    window.appState = window.appState || {};
    if(t) window.appState.token = t;
    if(j) window.appState.jti = j;
    // ensure startHeartbeat is available from main.js
    try{ if(typeof startHeartbeat === 'function') startHeartbeat(t, j); }catch(e){}
  }, { t: token, j: jti });

  // call heartbeat once explicitly from the page context and await it
  await page.evaluate(() => {
    try{ if(typeof heartbeat === 'function') return heartbeat(); }catch(e){}
  });

  // give the client and server a moment to process (allow slightly longer on CI/macos)
  await page.waitForTimeout(1000);

  // assert we saw the client-side debug log indicating heartbeat was sent
  const sawHeartbeatLog = consoleMsgs.some(m => m.text && m.text.includes('heartbeat sending'));
  expect(sawHeartbeatLog).toBeTruthy();

  // now query the presence endpoint for this user (retry for a short window)
  let body = null;
  let got = false;
  const start = Date.now();
  while(Date.now() - start < 8000){
    const resp2 = await request.get(`${BASE}/presence/${user.id}`);
    if(resp2.ok()){
      body = await resp2.json();
      const s2 = String(body.status || '').toLowerCase();
      if(['online','afk'].includes(s2)) { got = true; break; }
    }
    await new Promise(r => setTimeout(r, 250));
  }
  expect(got).toBeTruthy();
});
