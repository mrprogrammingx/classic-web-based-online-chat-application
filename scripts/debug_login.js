const { chromium } = require('playwright');
(async ()=>{
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  // Ensure we capture init-time errors and unhandled rejections with stacks
  await page.addInitScript(() => {
    try{
      window.addEventListener('error', (e) => {
        try{ console.log('[INIT ERROR]', e.error && e.error.stack ? e.error.stack : (e.message || 'no-message')); }catch(e){}
      });
      window.addEventListener('unhandledrejection', (e) => {
        try{ const r = e && e.reason; console.log('[INIT REJECTION]', r && (r.stack || r)); }catch(e){}
      });
    }catch(e){}
  });

  page.on('console', msg => {
    try{ const loc = msg.location ? msg.location() : {}; console.log('[PAGE]', msg.type(), msg.text(), loc); }catch(e){ console.log('[PAGE]', msg.type(), msg.text()); }
  });
  page.on('requestfailed', req => { try{ console.log('[REQUEST FAILED]', req.url(), req.failure().errorText) }catch(e){} });
  page.on('response', res => { try{ if(res.status()>=400) console.log('[RESPONSE]', res.status(), res.url()); }catch(e){} });
  // Print full stack when a pageerror occurs
  page.on('pageerror', err => console.log('[PAGE ERROR STACK]', err && err.stack ? err.stack : err && err.message));

  await page.goto('http://127.0.0.1:8000/static/auth/login.html');
  // Small delay to allow page scripts to run and potentially throw
  await page.waitForTimeout(250);
  // Interact with the login form if present
  try{ await page.fill('#email', `noone+${Date.now()}@example.com`); }catch(e){}
  try{ await page.fill('#password', 'bad'); }catch(e){}
  try{ await page.click('#login'); }catch(e){}

  // wait a bit for errors and modal behavior
  await page.waitForTimeout(2000);
  let modalHtml = '';
  try{ modalHtml = await page.$eval('#modal-root', el => el.innerHTML); }catch(e){}
  console.log('modal-root innerHTML:', modalHtml);
  let scripts = [];
  try{ scripts = await page.$$eval('script', els => els.map(e=>e.src)); }catch(e){}
  console.log('loaded script srcs:', scripts);

  // Also print inline script sizes to see if any inline scripts are empty/truncated
  try{
    const inlineInfo = await page.$$eval('script:not([src])', els => els.map(e=>({ len: e.innerHTML.length, snippet: e.innerHTML.slice(0,300) })));
    console.log('inline scripts info:', inlineInfo);
  }catch(e){ console.log('inline scripts eval failed', e) }

  // From Node, fetch each script URL to inspect response body for truncation or 404
  try{
    for(const s of scripts.filter(Boolean)){
      try{
        const res = await fetch(s);
        const text = await res.text();
        console.log('fetched', s, 'status', res.status, 'len', text.length, 'snippet:', text.slice(0,600));
      }catch(e){ console.log('fetch failed for', s, e && e.message) }
    }
  }catch(e){ console.log('remote fetch of scripts failed', e) }

  // give any late errors another moment
  await page.waitForTimeout(1000);
  await browser.close();
})();
