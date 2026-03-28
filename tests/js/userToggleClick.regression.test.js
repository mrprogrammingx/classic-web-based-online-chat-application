/** @jest-environment jsdom */

// Test that clicking the user-toggle opens the sessions panel. Covers two
// scenarios: (1) sessions lib already loaded (window.loadSessions present),
// (2) sessions lib not loaded and is dynamically added by main.js click handler.

const fs = require('fs');
const path = require('path');

const SESSIONS_SRC = fs.readFileSync(path.join(__dirname, '../../static/app/lib/sessions.js'), 'utf8');

beforeEach(() => {
  document.body.innerHTML = '<div id="user-info"></div>';
  global.console.debug = global.console.log;
  delete global.fetch;
  // Ensure a clean global/window state between tests so earlier suites don't leak
  if (typeof window !== 'undefined') {
    try { delete window.loadSessions; } catch (e) {}
    try { delete window.renderUserInfo; } catch (e) {}
  }
});

function loadSessions(){ const el = document.createElement('script'); el.textContent = SESSIONS_SRC; document.body.appendChild(el); }

test('click toggles panel when loadSessions already present', async () => {
  // load sessions lib directly and use its renderUserInfo to create the DOM
  loadSessions();
  expect(typeof window.renderUserInfo).toBe('function');
  window.renderUserInfo({ id: 1, username: 'Alice', is_admin: 0 });
  const toggle = document.getElementById('user-toggle');
  expect(toggle).toBeTruthy();
  const panel = document.getElementById('user-panel');
  expect(panel).toBeTruthy();
  // Ensure panel is hidden initially
  expect(panel.style.display).toBe('none');
  toggle.click();
  expect(panel.style.display).toBe('block');
  toggle.click();
  expect(panel.style.display).toBe('none');
});

test('click dynamically loads sessions.js when not present and opens panel', async () => {
  // no sessions loaded yet
  expect(window.loadSessions).toBeUndefined();
  // prepare a mock fetch used by sessions.loadSessions to populate sessions
  global.fetch = async (url, opts) => ({ ok: true, json: async () => ({ sessions: [] }) });
  // Create a minimal fallback user info so the toggle exists
  const ui = document.getElementById('user-info');
  ui.innerHTML = '<div class="user-dropdown"><div class="user-toggle" id="user-toggle" tabindex="0"><span class="avatar">A</span><strong>Alice</strong></div></div>';
  const toggle = document.getElementById('user-toggle');
  // attach click handler that mimics main.js behavior: append sessions.js and call load
  toggle.addEventListener('click', ()=>{
    const s = document.createElement('script'); s.textContent = SESSIONS_SRC; s.onload = function(){ try{ const bootUser = { id:1, username:'Alice' }; if(window && typeof window.renderUserInfo === 'function') window.renderUserInfo(bootUser); if(window && typeof window.loadSessions === 'function') window.loadSessions(); }catch(e){} }; document.head.appendChild(s);
  });
  // simulate click which will append the sessions script
  toggle.click();
  // allow script eval & microtasks
  await Promise.resolve();
  // after sessions loads, window.loadSessions should be present and panel should be created
  expect(typeof window.loadSessions).toBe('function');
  const panel = document.getElementById('user-panel');
  expect(panel).toBeTruthy();
});
