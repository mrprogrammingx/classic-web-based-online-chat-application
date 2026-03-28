/**
 * tests/js/rooms-create-modal.test.js
 * Verify the Create Room button shows the shared modal and only POSTs when confirmed.
 */

describe('rooms create modal', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <section id="create-room">
        <input id="new-room-name" />
        <select id="new-room-visibility"><option value="public">Public</option><option value="private">Private</option></select>
        <button id="btn-create-room">Create</button>
      </section>
      <div id="rooms-list"></div>
      <div id="modal-root"></div>
      <div id="toast-root"></div>
      <div id="rooms-pagination" data-offset="0"></div>
    `;
    window.SITE_CONFIG = window.SITE_CONFIG || {};
  });

  afterEach(() => {
    jest.resetAllMocks && jest.resetAllMocks();
    delete window.SITE_CONFIG;
    if(document.getElementById('rooms-list')) document.getElementById('rooms-list').innerHTML = '';
  });

  test('shows modal and POSTs when confirmed', async () => {
    const roomsPayload = { rooms: [], total: 0 };
    const fetchMock = jest.fn((url, opts) => {
      const u = String(url || '');
      // GET /rooms
      if(u.indexOf('/rooms?') !== -1 || u.endsWith('/rooms')){
        // return empty list
        return Promise.resolve({ status: 200, json: () => Promise.resolve(roomsPayload) });
      }
      // POST /rooms
      if(u.endsWith('/rooms') && opts && opts.method === 'POST'){
        return Promise.resolve({ status: 200, json: () => Promise.resolve({ room: { id: 999, name: JSON.parse(opts.body).name } }) });
      }
      return Promise.resolve({ status: 404, json: () => Promise.resolve({}) });
    });
    global.fetch = fetchMock;

    // modal resolves true (confirmed)
    const modalMock = jest.fn(() => Promise.resolve(true));
    window.showModal = modalMock;

    // minimal globals used by script
    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };

    // load script and attach
    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await Promise.resolve();

    // fill form and click create
    document.getElementById('new-room-name').value = 'My New Room';
    document.getElementById('btn-create-room').click();
    // allow async handlers to run
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(modalMock).toHaveBeenCalled();
    // Ensure a POST to /rooms occurred with expected body
    const postCalls = fetchMock.mock.calls.filter(c => String(c[0]).endsWith('/rooms') && c[1] && c[1].method === 'POST');
    expect(postCalls.length).toBeGreaterThan(0);
    const sentBody = JSON.parse(postCalls[0][1].body || '{}');
    expect(sentBody.name).toBe('My New Room');
  });

  test('shows modal and does not POST when canceled', async () => {
    const roomsPayload = { rooms: [], total: 0 };
    const fetchMock = jest.fn((url, opts) => {
      const u = String(url || '');
      if(u.indexOf('/rooms?') !== -1 || u.endsWith('/rooms')){
        return Promise.resolve({ status: 200, json: () => Promise.resolve(roomsPayload) });
      }
      return Promise.resolve({ status: 404, json: () => Promise.resolve({}) });
    });
    global.fetch = fetchMock;

    // modal resolves false (canceled)
    const modalMock = jest.fn(() => Promise.resolve(false));
    window.showModal = modalMock;

    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };

    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await Promise.resolve();

    document.getElementById('new-room-name').value = 'Canceled Room';
    document.getElementById('btn-create-room').click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(modalMock).toHaveBeenCalled();
    // No POST calls should have been made
    const postCalls = fetchMock.mock.calls.filter(c => String(c[0]).endsWith('/rooms') && c[1] && c[1].method === 'POST');
    expect(postCalls.length).toBe(0);
  });

});
