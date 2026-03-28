/** @jest-environment jsdom */

// Regression tests for static/app/lib/sessions.js
// We load the script into JSDOM and exercise loadSessions under different
// conditions: (1) window.fetchJSON present and resolves, (2) window.fetchJSON
// missing and fallback uses global fetch, (3) fetch stalls and timeout triggers.

const fs = require('fs');
const path = require('path');

const SESSIONS_SRC = fs.readFileSync(path.join(__dirname, '../../static/app/lib/sessions.js'), 'utf8');

beforeEach(() => {
  // Reset DOM
  document.body.innerHTML = `
    <div id="sessions"></div>
  `;
  // clear any globals
  delete global.window.fetchJSON;
  delete global.fetch;
  // Ensure console.debug doesn't fail in test environment
  global.console.debug = global.console.log;
});

function getSessionsListText(){
  const el = document.querySelector('#sessions');
  return el ? el.innerHTML : null;
}

function loadSessionsScript(){
  // Inject the sessions.js source into the JSDOM page so it executes in the
  // browser-like window context and attaches window.loadSessions etc.
  const el = document.createElement('script');
  el.textContent = SESSIONS_SRC;
  document.body.appendChild(el);
}

test('uses window.fetchJSON when present and populates list', async () => {
  // provide a mock fetchJSON that returns a sessions payload
  global.window.fetchJSON = async (url, opts) => ({ sessions: [{ jti: 'a1', created_at: 1, last_active: 2 }] });
  loadSessionsScript();
  // call the exported loadSessions attached to window
  expect(typeof window.loadSessions).toBe('function');
  await window.loadSessions();
  const html = getSessionsListText();
  expect(html).toContain('jti: a1');
});

test('falls back to global fetch when window.fetchJSON missing', async () => {
  // mock global fetch
  global.fetch = async (url, opts) => ({ ok: true, json: async () => ({ sessions: [{ jti: 'b2', created_at: 1 }] }) });
  loadSessionsScript();
  await window.loadSessions();
  const html = getSessionsListText();
  expect(html).toContain('jti: b2');
});

test('times out and shows error when fetch stalls', async () => {
  // mock fetch that never resolves
  global.fetch = (url, opts) => new Promise(() => {});
  loadSessionsScript();
  // set a shorter timeout by patching the module source? Instead, emulate
  // a reasonable timeout by using jest fake timers and advancing.
  jest.useFakeTimers();
  const p = window.loadSessions();
  // advance timers by 10s to trigger the 8s timeout in code
  jest.advanceTimersByTime(10000);
  // allow pending promises to resolve
  await Promise.resolve();
  // flush microtasks
  await p.catch(()=>{});
  const html = getSessionsListText();
  expect(html).toContain('Error loading sessions');
  jest.useRealTimers();
});
