const { chromium } = require('playwright');
 (async()=>{
  const { chromium, request } = require('playwright');
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  // register a user via API using Playwright request
  const req = await request.newContext();
  const suffix = Math.random().toString(36).slice(2,7);
  const email = `smoke_${suffix}@example.com`;
  const username = `smoke_${suffix}`;
  const resp = await req.post(`${BASE}/register`, { data: { email, username, password: 'pw' } });
  const body = await resp.json();
  const token = body.token;
  console.log('registered user', username);
  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true }]);
  const page = await context.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.stack || err.toString()));
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  // wait briefly for shared-header-loaded event (header-loader dispatches this)
  const fired = await page.evaluate(() => new Promise((res) => {
    if(window.__shared_header_loaded_seen) return res(true);
    window.addEventListener('shared-header-loaded', () => { window.__shared_header_loaded_seen = true; res(true); });
    setTimeout(() => res(false), 2000);
  }));
  console.log('shared-header-loaded fired?', fired);
  const scriptsList = await page.evaluate(()=> Array.from(document.scripts).map(s=> ({ src: s.src, inline: !(s.src), text: s.textContent && s.textContent.slice(0,120) }) ));
  console.log('scripts on page:', scriptsList.map(s=>s.src || '<inline>').join('\n'));
  const docCookie = await page.evaluate(()=> document.cookie);
  console.log('document.cookie:', docCookie);
  const ctxCookies = await context.cookies();
  console.log('context.cookies():', ctxCookies);
  const userInfo = await page.evaluate(()=>{ const el = document.getElementById('user-info'); return el ? el.innerHTML : null; });
  console.log('user-info innerHTML:', userInfo);
  await browser.close();
})();