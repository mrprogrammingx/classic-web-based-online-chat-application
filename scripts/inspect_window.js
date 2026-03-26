const { chromium } = require('playwright');
(async ()=>{
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8000/static/auth/login.html');
  const keys = ['showModal','showAlert','showToast','parseJwt','initAuthPages','ensureUiRoots','handleComposerSubmit'];
  for(const k of keys){
    const info = await page.evaluate((k)=>{ try{ return { key:k, type: typeof window[k], defined: !!window[k], src: (typeof window[k] === 'function') ? (window[k].toString().slice(0,200)) : null }; }catch(e){ return { key:k, error: e.message }; } }, k);
    console.log(info);
  }
  const scripts = await page.$$eval('script', els => els.map(e=>e.src));
  console.log('scripts', scripts);
  await browser.close();
})();
