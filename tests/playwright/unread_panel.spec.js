const { test, expect } = require('@playwright/test');
const helpers = require('./helpers');

test('open unread panel shows items or empty state', async ({ browser, request }) => {
  const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';
  const created = await helpers.registerUser(request, 'unread');
  const token = created.token;
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  await context.addCookies([{ name: 'token', value: token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  await page.goto(BASE + '/static/chat.html');
  // wait for header and unread button
  await page.waitForSelector('#unread-total', { timeout: 10000 });
  // click to open panel
  await page.click('#unread-total');
  // wait for panel to be added to the DOM
  const panel = page.locator('.unread-panel');
  await panel.waitFor({ state: 'visible', timeout: 5000 });
  // assert panel contains either 'No unread' or a list item
  const hasNoUnread = await panel.locator('text=No unread messages').count();
  const listItems = await panel.locator('ul li').count();
  expect((hasNoUnread > 0) || (listItems > 0)).toBeTruthy();
  await context.close();
});
