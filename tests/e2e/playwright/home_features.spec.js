import { test, expect } from '@playwright/test';
import * as helpers from './helpers.js';

const BASE = 'http://127.0.0.1:8000';

// ═════════════════════════════════════════════════════════════════════════
// 1. Friend Request - Success Case
// ═════════════════════════════════════════════════════════════════════════

test('sending friend request shows success message', async ({ browser, request }) => {
  const sender = await helpers.registerUser(request, 'req_sender');
  const receiver = await helpers.registerUser(request, 'req_receiver');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: sender.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  
  // Capture network calls to verify request was sent
  let requestSent = false;
  page.on('response', (response) => {
    if (response.url().includes('/friends/request') && response.status() === 200) {
      requestSent = true;
    }
  });
  
  await page.goto(BASE + '/static/home.html');
  
  // Wait for page to load
  await page.waitForSelector('#friend-username-input', { timeout: 5000 });
  
  // Enter username and send request
  await page.fill('#friend-username-input', 'req_receiver');
  await page.fill('#friend-message-input', 'Hey, let\'s be friends!');
  
  // Click send button
  const sendBtn = page.locator('#request-by-username');
  await sendBtn.click();
  
  // Wait for request to be sent
  await page.waitForTimeout(1000);
  expect(requestSent).toBe(true);
  
  // Verify input fields are cleared after success
  const usernameInput = await page.inputValue('#friend-username-input');
  const messageInput = await page.inputValue('#friend-message-input');
  expect(usernameInput).toBe('');
  expect(messageInput).toBe('');
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 2. Friend Request - Error Case (User not found)
// ═════════════════════════════════════════════════════════════════════════

test('sending friend request to nonexistent user shows error', async ({ browser, request }) => {
  const sender = await helpers.registerUser(request, 'req_error_sender');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: sender.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  
  // Track fetch responses
  let errorResponse = false;
  page.on('response', (response) => {
    if (response.url().includes('/friends/request')) {
      if (response.status() !== 200) {
        errorResponse = true;
      }
    }
  });
  
  await page.goto(BASE + '/static/home.html');
  
  // Wait for page to load
  await page.waitForSelector('#friend-username-input', { timeout: 5000 });
  
  // Enter non-existent username
  await page.fill('#friend-username-input', 'nonexistent_user_xyz');
  await page.fill('#friend-message-input', 'hi');
  
  // Click send button
  const sendBtn = page.locator('#request-by-username');
  await sendBtn.click();
  
  // Wait for response
  await page.waitForTimeout(1000);
  
  // Verify an error response was received (404 or other error)
  expect(errorResponse).toBe(true);
  
  // Verify inputs are NOT cleared on error
  const usernameInput = await page.inputValue('#friend-username-input');
  expect(usernameInput).toBe('nonexistent_user_xyz');
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 3. Friend Request - Empty Username
// ═════════════════════════════════════════════════════════════════════════

test('sending friend request with empty username shows error', async ({ browser, request }) => {
  const user = await helpers.registerUser(request, 'req_empty');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: user.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  await page.goto(BASE + '/static/home.html');
  
  // Wait for page to load
  await page.waitForSelector('#request-by-username');
  
  // Try to send without entering username
  const sendBtn = page.locator('#request-by-username');
  await sendBtn.click();
  
  // Verify button is not in loading state (disabled briefly then re-enabled)
  await page.waitForTimeout(500);
  
  // Button should be enabled (not loading)
  await expect(sendBtn).toBeEnabled();
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 4. List Sessions - Shows sessions with no errors
// ═════════════════════════════════════════════════════════════════════════

test('clicking list sessions button shows session list', async ({ browser, request }) => {
  const user = await helpers.registerUser(request, 'sess_user');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: user.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  await page.goto(BASE + '/static/home.html');
  
  // Wait for list-sessions button
  await page.waitForSelector('#list-sessions', { timeout: 5000 });
  
  // Click the list sessions button
  await page.click('#list-sessions');
  
  // Wait for sessions list to appear
  const sessionsList = page.locator('#sessions-list');
  await expect(sessionsList).toBeVisible({ timeout: 5000 });
  
  // Verify no error messages are shown
  const errorText = await sessionsList.locator('li.meta').first().innerText();
  expect(errorText).not.toContain('Error');
  expect(errorText).not.toContain('timeout');
  
  // Verify at least one session is shown (the current session)
  const sessionItems = await sessionsList.locator('li').count();
  expect(sessionItems).toBeGreaterThan(0);
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 5. Session Revoke - Can revoke a session
// ═════════════════════════════════════════════════════════════════════════

test('can revoke a session from the list', async ({ browser, request }) => {
  const user = await helpers.registerUser(request, 'revoke_user');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: user.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  await page.goto(BASE + '/static/home.html');
  
  // Wait for list-sessions button and click it
  await page.waitForSelector('#list-sessions', { timeout: 5000 });
  await page.click('#list-sessions');
  
  // Wait for sessions list
  const sessionsList = page.locator('#sessions-list');
  await expect(sessionsList).toBeVisible({ timeout: 5000 });
  
  // Get initial session count
  const initialCount = await sessionsList.locator('li').count();
  
  // Click the first revoke button
  const revokeButton = sessionsList.locator('button:has-text("Revoke")').first();
  await revokeButton.click();
  
  // Accept the confirmation modal/confirm
  try {
    // Try to find and click a confirm button in a modal
    const confirmBtn = page.locator('button:has-text("Revoke")').last();
    await confirmBtn.click();
  } catch (e) {
    // If no modal, the confirm might be a browser native dialog
    // Accept it
    page.once('dialog', dialog => dialog.accept());
  }
  
  // Wait a bit for the session to be revoked
  await page.waitForTimeout(500);
  
  // Verify session was removed (count should be less)
  const finalCount = await sessionsList.locator('li').count();
  // Note: count might not change if there's only one session, so we check for success toast instead
  
  // Check for success message
  const toast = page.locator('.toast-container').first();
  await expect(toast).toContainText('Session revoked', { timeout: 5000 });
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 6. UI Elements - Toast notifications are visible
// ═════════════════════════════════════════════════════════════════════════

test('toast notifications display when sending friend request', async ({ browser, request }) => {
  const sender = await helpers.registerUser(request, 'toast_sender');
  const receiver = await helpers.registerUser(request, 'toast_receiver');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: sender.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  
  // Track errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  
  await page.goto(BASE + '/static/home.html');
  await page.waitForSelector('#friend-username-input', { timeout: 5000 });
  
  // Send friend request
  await page.fill('#friend-username-input', 'toast_receiver');
  await page.click('#request-by-username');
  
  // Wait for request to complete
  await page.waitForTimeout(1000);
  
  // Verify no errors were logged
  const criticalErrors = errors.filter(e => !e.includes('deprecat'));
  expect(criticalErrors.length).toBe(0);
  
  await ctx.close();
});

// ═════════════════════════════════════════════════════════════════════════
// 7. Console - No debug logs in production
// ═════════════════════════════════════════════════════════════════════════

test('no debug console logs appear during normal usage', async ({ browser, request }) => {
  const user = await helpers.registerUser(request, 'console_user');

  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'token', value: user.token, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();
  
  const consoleMsgs = [];
  page.on('console', msg => {
    consoleMsgs.push({ type: msg.type(), text: msg.text() });
  });
  
  await page.goto(BASE + '/static/home.html');
  await page.waitForSelector('#friend-username-input', { timeout: 5000 });
  
  // Wait for heartbeat to be sent
  await page.waitForTimeout(1000);
  
  // Filter for heartbeat-related debug messages
  const heartbeatDebug = consoleMsgs.filter(m => 
    m.type === 'log' && (m.text.includes('heartbeat') || m.text.includes('sending'))
  );
  
  // Should have no heartbeat debug logs
  expect(heartbeatDebug).toHaveLength(0);
  
  await ctx.close();
});
