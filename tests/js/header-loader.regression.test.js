/**
 * tests/js/header-loader.regression.test.js
 * Regression test to ensure the header loader preserves the Home label and
 * applies the configurable mainButtonText to the chat button only.
 *
 * Requires: jest + jest-environment-jsdom in your devDependencies.
 */

describe('header loader regression', () => {
  beforeEach(() => {
    // prepare minimal DOM placeholder and an explicit SITE_CONFIG so the loader
    // has canonical hrefs available synchronously
    document.body.innerHTML = '<div id="shared-header-placeholder"></div>';
    window.SITE_CONFIG = { homeHref: '/static/home.html', mainHref: '/static/chat/index.html', mainButtonText: 'CHAT-OVERRIDE' };
  });

  afterEach(() => {
    jest.resetAllMocks && jest.resetAllMocks();
    delete window.SITE_CONFIG;
    // clear the placeholder so requiring the loader multiple times in the same
    // jest run doesn't accumulate nodes
    document.getElementById('shared-header-placeholder').innerHTML = '';
  });

  test('preserves Home label and applies mainButtonText to chat button', async () => {
    const frag = `
      <header class="topmenu">
        <nav class="topnav">
          <div class="nav-left">
            <a id="btn-home" href="#">Home</a>
            <a id="btn-chat" href="/static/chat/index.html">Chat</a>
          </div>
        </nav>
      </header>
    `;

    // Stub fetch: site-config.json -> empty object, header fragment -> our frag
    global.fetch = jest.fn((url) => {
      const s = String(url || '');
      if (s.indexOf('site-config.json') !== -1) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ mainButtonText: 'CHAT-OVERRIDE' }) });
      }
      if (s.indexOf('header/header.html') !== -1 || s.indexOf('/static/header/header.html') !== -1) {
        return Promise.resolve({ ok: true, text: () => Promise.resolve(frag) });
      }
      return Promise.resolve({ ok: false });
    });

    // Wait for the loader to dispatch 'shared-header-loaded'
    const done = new Promise(resolve => {
      window.addEventListener('shared-header-loaded', () => setTimeout(resolve, 0), { once: true });
    });

    // Require the loader; it executes immediately in the test jsdom environment
    require('../../static/header/header-loader.js');

    await done;

    const home = document.getElementById('btn-home');
    const chat = document.getElementById('btn-chat');

    expect(home).toBeTruthy();
    expect(chat).toBeTruthy();
    // Home label must remain 'Home'
    expect(home.textContent).toBe('Home');
    // Chat button should be overridden by SITE_CONFIG.mainButtonText
    expect(chat.textContent).toBe('CHAT-OVERRIDE');
    // hrefs should be canonical
    expect(home.getAttribute('href')).toBe('/static/home.html');
    expect(chat.getAttribute('href')).toBe('/static/chat/index.html');
  });
});
