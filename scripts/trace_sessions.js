const { chromium, request } = require('playwright');
(async()=>{
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  const api = await request.newContext();
  const suffix = Math.random().toString(36).slice(2,7);
  const email = `sess_${suffix}@example.com`;
  const username = `sess_${suffix}`;
  const reg = await api.post(`${BASE}/register`, { data: { email, username, password: 'pw' } });
  const body = await reg.json();
  const token = body.token;
  console.log('registered', username);
  // create second session via login
  const loginResp = await api.post(`${BASE}/login`, { data: { email, password: 'pw' } });
  console.log('/login second session status', loginResp.status());

  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true }]);
  const page = await context.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.stack || err.toString()));
  page.on('request', req => { if(req.url().includes('/sessions')) console.log('REQ>', req.method(), req.url()); });
  page.on('response', res => { if(res.url().includes('/sessions')) console.log('RESP>', res.status(), res.url()); });
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  // wait for user-toggle to appear
  await page.waitForSelector('#user-toggle', { timeout: 5000 }).catch(()=>{ console.log('user-toggle not found'); });
  // click the toggle
  await page.click('#user-toggle').catch(e=>console.log('click failed', e && e.message));
  // wait a bit for sessions to load
  await page.waitForTimeout(800);
  const sessionsHtml = await page.evaluate(()=>{ return {
    userInfo: (document.getElementById('user-info') && document.getElementById('user-info').outerHTML) || null,
    hasLoadSessions: !!(window && typeof window.loadSessions === 'function'),
    hasRenderUserInfo: !!(window && typeof window.renderUserInfo === 'function'),
    sessionsListHtml: (document.querySelector('.sessions-list') && document.querySelector('.sessions-list').innerHTML) || null
  }; });
  console.log('after click:', sessionsHtml);
  console.log('sessions-list innerHTML:', sessionsHtml);
  await browser.close();
})();