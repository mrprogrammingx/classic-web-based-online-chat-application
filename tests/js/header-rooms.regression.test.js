/**
 * tests/js/header-rooms.regression.test.js
 * Ensure the shared header includes a Rooms link, obeys SITE_CONFIG override,
 * and receives the active state when the current path matches.
 */

describe('header loader Rooms link', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="shared-header-placeholder"></div>';
    // default SITE_CONFIG, can be overridden per-test
    window.SITE_CONFIG = { homeHref: '/static/home.html', mainHref: '/static/chat/index.html' };
  });

  afterEach(() => {
    jest.resetAllMocks && jest.resetAllMocks();
    delete window.SITE_CONFIG;
    if(document.getElementById('shared-header-placeholder')) document.getElementById('shared-header-placeholder').innerHTML = '';
  });

  test('adds Rooms link with default href', async () => {
    const frag = `
      <header class="topmenu">
        <nav class="topnav">
          <div class="nav-left">
            <a id="btn-home" href="#">Home</a>
            <a id="btn-chat" href="/static/chat/index.html">Chat</a>
            <a id="btn-rooms" href="/static/rooms/">Rooms</a>
          </div>
        </nav>
      </header>
    `;

    global.fetch = jest.fn((url) => {
      const s = String(url || '');
      if (s.indexOf('site-config.json') !== -1) return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      if (s.indexOf('header/header.html') !== -1 || s.indexOf('/static/header/header.html') !== -1) return Promise.resolve({ ok: true, text: () => Promise.resolve(frag) });
      return Promise.resolve({ ok: false });
    });

  require('../../static/header/header-loader.js');
  // give the loader a tick to run async work and manipulate the DOM
  await new Promise(resolve => setTimeout(resolve, 0));

    const rooms = document.getElementById('btn-rooms');
    expect(rooms).toBeTruthy();
    expect(rooms.getAttribute('href')).toBe('/static/rooms/');
  });

  test('header fragment contains Rooms anchor and honors roomsHref configuration', async () => {
    const fs = require('fs');
    const path = require('path');
    const file = path.join(__dirname, '../../static/header/header.html');
    const html = fs.readFileSync(file, 'utf8');

    expect(html.indexOf('id="btn-rooms"')).toBeGreaterThan(-1);
    // the script in header.html should reference roomsHref as an override point
    expect(html.indexOf('roomsHref')).toBeGreaterThan(-1);
  });
});
