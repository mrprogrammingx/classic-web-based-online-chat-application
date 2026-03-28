/**
 * tests/js/rooms-link.test.js
 * Verify clicking a room title calls window.selectRoom when present (and prevents navigation),
 * and allows navigation when selectRoom is not present.
 */

describe('rooms link click behavior', () => {
  beforeEach(() => {
    document.body.innerHTML = '\n      <div id="rooms-list"></div>\n      <div id="rooms-pagination" data-offset="0"></div>\n    ';
    window.SITE_CONFIG = window.SITE_CONFIG || {};
  });

  afterEach(() => {
    jest.resetAllMocks && jest.resetAllMocks();
    delete window.SITE_CONFIG;
    // clear module cache so requiring rooms.js re-executes for each test
    try{ delete require.cache[require.resolve('../../static/app/lib/rooms.js')]; }catch(e){}
  });

  test('calls selectRoom and prevents default when selectRoom available', async () => {
    const roomsPayload = { rooms: [{ id: 42, name: 'Room 42', description: '', member_count: 1, is_member: false }], total: 1 };
    global.fetch = jest.fn((url, opts) => {
      const u = String(url || '');
      if(u.indexOf('/rooms') !== -1) return Promise.resolve({ status: 200, json: () => Promise.resolve(roomsPayload) });
      return Promise.resolve({ status: 404, json: () => Promise.resolve({}) });
    });

    window.selectRoom = jest.fn();
    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };

    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(resolve => setTimeout(resolve, 0));

    const a = document.querySelector('#rooms-list a');
    expect(a).toBeTruthy();
    expect(a.getAttribute('href')).toBe('/static/chat/index.html?room=42');

    const preventSpy = jest.spyOn(Event.prototype, 'preventDefault');
    a.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(window.selectRoom).toHaveBeenCalled();
    expect(preventSpy).toHaveBeenCalled();
    preventSpy.mockRestore();
  });

  test('allows navigation (does not preventDefault) when selectRoom absent', async () => {
    const roomsPayload = { rooms: [{ id: 99, name: 'Room 99', description: '', member_count: 1, is_member: false }], total: 1 };
    global.fetch = jest.fn((url, opts) => {
      const u = String(url || '');
      if(u.indexOf('/rooms') !== -1) return Promise.resolve({ status: 200, json: () => Promise.resolve(roomsPayload) });
      return Promise.resolve({ status: 404, json: () => Promise.resolve({}) });
    });

    // ensure selectRoom is not present
    try{ delete window.selectRoom; }catch(e){}
    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };

    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(resolve => setTimeout(resolve, 0));

    const a = document.querySelector('#rooms-list a');
    expect(a).toBeTruthy();
    expect(a.getAttribute('href')).toBe('/static/chat/index.html?room=99');

    const preventSpy = jest.spyOn(Event.prototype, 'preventDefault');
    a.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(preventSpy).not.toHaveBeenCalled();
    preventSpy.mockRestore();
  });
});
