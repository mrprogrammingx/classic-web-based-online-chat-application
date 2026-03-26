const { test, expect } = require('./fixtures');

// Test the register flow: intercept /register to simulate success and ensure redirect to /static/home.html
test('register -> real backend -> home loads and UI initialized', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/static/auth/register.html');
  const email = `pwtest+${Date.now()}@example.com`;
  const username = `pwtest_${Date.now()}`;
  await page.fill('#email', email);
  await page.fill('#username', username);
  await page.fill('#password', 'Secret123!');
  await page.click('#register');

  // wait for redirect to home (allow a bit more time). Derive expected home href from SITE_CONFIG if available.
  const expectedHome = await page.evaluate(()=>{ try{ return (window.SITE_CONFIG && window.SITE_CONFIG.homeHref) ? window.SITE_CONFIG.homeHref : '/static/home.html'; }catch(e){ return '/static/home.html'; } });
  await page.waitForURL('**' + expectedHome, { timeout: 5000 });
  // UI should initialize: user-info should contain the username; wait a bit longer for client boot
  try{
    await page.waitForSelector('#user-info strong', { timeout: 5000 });
    const display = await page.locator('#user-info strong').innerText();
    expect(display.toLowerCase()).toContain(username.toLowerCase());
  }catch(e){
    // fallback: search for username text anywhere visible on the page
    const found = await page.locator(`text=${username}`).count();
    expect(found).toBeGreaterThan(0);
  }
});
