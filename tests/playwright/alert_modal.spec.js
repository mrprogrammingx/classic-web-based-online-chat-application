const { test, expect } = require('@playwright/test');

// This test ensures that when login fails, the polished alert modal appears and keyboard works
test('login failure shows alert modal and responds to keyboard (focus trapping)', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/static/auth/login.html');
  // submit credentials that don't exist to cause failure
  await page.fill('#email', `noone+${Date.now()}@example.com`);
  await page.fill('#password', 'bad');
  await page.click('#login');

  // wait for modal to appear
  const modal = await page.waitForSelector('.modal-backdrop .modal-box', { timeout: 3000 });
  expect(modal).toBeTruthy();

  // confirm that modal shows some error text
  const body = await page.locator('.modal-body').innerText();
  expect(body.length).toBeGreaterThan(0);

  const confirmBtn = page.locator('.modal-actions .confirm');
  const cancelBtn = page.locator('.modal-actions button:not(.confirm)');

  // confirm initial focus is on the confirm button
  await expect(confirmBtn).toBeFocused();

  // Tab should move focus — either to a cancel button if present, or remain on confirm
  await page.keyboard.press('Tab');
  const cancelCount = await cancelBtn.count();
  if(cancelCount > 0){
    await expect(cancelBtn).toBeFocused();
    // Shift+Tab should move focus back to confirm
    await page.keyboard.press('Shift+Tab');
    await expect(confirmBtn).toBeFocused();
  } else {
    // no cancel button: focus should remain on confirm
    await expect(confirmBtn).toBeFocused();
  }

  // press Escape to dismiss and ensure modal is removed and focus returns to login button
  await page.keyboard.press('Escape');
  await expect(page.locator('.modal-backdrop')).toHaveCount(0);
  await expect(page.locator('#login')).toBeFocused();

});
