const { test, expect } = require('@playwright/test');
const uuid = require('crypto').randomUUID;

// Smoke: register a new user (via fetch) and verify clicking "List sessions"
// shows at least one session in the sessions panel.

test('list sessions button shows sessions', async ({ page, baseURL }) => {
  const id = uuid().slice(0,8);
  const email = `smoke+${id}@example.com`;
  const username = `smoke_${id}`;
  const password = 'pw1234';

  // register using the UI so the client-side flow is exercised and cookie is set
  await page.goto(`${baseURL}/static/auth/register.html`);
  await page.fill('#email', email);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await Promise.all([
    page.waitForNavigation({ url: `${baseURL}/static/home.html` }),
    page.click('#register')
  ]);

  // Wait for the List sessions button and click it
  await page.waitForSelector('#list-sessions');
  await page.click('#list-sessions');

  // Wait for sessions-list to be attached and contain at least one <li>
  // Wait for the right-side #sessions container to contain at least one <li>
  await page.waitForSelector('#sessions', { state: 'attached' });
  await page.waitForFunction(() => {
    const container = document.querySelector('#sessions');
    if(!container) return false;
    return container.querySelectorAll('li').length > 0;
  }, { timeout: 10000 });
  const items = await page.$$eval('#sessions li', els => els.map(e => e.textContent.trim()));
  expect(items.length).toBeGreaterThan(0);
});
