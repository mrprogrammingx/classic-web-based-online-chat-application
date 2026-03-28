/** @jest-environment jsdom */

// Test that sessions.js renderUserInfo always creates the admin badge element
// and toggles its visibility according to user.is_admin.

const fs = require('fs');
const path = require('path');

const SESSIONS_SRC = fs.readFileSync(path.join(__dirname, '../../static/app/lib/sessions.js'), 'utf8');

beforeEach(() => {
  document.body.innerHTML = '<div id="user-info"></div>';
  global.console.debug = global.console.log;
});

function loadSessionsScript(){
  const el = document.createElement('script'); el.textContent = SESSIONS_SRC; document.body.appendChild(el);
}

test('renderUserInfo creates badge element and shows for admin', () => {
  loadSessionsScript();
  expect(typeof window.renderUserInfo).toBe('function');
  window.renderUserInfo({ id: 1, username: 'Alice', is_admin: 1 });
  const badge = document.querySelector('.user-toggle .badge');
  expect(badge).toBeTruthy();
  // visible when admin (no explicit style.display === 'none')
  expect(badge.style.display).not.toBe('none');
});

test('renderUserInfo creates badge element but hides for non-admin', () => {
  loadSessionsScript();
  window.renderUserInfo({ id: 2, username: 'Bob', is_admin: 0 });
  const badge = document.querySelector('.user-toggle .badge');
  expect(badge).toBeTruthy();
  expect(badge.style.display).toBe('none');
});
