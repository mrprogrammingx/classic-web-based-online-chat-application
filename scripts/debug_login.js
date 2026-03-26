const { chromium } = require('playwright');
(async ()=>{
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  page.on('console', msg => console.log('[PAGE]', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message));
  await page.goto('http://127.0.0.1:8000/static/auth/login.html');
  await page.fill('#email', `noone+${Date.now()}@example.com`);
  await page.fill('#password', 'bad');
  await page.click('#login');
  // wait a bit
  await page.waitForTimeout(2000);
  const modalHtml = await page.$eval('#modal-root', el => el.innerHTML);
  console.log('modal-root innerHTML:', modalHtml);
  const scripts = await page.$$eval('script', els => els.map(e=>e.src));
  console.log('loaded script srcs:', scripts);
  // capture any page error stacks
  // pageerror handler prints message; attach one-time listener for uncaught exceptions
  page.on('pageerror', err => console.log('[PAGE ERROR STACK]', err.stack));
  await page.waitForTimeout(1000);
  await browser.close();
})();
