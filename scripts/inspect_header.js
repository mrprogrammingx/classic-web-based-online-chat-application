const { chromium } = require('playwright');
(async()=>{
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.stack || err.toString()));
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  const userInfo = await page.evaluate(()=>{ const el = document.getElementById('user-info'); return el ? el.innerHTML : null; });
  console.log('user-info innerHTML:', userInfo);
  const scripts = await page.evaluate(()=> Array.from(document.scripts).map(s=>({src:s.src, text: s.src? null : s.textContent && s.textContent.slice(0,200)})));
  console.log('scripts:', scripts);
  await browser.close();
})();